"""Pousada Management System - FastAPI backend.
Modules: Auth, Settings/Gallery, Rooms, Reservations (FNRH public + internal),
Financial ledger, iCal export/import, WhatsApp templates, file uploads.
"""
import os
import asyncio
import uuid
import logging
import hashlib
import hmac
import csv
import calendar as cal
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Annotated

import base64
from io import BytesIO
import re
import ipaddress
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import bcrypt
import httpx
import jwt
import qrcode
import requests
import stripe
from icalendar import Calendar, Event
from breeds import classify_breed, ALL_BREEDS
from holidays import get_brazilian_holidays, is_brazilian_holiday
import hr_rules
from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, Response, Request, status
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ----- Setup -----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24 * 7
ADMIN_EMAIL_DEFAULT = os.environ.get("ADMIN_EMAIL", "admin@pousada.com")
ADMIN_PASSWORD_DEFAULT = os.environ.get("ADMIN_PASSWORD", "pousada2024")

APP_NAME = "pousada-mgmt"
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
_storage_key = None

# Emergent managed email
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Pousada")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

# Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Cron webhook secret (platform-managed scheduled tasks)
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pousada")

app = FastAPI(title="Pousada Management API")
api = APIRouter(prefix="/api")


# ----- Helpers -----
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def require_admin(token: Optional[str] = Depends(oauth2)):
    """Any authenticated staff user (admin or reception)."""
    if not token:
        raise HTTPException(401, "Não autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido ou expirado")
    user = await db.users.find_one({"id": payload["sub"], "is_deleted": {"$ne": True}}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Usuário não encontrado")
    return user


async def require_admin_role(user=Depends(require_admin)):
    """Only admin role (blocks reception)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas administradores")
    return user


def clean_doc(d: dict) -> dict:
    d = {k: v for k, v in d.items() if k != "_id"}
    return d


# ----- Storage -----
def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    if not EMERGENT_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if r.status_code == 404:
        key = init_storage(force=True)
        r = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = init_storage()
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 404:
        key = init_storage(force=True)
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


# ----- Models -----
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = "Minha Pousada"
    tagline: Optional[str] = ""
    description: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""  # telefone clicável
    whatsapp: Optional[str] = ""
    pix_key: Optional[str] = ""
    pix_key_type: Optional[str] = ""  # cpf, cnpj, email, phone, random
    address: Optional[str] = ""
    latitude: Optional[str] = ""
    longitude: Optional[str] = ""
    checkin_time: Optional[str] = "14:00"
    checkout_time: Optional[str] = "11:00"
    cover_image: Optional[str] = ""
    logo_url: Optional[str] = ""
    instagram: Optional[str] = ""
    facebook: Optional[str] = ""
    airbnb_url: Optional[str] = ""
    booking_url: Optional[str] = ""
    triplar_url: Optional[str] = ""
    whatsapp_webhook_url: Optional[str] = ""  # notificação push (ex.: CallMeBot)
    holidays: Optional[str] = ""  # ISO dates separated by comma or newline (feriados importantes)
    weekend_surcharge_pct: float = 10.0
    child_rate_pct: float = 65.0
    extra_adult_discount_pct: float = 10.0
    pet_small_pct: float = 20.7
    pet_medium_pct: float = 27.6
    pet_large_pct: float = 34.5
    policies: Optional[str] = ""


class GalleryItem(BaseModel):
    id: str = Field(default_factory=new_id)
    url: str
    caption: Optional[str] = ""
    sort_order: int = 0


class Room(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    category: Optional[str] = "Quarto"
    max_adults: int = 2
    max_children: int = 0
    amenities: List[str] = []
    daily_rate: float = 0.0
    rate_per_guest: bool = False  # se True, ValorTotal = rate * hóspedes * noites
    min_stay: int = 1
    status: str = "available"
    description: Optional[str] = ""
    cover_image: Optional[str] = ""
    ical_token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = Field(default_factory=now_iso)


class RoomIn(BaseModel):
    name: str
    category: Optional[str] = "Quarto"
    max_adults: int = 2
    max_children: int = 0
    amenities: List[str] = []
    daily_rate: float = 0.0
    rate_per_guest: bool = False
    min_stay: int = 1
    status: str = "available"
    description: Optional[str] = ""
    cover_image: Optional[str] = ""


class Reservation(BaseModel):
    id: str = Field(default_factory=new_id)
    room_id: Optional[str] = None
    source: str = "direct"  # direct | public_form | ota_import
    ota_source: Optional[str] = None  # airbnb, booking, triplar
    status: str = "pending"  # pending | confirmed | cancelled | maintenance | blocked | checked_in | checked_out
    # Guest data (FNRH)
    guest_name: str = ""
    guest_document: Optional[str] = ""  # CPF/Passaporte
    guest_email: Optional[str] = ""
    guest_phone: Optional[str] = ""
    guest_birthdate: Optional[str] = ""
    guest_address: Optional[str] = ""
    travel_reason: Optional[str] = ""
    transport: Optional[str] = ""
    # Stay
    checkin_date: str  # YYYY-MM-DD
    checkout_date: str
    adults: int = 1
    children: int = 0
    estimated_arrival: Optional[str] = ""
    notes: Optional[str] = ""
    total_amount: float = 0.0
    deposit_amount: float = 0.0
    accepted_terms: bool = False
    ota_uid: Optional[str] = None  # for imported events
    payment_receipt_url: Optional[str] = ""
    # Stripe payment link
    stripe_session_id: Optional[str] = None
    stripe_payment_url: Optional[str] = None
    stripe_payment_status: Optional[str] = None  # pending | paid | failed | expired
    stripe_amount: Optional[float] = None
    # New pricing fields
    children_0_3: int = 0
    children_4_10: int = 0
    pets_small: int = 0
    pets_medium: int = 0
    pets_large: int = 0
    pets: List[dict] = []
    pricing_breakdown: Optional[dict] = None
    created_at: str = Field(default_factory=now_iso)


class ReservationIn(BaseModel):
    room_id: Optional[str] = None
    guest_name: str
    guest_document: Optional[str] = ""
    guest_email: Optional[str] = ""
    guest_phone: Optional[str] = ""
    guest_birthdate: Optional[str] = ""
    guest_address: Optional[str] = ""
    travel_reason: Optional[str] = ""
    transport: Optional[str] = ""
    checkin_date: str
    checkout_date: str
    adults: int = 1
    children: int = 0
    children_0_3: int = 0
    children_4_10: int = 0
    pets_small: int = 0
    pets_medium: int = 0
    pets_large: int = 0
    estimated_arrival: Optional[str] = ""
    notes: Optional[str] = ""
    total_amount: float = 0.0
    deposit_amount: float = 0.0
    status: Optional[str] = "pending"
    source: Optional[str] = "direct"


class PetItem(BaseModel):
    type: str = "cão"
    breed: str = ""
    size: Optional[str] = None  # small | medium | large (auto-classified if missing)


class PublicReservationIn(BaseModel):
    room_id: Optional[str] = None
    guest_name: str = Field(min_length=2)
    guest_document: str = Field(min_length=3)
    guest_email: EmailStr
    guest_phone: str
    guest_birthdate: str
    guest_address: Optional[str] = ""
    travel_reason: Optional[str] = ""
    transport: Optional[str] = ""
    checkin_date: str
    checkout_date: str
    adults: int = 1
    children: int = 0
    children_0_3: int = 0
    children_4_10: int = 0
    pets_small: int = 0
    pets_medium: int = 0
    pets_large: int = 0
    pets: List[PetItem] = []
    estimated_arrival: Optional[str] = ""
    notes: Optional[str] = ""
    accepted_terms: bool
    payment_receipt_url: Optional[str] = ""


class ReservationStatusIn(BaseModel):
    status: str


class FinanceEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str  # income | expense
    category: str
    amount: float
    entry_date: str  # YYYY-MM-DD
    description: Optional[str] = ""
    reservation_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class FinanceIn(BaseModel):
    kind: str
    category: str
    amount: float
    entry_date: str
    description: Optional[str] = ""
    reservation_id: Optional[str] = None


class ICalImportSource(BaseModel):
    id: str = Field(default_factory=new_id)
    room_id: str
    name: str  # Airbnb, Booking, TripLar
    url: str
    last_sync: Optional[str] = None
    last_status: Optional[str] = None
    imported_count: int = 0
    created_at: str = Field(default_factory=now_iso)


class ICalSourceIn(BaseModel):
    room_id: str
    name: str
    url: str


class WhatsAppTemplate(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    body: str
    created_at: str = Field(default_factory=now_iso)


class WhatsAppTemplateIn(BaseModel):
    title: str
    body: str


# ----- Startup: seed admin, defaults, indices -----
@app.on_event("startup")
async def startup():
    # Storage init (best-effort)
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.warning(f"Object storage init failed: {e}")

    # Seed default admin (idempotent)
    existing = await db.users.find_one({"email": ADMIN_EMAIL_DEFAULT.lower()})
    if not existing:
        await db.users.insert_one({
            "id": new_id(),
            "email": ADMIN_EMAIL_DEFAULT.lower(),
            "password_hash": hash_password(ADMIN_PASSWORD_DEFAULT),
            "role": "admin",
            "is_deleted": False,
            "created_at": now_iso(),
        })
        logger.info(f"Seeded admin user: {ADMIN_EMAIL_DEFAULT}")

    # Seed default settings
    settings = await db.settings.find_one({"id": "singleton"})
    if not settings:
        default = SettingsIn().model_dump()
        default["id"] = "singleton"
        default["updated_at"] = now_iso()
        await db.settings.insert_one(default)

    # Indices
    try:
        await db.reservations.create_index([("room_id", 1), ("checkin_date", 1)])
        await db.rooms.create_index("ical_token", unique=True)
    except Exception:
        pass

    # Auto-sync iCal every 15 min (background task)
    asyncio.create_task(_ical_auto_sync_loop())


async def _ical_auto_sync_loop():
    """Every 15 minutes, sync all iCal sources so Airbnb/Booking/TripLar blocks import automatically."""
    await asyncio.sleep(30)  # small delay after startup
    while True:
        try:
            sources = await db.ical_sources.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
            for s in sources:
                try:
                    await _sync_source(s)
                except Exception as e:
                    logger.warning(f"auto-sync source failed: {e}")
            if sources:
                logger.info(f"iCal auto-sync completed: {len(sources)} source(s)")
        except Exception as e:
            logger.error(f"iCal auto-sync loop error: {e}")
        await asyncio.sleep(15 * 60)


# ----- Auth -----
@api.post("/auth/login")
async def login(data: LoginIn):
    user = await db.users.find_one({"email": data.email.lower(), "is_deleted": {"$ne": True}}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Credenciais inválidas")
    token = make_token(user["id"], user["email"])
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@api.get("/auth/me")
async def me(user=Depends(require_admin)):
    return {"id": user["id"], "email": user["email"], "role": user["role"]}


@api.post("/auth/change-password")
async def change_password(data: ChangePasswordIn, user=Depends(require_admin)):
    if not verify_password(data.current_password, user["password_hash"]):
        raise HTTPException(400, "Senha atual incorreta")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(data.new_password)}})
    return {"ok": True}


# ----- Public Settings & Gallery -----
@api.get("/public/settings")
async def get_public_settings():
    s = await db.settings.find_one({"id": "singleton"}, {"_id": 0})
    if not s:
        return SettingsIn().model_dump()
    return clean_doc(s)


@api.get("/public/gallery")
async def get_public_gallery():
    items = await db.gallery.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("sort_order", 1).to_list(200)
    return [clean_doc(i) for i in items]


@api.get("/public/rooms")
async def get_public_rooms():
    rooms = await db.rooms.find({"is_deleted": {"$ne": True}}, {"_id": 0, "ical_token": 0}).to_list(200)
    return [clean_doc(r) for r in rooms]


# ----- Admin Settings -----
@api.get("/settings")
async def admin_get_settings(user=Depends(require_admin)):
    s = await db.settings.find_one({"id": "singleton"}, {"_id": 0})
    return clean_doc(s) if s else SettingsIn().model_dump()


@api.put("/settings")
async def admin_put_settings(data: SettingsIn, user=Depends(require_admin_role)):
    doc = data.model_dump()
    doc["id"] = "singleton"
    doc["updated_at"] = now_iso()
    await db.settings.update_one({"id": "singleton"}, {"$set": doc}, upsert=True)
    return doc


# ----- Gallery admin -----
class GalleryIn(BaseModel):
    url: str
    caption: Optional[str] = ""
    sort_order: int = 0


@api.get("/gallery")
async def gallery_list(user=Depends(require_admin)):
    items = await db.gallery.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("sort_order", 1).to_list(500)
    return [clean_doc(i) for i in items]


@api.post("/gallery")
async def gallery_add(data: GalleryIn, user=Depends(require_admin_role)):
    item = GalleryItem(**data.model_dump()).model_dump()
    item["is_deleted"] = False
    item["created_at"] = now_iso()
    await db.gallery.insert_one(item)
    return clean_doc(item)


@api.delete("/gallery/{item_id}")
async def gallery_delete(item_id: str, user=Depends(require_admin_role)):
    await db.gallery.update_one({"id": item_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


# ----- File upload -----
@api.post("/uploads")
async def upload_file(file: UploadFile = File(...), user=Depends(require_admin)):
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/uploads/{user['id']}/{new_id()}.{ext}"
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Arquivo muito grande (máx 15MB)")
    ctype = file.content_type or "application/octet-stream"
    result = put_object(path, data, ctype)
    file_doc = {
        "id": new_id(),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": now_iso(),
    }
    await db.files.insert_one(file_doc)
    return {"path": result["path"], "url": f"/api/files/{result['path']}", "size": file_doc["size"]}


@api.get("/files/{path:path}")
async def download_file(path: str):
    # Public read for uploaded images (gallery is public anyway)
    record = await db.files.find_one({"storage_path": path, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Arquivo não encontrado")
    data, ctype = get_object(path)
    return Response(content=data, media_type=record.get("content_type", ctype))


# ----- Rooms -----
@api.get("/rooms")
async def rooms_list(user=Depends(require_admin)):
    rooms = await db.rooms.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    return [clean_doc(r) for r in rooms]


@api.post("/rooms")
async def rooms_create(data: RoomIn, user=Depends(require_admin_role)):
    room = Room(**data.model_dump()).model_dump()
    room["is_deleted"] = False
    await db.rooms.insert_one(room)
    return clean_doc(room)


@api.put("/rooms/{room_id}")
async def rooms_update(room_id: str, data: RoomIn, user=Depends(require_admin_role)):
    update = data.model_dump()
    update["updated_at"] = now_iso()
    result = await db.rooms.update_one({"id": room_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Quarto não encontrado")
    room = await db.rooms.find_one({"id": room_id}, {"_id": 0})
    return clean_doc(room)


@api.delete("/rooms/{room_id}")
async def rooms_delete(room_id: str, user=Depends(require_admin_role)):
    await db.rooms.update_one({"id": room_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


# ----- Reservations -----
@api.get("/reservations")
async def reservations_list(
    user=Depends(require_admin),
    room_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    q: dict = {"is_deleted": {"$ne": True}}
    if room_id:
        q["room_id"] = room_id
    if status_filter:
        q["status"] = status_filter
    if from_date:
        q["checkout_date"] = {"$gte": from_date}
    if to_date:
        q["checkin_date"] = {"$lte": to_date}
    rows = await db.reservations.find(q, {"_id": 0}).sort("checkin_date", 1).to_list(2000)
    return [clean_doc(r) for r in rows]


@api.post("/reservations")
async def reservations_create(data: ReservationIn, user=Depends(require_admin)):
    r = Reservation(**data.model_dump()).model_dump()
    r["is_deleted"] = False
    await db.reservations.insert_one(r)
    return clean_doc(r)


@api.put("/reservations/{res_id}")
async def reservations_update(res_id: str, data: ReservationIn, user=Depends(require_admin)):
    update = data.model_dump()
    update["updated_at"] = now_iso()
    result = await db.reservations.update_one({"id": res_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Reserva não encontrada")
    r = await db.reservations.find_one({"id": res_id}, {"_id": 0})
    return clean_doc(r)


@api.patch("/reservations/{res_id}/status")
async def reservations_set_status(res_id: str, data: ReservationStatusIn, user=Depends(require_admin)):
    valid = {"pending", "confirmed", "cancelled", "maintenance", "blocked", "checked_in", "checked_out"}
    if data.status not in valid:
        raise HTTPException(400, "Status inválido")
    result = await db.reservations.update_one({"id": res_id}, {"$set": {"status": data.status, "updated_at": now_iso()}})
    if result.matched_count == 0:
        raise HTTPException(404, "Reserva não encontrada")
    r = await db.reservations.find_one({"id": res_id}, {"_id": 0})
    return clean_doc(r)


@api.delete("/reservations/{res_id}")
async def reservations_delete(res_id: str, user=Depends(require_admin)):
    await db.reservations.update_one({"id": res_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


# ----- Email (Resend via Emergent proxy) -----
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Optional[str]:
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY missing; skipping email send")
        return None
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as clientx:
            resp = await clientx.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return None


def _guest_email_html(settings: dict, r: dict, room_name: str) -> str:
    name = escape(r.get("guest_name") or "")
    ci = escape(r.get("checkin_date") or "")
    co = escape(r.get("checkout_date") or "")
    inn = escape(settings.get("name") or EMAIL_FROM_NAME)
    room = escape(room_name or "—")
    return (
        f'<table role="presentation" width="100%" style="max-width:560px;margin:0 auto">'
        f'<tr><td style="padding:24px;font-family:Arial,sans-serif;color:#1c1917">'
        f'<h2 style="color:#C85A32;margin:0 0 12px">Pré-reserva recebida</h2>'
        f'<p>Olá {name}, obrigado por escolher a <strong>{inn}</strong>!</p>'
        f'<p>Recebemos sua pré-reserva para <strong>{ci}</strong> até <strong>{co}</strong>'
        f' — quarto preferido: {room}. Nossa equipe confirma disponibilidade e envia os próximos passos em breve.</p>'
        f'<p style="font-size:12px;color:#888">Enviado por {inn}. Nunca pedimos senhas ou dados de cartão por e-mail.</p>'
        f'</td></tr></table>'
    )


def _owner_email_html(settings: dict, r: dict, room_name: str) -> str:
    name = escape(r.get("guest_name") or "")
    email = escape(r.get("guest_email") or "")
    phone = escape(r.get("guest_phone") or "")
    ci = escape(r.get("checkin_date") or "")
    co = escape(r.get("checkout_date") or "")
    adults = escape(str(r.get("adults") or 1))
    children = escape(str(r.get("children") or 0))
    inn = escape(settings.get("name") or EMAIL_FROM_NAME)
    room = escape(room_name or "—")
    return (
        f'<table role="presentation" width="100%" style="max-width:560px;margin:0 auto">'
        f'<tr><td style="padding:24px;font-family:Arial,sans-serif;color:#1c1917">'
        f'<h2 style="color:#2D5A43;margin:0 0 12px">Nova pré-reserva</h2>'
        f'<p><strong>Hóspede:</strong> {name}<br>'
        f'<strong>Contato:</strong> {phone} · {email}<br>'
        f'<strong>Datas:</strong> {ci} → {co}<br>'
        f'<strong>Quarto:</strong> {room}<br>'
        f'<strong>Pessoas:</strong> {adults} adultos, {children} crianças</p>'
        f'<p style="font-size:12px;color:#888">Enviado por {inn}. Abra o painel para confirmar.</p>'
        f'</td></tr></table>'
    )


def _parse_holidays(raw: str) -> set:
    if not raw:
        return set()
    out = set()
    for token in raw.replace("\n", ",").split(","):
        t = token.strip()
        if not t:
            continue
        try:
            date.fromisoformat(t)
            out.add(t)
        except Exception:
            pass
    return out


def compute_pricing(room: dict, checkin: str, checkout: str, adults: int, children_0_3: int, children_4_10: int,
                     pets_small: int, pets_medium: int, pets_large: int, settings: dict) -> dict:
    """Apply Pousada Vale do Sol pricing rules per spec.
    - Weekend/holiday surcharge on the nightly base rate
    - 2nd+ adult: -10% (non cumulative — each extra adult flat 10% off)
    - First child 0-3: free; other 0-3 children + all 4-10 children pay 65%
    - Pets: %-based fee over 1-adult nightly rate (small 20.7%, medium 27.6%, large 34.5%)
    """
    try:
        ci = date.fromisoformat(checkin)
        co = date.fromisoformat(checkout)
    except Exception:
        return {"total": 0, "nights": [], "n_nights": 0, "error": "Datas inválidas"}
    n = (co - ci).days
    if n <= 0:
        return {"total": 0, "nights": [], "n_nights": 0}

    base_rate = float(room.get("daily_rate") or 0)
    weekend_pct = float(settings.get("weekend_surcharge_pct", 10.0)) / 100.0
    child_pct = float(settings.get("child_rate_pct", 65.0)) / 100.0
    adult_disc_pct = float(settings.get("extra_adult_discount_pct", 10.0)) / 100.0
    pet_small = float(settings.get("pet_small_pct", 20.7)) / 100.0
    pet_medium = float(settings.get("pet_medium_pct", 27.6)) / 100.0
    pet_large = float(settings.get("pet_large_pct", 34.5)) / 100.0
    holidays = _parse_holidays(settings.get("holidays") or "")

    adults = max(1, int(adults or 1))
    children_0_3 = max(0, int(children_0_3 or 0))
    children_4_10 = max(0, int(children_4_10 or 0))
    paid_kids_0_3 = max(0, children_0_3 - 1)  # first 0-3 free
    paying_children = paid_kids_0_3 + children_4_10

    nights = []
    total = 0.0
    for i in range(n):
        d = ci + timedelta(days=i)
        is_weekend = d.weekday() in (4, 5)  # Fri, Sat night
        is_custom_holiday = d.isoformat() in holidays
        is_nat_holiday, holiday_name = is_brazilian_holiday(d)
        is_holiday = is_custom_holiday or is_nat_holiday
        surcharge = weekend_pct if (is_weekend or is_holiday) else 0.0
        nightly = base_rate * (1 + surcharge)
        # Adults
        first_adult = nightly
        extra_adult_each = nightly * (1 - adult_disc_pct)
        adults_val = first_adult + max(0, adults - 1) * extra_adult_each
        # Children
        kids_val = paying_children * nightly * child_pct
        # Pets (percent of nightly base for 1 adult)
        pets_val = (pets_small * pet_small + pets_medium * pet_medium + pets_large * pet_large) * nightly
        night_total = adults_val + kids_val + pets_val
        nights.append({
            "date": d.isoformat(),
            "surcharge": round(surcharge * 100, 2),
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "is_national_holiday": is_nat_holiday,
            "holiday_name": holiday_name,
            "nightly_rate": round(nightly, 2),
            "adults_value": round(adults_val, 2),
            "children_value": round(kids_val, 2),
            "pets_value": round(pets_val, 2),
            "total": round(night_total, 2),
        })
        total += night_total

    return {
        "total": round(total, 2),
        "n_nights": n,
        "nights": nights,
        "adults": adults,
        "children_0_3": children_0_3,
        "children_4_10": children_4_10,
        "free_children": min(1, children_0_3),
        "paying_children": paying_children,
        "pets": {"small": pets_small, "medium": pets_medium, "large": pets_large},
        "base_rate": base_rate,
    }


# ----- Pets breed classification -----
@api.get("/pets/classify")
async def pets_classify(breed: str, pet_type: str = ""):
    size, matched = classify_breed(breed, pet_type)
    return {"breed": breed, "type": pet_type, "size": size, "matched": matched,
            "message": None if matched else "Raça não reconhecida — usando porte médio como padrão. Ajuste manualmente se necessário."}


@api.get("/pets/breeds")
async def pets_breeds_list():
    """Autocomplete list of known breeds."""
    return {"breeds": sorted(ALL_BREEDS.keys())}


@api.get("/public/holidays")
async def public_holidays(year: int = Query(default=None)):
    """Return Brazilian national holidays for the given year (defaults to current)."""
    if year is None:
        year = datetime.now(timezone.utc).year
    y_now = get_brazilian_holidays(year)
    y_next = get_brazilian_holidays(year + 1)
    return {"year": year, "holidays": {**y_now, **y_next}}


# ----- Stripe payment links (admin generates per reservation) -----
class StripePaymentLinkIn(BaseModel):
    amount: Optional[float] = None  # BRL; if omitted uses reservation total_amount


@api.post("/reservations/{res_id}/payment-link")
async def create_payment_link(res_id: str, data: StripePaymentLinkIn, request: Request, user=Depends(require_admin)):
    if not stripe.api_key:
        raise HTTPException(503, "Stripe não configurado")
    r = await db.reservations.find_one({"id": res_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Reserva não encontrada")
    amount = float(data.amount) if data.amount else float(r.get("total_amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "Valor inválido — defina o total da reserva ou envie `amount`")
    origin = str(request.base_url).rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "unit_amount": int(round(amount * 100)),
                    "product_data": {
                        "name": "Reserva – Pousada Vale do Sol",
                        "description": f"{r.get('guest_name') or 'Hóspede'} · {r.get('checkin_date')} → {r.get('checkout_date')}",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/payment/cancel",
            metadata={"reservation_id": res_id, "guest_name": r.get("guest_name") or ""},
        )
    except stripe.error.StripeError as e:
        logger.error(f"stripe create failed: {e}")
        raise HTTPException(502, f"Falha ao criar link: {e.user_message or str(e)}")

    await db.reservations.update_one(
        {"id": res_id},
        {"$set": {
            "stripe_session_id": session.id,
            "stripe_payment_url": session.url,
            "stripe_payment_status": "pending",
            "stripe_amount": amount,
            "updated_at": now_iso(),
        }},
    )
    return {"url": session.url, "session_id": session.id, "amount": amount}


@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        logger.warning(f"stripe webhook parse error: {e}")
        raise HTTPException(400, "Invalid payload")

    obj = event["data"]["object"]
    t = event["type"]
    reservation_id = (obj.get("metadata") or {}).get("reservation_id")
    if not reservation_id:
        return {"status": "ignored"}

    if t == "checkout.session.completed":
        await db.reservations.update_one(
            {"id": reservation_id, "stripe_payment_status": {"$ne": "paid"}},
            {"$set": {
                "stripe_payment_status": obj.get("payment_status", "paid"),
                "status": "confirmed",
                "updated_at": now_iso(),
            }},
        )
    elif t == "checkout.session.async_payment_succeeded":
        await db.reservations.update_one(
            {"id": reservation_id},
            {"$set": {"stripe_payment_status": "paid", "status": "confirmed", "updated_at": now_iso()}},
        )
    elif t in ("checkout.session.async_payment_failed",):
        await db.reservations.update_one(
            {"id": reservation_id},
            {"$set": {"stripe_payment_status": "failed", "updated_at": now_iso()}},
        )
    elif t == "checkout.session.expired":
        await db.reservations.update_one(
            {"id": reservation_id},
            {"$set": {"stripe_payment_status": "expired", "updated_at": now_iso()}},
        )
    return {"status": "ok"}


# ----- Scheduled task: check-in reminder (3 days before) -----
async def _run_checkin_reminder():
    settings = await db.settings.find_one({"id": "primary"}, {"_id": 0}) or {}
    webhook = (settings.get("whatsapp_webhook_url") or "").strip()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    cur = db.reservations.find(
        {"checkin_date": target_date, "status": {"$in": ["confirmed", "pending"]}},
        {"_id": 0},
    )
    rooms_by_id = {r["id"]: r async for r in db.rooms.find({}, {"_id": 0})}
    sent = 0
    async for r in cur:
        room = rooms_by_id.get(r.get("room_id") or "", {})
        pay_url = r.get("stripe_payment_url") or ""
        parts = [
            f"🏨 *Lembrete de hospedagem* — {settings.get('name') or 'Pousada'}",
            f"Olá {r.get('guest_name') or 'hóspede'}! Sua estadia começa em 3 dias.",
            f"📅 {r.get('checkin_date')} → {r.get('checkout_date')}",
            f"🛏️ Quarto: {room.get('name') or '—'}",
        ]
        if settings.get("pix_key"):
            parts.append(f"💠 PIX: {settings['pix_key']} ({settings.get('pix_key_type') or 'chave'})")
        if pay_url:
            parts.append(f"💳 Link de pagamento (cartão): {pay_url}")
        parts.append("Qualquer dúvida, é só responder. Até breve! 🌿")
        msg = "\n".join(parts)
        if webhook:
            asyncio.create_task(_fire_webhook(webhook, msg))
        # per-guest WhatsApp direct push also, if a user-level webhook is set via settings
        sent += 1
    return sent


@api.post("/cron/checkin-reminder")
async def cron_checkin_reminder(request: Request, authorization: Optional[str] = Header(default=None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    expected = WEBHOOK_CRON_SECRET or ""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "unauthorized")
    asyncio.create_task(_run_checkin_reminder())
    return {"status": "accepted"}


@api.post("/admin/cron/checkin-reminder/run")
async def admin_trigger_reminder(user=Depends(require_admin)):
    """Manual trigger for testing — admin only."""
    count = await _run_checkin_reminder()
    return {"status": "ok", "scanned_date": (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat(), "sent": count}


def _normalize_pets_input(pets: list, pets_small: int, pets_medium: int, pets_large: int):
    """Given an array of pets (with breed) or legacy count fields, return (list_with_size, small_ct, med_ct, large_ct)."""
    out = []
    s = m = l = 0
    if pets:
        for p in pets:
            if not isinstance(p, dict):
                p = p.model_dump() if hasattr(p, "model_dump") else dict(p)
            breed = (p.get("breed") or "").strip()
            ptype = (p.get("type") or "").strip()
            size = (p.get("size") or "").strip().lower()
            if size not in ("small", "medium", "large"):
                size, _matched = classify_breed(breed, ptype)
            p["size"] = size
            p["breed"] = breed
            p["type"] = ptype or "cão"
            out.append(p)
            if size == "small": s += 1
            elif size == "large": l += 1
            else: m += 1
    else:
        s = max(0, int(pets_small or 0))
        m = max(0, int(pets_medium or 0))
        l = max(0, int(pets_large or 0))
    return out, s, m, l


class PricingCalcIn(BaseModel):
    room_id: str
    checkin_date: str
    checkout_date: str
    adults: int = 1
    children_0_3: int = 0
    children_4_10: int = 0
    pets_small: int = 0
    pets_medium: int = 0
    pets_large: int = 0
    pets: List[PetItem] = []


@api.post("/pricing/calc")
async def pricing_calc(data: PricingCalcIn):
    """Public pricing calculator — no PII, no reservation write. Used by the public form and admin."""
    room = await db.rooms.find_one({"id": data.room_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not room:
        raise HTTPException(404, "Quarto não encontrado")
    settings = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
    _pets_list, s, m, l = _normalize_pets_input(
        [p.model_dump() for p in data.pets], data.pets_small, data.pets_medium, data.pets_large
    )
    return compute_pricing(
        room, data.checkin_date, data.checkout_date,
        data.adults, data.children_0_3, data.children_4_10,
        s, m, l, settings,
    )


# ----- Public receipt upload (no auth, rate-limited by content-type + size) -----
@api.post("/public/uploads/receipt")
async def public_upload_receipt(file: UploadFile = File(...)):
    ctype = (file.content_type or "").lower()
    if not (ctype.startswith("image/") or ctype == "application/pdf"):
        raise HTTPException(400, "Envie uma imagem ou PDF")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Arquivo muito grande (máx 8MB)")
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/receipts/{new_id()}.{ext}"
    result = put_object(path, data, ctype)
    file_doc = {
        "id": new_id(),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": now_iso(),
    }
    await db.files.insert_one(file_doc)
    return {"path": result["path"], "url": f"/api/files/{result['path']}", "size": file_doc["size"]}


# ----- PUBLIC pre-reservation (write-only) -----
@api.post("/public/pre-reservation")
async def public_pre_reservation(data: PublicReservationIn):
    if not data.accepted_terms:
        raise HTTPException(400, "É necessário aceitar os termos")
    r = Reservation(
        **data.model_dump(),
        source="public_form",
        status="pending",
    ).model_dump()
    r["is_deleted"] = False
    # Normalize pets: classify by breed + aggregate counts
    pets_list, ps, pm, pl = _normalize_pets_input(r.get("pets") or [], r.get("pets_small", 0), r.get("pets_medium", 0), r.get("pets_large", 0))
    r["pets"] = pets_list
    r["pets_small"] = ps
    r["pets_medium"] = pm
    r["pets_large"] = pl
    # Compute pricing server-side
    try:
        settings0 = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
        if r.get("room_id"):
            room0 = await db.rooms.find_one({"id": r["room_id"], "is_deleted": {"$ne": True}}, {"_id": 0})
            if room0:
                r["pricing_breakdown"] = compute_pricing(
                    room0, r["checkin_date"], r["checkout_date"],
                    r.get("adults", 1), r.get("children_0_3", 0), r.get("children_4_10", 0),
                    ps, pm, pl, settings0,
                )
                r["total_amount"] = r["pricing_breakdown"].get("total", 0)
    except Exception as e:
        logger.warning(f"pricing calc failed: {e}")
    # Sync children legacy total
    r["children"] = int(r.get("children_0_3", 0) or 0) + int(r.get("children_4_10", 0) or 0)
    await db.reservations.insert_one(r)

    # Fire-and-forget emails
    try:
        settings = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
        room_name = "—"
        if r.get("room_id"):
            room = await db.rooms.find_one({"id": r["room_id"]}, {"_id": 0})
            if room:
                room_name = room.get("name") or "—"
        if r.get("guest_email"):
            asyncio.create_task(send_email(
                to=r["guest_email"],
                subject=f"Pré-reserva recebida — {settings.get('name') or EMAIL_FROM_NAME}",
                html=_guest_email_html(settings, r, room_name),
            ))
        if settings.get("email"):
            asyncio.create_task(send_email(
                to=settings["email"],
                subject=f"Nova pré-reserva: {r.get('guest_name')}",
                html=_owner_email_html(settings, r, room_name),
            ))
        # WhatsApp push via webhook (CallMeBot / n8n / Zapier)
        webhook = (settings.get("whatsapp_webhook_url") or "").strip()
        if webhook:
            msg = (
                f"🏨 *Nova pré-reserva* — {settings.get('name') or 'Pousada'}\n"
                f"Hóspede: {r.get('guest_name')}\n"
                f"Contato: {r.get('guest_phone')} | {r.get('guest_email')}\n"
                f"Datas: {r.get('checkin_date')} → {r.get('checkout_date')}\n"
                f"Quarto: {room_name}\n"
                f"Pessoas: {r.get('adults')} adultos, {r.get('children')} crianças"
            )
            asyncio.create_task(_fire_webhook(webhook, msg))
    except Exception as e:
        logger.warning(f"pre-reservation dispatch failed: {e}")

    return {"ok": True, "reservation_id": r["id"], "message": "Pré-reserva recebida. Aguarde contato para confirmação."}


async def _fire_webhook(url: str, text: str):
    """Send a WhatsApp push through a user-configured webhook (e.g. CallMeBot).
    Injects the message either as `text` query param (GET) or JSON body (POST).
    """
    try:
        async with httpx.AsyncClient(timeout=15) as clientx:
            if "{text}" in url:
                await clientx.get(url.replace("{text}", httpx.QueryParams({"t": text})["t"]))
            elif "callmebot.com" in url or "text=" in url:
                sep = "&" if "?" in url else "?"
                await clientx.get(f"{url}{sep}text={httpx.QueryParams({'t': text})['t']}")
            else:
                await clientx.post(url, json={"text": text})
        logger.info("WhatsApp webhook fired")
    except Exception as e:
        logger.warning(f"WhatsApp webhook error: {e}")


# ----- Users management (admin only) -----
class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "reception"  # admin | reception


class UserUpdateIn(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None


@api.get("/users")
async def users_list(user=Depends(require_admin_role)):
    rows = await db.users.find({"is_deleted": {"$ne": True}}, {"_id": 0, "password_hash": 0}).to_list(200)
    return [clean_doc(r) for r in rows]


@api.post("/users")
async def users_create(data: UserCreateIn, user=Depends(require_admin_role)):
    if data.role not in {"admin", "reception"}:
        raise HTTPException(400, "Perfil inválido")
    existing = await db.users.find_one({"email": data.email.lower(), "is_deleted": {"$ne": True}})
    if existing:
        raise HTTPException(400, "E-mail já cadastrado")
    doc = {
        "id": new_id(),
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "role": data.role,
        "is_deleted": False,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return {"id": doc["id"], "email": doc["email"], "role": doc["role"]}


@api.put("/users/{user_id}")
async def users_update(user_id: str, data: UserUpdateIn, user=Depends(require_admin_role)):
    update: dict = {}
    if data.role:
        if data.role not in {"admin", "reception"}:
            raise HTTPException(400, "Perfil inválido")
        update["role"] = data.role
    if data.password:
        if len(data.password) < 6:
            raise HTTPException(400, "Senha muito curta")
        update["password_hash"] = hash_password(data.password)
    if not update:
        raise HTTPException(400, "Nada para atualizar")
    result = await db.users.update_one({"id": user_id, "is_deleted": {"$ne": True}}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Usuário não encontrado")
    return {"ok": True}


@api.delete("/users/{user_id}")
async def users_delete(user_id: str, user=Depends(require_admin_role)):
    if user_id == user["id"]:
        raise HTTPException(400, "Não é possível excluir o próprio usuário")
    # Prevent deleting the last admin
    other_admins = await db.users.count_documents({"role": "admin", "is_deleted": {"$ne": True}, "id": {"$ne": user_id}})
    target = await db.users.find_one({"id": user_id})
    if target and target.get("role") == "admin" and other_admins == 0:
        raise HTTPException(400, "É necessário manter pelo menos um administrador")
    await db.users.update_one({"id": user_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


# ----- Occupancy heatmap -----
@api.get("/reports/occupancy")
async def occupancy_heatmap(user=Depends(require_admin), year: Optional[int] = None, month: Optional[int] = None):
    today = date.today()
    y = year or today.year
    m = month or today.month
    start = date(y, m, 1)
    end = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    rooms = await db.rooms.find({"is_deleted": {"$ne": True}}, {"_id": 0, "ical_token": 0}).to_list(500)
    reservations = await db.reservations.find(
        {"is_deleted": {"$ne": True}, "checkin_date": {"$lt": end.isoformat()}, "checkout_date": {"$gt": start.isoformat()}},
        {"_id": 0},
    ).to_list(5000)

    days = (end - start).days
    # Build room -> [status per day]
    matrix = {r["id"]: ["free"] * days for r in rooms}
    for r in reservations:
        rid = r.get("room_id")
        if rid not in matrix:
            continue
        try:
            ci = max(date.fromisoformat(r["checkin_date"]), start)
            co = min(date.fromisoformat(r["checkout_date"]), end)
        except Exception:
            continue
        for d in range((co - ci).days):
            idx = (ci - start).days + d
            if 0 <= idx < days:
                # priority: confirmed/checked_in > pending > blocked/maintenance
                current = matrix[rid][idx]
                new = r.get("status", "pending")
                priority = {"free": 0, "pending": 1, "blocked": 2, "maintenance": 2, "confirmed": 3, "checked_in": 3, "checked_out": 3, "cancelled": 0}
                if priority.get(new, 0) > priority.get(current, 0):
                    matrix[rid][idx] = new

    return {
        "year": y, "month": m, "days": days,
        "rooms": [{"id": r["id"], "name": r["name"], "cells": matrix[r["id"]]} for r in rooms],
    }


# ----- PIX BR Code (Copia-e-Cola + QR) -----
def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


# ----- Public QR (link to /reservar) -----
class PublicQRIn(BaseModel):
    url: str
    caption: Optional[str] = ""


@api.post("/qr/link")
async def qr_link(data: PublicQRIn, user=Depends(require_admin)):
    if not data.url:
        raise HTTPException(400, "URL obrigatória")
    img = qrcode.make(data.url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"url": data.url, "qr_png_base64": f"data:image/png;base64,{b64}"}


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def build_pix_brcode(pix_key: str, merchant_name: str = "POUSADA", merchant_city: str = "BRASIL", amount: Optional[float] = None, txid: str = "***") -> str:
    if not pix_key:
        return ""
    mai = _tlv("00", "br.gov.bcb.pix") + _tlv("01", pix_key)
    payload = (
        _tlv("00", "01")
        + _tlv("26", mai)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + (_tlv("54", f"{amount:.2f}") if amount and amount > 0 else "")
        + _tlv("58", "BR")
        + _tlv("59", _strip_accents(merchant_name)[:25] or "POUSADA")
        + _tlv("60", _strip_accents(merchant_city)[:15] or "BRASIL")
        + _tlv("62", _tlv("05", txid[:25] or "***"))
    )
    payload += "6304"
    return payload + _crc16_ccitt(payload)


class PixIn(BaseModel):
    amount: Optional[float] = None
    txid: Optional[str] = "***"


@api.post("/pix/brcode")
async def pix_brcode(data: PixIn, user=Depends(require_admin)):
    settings = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
    key = (settings.get("pix_key") or "").strip()
    if not key:
        raise HTTPException(400, "Chave PIX não configurada em Site & Galeria")
    name = settings.get("name") or "POUSADA"
    city = "BRASIL"
    if settings.get("address"):
        parts = [p.strip() for p in settings["address"].split(",") if p.strip()]
        if parts:
            city = parts[-1]
    payload = build_pix_brcode(key, name, city, data.amount, data.txid or "***")
    # Generate QR PNG (base64)
    img = qrcode.make(payload)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {
        "brcode": payload,
        "qr_png_base64": f"data:image/png;base64,{b64}",
        "amount": data.amount,
        "pix_key": key,
        "merchant_name": name,
    }


class BlockDatesIn(BaseModel):
    room_id: str
    from_date: str
    to_date: str
    reason: Optional[str] = "Bloqueado"


@api.post("/reservations/block")
async def block_dates(data: BlockDatesIn, user=Depends(require_admin)):
    room = await db.rooms.find_one({"id": data.room_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not room:
        raise HTTPException(404, "Quarto não encontrado")
    try:
        ci = date.fromisoformat(data.from_date)
        co = date.fromisoformat(data.to_date)
    except Exception:
        raise HTTPException(400, "Datas inválidas")
    if co <= ci:
        raise HTTPException(400, "Data final deve ser após a inicial")
    r = Reservation(
        room_id=data.room_id,
        checkin_date=data.from_date,
        checkout_date=data.to_date,
        guest_name=data.reason or "Bloqueado",
        source="direct",
        status="blocked",
        notes=f"Bloqueio manual: {data.reason or ''}",
    ).model_dump()
    r["is_deleted"] = False
    await db.reservations.insert_one(r)
    return clean_doc(r)


# ----- Voucher PDF (per reservation) -----
@api.get("/reservations/{res_id}/voucher.pdf")
async def reservation_voucher(res_id: str, user=Depends(require_admin)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

    r = await db.reservations.find_one({"id": res_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Reserva não encontrada")
    settings = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
    room = await db.rooms.find_one({"id": r.get("room_id")}, {"_id": 0}) if r.get("room_id") else None
    room_name = (room or {}).get("name", "—")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    TERRA = colors.HexColor("#C85A32")
    PALM = colors.HexColor("#2D5A43")
    SAND = colors.HexColor("#F4EFE6")
    story = []

    # Header
    logo_url = (settings.get("logo_url") or "").strip()
    header_cells = []
    try:
        if logo_url.startswith("/api/files/"):
            path = logo_url.split("/api/files/", 1)[1]
            b, _ = get_object(path)
            header_cells.append(RLImage(BytesIO(b), width=28*mm, height=28*mm))
        elif logo_url:
            lr = requests.get(logo_url, timeout=10)
            header_cells.append(RLImage(BytesIO(lr.content), width=28*mm, height=28*mm))
        else:
            header_cells.append(Paragraph("", styles["Normal"]))
    except Exception:
        header_cells.append(Paragraph("", styles["Normal"]))
    header_cells.append(Paragraph(
        f"<font color='#C85A32'><b>{settings.get('name') or 'Pousada'}</b></font><br/>"
        f"<font size=9 color='#57534E'>Voucher de Reserva</font>",
        styles["Normal"],
    ))
    ht = Table([header_cells], colWidths=[32*mm, 130*mm])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(ht)
    story.append(Spacer(1, 12))

    def brl(v):
        return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    guest_style = ParagraphStyle("g", parent=styles["Normal"], fontSize=11, leading=16)
    story.append(Paragraph(f"<b>Hóspede:</b> {r.get('guest_name','')}", guest_style))
    story.append(Paragraph(f"<b>Documento:</b> {r.get('guest_document','')}", guest_style))
    story.append(Paragraph(f"<b>Contato:</b> {r.get('guest_phone','')} · {r.get('guest_email','')}", guest_style))
    story.append(Spacer(1, 8))

    info = [
        ["Quarto", room_name],
        ["Check-in", f"{r.get('checkin_date','')} às {settings.get('checkin_time','14:00')}"],
        ["Check-out", f"{r.get('checkout_date','')} às {settings.get('checkout_time','11:00')}"],
        ["Adultos", str(r.get("adults", 1))],
        ["Crianças 0-3", str(r.get("children_0_3", 0))],
        ["Crianças 4-10", str(r.get("children_4_10", 0))],
        ["Pets", f"P {r.get('pets_small',0)} · M {r.get('pets_medium',0)} · G {r.get('pets_large',0)}"],
        ["Total", brl(r.get("total_amount", 0))],
        ["Status", (r.get("status") or "").upper()],
    ]
    t = Table(info, colWidths=[45*mm, 120*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SAND),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1C6B4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
        ("BACKGROUND", (0, -2), (-1, -2), TERRA),
        ("TEXTCOLOR", (0, -2), (-1, -2), colors.white),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Rules & PIX
    story.append(Paragraph("<b>Regras da estadia</b>", ParagraphStyle("h", parent=styles["Heading3"], textColor=PALM, fontSize=12)))
    story.append(Paragraph("• É totalmente proibido fumar dentro dos quartos.", styles["Normal"]))
    if (r.get("pets_small", 0) + r.get("pets_medium", 0) + r.get("pets_large", 0)) > 0:
        story.append(Paragraph("• O animal não pode dormir nas camas e qualquer dano ou avaria causada pelo animal é de inteira responsabilidade do tutor.", styles["Normal"]))
    if settings.get("policies"):
        story.append(Paragraph(f"• {settings.get('policies')}", styles["Normal"]))
    story.append(Spacer(1, 10))

    if settings.get("pix_key"):
        story.append(Paragraph("<b>Pagamento via PIX</b>", ParagraphStyle("h2", parent=styles["Heading3"], textColor=PALM, fontSize=12)))
        story.append(Paragraph(f"Chave ({settings.get('pix_key_type','')}): <font face='Courier'>{settings.get('pix_key')}</font>", styles["Normal"]))
        story.append(Paragraph(f"Beneficiário: {settings.get('name','')}", styles["Normal"]))

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f"<font size=8 color='#78716C'>Emitido em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')} · {settings.get('address','')}</font>",
        styles["Normal"],
    ))
    doc.build(story)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="voucher_{r.get("guest_name","hospede").split()[0]}_{r.get("checkin_date","")}.pdf"'},
    )


# ----- Finance PDF report -----
@api.get("/finance/report.pdf")
async def finance_report_pdf(user=Depends(require_admin_role), from_date: Optional[str] = None, to_date: Optional[str] = None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT

    settings = await db.settings.find_one({"id": "singleton"}, {"_id": 0}) or {}
    q: dict = {"is_deleted": {"$ne": True}}
    if from_date or to_date:
        q["entry_date"] = {}
        if from_date:
            q["entry_date"]["$gte"] = from_date
        if to_date:
            q["entry_date"]["$lte"] = to_date
    rows = await db.finance.find(q, {"_id": 0}).sort("entry_date", 1).to_list(5000)
    income = sum(r["amount"] for r in rows if r["kind"] == "income")
    expense = sum(r["amount"] for r in rows if r["kind"] == "expense")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    TERRA = colors.HexColor("#C85A32")
    PALM = colors.HexColor("#2D5A43")
    SAND = colors.HexColor("#F4EFE6")

    title_style = ParagraphStyle("title", parent=styles["Heading1"], textColor=TERRA, fontSize=22, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#57534E"), fontSize=10, spaceAfter=14)

    story = []
    # Header row: logo + title
    logo_url = (settings.get("logo_url") or "").strip()
    header_cells = []
    if logo_url:
        try:
            if logo_url.startswith("/api/files/"):
                path = logo_url.split("/api/files/", 1)[1]
                data, _ct = get_object(path)
                logo_img = RLImage(BytesIO(data), width=28*mm, height=28*mm)
            else:
                lr = requests.get(logo_url, timeout=10)
                logo_img = RLImage(BytesIO(lr.content), width=28*mm, height=28*mm)
            logo_img.hAlign = "LEFT"
            header_cells.append(logo_img)
        except Exception:
            header_cells.append(Paragraph("", styles["Normal"]))
    else:
        header_cells.append(Paragraph("", styles["Normal"]))

    header_cells.append(Paragraph(
        f"<font color='#C85A32'><b>{settings.get('name') or 'Pousada'}</b></font><br/>"
        f"<font size=9 color='#57534E'>Relatório Financeiro<br/>Período: {from_date or 'início'} → {to_date or 'hoje'}</font>",
        styles["Normal"],
    ))
    ht = Table([header_cells], colWidths=[32*mm, 130*mm])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(ht)
    story.append(Spacer(1, 6))
    story.append(Paragraph("<hr/>", styles["Normal"]))
    story.append(Spacer(1, 6))

    # Summary
    profit = income - expense
    summary_data = [
        ["Receitas", f"R$ {income:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")],
        ["Despesas", f"R$ {expense:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")],
        ["Lucro líquido", f"R$ {profit:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")],
    ]
    st = Table(summary_data, colWidths=[80*mm, 60*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SAND),
        ("BACKGROUND", (0, 1), (-1, 1), SAND),
        ("BACKGROUND", (0, 2), (-1, 2), TERRA),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
    ]))
    story.append(st)
    story.append(Spacer(1, 16))

    # Entries table
    story.append(Paragraph("<b>Lançamentos</b>", ParagraphStyle("h2", parent=styles["Heading2"], textColor=PALM, fontSize=13)))
    tbl = [["Data", "Tipo", "Categoria", "Descrição", "Valor (R$)"]]
    for r in rows:
        tbl.append([
            r.get("entry_date", ""),
            "Receita" if r.get("kind") == "income" else "Despesa",
            r.get("category", ""),
            (r.get("description") or "")[:60],
            f"{float(r.get('amount', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        ])
    if len(tbl) == 1:
        tbl.append(["—", "—", "—", "Sem lançamentos no período", "0,00"])
    t = Table(tbl, colWidths=[22*mm, 20*mm, 32*mm, 66*mm, 22*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALM),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SAND]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1C6B4")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 24))
    story.append(Paragraph(
        f"<font size=8 color='#78716C'>Gerado por {settings.get('name') or 'Pousada'} · {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}</font>",
        styles["Normal"],
    ))

    doc.build(story)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="financeiro_{from_date or "inicio"}_{to_date or "hoje"}.pdf"'},
    )


# ----- Finance -----
@api.get("/finance")
async def finance_list(user=Depends(require_admin_role), from_date: Optional[str] = None, to_date: Optional[str] = None):
    q: dict = {"is_deleted": {"$ne": True}}
    if from_date or to_date:
        q["entry_date"] = {}
        if from_date:
            q["entry_date"]["$gte"] = from_date
        if to_date:
            q["entry_date"]["$lte"] = to_date
    rows = await db.finance.find(q, {"_id": 0}).sort("entry_date", -1).to_list(2000)
    return [clean_doc(r) for r in rows]


@api.post("/finance")
async def finance_create(data: FinanceIn, user=Depends(require_admin_role)):
    if data.kind not in {"income", "expense"}:
        raise HTTPException(400, "Tipo inválido")
    entry = FinanceEntry(**data.model_dump()).model_dump()
    entry["is_deleted"] = False
    await db.finance.insert_one(entry)
    return clean_doc(entry)


@api.delete("/finance/{entry_id}")
async def finance_delete(entry_id: str, user=Depends(require_admin_role)):
    await db.finance.update_one({"id": entry_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.get("/finance/export.csv")
async def finance_export_csv(user=Depends(require_admin_role), from_date: Optional[str] = None, to_date: Optional[str] = None):
    q: dict = {"is_deleted": {"$ne": True}}
    if from_date or to_date:
        q["entry_date"] = {}
        if from_date:
            q["entry_date"]["$gte"] = from_date
        if to_date:
            q["entry_date"]["$lte"] = to_date
    rows = await db.finance.find(q, {"_id": 0}).sort("entry_date", 1).to_list(5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Data", "Tipo", "Categoria", "Valor", "Descricao"])
    for r in rows:
        w.writerow([
            r.get("entry_date", ""),
            "Receita" if r.get("kind") == "income" else "Despesa",
            r.get("category", ""),
            f"{float(r.get('amount', 0)):.2f}",
            (r.get("description") or "").replace("\n", " "),
        ])
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="financeiro_{from_date or "inicio"}_{to_date or "hoje"}.csv"'},
    )


@api.get("/finance/monthly")
async def finance_monthly(user=Depends(require_admin_role), months: int = 6):
    """Aggregate income/expense per month for the last N months."""
    today = date.today()
    year, month = today.year, today.month
    result: list = []
    for i in range(months - 1, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        end = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
        rows = await db.finance.find(
            {"is_deleted": {"$ne": True}, "entry_date": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
            {"_id": 0},
        ).to_list(2000)
        inc = sum(r["amount"] for r in rows if r["kind"] == "income")
        exp = sum(r["amount"] for r in rows if r["kind"] == "expense")
        result.append({
            "label": f"{start.strftime('%b')}/{str(y)[2:]}",
            "month": start.isoformat(),
            "income": round(inc, 2),
            "expense": round(exp, 2),
            "profit": round(inc - exp, 2),
        })
    return result


@api.get("/finance/summary")
async def finance_summary(user=Depends(require_admin_role), from_date: Optional[str] = None, to_date: Optional[str] = None):
    q: dict = {"is_deleted": {"$ne": True}}
    if from_date or to_date:
        q["entry_date"] = {}
        if from_date:
            q["entry_date"]["$gte"] = from_date
        if to_date:
            q["entry_date"]["$lte"] = to_date
    rows = await db.finance.find(q, {"_id": 0}).to_list(5000)
    income = sum(r["amount"] for r in rows if r["kind"] == "income")
    expense = sum(r["amount"] for r in rows if r["kind"] == "expense")
    # Occupancy: nights confirmed in period / total nights available
    res_q = {"is_deleted": {"$ne": True}, "status": {"$in": ["confirmed", "checked_in", "checked_out"]}}
    if from_date:
        res_q["checkout_date"] = {"$gte": from_date}
    if to_date:
        res_q["checkin_date"] = {"$lte": to_date}
    reservations = await db.reservations.find(res_q, {"_id": 0}).to_list(5000)
    booked_nights = 0
    for r in reservations:
        try:
            ci = date.fromisoformat(r["checkin_date"])
            co = date.fromisoformat(r["checkout_date"])
            booked_nights += max(0, (co - ci).days)
        except Exception:
            pass
    room_count = await db.rooms.count_documents({"is_deleted": {"$ne": True}})
    try:
        if from_date and to_date:
            days = max(1, (date.fromisoformat(to_date) - date.fromisoformat(from_date)).days)
        else:
            days = 30
    except Exception:
        days = 30
    capacity = room_count * days if room_count else 0
    occupancy = round((booked_nights / capacity) * 100, 1) if capacity else 0
    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "profit": round(income - expense, 2),
        "occupancy": occupancy,
        "booked_nights": booked_nights,
        "capacity": capacity,
    }


# ----- iCal Export (public per-room) -----
@api.get("/ical/room/{room_id}/{token}.ics")
async def ical_export(room_id: str, token: str):
    room = await db.rooms.find_one({"id": room_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not room:
        raise HTTPException(404, "Quarto não encontrado")
    if not hmac.compare_digest(room.get("ical_token", ""), token):
        raise HTTPException(403, "Token inválido")
    cal = Calendar()
    cal.add("prodid", "-//Pousada Mgmt//PT-BR//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"Pousada - {room['name']}")
    reservations = await db.reservations.find(
        {
            "room_id": room_id,
            "is_deleted": {"$ne": True},
            "status": {"$in": ["confirmed", "checked_in", "checked_out", "blocked", "maintenance"]},
        },
        {"_id": 0},
    ).to_list(2000)
    for r in reservations:
        try:
            ev = Event()
            ev.add("uid", f"{r['id']}@pousada")
            ev.add("summary", f"{r.get('guest_name') or 'Reservado'} ({r['status']})")
            ev.add("dtstart", date.fromisoformat(r["checkin_date"]))
            ev.add("dtend", date.fromisoformat(r["checkout_date"]))
            ev.add("dtstamp", datetime.now(timezone.utc))
            ev.add("description", r.get("notes") or "")
            cal.add_component(ev)
        except Exception as e:
            logger.warning(f"skip export event {r.get('id')}: {e}")
    return Response(content=cal.to_ical(), media_type="text/calendar")


# ----- iCal Import Sources -----
@api.get("/ical/sources")
async def ical_sources_list(user=Depends(require_admin)):
    rows = await db.ical_sources.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    return [clean_doc(r) for r in rows]


@api.post("/ical/sources")
async def ical_sources_add(data: ICalSourceIn, user=Depends(require_admin_role)):
    s = ICalImportSource(**data.model_dump()).model_dump()
    s["is_deleted"] = False
    await db.ical_sources.insert_one(s)
    return clean_doc(s)


@api.delete("/ical/sources/{source_id}")
async def ical_sources_delete(source_id: str, user=Depends(require_admin_role)):
    await db.ical_sources.update_one({"id": source_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


async def _sync_source(source: dict) -> dict:
    try:
        r = requests.get(source["url"], timeout=30)
        r.raise_for_status()
        cal = Calendar.from_ical(r.text)
        count = 0
        for comp in cal.walk("VEVENT"):
            uid = str(comp.get("uid") or f"noid-{new_id()}")
            dtstart = comp.get("dtstart")
            dtend = comp.get("dtend")
            summary = str(comp.get("summary") or "OTA Reserva")
            if not dtstart or not dtend:
                continue
            d_start = dtstart.dt
            d_end = dtend.dt
            if isinstance(d_start, datetime):
                d_start = d_start.date()
            if isinstance(d_end, datetime):
                d_end = d_end.date()
            existing = await db.reservations.find_one({"ota_uid": uid, "room_id": source["room_id"]}, {"_id": 0})
            doc = {
                "room_id": source["room_id"],
                "source": "ota_import",
                "ota_source": source["name"],
                "ota_uid": uid,
                "status": "blocked",
                "guest_name": summary,
                "checkin_date": d_start.isoformat(),
                "checkout_date": d_end.isoformat(),
                "notes": f"Importado de {source['name']}",
                "is_deleted": False,
                "updated_at": now_iso(),
            }
            if existing:
                await db.reservations.update_one({"id": existing["id"]}, {"$set": doc})
            else:
                doc["id"] = new_id()
                doc["created_at"] = now_iso()
                doc["adults"] = 1
                doc["children"] = 0
                doc["accepted_terms"] = False
                doc["total_amount"] = 0.0
                doc["deposit_amount"] = 0.0
                await db.reservations.insert_one(doc)
            count += 1
        await db.ical_sources.update_one(
            {"id": source["id"]},
            {"$set": {"last_sync": now_iso(), "last_status": "ok", "imported_count": count}},
        )
        return {"ok": True, "count": count}
    except Exception as e:
        await db.ical_sources.update_one(
            {"id": source["id"]}, {"$set": {"last_sync": now_iso(), "last_status": f"error: {e}"}}
        )
        return {"ok": False, "error": str(e)}


@api.post("/ical/sync")
async def ical_sync_all(user=Depends(require_admin)):
    sources = await db.ical_sources.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    results = []
    for s in sources:
        r = await _sync_source(s)
        results.append({"source": s["name"], "room_id": s["room_id"], **r})
    return {"synced": len(results), "results": results}


@api.post("/ical/sync/{source_id}")
async def ical_sync_one(source_id: str, user=Depends(require_admin)):
    s = await db.ical_sources.find_one({"id": source_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Fonte não encontrada")
    return await _sync_source(s)


# ----- WhatsApp templates -----
@api.get("/whatsapp/templates")
async def wa_templates_list(user=Depends(require_admin)):
    rows = await db.wa_templates.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    if not rows:
        # seed defaults
        defaults = [
            {"title": "Boas-vindas", "body": "Olá {nome}! Obrigado por escolher a nossa pousada. Sua reserva do quarto {quarto} para {checkin} até {checkout} foi recebida."},
            {"title": "Confirmação com PIX", "body": "Olá {nome}! Para confirmar sua reserva ({checkin} a {checkout}), envie o valor de R$ {valor} via PIX para: {chave_pix}. Após o envio, nos envie o comprovante por aqui."},
            {"title": "Lembrete de Check-in", "body": "Olá {nome}! Estamos ansiosos pela sua chegada em {checkin}. O check-in é a partir das {checkin_time}. Qualquer dúvida, estamos à disposição."},
            {"title": "Instruções de chegada", "body": "Olá {nome}! Segue endereço: {endereco}. WhatsApp de emergência: {whatsapp}. Bem-vindo!"},
        ]
        for t in defaults:
            wt = WhatsAppTemplate(**t).model_dump()
            wt["is_deleted"] = False
            await db.wa_templates.insert_one(wt)
        rows = await db.wa_templates.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    return [clean_doc(r) for r in rows]


@api.post("/whatsapp/templates")
async def wa_templates_create(data: WhatsAppTemplateIn, user=Depends(require_admin)):
    t = WhatsAppTemplate(**data.model_dump()).model_dump()
    t["is_deleted"] = False
    await db.wa_templates.insert_one(t)
    return clean_doc(t)


@api.put("/whatsapp/templates/{tid}")
async def wa_templates_update(tid: str, data: WhatsAppTemplateIn, user=Depends(require_admin)):
    result = await db.wa_templates.update_one({"id": tid}, {"$set": data.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(404, "Template não encontrado")
    t = await db.wa_templates.find_one({"id": tid}, {"_id": 0})
    return clean_doc(t)


@api.delete("/whatsapp/templates/{tid}")
async def wa_templates_delete(tid: str, user=Depends(require_admin)):
    await db.wa_templates.update_one({"id": tid}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.get("/")
async def root():
    return {"service": "pousada-mgmt", "status": "ok"}


# ============================================================================
# HR MODULE — Fase 1: colaboradores, escalas 5x2, dashboard, portal colaborador
# ============================================================================

class EmployeeIn(BaseModel):
    name: str = Field(min_length=2)
    cpf: Optional[str] = ""
    role_title: Optional[str] = "Camareira"
    email: Optional[str] = ""
    phone: Optional[str] = ""
    hire_date: str  # YYYY-MM-DD
    base_salary: float = 0.0
    weekly_hours: int = 44
    weekly_rest_days: List[int] = [5, 6]  # 0=Mon..6=Sun
    default_shift_start: str = "08:00"
    default_shift_end: str = "17:00"
    status: Optional[str] = "active"
    dependents: int = 0
    sunday_rest_every_weeks: int = Field(default=3, ge=1, le=7)
    sunday_offset: int = 0


class EmployeePortalPasswordIn(BaseModel):
    password: str = Field(min_length=4)


class ShiftUpdateIn(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_rest: Optional[bool] = None
    notes: Optional[str] = ""


class EmployeeLoginIn(BaseModel):
    email: str
    password: str


EMP_JWT_SUB_PREFIX = "emp:"


def make_employee_jwt(employee_id: str) -> str:
    return jwt.encode(
        {"sub": EMP_JWT_SUB_PREFIX + employee_id,
         "exp": datetime.now(timezone.utc) + timedelta(days=30)},
        JWT_SECRET, algorithm=JWT_ALG,
    )


async def require_employee(token: Optional[str] = Depends(oauth2)):
    if not token:
        raise HTTPException(401, "Não autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido ou expirado")
    sub = payload.get("sub") or ""
    if not sub.startswith(EMP_JWT_SUB_PREFIX):
        raise HTTPException(401, "Token não é de colaborador")
    emp_id = sub[len(EMP_JWT_SUB_PREFIX):]
    emp = await db.employees.find_one({"id": emp_id, "status": "active"}, {"_id": 0, "portal_password_hash": 0})
    if not emp:
        raise HTTPException(401, "Colaborador não encontrado ou inativo")
    return emp


def month_bounds(month: str):
    try:
        y, m = int(month[:4]), int(month[5:7])
        if m < 1 or m > 12 or len(month) != 7:
            raise ValueError
    except Exception:
        raise HTTPException(400, "Formato inválido. Use YYYY-MM")
    _, last_day = cal.monthrange(y, m)
    return y, m, f"{month}-01", f"{month}-{last_day:02d}"


async def apply_vacations_to_shifts(employee_id: str, start: str, end: str):
    async for v in db.vacations.find({"employee_id": employee_id, "status": "approved",
                                      "start_date": {"$lte": end}, "end_date": {"$gte": start}}, {"_id": 0}):
        await db.shifts.update_many(
            {"employee_id": employee_id, "date": {"$gte": max(start, v["start_date"]), "$lte": min(end, v["end_date"])}},
            {"$set": {"is_rest": True, "is_vacation": True, "is_dsr": False, "start_time": None, "end_time": None, "notes": "Férias"}},
        )


# ----- Admin HR routes -----
@api.post("/hr/employees")
async def hr_create_employee(data: EmployeeIn, user=Depends(require_admin_role)):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["email"] = (doc.get("email") or "").lower().strip()
    doc["created_at"] = now_iso()
    doc["portal_password_hash"] = None
    doc["portal_password_set"] = False
    await db.employees.insert_one(doc)
    out = {k: v for k, v in doc.items() if k not in ("_id", "portal_password_hash")}
    return out


@api.get("/hr/employees")
async def hr_list_employees(user=Depends(require_admin)):
    cur = db.employees.find({"deleted": {"$ne": True}}, {"_id": 0, "portal_password_hash": 0}).sort("name", 1)
    return [e async for e in cur]


@api.get("/hr/employees/{eid}")
async def hr_get_employee(eid: str, user=Depends(require_admin)):
    e = await db.employees.find_one({"id": eid}, {"_id": 0, "portal_password_hash": 0})
    if not e: raise HTTPException(404, "Colaborador não encontrado")
    return e


@api.put("/hr/employees/{eid}")
async def hr_update_employee(eid: str, data: EmployeeIn, user=Depends(require_admin_role)):
    patch = data.model_dump()
    patch["email"] = (patch.get("email") or "").lower().strip()
    patch["updated_at"] = now_iso()
    r = await db.employees.update_one({"id": eid}, {"$set": patch})
    if r.matched_count == 0: raise HTTPException(404, "Colaborador não encontrado")
    return {"ok": True}


@api.delete("/hr/employees/{eid}")
async def hr_delete_employee(eid: str, user=Depends(require_admin_role)):
    await db.employees.update_one({"id": eid}, {"$set": {"status": "inactive", "deleted": True, "email": "", "updated_at": now_iso()}})
    await db.shifts.delete_many({"employee_id": eid, "date": {"$gte": datetime.now(hr_rules.BR_TZ).date().isoformat()}})
    return {"ok": True}


@api.post("/hr/employees/{eid}/portal-password")
async def hr_set_portal_password(eid: str, data: EmployeePortalPasswordIn, user=Depends(require_admin_role)):
    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    r = await db.employees.update_one(
        {"id": eid},
        {"$set": {"portal_password_hash": hashed, "portal_password_set": True, "updated_at": now_iso()}},
    )
    if r.matched_count == 0: raise HTTPException(404, "Colaborador não encontrado")
    return {"ok": True}


@api.post("/hr/employees/{eid}/schedule/generate")
async def hr_generate_schedule(eid: str, month: str = Query(..., description="YYYY-MM"), user=Depends(require_admin_role)):
    emp = await db.employees.find_one({"id": eid}, {"_id": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    y, m, first, last = month_bounds(month)
    shifts = hr_rules.generate_shifts(emp, y, m, new_id)
    await db.shifts.delete_many({"employee_id": eid, "date": {"$gte": first, "$lte": last}})
    if shifts:
        await db.shifts.insert_many([{**s, "created_at": now_iso()} for s in shifts])
    await apply_vacations_to_shifts(eid, first, last)
    saved = [s async for s in db.shifts.find({"employee_id": eid, "date": {"$gte": first, "$lte": last}}, {"_id": 0})]
    return {"created": len(shifts), "violations": hr_rules.validate_schedule(saved, emp)}


@api.get("/hr/schedule")
async def hr_schedule(month: str = Query(..., description="YYYY-MM"),
                      employee_id: Optional[str] = None,
                      user=Depends(require_admin)):
    _, _, first, last = month_bounds(month)
    q: dict = {"date": {"$gte": first, "$lte": last}}
    if employee_id: q["employee_id"] = employee_id
    cur = db.shifts.find(q, {"_id": 0}).sort("date", 1)
    return [s async for s in cur]


@api.get("/hr/schedule/violations")
async def hr_schedule_violations(month: str = Query(...), employee_id: str = Query(...), user=Depends(require_admin)):
    _, _, first, last = month_bounds(month)
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    shifts = [s async for s in db.shifts.find({"employee_id": employee_id, "date": {"$gte": first, "$lte": last}}, {"_id": 0})]
    return hr_rules.validate_schedule(shifts, emp)


@api.put("/hr/shifts/{sid}")
async def hr_update_shift(sid: str, data: ShiftUpdateIn, user=Depends(require_admin_role)):
    patch = {k: v for k, v in data.model_dump().items() if v is not None}
    for k in ("start_time", "end_time"):
        if patch.get(k) and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", patch[k]):
            raise HTTPException(400, "Horário inválido (HH:MM)")
    if patch.get("is_rest") is False and not (patch.get("start_time") and patch.get("end_time")):
        cur = await db.shifts.find_one({"id": sid}, {"_id": 0})
        if not cur: raise HTTPException(404, "Turno não encontrado")
        emp = await db.employees.find_one({"id": cur["employee_id"]}, {"_id": 0}) or {}
        patch.setdefault("start_time", emp.get("default_shift_start") or "08:00")
        patch.setdefault("end_time", emp.get("default_shift_end") or "17:00")
        patch["is_vacation"] = False
        patch["is_dsr"] = False
    patch["source"] = "manual"
    patch["updated_at"] = now_iso()
    # If marked as rest, clear times; else require both times
    if patch.get("is_rest") is True:
        patch["start_time"] = None
        patch["end_time"] = None
        cur = await db.shifts.find_one({"id": sid}, {"_id": 0, "weekday": 1})
        patch["is_dsr"] = bool(cur and cur.get("weekday") == 6)
    r = await db.shifts.update_one({"id": sid}, {"$set": patch})
    if r.matched_count == 0: raise HTTPException(404, "Turno não encontrado")
    return {"ok": True}


@api.get("/hr/dashboard")
async def hr_dashboard(user=Depends(require_admin)):
    now_br = datetime.now(hr_rules.BR_TZ)
    today, now_hhmm = now_br.date().isoformat(), now_br.strftime("%H:%M")
    employees = {}
    async for e in db.employees.find({"status": "active"}, {"_id": 0, "portal_password_hash": 0}):
        employees[e["id"]] = e
    shifts_today = {s["employee_id"]: s async for s in db.shifts.find({"date": today}, {"_id": 0})}
    punches: dict = {}
    async for r in db.time_records.find({"date": today, "voided": {"$ne": True}}, {"_id": 0}).sort("ts", 1):
        punches.setdefault(r["employee_id"], []).append(r)
    working_now, on_break, resting, scheduled_today, late, off_today = [], [], [], [], [], []
    for eid, emp in employees.items():
        s = shifts_today.get(eid)
        recs = punches.get(eid, [])
        last = recs[-1]["type"] if recs else None
        item = {"employee": emp, "shift": s, "last_punch": recs[-1] if recs else None}
        if last in ("entrada", "fim_intervalo"):
            working_now.append(item)
        elif last == "inicio_intervalo":
            on_break.append(item)
        elif not s:
            off_today.append(emp)
        elif s.get("is_rest"):
            resting.append(item)
        elif not recs and s.get("start_time") and now_hhmm > (datetime.strptime(s["start_time"], "%H:%M") + timedelta(minutes=hr_rules.TOLERANCE_MIN)).strftime("%H:%M") and now_hhmm < (s.get("end_time") or "23:59"):
            late.append(item)
        else:
            scheduled_today.append(item)
    _, _, first, last_d = month_bounds(today[:7])
    alerts = []
    month_shifts: dict = {}
    async for s in db.shifts.find({"date": {"$gte": first, "$lte": last_d}}, {"_id": 0}):
        month_shifts.setdefault(s["employee_id"], []).append(s)
    all_vac: dict = {}
    async for v in db.vacations.find({}, {"_id": 0}):
        all_vac.setdefault(v["employee_id"], []).append(v)
    for eid, emp in employees.items():
        if eid not in month_shifts:
            alerts.append({"level": "info", "type": "escala", "employee_id": eid, "employee_name": emp["name"],
                           "message": f"Sem escala gerada para {today[:7]}."})
        else:
            for v in hr_rules.validate_schedule(month_shifts[eid], emp)[:3]:
                alerts.append({"level": "warning", "type": "escala", "employee_id": eid, "employee_name": emp["name"], "message": v["message"]})
        for p in hr_rules.vacation_periods(emp, all_vac.get(eid, []), now_br.date()):
            if p["status"] == "vencido":
                alerts.append({"level": "danger", "type": "ferias", "employee_id": eid, "employee_name": emp["name"],
                               "message": f"Férias VENCIDAS (aquisitivo {p['period_start']}) — saldo {p['balance']}d, pagamento em dobro (art. 137)."})
            elif p["status"] == "vencendo":
                alerts.append({"level": "warning", "type": "ferias", "employee_id": eid, "employee_name": emp["name"],
                               "message": f"Férias vencem em {p['concessive_end']} — saldo {p['balance']}d."})
    pending_vac = await db.vacations.count_documents({"status": "pending"})
    for x in late:
        alerts.append({"level": "warning", "type": "ponto", "employee_id": x["employee"]["id"], "employee_name": x["employee"]["name"],
                       "message": f"Sem registro de entrada (turno às {x['shift']['start_time']})."})
    return {
        "today": today, "now": now_hhmm,
        "working_now": working_now, "on_break": on_break, "resting_today": resting,
        "scheduled_today": scheduled_today, "late": late, "off_today": off_today,
        "alerts": alerts, "pending_vacations": pending_vac,
        "totals": {"employees": len(employees), "working_now": len(working_now), "on_break": len(on_break),
                   "resting_today": len(resting), "late": len(late), "off_today": len(off_today),
                   "pending_vacations": pending_vac},
    }


# ----- Employee portal routes -----
@api.post("/employee/auth/login")
async def employee_login(data: EmployeeLoginIn):
    email = (data.email or "").lower().strip()
    emp = await db.employees.find_one({"email": email, "status": "active"}, {"_id": 0})
    if not emp or not emp.get("portal_password_hash"):
        raise HTTPException(401, "Credenciais inválidas")
    try:
        if not bcrypt.checkpw(data.password.encode(), emp["portal_password_hash"].encode()):
            raise HTTPException(401, "Credenciais inválidas")
    except ValueError:
        raise HTTPException(401, "Credenciais inválidas")
    token = make_employee_jwt(emp["id"])
    emp.pop("portal_password_hash", None)
    return {"access_token": token, "token_type": "bearer", "employee": emp}


@api.get("/employee/me")
async def employee_me(emp=Depends(require_employee)):
    return emp


@api.get("/employee/schedule")
async def employee_schedule(month: str = Query(...), emp=Depends(require_employee)):
    _, _, first, last = month_bounds(month)
    cur = db.shifts.find({"employee_id": emp["id"], "date": {"$gte": first, "$lte": last}}, {"_id": 0}).sort("date", 1)
    return [s async for s in cur]


# ============================================================================
# HR MODULE — Fase 2: ponto eletrônico, férias, folha (prévia)
# ============================================================================

class PunchAdjustIn(BaseModel):
    employee_id: str
    date: str
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    type: str
    reason: str = Field(min_length=5)


class VoidIn(BaseModel):
    reason: str = Field(min_length=5)


class VacationIn(BaseModel):
    period_start: str
    start_date: str
    days: int
    sell_days: int = 0
    notes: Optional[str] = ""


class VacationHrIn(VacationIn):
    employee_id: str


class VacationDecisionIn(BaseModel):
    approve: bool
    notes: Optional[str] = ""


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")


async def next_nsr() -> int:
    doc = await db.counters.find_one_and_update({"_id": "time_record_nsr"}, {"$inc": {"value": 1}},
                                                upsert=True, return_document=True)
    return doc["value"]


async def create_time_record(emp: dict, ts: datetime, rtype: str, source: str, ip: str, ua: str, **extra) -> dict:
    nsr = await next_nsr()
    last = await db.time_records.find_one({}, {"_id": 0, "hash": 1}, sort=[("nsr", -1)])
    prev_hash = (last or {}).get("hash", "")
    ts_iso = ts.astimezone(timezone.utc).isoformat()
    local = ts.astimezone(hr_rules.BR_TZ)
    digest = hashlib.sha256(f"{prev_hash}|{nsr}|{emp['id']}|{emp.get('cpf', '')}|{ts_iso}|{rtype}".encode()).hexdigest()
    doc = {"id": new_id(), "nsr": nsr, "employee_id": emp["id"], "employee_name": emp["name"],
           "employee_cpf": emp.get("cpf", ""), "date": local.date().isoformat(), "time": local.strftime("%H:%M:%S"),
           "ts": ts_iso, "type": rtype, "source": source, "ip": ip, "user_agent": ua[:200],
           "hash": digest, "prev_hash": prev_hash, "voided": False, "created_at": now_iso(), **extra}
    await db.time_records.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def build_timesheet(emp: dict, month: str) -> dict:
    _, _, first, last = month_bounds(month)
    shifts = {s["date"]: s async for s in db.shifts.find({"employee_id": emp["id"], "date": {"$gte": first, "$lte": last}}, {"_id": 0})}
    recs: dict = {}
    async for r in db.time_records.find({"employee_id": emp["id"], "date": {"$gte": first, "$lte": last}}, {"_id": 0}).sort("ts", 1):
        recs.setdefault(r["date"], []).append(r)
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    days = []
    while d <= end:
        iso = d.isoformat()
        shift = shifts.get(iso) if iso >= (emp.get("hire_date") or "") else None
        day = hr_rules.compute_day(recs.get(iso, []), shift, iso)
        day["all_records"] = recs.get(iso, [])
        day["shift"] = shift
        days.append(day)
        d += timedelta(days=1)
    working_days = sum(1 for x in days if x["expected_min"] > 0)
    rest_days = sum(1 for x in days if x["is_rest"] and not x["is_vacation"]) + sum(1 for x in days if x["holiday"] and not x["is_rest"])
    return {"employee": emp, "month": month, "days": days, "summary": hr_rules.summarize_month(days),
            "working_days": working_days, "rest_days": rest_days}


def _fmt_min(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _pdf_doc(buf, title: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm, title=title)


def _pdf_table(rows, widths=None, header=True):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d6d3d1")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f4")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


# ----- Ponto: colaborador -----
@api.post("/employee/punch")
async def employee_punch(request: Request, emp=Depends(require_employee)):
    now = datetime.now(timezone.utc)
    today = now.astimezone(hr_rules.BR_TZ).date().isoformat()
    todays = [r async for r in db.time_records.find({"employee_id": emp["id"], "date": today, "voided": {"$ne": True}}, {"_id": 0}).sort("ts", 1)]
    if todays and (now - datetime.fromisoformat(todays[-1]["ts"])).total_seconds() < 60:
        raise HTTPException(429, "Aguarde 1 minuto entre marcações")
    if len(todays) >= 4:
        raise HTTPException(400, "Todas as marcações do dia já foram registradas. Procure o RH para ajustes.")
    rtype = hr_rules.PUNCH_SEQUENCE[len(todays)]
    rec = await create_time_record(emp, now, rtype, "portal", client_ip(request), request.headers.get("user-agent", ""))
    return {**rec, "label": hr_rules.PUNCH_LABELS[rtype]}


@api.get("/employee/punches/today")
async def employee_punches_today(emp=Depends(require_employee)):
    now_br = datetime.now(hr_rules.BR_TZ)
    today = now_br.date().isoformat()
    recs = [r async for r in db.time_records.find({"employee_id": emp["id"], "date": today, "voided": {"$ne": True}}, {"_id": 0}).sort("ts", 1)]
    nxt = hr_rules.PUNCH_SEQUENCE[len(recs)] if len(recs) < 4 else None
    return {"date": today, "server_time": now_br.strftime("%H:%M:%S"), "records": recs,
            "next_type": nxt, "next_label": hr_rules.PUNCH_LABELS.get(nxt) if nxt else None}


@api.get("/employee/timesheet")
async def employee_timesheet(month: str = Query(...), emp=Depends(require_employee)):
    return await build_timesheet(emp, month)


# ----- Ponto: RH -----
@api.get("/hr/timesheet")
async def hr_timesheet(employee_id: str = Query(...), month: str = Query(...), user=Depends(require_admin)):
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    return await build_timesheet(emp, month)


@api.post("/hr/time-records")
async def hr_adjust_punch(data: PunchAdjustIn, request: Request, user=Depends(require_admin_role)):
    if data.type not in hr_rules.PUNCH_SEQUENCE:
        raise HTTPException(400, "Tipo de marcação inválido")
    emp = await db.employees.find_one({"id": data.employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    try:
        ts = datetime.fromisoformat(f"{data.date}T{data.time}:00").replace(tzinfo=hr_rules.BR_TZ)
    except ValueError:
        raise HTTPException(400, "Data inválida")
    if ts > datetime.now(timezone.utc):
        raise HTTPException(400, "Não é possível incluir marcação futura")
    return await create_time_record(emp, ts, data.type, "ajuste_rh", client_ip(request), request.headers.get("user-agent", ""),
                                    adjusted_by=user.get("email"), reason=data.reason)


@api.post("/hr/time-records/{rid}/void")
async def hr_void_punch(rid: str, data: VoidIn, user=Depends(require_admin_role)):
    r = await db.time_records.update_one({"id": rid, "voided": {"$ne": True}}, {"$set": {
        "voided": True, "void_reason": data.reason, "voided_by": user.get("email"), "voided_at": now_iso()}})
    if r.matched_count == 0: raise HTTPException(404, "Marcação não encontrada")
    return {"ok": True}


@api.get("/hr/timesheet/pdf")
async def hr_timesheet_pdf(employee_id: str = Query(...), month: str = Query(...), user=Depends(require_admin)):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, Spacer
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    ts = await build_timesheet(emp, month)
    st = getSampleStyleSheet()
    wd = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    rows = [["Data", "Dia", "Marcações", "Previsto", "Trabalhado", "HE 50%", "HE 100%", "Noturno", "Obs."]]
    for d in ts["days"]:
        marks = " ".join(r["time"][:5] + ("*" if r["source"] != "portal" else "") for r in d["records"])
        obs = "Férias" if d["is_vacation"] else ("Folga" if d["is_rest"] else "")
        obs = ", ".join([x for x in [obs, d["holiday"] or ""] + d["flags"] if x])
        rows.append([d["date"][8:] + "/" + d["date"][5:7], wd[date.fromisoformat(d["date"]).weekday()], marks,
                     _fmt_min(d["expected_min"]), _fmt_min(d["worked_min"]), _fmt_min(d["extra50_min"]),
                     _fmt_min(d["extra100_min"]), _fmt_min(d["night_min"]), Paragraph(obs, st["BodyText"]) if obs else ""])
    s = ts["summary"]
    rows.append(["Total", "", "", _fmt_min(s["expected_min"]), _fmt_min(s["worked_min"]), _fmt_min(s["extra50_min"]),
                 _fmt_min(s["extra100_min"]), _fmt_min(s["night_min"]), f"Faltas: {s['absences']}"])
    buf = BytesIO()
    doc = _pdf_doc(buf, f"Espelho de ponto {month}")
    story = [Paragraph(f"<b>Espelho de Ponto — {month[5:]}/{month[:4]}</b>", st["Title"]),
             Paragraph(f"Empregador: Pousada Vale do Sol · Colaborador: <b>{escape(emp['name'])}</b> · CPF: {escape(emp.get('cpf') or '-')} · "
                       f"Cargo: {escape(emp.get('role_title') or '-')} · Admissão: {emp.get('hire_date')}", st["BodyText"]),
             Spacer(1, 6),
             _pdf_table(rows, [36, 26, 110, 40, 48, 40, 44, 40, 140]),
             Spacer(1, 8),
             Paragraph("* marcação incluída pelo RH (ajuste com justificativa registrada). Registros com NSR e hash encadeado "
                       "(Portaria MTP 671/2021). Tolerância de 10 min/dia (art. 58 §1º CLT).", st["BodyText"]),
             Spacer(1, 30),
             Paragraph("_______________________________ &nbsp;&nbsp;&nbsp;&nbsp; _______________________________", st["BodyText"]),
             Paragraph("Assinatura do colaborador &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Assinatura do empregador", st["BodyText"])]
    doc.build(story)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="espelho-ponto-{month}.pdf"'})


# ----- Férias -----
async def _vacation_context(emp: dict):
    vacs = [v async for v in db.vacations.find({"employee_id": emp["id"]}, {"_id": 0}).sort("start_date", -1)]
    today = datetime.now(hr_rules.BR_TZ).date()
    return vacs, hr_rules.vacation_periods(emp, vacs, today), today


async def _create_vacation(emp: dict, data: VacationIn, status_: str, by: str) -> dict:
    vacs, periods, today = await _vacation_context(emp)
    period = next((p for p in periods if p["period_start"] == data.period_start), None)
    if not period: raise HTTPException(400, "Período aquisitivo inválido")
    try:
        start = date.fromisoformat(data.start_date)
    except ValueError:
        raise HTTPException(400, "Data inválida")
    err = hr_rules.validate_vacation_request(period, start, data.days, data.sell_days, today)
    if err: raise HTTPException(400, err)
    end = start + timedelta(days=data.days - 1)
    overlap = await db.vacations.find_one({"employee_id": emp["id"], "status": {"$in": ["pending", "approved"]},
                                           "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()}})
    if overlap: raise HTTPException(400, "Já existe férias neste intervalo")
    doc = {"id": new_id(), "employee_id": emp["id"], "employee_name": emp["name"], "period_start": data.period_start,
           "start_date": start.isoformat(), "end_date": end.isoformat(), "days": data.days, "sell_days": data.sell_days,
           "status": status_, "requested_by": by, "notes": data.notes or "", "created_at": now_iso(),
           "notice_ok": (start - today).days >= 30}
    await db.vacations.insert_one(doc)
    doc.pop("_id", None)
    if status_ == "approved":
        await apply_vacations_to_shifts(emp["id"], doc["start_date"], doc["end_date"])
    return doc


@api.get("/employee/vacations")
async def employee_vacations(emp=Depends(require_employee)):
    vacs, periods, _ = await _vacation_context(emp)
    return {"periods": periods, "requests": vacs}


@api.post("/employee/vacations")
async def employee_request_vacation(data: VacationIn, emp=Depends(require_employee)):
    return await _create_vacation(emp, data, "pending", "employee")


@api.post("/employee/vacations/{vid}/cancel")
async def employee_cancel_vacation(vid: str, emp=Depends(require_employee)):
    r = await db.vacations.update_one({"id": vid, "employee_id": emp["id"], "status": "pending"},
                                      {"$set": {"status": "cancelled", "decided_at": now_iso()}})
    if r.matched_count == 0: raise HTTPException(404, "Pedido não encontrado ou já decidido")
    return {"ok": True}


@api.get("/hr/vacations")
async def hr_vacations(user=Depends(require_admin)):
    out = []
    async for emp in db.employees.find({"status": "active"}, {"_id": 0, "portal_password_hash": 0}).sort("name", 1):
        vacs, periods, _ = await _vacation_context(emp)
        out.append({"employee": emp, "periods": periods, "requests": vacs})
    return out


@api.post("/hr/vacations")
async def hr_create_vacation(data: VacationHrIn, user=Depends(require_admin_role)):
    emp = await db.employees.find_one({"id": data.employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    return await _create_vacation(emp, data, "approved", user.get("email") or "rh")


@api.post("/hr/vacations/{vid}/decision")
async def hr_decide_vacation(vid: str, data: VacationDecisionIn, user=Depends(require_admin_role)):
    v = await db.vacations.find_one({"id": vid, "status": "pending"}, {"_id": 0})
    if not v: raise HTTPException(404, "Pedido não encontrado ou já decidido")
    new_status = "approved" if data.approve else "rejected"
    await db.vacations.update_one({"id": vid}, {"$set": {"status": new_status, "decision_notes": data.notes or "",
                                                         "decided_by": user.get("email"), "decided_at": now_iso()}})
    if data.approve:
        await apply_vacations_to_shifts(v["employee_id"], v["start_date"], v["end_date"])
    return {"ok": True, "status": new_status}


# ----- Folha (prévia) -----
async def _payroll_for(emp: dict, month: str) -> dict:
    ts = await build_timesheet(emp, month)
    p = hr_rules.calc_payroll(emp, ts["summary"], ts["working_days"], ts["rest_days"], month)
    p["month"] = month
    return p


@api.get("/hr/payroll")
async def hr_payroll(month: str = Query(...), user=Depends(require_admin)):
    month_bounds(month)
    rows = [await _payroll_for(e, month) async for e in db.employees.find({"status": "active"}, {"_id": 0, "portal_password_hash": 0}).sort("name", 1)]
    totals = {k: round(sum(r[k] for r in rows), 2) for k in ("gross", "inss", "net", "fgts")}
    totals["irrf"] = round(sum(r["irrf"]["value"] for r in rows), 2)
    return {"month": month, "rows": rows, "totals": totals, "tables": hr_rules.TABLES_REF, "preview": True}


@api.get("/hr/payroll/pdf")
async def hr_payroll_pdf(employee_id: str = Query(...), month: str = Query(...), user=Depends(require_admin)):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, Spacer
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "portal_password_hash": 0})
    if not emp: raise HTTPException(404, "Colaborador não encontrado")
    p = await _payroll_for(emp, month)
    st = getSampleStyleSheet()
    brl = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    rows = [["Cód.", "Descrição", "Ref.", "Proventos", "Descontos"]]
    rows += [[e["code"], e["label"], e["ref"], brl(e["value"]), ""] for e in p["earnings"] if e["value"]]
    rows += [[d["code"], d["label"], d["ref"], "", brl(d["value"])] for d in p["deductions"] if d["value"]]
    tot_desc = sum(d["value"] for d in p["deductions"][2:])
    rows.append(["", "Totais", "", brl(p["gross"]), brl(tot_desc)])
    rows.append(["", "LÍQUIDO A RECEBER", "", "", brl(p["net"])])
    buf = BytesIO()
    doc = _pdf_doc(buf, f"Holerite prévia {month}")
    story = [Paragraph(f"<b>Demonstrativo de Pagamento — PRÉVIA — {month[5:]}/{month[:4]}</b>", st["Title"]),
             Paragraph(f"Pousada Vale do Sol · <b>{escape(emp['name'])}</b> · CPF {escape(emp.get('cpf') or '-')} · "
                       f"{escape(emp.get('role_title') or '-')} · Admissão {emp.get('hire_date')}", st["BodyText"]),
             Spacer(1, 8), _pdf_table(rows, [36, 220, 70, 80, 80]), Spacer(1, 8),
             _pdf_table([["Salário base", "Base INSS", "Base IRRF", "FGTS do mês (8%)", "Valor hora"],
                         [brl(p["base_salary"]), brl(p["gross"]), brl(p["irrf"]["base"]), brl(p["fgts"]), brl(p["hour_value"])]]),
             Spacer(1, 10),
             Paragraph(f"<b>PRÉVIA — documento sem valor fiscal.</b> Estimativa calculada a partir do ponto eletrônico. "
                       f"Tabelas: {p['tables']}. Não inclui férias, 13º, vale-transporte, benefícios ou convenção coletiva. "
                       f"Confira com sua contabilidade antes do pagamento.", st["BodyText"])]
    doc.build(story)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="holerite-previa-{month}.pdf"'})


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
