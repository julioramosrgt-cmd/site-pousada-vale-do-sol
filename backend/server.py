"""Pousada Management System - FastAPI backend.
Modules: Auth, Settings/Gallery, Rooms, Reservations (FNRH public + internal),
Financial ledger, iCal export/import, WhatsApp templates, file uploads.
"""
import os
import uuid
import logging
import hashlib
import hmac
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Annotated

import bcrypt
import jwt
import requests
from icalendar import Calendar, Event
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
    whatsapp: Optional[str] = ""
    pix_key: Optional[str] = ""
    pix_key_type: Optional[str] = ""  # cpf, cnpj, email, phone, random
    address: Optional[str] = ""
    checkin_time: Optional[str] = "14:00"
    checkout_time: Optional[str] = "11:00"
    cover_image: Optional[str] = ""
    instagram: Optional[str] = ""
    facebook: Optional[str] = ""
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
    min_stay: int = 1
    status: str = "available"  # available | maintenance
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
    estimated_arrival: Optional[str] = ""
    notes: Optional[str] = ""
    total_amount: float = 0.0
    deposit_amount: float = 0.0
    status: Optional[str] = "pending"
    source: Optional[str] = "direct"


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
    estimated_arrival: Optional[str] = ""
    notes: Optional[str] = ""
    accepted_terms: bool


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
async def admin_put_settings(data: SettingsIn, user=Depends(require_admin)):
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
async def gallery_add(data: GalleryIn, user=Depends(require_admin)):
    item = GalleryItem(**data.model_dump()).model_dump()
    item["is_deleted"] = False
    item["created_at"] = now_iso()
    await db.gallery.insert_one(item)
    return clean_doc(item)


@api.delete("/gallery/{item_id}")
async def gallery_delete(item_id: str, user=Depends(require_admin)):
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
async def rooms_create(data: RoomIn, user=Depends(require_admin)):
    room = Room(**data.model_dump()).model_dump()
    room["is_deleted"] = False
    await db.rooms.insert_one(room)
    return clean_doc(room)


@api.put("/rooms/{room_id}")
async def rooms_update(room_id: str, data: RoomIn, user=Depends(require_admin)):
    update = data.model_dump()
    update["updated_at"] = now_iso()
    result = await db.rooms.update_one({"id": room_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Quarto não encontrado")
    room = await db.rooms.find_one({"id": room_id}, {"_id": 0})
    return clean_doc(room)


@api.delete("/rooms/{room_id}")
async def rooms_delete(room_id: str, user=Depends(require_admin)):
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
    await db.reservations.insert_one(r)
    # Return only a confirmation, no sensitive listing
    return {"ok": True, "reservation_id": r["id"], "message": "Pré-reserva recebida. Aguarde contato para confirmação."}


# ----- Finance -----
@api.get("/finance")
async def finance_list(user=Depends(require_admin), from_date: Optional[str] = None, to_date: Optional[str] = None):
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
async def finance_create(data: FinanceIn, user=Depends(require_admin)):
    if data.kind not in {"income", "expense"}:
        raise HTTPException(400, "Tipo inválido")
    entry = FinanceEntry(**data.model_dump()).model_dump()
    entry["is_deleted"] = False
    await db.finance.insert_one(entry)
    return clean_doc(entry)


@api.delete("/finance/{entry_id}")
async def finance_delete(entry_id: str, user=Depends(require_admin)):
    await db.finance.update_one({"id": entry_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.get("/finance/summary")
async def finance_summary(user=Depends(require_admin), from_date: Optional[str] = None, to_date: Optional[str] = None):
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
async def ical_sources_add(data: ICalSourceIn, user=Depends(require_admin)):
    s = ICalImportSource(**data.model_dump()).model_dump()
    s["is_deleted"] = False
    await db.ical_sources.insert_one(s)
    return clean_doc(s)


@api.delete("/ical/sources/{source_id}")
async def ical_sources_delete(source_id: str, user=Depends(require_admin)):
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
