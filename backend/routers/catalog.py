from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import re, uuid
from core import db, CATEGORIES, HIDDEN_LISTING, encrypt, now, public
from routers.availability import busy_slots, is_free

router = APIRouter()
VISIBLE = {"listing_status": {"$nin": HIDDEN_LISTING}}


class PhotographerRegistration(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    category: str
    bank_account: str = Field(min_length=8, max_length=30)
    location: str = "Makassar, Sulawesi Selatan"


@router.get("/")
async def root():
    return {"message": "Jasa Kamera API aktif", "categories": CATEGORIES}


@router.get("/categories")
async def categories():
    return [{"name": c, "slug": c.lower()} for c in CATEGORIES]


@router.get("/photographers")
async def list_photographers(category: Optional[str] = None, search: Optional[str] = None, sort: str = "relevan", min_price: int = 0, max_price: int = 100000000):
    query = {**VISIBLE, "starting_price": {"$gte": min_price, "$lte": max_price}}
    if category in CATEGORIES:
        query["category"] = category
    if search:
        s = re.escape(search)
        query["$or"] = [{"name": {"$regex": s, "$options": "i"}}, {"category": {"$regex": s, "$options": "i"}}]
    docs = await db.photographers.find(query, {"_id": 0}).to_list(200)
    if sort == "harga-rendah":
        docs.sort(key=lambda x: x["starting_price"])
    if sort == "rating":
        docs.sort(key=lambda x: x.get("rating") or 0, reverse=True)
    return docs


@router.get("/photographers/available")
async def available(date: str, time: str, duration: int = 2, category: Optional[str] = None, exclude: Optional[str] = None):
    query = dict(VISIBLE)
    if category in CATEGORIES:
        query["category"] = category
    docs = await db.photographers.find(query, {"_id": 0}).to_list(200)
    result = []
    for p in docs:
        if p["photographer_id"] != exclude and await is_free(p["photographer_id"], date, time, duration):
            result.append(p)
    return result[:6]


@router.get("/photographers/{slug}")
async def get_photographer(slug: str):
    doc = await db.photographers.find_one({"slug": slug, **VISIBLE}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    return doc


@router.get("/photographers/{slug}/availability")
async def photographer_availability(slug: str, month: str):
    doc = await db.photographers.find_one({"slug": slug, **VISIBLE}, {"_id": 0, "photographer_id": 1})
    if not doc:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    return await busy_slots(doc["photographer_id"], month)


@router.get("/services")
async def services(category: Optional[str] = None):
    docs = await db.photographers.find(VISIBLE, {"_id": 0}).to_list(200)
    result = []
    for p in docs:
        for s in p.get("services", []):
            if not category or s["category"] == category:
                result.append({**s, "photographer_name": p["name"], "photographer_slug": p["slug"], "image": (p.get("gallery") or [""])[0], "verified": p.get("verified", False)})
    return result


@router.post("/photographers/register")
async def register_photographer(payload: PhotographerRegistration):
    if payload.category not in CATEGORIES:
        raise HTTPException(400, "Pilih salah satu dari empat kategori yang tersedia")
    digits = re.sub(r"\D", "", payload.bank_account)
    if len(digits) < 8:
        raise HTTPException(400, "Nomor rekening minimal 8 digit angka")
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}, {"_id": 1}):
        raise HTTPException(409, "Email sudah terdaftar. Silakan masuk dengan Google.")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    pid = f"ph_{uuid.uuid4().hex[:8]}"
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") + "-" + pid[-4:]
    masked = "••••" + digits[-4:]
    await db.users.insert_one({"user_id": user_id, "email": email, "name": payload.name, "role": "photographer", "photographer_id": pid, "category": payload.category, "bank_account_encrypted": encrypt(digits), "bank_account_masked": masked, "created_at": now()})
    await db.photographers.insert_one({"photographer_id": pid, "user_id": user_id, "slug": slug, "name": payload.name, "username": "@" + slug.replace("-", ""), "category": payload.category, "location": payload.location, "bio": "Profil baru di Jasa Kamera.", "profile_image": "", "gallery": [], "verified": False, "demo": False, "listing_status": "pending", "rating": None, "reviews": 0, "starting_price": 0, "min_duration": 2, "service_area": "Makassar dan sekitarnya", "services": [], "created_at": now()})
    return public({"user_id": user_id, "photographer_id": pid, "name": payload.name, "category": payload.category, "bank_account_masked": masked, "verification_status": "pending"})
