import uuid
from datetime import date as Date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from auth import current_user
from core import COMMISSION_RATE, HIDDEN_LISTING, audit, db, new_id, now, public
from ledger import credit_completed_booking
from routers.availability import conflicts
from storage import DELIVERY_TYPES, load, save_upload

router = APIRouter()
TRANSITIONS = {
    "photographer": {"pending": ["accepted", "declined"], "accepted": ["cancelled"]},
    "customer": {"pending": ["cancelled"], "accepted": ["cancelled"], "delivered": ["completed", "revision_requested", "disputed"]},
    "admin": {"pending": ["cancelled"], "accepted": ["cancelled"], "disputed": ["completed", "cancelled"], "delivered": ["completed"]},
}


class BookingCreate(BaseModel):
    photographer_id: str
    service_id: str
    date: str
    time: str
    duration: int = Field(2, ge=1, le=12)
    location: str = Field(min_length=2, max_length=200)
    notes: str = Field("", max_length=1000)
    agree_policy: bool = False


class StatusUpdate(BaseModel):
    status: str
    note: str = Field("", max_length=500)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=1000)


@router.post("/bookings")
async def create_booking(payload: BookingCreate, user=Depends(current_user)):
    if user.get("role", "customer") != "customer":
        raise HTTPException(403, "Hanya customer yang dapat mengajukan booking")
    if not payload.agree_policy:
        raise HTTPException(400, "Setujui kebijakan pemesanan, pembatalan, dan penyerahan hasil terlebih dahulu")
    p = await db.photographers.find_one({"photographer_id": payload.photographer_id, "listing_status": {"$nin": HIDDEN_LISTING}}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    service = next((s for s in p.get("services", []) if s["service_id"] == payload.service_id), None)
    if not service:
        raise HTTPException(400, "Paket layanan tidak ditemukan")
    try:
        if Date.fromisoformat(payload.date) < Date.today():
            raise HTTPException(400, "Tanggal sesi tidak boleh di masa lalu")
    except ValueError:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD")
    if await conflicts(p["photographer_id"], payload.date, payload.time, payload.duration):
        raise HTTPException(409, "Jadwal fotografer sudah terisi pada waktu tersebut")
    dup = await db.bookings.find_one({"customer_id": user["user_id"], "photographer_id": p["photographer_id"], "date": payload.date, "time": payload.time, "status": "pending"}, {"_id": 1})
    if dup:
        raise HTTPException(409, "Kamu sudah mengajukan permintaan untuk jadwal ini")
    total = service["price"]
    commission = round(total * COMMISSION_RATE)
    booking = {
        "booking_id": f"JK-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": user["user_id"], "customer_name": user.get("name", ""), "photographer_id": p["photographer_id"], "photographer_name": p["name"], "photographer_slug": p["slug"],
        "service_id": service["service_id"], "service": service["title"], "category": p["category"], "date": payload.date, "time": payload.time, "duration": payload.duration,
        "location": payload.location, "notes": payload.notes, "total": total, "commission": commission, "photographer_earning": total - commission, "commission_rate": COMMISSION_RATE,
        "status": "pending", "payment_status": "demo_deferred", "policy_agreed_at": now(), "policy_version": "2026-10",
        "history": [{"status": "pending", "by": "customer", "note": "Permintaan dibuat", "at": now()}], "created_at": now(),
    }
    await db.bookings.insert_one(dict(booking))
    return public(booking)


def role_filter(user):
    role = user.get("role", "customer")
    if role == "photographer":
        return {"photographer_id": user.get("photographer_id", "-")}
    if role == "admin":
        return {}
    return {"customer_id": user["user_id"]}


async def load_booking(booking_id, user):
    b = await db.bookings.find_one({"booking_id": booking_id, **role_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    return b


async def set_status(b, status, user, note=""):
    role = user.get("role", "customer")
    entry = {"status": status, "by": role, "note": note, "at": now()}
    res = await db.bookings.update_one({"booking_id": b["booking_id"], "status": b["status"]}, {"$set": {"status": status, "updated_at": now()}, "$push": {"history": entry}})
    if not res.modified_count:
        raise HTTPException(409, "Status pesanan sudah berubah, muat ulang halaman")
    await audit(user, f"booking.{status}", b["booking_id"], note)
    if status == "completed":
        await credit_completed_booking(b)


@router.get("/bookings")
async def my_bookings(status: str = "", user=Depends(current_user)):
    q = role_filter(user)
    if status:
        q["status"] = status
    items = await db.bookings.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    ids = [b["booking_id"] for b in items]
    deliveries = {}
    async for d in db.deliveries.find({"booking_id": {"$in": ids}}, {"_id": 0, "files.storage_path": 0}).sort("created_at", 1):
        deliveries.setdefault(d["booking_id"], []).append(d)
    reviewed = {r["booking_id"] async for r in db.reviews.find({"booking_id": {"$in": ids}}, {"booking_id": 1})}
    for b in items:
        b["deliveries"] = deliveries.get(b["booking_id"], [])
        b["reviewed"] = b["booking_id"] in reviewed
    return items


@router.post("/bookings/{booking_id}/status")
async def update_status(booking_id: str, payload: StatusUpdate, user=Depends(current_user)):
    role = user.get("role", "customer")
    b = await load_booking(booking_id, user)
    if payload.status not in TRANSITIONS.get(role, {}).get(b["status"], []):
        raise HTTPException(400, f"Status tidak dapat diubah dari {b['status']} ke {payload.status}")
    if payload.status in ("revision_requested", "disputed") and len(payload.note.strip()) < 5:
        raise HTTPException(400, "Jelaskan alasan revisi atau keberatan (minimal 5 karakter)")
    if payload.status != "accepted":
        await set_status(b, payload.status, user, payload.note)
        return await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0})
    lock_id = f"{b['photographer_id']}:{b['date']}"
    try:
        await db.slot_locks.insert_one({"_id": lock_id, "at": now()})
    except DuplicateKeyError:
        raise HTTPException(409, "Jadwal sedang diproses, coba lagi sebentar")
    try:
        if await conflicts(b["photographer_id"], b["date"], b["time"], b["duration"], ignore_booking=booking_id):
            raise HTTPException(409, "Jadwal bentrok dengan pesanan atau blokir lain")
        await set_status(b, "accepted", user, payload.note)
    finally:
        await db.slot_locks.delete_one({"_id": lock_id})
    return await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0})


@router.post("/bookings/{booking_id}/deliver")
async def deliver(booking_id: str, note: str = Form(""), link: str = Form(""), files: list[UploadFile] = File(default=[]), user=Depends(current_user)):
    if user.get("role") != "photographer":
        raise HTTPException(403, "Hanya fotografer yang dapat menyerahkan hasil")
    b = await load_booking(booking_id, user)
    if b["status"] not in ("accepted", "revision_requested"):
        raise HTTPException(400, "Hasil hanya dapat diserahkan untuk pesanan yang dikonfirmasi atau diminta revisi")
    link = link.strip()
    if link and not link.startswith("https://"):
        raise HTTPException(400, "Tautan hasil harus diawali https://")
    if not files and not link:
        raise HTTPException(400, "Unggah file hasil atau sertakan tautan galeri")
    if len(files) > 10:
        raise HTTPException(400, "Maksimal 10 file per penyerahan")
    saved = []
    for f in files:
        meta = await save_upload(f, f"deliveries/{booking_id}", DELIVERY_TYPES, 25)
        saved.append({"file_id": new_id("file"), **meta})
    d = {"delivery_id": new_id("dlv"), "booking_id": booking_id, "note": note[:1000], "link": link, "files": saved, "created_at": now()}
    await db.deliveries.insert_one(dict(d))
    await set_status(b, "delivered", user, "Hasil diserahkan")
    return {"ok": True, "delivery_id": d["delivery_id"]}


@router.get("/bookings/{booking_id}/files/{file_id}")
async def download_file(booking_id: str, file_id: str, user=Depends(current_user)):
    await load_booking(booking_id, user)
    d = await db.deliveries.find_one({"booking_id": booking_id, "files.file_id": file_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "File tidak ditemukan")
    f = next(x for x in d["files"] if x["file_id"] == file_id)
    data = await load(f["storage_path"])
    return Response(content=data, media_type=f["content_type"], headers={"Content-Disposition": f'attachment; filename="{f["original_filename"] or file_id}"', "Cache-Control": "private, no-store"})


@router.post("/bookings/{booking_id}/review")
async def review(booking_id: str, payload: ReviewIn, user=Depends(current_user)):
    if user.get("role", "customer") != "customer":
        raise HTTPException(403, "Hanya customer yang dapat memberi ulasan")
    b = await load_booking(booking_id, user)
    if b["status"] != "completed":
        raise HTTPException(400, "Ulasan hanya untuk pesanan yang sudah selesai")
    if await db.reviews.find_one({"booking_id": booking_id}):
        raise HTTPException(409, "Pesanan ini sudah diulas")
    await db.reviews.insert_one({"review_id": new_id("rev"), "booking_id": booking_id, "photographer_id": b["photographer_id"], "customer_name": user.get("name", "Customer"), "rating": payload.rating, "comment": payload.comment.strip(), "service": b["service"], "created_at": now()})
    ratings = [r["rating"] async for r in db.reviews.find({"photographer_id": b["photographer_id"]}, {"rating": 1})]
    await db.photographers.update_one({"photographer_id": b["photographer_id"]}, {"$set": {"rating": round(sum(ratings) / len(ratings), 2), "reviews": len(ratings), "rating_source": "verified"}})
    return {"ok": True}
