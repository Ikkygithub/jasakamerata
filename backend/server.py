from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import os, uuid, hashlib, base64, logging, requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Jasa Kamera API")
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)

_key = base64.urlsafe_b64encode(hashlib.sha256(mongo_url.encode()).digest())
cipher = Fernet(_key)
CATEGORIES = ["Wedding", "Commercial", "Event", "Graduation"]
IMAGES = [
    "https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1531058020387-3be344556be6?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1523580846011-d3a5bc25702b?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1511578314322-379afb476865?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1520857014576-2c4f4c972b57?q=80&w=1200&auto=format&fit=crop",
]
NAMES = ["Naya Visuals", "Ruang Rona", "Karsa Studio", "Arunika Photo", "Sora Works", "Lensa Selatan", "Mata Makassar", "Pijar Studio", "Kita Frame", "Bumi Visual", "Kanvas Event", "Siluet Co."]

def public(doc):
    if not doc: return None
    doc = {k: v for k, v in doc.items() if k != "_id" and k not in {"bank_account_encrypted"}}
    return doc

def photographer(i, name, category):
    slug = name.lower().replace(" ", "-")
    gallery = [IMAGES[(i + j) % len(IMAGES)] for j in range(4)]
    return {"photographer_id": f"ph_{i:02d}", "slug": slug, "name": name, "username": "@" + slug.replace("-", ""), "category": category, "location": "Makassar, Sulawesi Selatan", "bio": "Fotografer freelance Makassar yang mengubah momen penting menjadi cerita visual yang hangat dan jujur.", "profile_image": gallery[1], "gallery": gallery, "verified": i % 4 != 0, "demo": True, "rating": 4.8 + (i % 3) / 10, "reviews": i % 5 + 2, "starting_price": [650000, 850000, 500000, 350000][i % 4], "min_duration": 2, "service_area": "Makassar dan sekitarnya", "availability": "Tersedia untuk tanggal pilihan", "services": [{"service_id": f"svc_{i}1", "title": ["Cerita Pernikahan Intim", "Katalog Brand & Produk", "Dokumentasi Event", "Sesi Wisuda Personal"][CATEGORIES.index(category)], "category": category, "price": [650000, 850000, 500000, 350000][i % 4], "pricing_type": "per paket", "duration": "2–4 jam", "deliverables": "80 foto edit berkualitas tinggi", "turnaround": "7 hari kerja"}, {"service_id": f"svc_{i}2", "title": "Paket Lengkap " + category, "category": category, "price": [1250000, 1500000, 950000, 650000][i % 4], "pricing_type": "per paket", "duration": "6 jam", "deliverables": "250 foto edit + galeri online", "turnaround": "10 hari kerja"}]}

@app.on_event("startup")
async def seed_data():
    if await db.photographers.count_documents({}) < 12:
        await db.photographers.delete_many({})
        await db.photographers.insert_many([photographer(i + 1, n, CATEGORIES[i % 4]) for i, n in enumerate(NAMES)])

class OAuthSession(BaseModel):
    session_id: str

class PhotographerRegistration(BaseModel):
    name: str = Field(min_length=2)
    email: str
    category: str
    bank_account: str = Field(min_length=8)
    location: str = "Makassar, Sulawesi Selatan"

class MessageCreate(BaseModel):
    photographer_id: str
    text: str = Field(min_length=1, max_length=2000)

class BookingCreate(BaseModel):
    photographer_id: str
    service_id: str
    date: str
    time: str
    duration: int = 2
    location: str
    notes: str = ""

class FavoriteCreate(BaseModel):
    photographer_id: str

@api.get("/")
async def root(): return {"message": "Jasa Kamera API aktif", "categories": CATEGORIES}

@api.get("/categories")
async def categories(): return [{"name": c, "slug": c.lower()} for c in CATEGORIES]

@api.get("/photographers")
async def list_photographers(category: Optional[str] = None, search: Optional[str] = None, sort: str = "relevan", min_price: int = 0, max_price: int = 10000000):
    query = {"starting_price": {"$gte": min_price, "$lte": max_price}}
    if category and category in CATEGORIES: query["category"] = category
    if search: query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"category": {"$regex": search, "$options": "i"}}]
    docs = await db.photographers.find(query, {"_id": 0}).to_list(100)
    if sort == "harga-rendah": docs.sort(key=lambda x: x["starting_price"])
    if sort == "rating": docs.sort(key=lambda x: x["rating"], reverse=True)
    return docs

@api.get("/photographers/{slug}")
async def get_photographer(slug: str):
    doc = await db.photographers.find_one({"slug": slug}, {"_id": 0})
    if not doc: raise HTTPException(404, "Fotografer tidak ditemukan")
    return doc

@api.get("/services")
async def services(category: Optional[str] = None):
    docs = await db.photographers.find({}, {"_id": 0}).to_list(100)
    result = []
    for p in docs:
        for s in p["services"]:
            if not category or s["category"] == category: result.append({**s, "photographer_name": p["name"], "photographer_slug": p["slug"], "image": p["gallery"][0], "verified": p["verified"]})
    return result

@api.post("/photographers/register")
async def register_photographer(payload: PhotographerRegistration):
    if payload.category not in CATEGORIES: raise HTTPException(400, "Pilih salah satu dari empat kategori yang tersedia")
    account = cipher.encrypt(payload.bank_account.encode()).decode()
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {"user_id": user_id, "email": payload.email, "name": payload.name, "role": "photographer", "category": payload.category, "location": payload.location, "bank_account_encrypted": account, "bank_account_masked": "Rekening terenkripsi ••••" + payload.bank_account[-4:], "verification_status": "pending", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(doc)
    return {"user_id": user_id, "name": payload.name, "category": payload.category, "bank_account_masked": doc["bank_account_masked"], "verification_status": "pending"}

@api.post("/auth/session")
async def auth_session(payload: OAuthSession, response: Response):
    try:
        result = requests.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": payload.session_id}, timeout=10)
        data = result.json()
    except Exception as exc: raise HTTPException(401, f"Sesi Google tidak dapat diverifikasi: {exc}")
    user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if not user:
        user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": data["email"], "name": data.get("name", "Pengguna Jasa Kamera"), "picture": data.get("picture", ""), "role": "customer", "created_at": datetime.now(timezone.utc).isoformat()}
        await db.users.insert_one(user)
    token = data["session_token"]
    await db.user_sessions.update_many({"user_id": user["user_id"]}, {"$set": {"expired": True}})
    await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token, "expires_at": datetime.now(timezone.utc) + timedelta(days=7)})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return public(user)

async def current_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(401, "Silakan masuk terlebih dahulu")
    session = await db.user_sessions.find_one({"session_token": token, "expired": {"$ne": True}}, {"_id": 0})
    if not session: raise HTTPException(401, "Sesi berakhir")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user: raise HTTPException(401, "Pengguna tidak ditemukan")
    return user

@api.get("/auth/me")
async def auth_me(request: Request): return public(await current_user(request))

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token: await db.user_sessions.update_many({"session_token": token}, {"$set": {"expired": True}})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

@api.post("/chat/messages")
async def send_message(payload: MessageCreate, request: Request):
    user = await current_user(request)
    msg = {"message_id": f"msg_{uuid.uuid4().hex[:10]}", "sender_id": user["user_id"], "photographer_id": payload.photographer_id, "text": payload.text, "created_at": datetime.now(timezone.utc).isoformat(), "status": "sent"}
    await db.messages.insert_one(msg)
    return public(msg)

@api.post("/favorites")
async def add_favorite(payload: FavoriteCreate, request: Request):
    user = await current_user(request)
    p = await db.photographers.find_one({"photographer_id": payload.photographer_id}, {"_id": 0, "photographer_id": 1, "name": 1, "slug": 1})
    if not p: raise HTTPException(404, "Fotografer tidak ditemukan")
    favorite = {"favorite_id": f"fav_{uuid.uuid4().hex[:10]}", "user_id": user["user_id"], **p, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.favorites.update_one({"user_id": user["user_id"], "photographer_id": payload.photographer_id}, {"$set": favorite}, upsert=True)
    return public(favorite)

@api.delete("/favorites/{photographer_id}")
async def remove_favorite(photographer_id: str, request: Request):
    user = await current_user(request)
    await db.favorites.delete_one({"user_id": user["user_id"], "photographer_id": photographer_id})
    return {"ok": True}

@api.get("/chat/messages/{photographer_id}")
async def messages(photographer_id: str, request: Request):
    user = await current_user(request)
    return await db.messages.find({"$or": [{"sender_id": user["user_id"], "photographer_id": photographer_id}, {"sender_id": photographer_id, "photographer_id": user["user_id"]}]}, {"_id": 0}).sort("created_at", 1).to_list(100)

@api.post("/bookings")
async def create_booking(payload: BookingCreate, request: Request):
    user = await current_user(request)
    p = await db.photographers.find_one({"photographer_id": payload.photographer_id}, {"_id": 0})
    if not p: raise HTTPException(404, "Fotografer tidak ditemukan")
    service = next((s for s in p["services"] if s["service_id"] == payload.service_id), p["services"][0])
    booking = {"booking_id": f"JK-{uuid.uuid4().hex[:8].upper()}", "customer_id": user["user_id"], "photographer_id": p["photographer_id"], "photographer_name": p["name"], "service": service["title"], "date": payload.date, "time": payload.time, "duration": payload.duration, "location": payload.location, "notes": payload.notes, "total": service["price"], "commission": round(service["price"] * .1), "status": "pending", "payment_status": "deferred", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.bookings.insert_one(booking)
    return public(booking)

@api.get("/dashboard/summary")
async def dashboard(request: Request):
    user = await current_user(request)
    bookings = await db.bookings.find({"customer_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"user": public(user), "bookings": bookings, "wallet": {"recorded_balance": 0, "withdrawable": 0, "note": "Saldo demo tercatat; belum merupakan transfer dana."}}

app.include_router(api)
origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[] if "*" in origins else origins, allow_origin_regex=".*" if "*" in origins else None, allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown(): client.close()