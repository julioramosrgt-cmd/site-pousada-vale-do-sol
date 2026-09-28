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
from icalendar import Calendar, Event
from breeds import classify_breed, ALL_BREEDS
from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, Response, status
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
        is_holiday = d.isoformat() in holidays
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
