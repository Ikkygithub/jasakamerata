from fastapi import APIRouter, HTTPException, Response
from typing import Optional
import re
from core import db, CATEGORIES, HIDDEN_LISTING
from storage import load
from routers.availability import busy_slots, is_free, to_minutes

router = APIRouter()
VISIBLE = {"listing_status": {"$nin": HIDDEN_LISTING}}


@router.get("/")
async def root():
    return {"message": "Jasakamerata API aktif", "categories": CATEGORIES}


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
    docs = await db.photographers.find(query, {"_id": 0, "user_id": 0}).to_list(200)
    if sort == "harga-rendah":
        docs.sort(key=lambda x: x["starting_price"])
    if sort == "rating":
        docs.sort(key=lambda x: x.get("rating") or 0, reverse=True)
    return docs


@router.get("/photographers/featured")
async def featured():
    result = []
    for c in CATEGORIES:
        docs = await db.photographers.find({**VISIBLE, "category": c}, {"_id": 0}).sort([("verified", -1), ("rating", -1)]).to_list(2)
        result.extend(docs)
    return result


@router.get("/photographers/available")
async def available(date: str, time: str, duration: int = 2, category: Optional[str] = None, exclude: Optional[str] = None):
    query = dict(VISIBLE)
    if category in CATEGORIES:
        query["category"] = category
    docs = await db.photographers.find(query, {"_id": 0}).to_list(200)
    result = []
    to_minutes(time)
    for p in docs:
        if p["photographer_id"] != exclude and await is_free(p["photographer_id"], date, time, duration):
            result.append(p)
    return result[:6]


@router.get("/photographers/{slug}")
async def get_photographer(slug: str):
    doc = await db.photographers.find_one({"slug": slug, **VISIBLE}, {"_id": 0, "user_id": 0})
    if not doc:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    doc["portfolio"] = await db.portfolio_items.find({"photographer_id": doc["photographer_id"], "is_deleted": False}, {"_id": 0, "item_id": 1, "url": 1, "title": 1, "description": 1}).sort([("is_cover", -1), ("order", 1)]).to_list(100)
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


@router.get("/media/{item_id}")
async def media(item_id: str):
    it = await db.portfolio_items.find_one({"item_id": item_id, "is_deleted": False}, {"_id": 0})
    if not it or not it.get("storage_path"):
        raise HTTPException(404, "Foto tidak ditemukan")
    return Response(content=await load(it["storage_path"]), media_type=it["content_type"], headers={"Cache-Control": "public, max-age=86400"})


@router.get("/photographers/{slug}/reviews")
async def reviews(slug: str):
    p = await db.photographers.find_one({"slug": slug, **VISIBLE}, {"photographer_id": 1})
    if not p:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    return await db.reviews.find({"photographer_id": p["photographer_id"]}, {"_id": 0, "booking_id": 0}).sort("created_at", -1).to_list(50)
