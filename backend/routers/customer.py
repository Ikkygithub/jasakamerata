from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from core import db, now, new_id, HIDDEN_LISTING
from auth import current_user

router = APIRouter()
VISIBLE = {"listing_status": {"$nin": HIDDEN_LISTING}}


class FavoriteCreate(BaseModel):
    photographer_id: str


@router.get("/favorites")
async def list_favorites(user=Depends(current_user)):
    favs = await db.favorites.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    ids = [f["photographer_id"] for f in favs]
    people = {p["photographer_id"]: p for p in await db.photographers.find({"photographer_id": {"$in": ids}, **VISIBLE}, {"_id": 0}).to_list(200)}
    return [people[i] for i in ids if i in people]


@router.post("/favorites")
async def add_favorite(payload: FavoriteCreate, user=Depends(current_user)):
    p = await db.photographers.find_one({"photographer_id": payload.photographer_id, **VISIBLE}, {"_id": 0, "photographer_id": 1})
    if not p:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    await db.favorites.update_one({"user_id": user["user_id"], "photographer_id": payload.photographer_id}, {"$setOnInsert": {"favorite_id": new_id("fav"), "created_at": now()}}, upsert=True)
    return {"ok": True, "photographer_id": payload.photographer_id}


@router.delete("/favorites/{photographer_id}")
async def remove_favorite(photographer_id: str, user=Depends(current_user)):
    await db.favorites.delete_one({"user_id": user["user_id"], "photographer_id": photographer_id})
    return {"ok": True}


@router.get("/dashboard/summary")
async def dashboard(user=Depends(current_user)):
    bookings = await db.bookings.find({"customer_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5)
    active = await db.bookings.count_documents({"customer_id": user["user_id"], "status": {"$in": ["pending", "accepted"]}})
    favs = await db.favorites.count_documents({"user_id": user["user_id"]})
    unread = 0
    async for c in db.conversations.find({"customer_id": user["user_id"]}, {"unread_customer": 1}):
        unread += c.get("unread_customer", 0)
    return {"bookings": bookings, "active_bookings": active, "favorites": favs, "unread": unread}
