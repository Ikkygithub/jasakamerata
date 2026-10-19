from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from core import db, now, new_id, public, encrypt, audit, CATEGORIES
from auth import require_role
from routers.availability import to_minutes, validate_date

router = APIRouter(prefix="/photographer")
me = require_role("photographer")


class ProfileUpdate(BaseModel):
    bio: Optional[str] = Field(None, max_length=1000)
    service_area: Optional[str] = Field(None, max_length=200)
    profile_image: Optional[str] = Field(None, max_length=500)
    min_duration: Optional[int] = Field(None, ge=1, le=12)


class ServiceIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    price: int = Field(ge=50000, le=100000000)
    duration: str = Field(min_length=1, max_length=50)
    deliverables: str = Field(min_length=1, max_length=200)
    turnaround: str = Field("7 hari kerja", max_length=50)
    pricing_type: str = "per paket"


class GalleryIn(BaseModel):
    url: str = Field(min_length=10, max_length=500)


class BlockIn(BaseModel):
    date: str
    start: str = "00:00"
    end: str = "23:59"
    reason: str = Field("", max_length=200)


class PayoutIn(BaseModel):
    amount: int = Field(ge=50000)


async def profile_of(user):
    p = await db.photographers.find_one({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Profil fotografer belum terhubung")
    return p


async def wallet_of(user):
    pid = user.get("photographer_id", "-")
    earned = 0
    async for b in db.bookings.find({"photographer_id": pid, "status": "completed"}, {"photographer_earning": 1}):
        earned += b.get("photographer_earning", 0)
    pending = 0
    async for b in db.bookings.find({"photographer_id": pid, "status": "accepted"}, {"photographer_earning": 1}):
        pending += b.get("photographer_earning", 0)
    requested = 0
    async for po in db.payouts.find({"photographer_id": pid, "status": {"$in": ["requested", "approved"]}}, {"amount": 1}):
        requested += po["amount"]
    return {"earned": earned, "pending": pending, "withdrawn_or_requested": requested, "available": max(earned - requested, 0), "bank_account_masked": user.get("bank_account_masked", "Belum diatur"), "note": "DEMO — saldo tercatat, belum ada transfer dana nyata."}


async def recalc_price(pid):
    p = await db.photographers.find_one({"photographer_id": pid}, {"services": 1})
    prices = [s["price"] for s in p.get("services", [])]
    await db.photographers.update_one({"photographer_id": pid}, {"$set": {"starting_price": min(prices) if prices else 0}})


@router.get("/me")
async def overview(user=Depends(me)):
    p = await profile_of(user)
    pid = p["photographer_id"]
    counts = {s: await db.bookings.count_documents({"photographer_id": pid, "status": s}) for s in ["pending", "accepted", "completed", "declined", "cancelled"]}
    unread = 0
    async for c in db.conversations.find({"photographer_id": pid}, {"unread_photographer": 1}):
        unread += c.get("unread_photographer", 0)
    return {"profile": p, "counts": counts, "unread": unread, "wallet": await wallet_of(user)}


@router.put("/profile")
async def update_profile(payload: ProfileUpdate, user=Depends(me)):
    p = await profile_of(user)
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if data:
        await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$set": data})
    return await profile_of(user)


@router.post("/services")
async def add_service(payload: ServiceIn, user=Depends(me)):
    p = await profile_of(user)
    svc = {"service_id": new_id("svc"), "category": p["category"], **payload.model_dump()}
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$push": {"services": svc}})
    await recalc_price(p["photographer_id"])
    return svc


@router.put("/services/{service_id}")
async def edit_service(service_id: str, payload: ServiceIn, user=Depends(me)):
    p = await profile_of(user)
    if not any(s["service_id"] == service_id for s in p.get("services", [])):
        raise HTTPException(404, "Layanan tidak ditemukan")
    sets = {f"services.$.{k}": v for k, v in payload.model_dump().items()}
    await db.photographers.update_one({"photographer_id": p["photographer_id"], "services.service_id": service_id}, {"$set": sets})
    await recalc_price(p["photographer_id"])
    return {"ok": True}


@router.delete("/services/{service_id}")
async def delete_service(service_id: str, user=Depends(me)):
    p = await profile_of(user)
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$pull": {"services": {"service_id": service_id}}})
    await recalc_price(p["photographer_id"])
    return {"ok": True}


@router.post("/gallery")
async def add_gallery(payload: GalleryIn, user=Depends(me)):
    if not payload.url.startswith("https://"):
        raise HTTPException(400, "URL gambar harus diawali https://")
    p = await profile_of(user)
    if len(p.get("gallery", [])) >= 20:
        raise HTTPException(400, "Maksimal 20 foto portofolio")
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$push": {"gallery": payload.url}})
    return (await profile_of(user))["gallery"]


@router.delete("/gallery/{index}")
async def remove_gallery(index: int, user=Depends(me)):
    p = await profile_of(user)
    gallery = p.get("gallery", [])
    if index < 0 or index >= len(gallery):
        raise HTTPException(404, "Foto tidak ditemukan")
    gallery.pop(index)
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$set": {"gallery": gallery}})
    return gallery


@router.get("/availability")
async def list_blocks(user=Depends(me)):
    return await db.availability_blocks.find({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0}).sort("date", 1).to_list(500)


@router.post("/availability")
async def add_block(payload: BlockIn, user=Depends(me)):
    validate_date(payload.date)
    if to_minutes(payload.start) >= to_minutes(payload.end):
        raise HTTPException(400, "Jam selesai harus setelah jam mulai")
    blk = {"block_id": new_id("blk"), "photographer_id": user["photographer_id"], **payload.model_dump(), "created_at": now()}
    await db.availability_blocks.insert_one(dict(blk))
    return blk


@router.delete("/availability/{block_id}")
async def delete_block(block_id: str, user=Depends(me)):
    res = await db.availability_blocks.delete_one({"block_id": block_id, "photographer_id": user.get("photographer_id", "-")})
    if not res.deleted_count:
        raise HTTPException(404, "Blokir jadwal tidak ditemukan")
    return {"ok": True}


@router.get("/payouts")
async def list_payouts(user=Depends(me)):
    return await db.payouts.find({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0, "bank_snapshot_encrypted": 0}).sort("created_at", -1).to_list(100)


@router.post("/payouts")
async def request_payout(payload: PayoutIn, user=Depends(me)):
    wallet = await wallet_of(user)
    if payload.amount > wallet["available"]:
        raise HTTPException(400, "Jumlah melebihi saldo yang dapat dicairkan")
    full = await db.users.find_one({"user_id": user["user_id"]}, {"bank_account_encrypted": 1})
    if not full or not full.get("bank_account_encrypted"):
        raise HTTPException(400, "Rekening belum terdaftar")
    po = {"payout_id": new_id("po"), "photographer_id": user["photographer_id"], "photographer_name": user.get("name", ""), "amount": payload.amount, "bank_account_masked": user.get("bank_account_masked"), "bank_snapshot_encrypted": full["bank_account_encrypted"], "status": "requested", "demo": True, "created_at": now()}
    await db.payouts.insert_one(dict(po))
    await audit(user, "payout.requested", po["payout_id"], str(payload.amount))
    return public(po)
