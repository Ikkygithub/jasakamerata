from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import date as Date
import uuid
from core import db, now, public, audit, COMMISSION_RATE, HIDDEN_LISTING
from auth import current_user
from routers.availability import conflicts

router = APIRouter()
TRANSITIONS = {
    "photographer": {"pending": ["accepted", "declined"], "accepted": ["completed", "cancelled"]},
    "customer": {"pending": ["cancelled"], "accepted": ["cancelled"]},
    "admin": {"pending": ["cancelled"], "accepted": ["cancelled", "completed"]},
}


class BookingCreate(BaseModel):
    photographer_id: str
    service_id: str
    date: str
    time: str
    duration: int = Field(2, ge=1, le=12)
    location: str = Field(min_length=2, max_length=200)
    notes: str = Field("", max_length=1000)


class StatusUpdate(BaseModel):
    status: str
    note: str = Field("", max_length=500)


@router.post("/bookings")
async def create_booking(payload: BookingCreate, user=Depends(current_user)):
    if user.get("role", "customer") != "customer":
        raise HTTPException(403, "Hanya customer yang dapat mengajukan booking")
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
    booking = {
        "booking_id": f"JK-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": user["user_id"], "customer_name": user.get("name", ""), "photographer_id": p["photographer_id"], "photographer_name": p["name"], "photographer_slug": p["slug"],
        "service_id": service["service_id"], "service": service["title"], "category": p["category"], "date": payload.date, "time": payload.time, "duration": payload.duration,
        "location": payload.location, "notes": payload.notes, "total": total, "commission": round(total * COMMISSION_RATE), "photographer_earning": total - round(total * COMMISSION_RATE),
        "status": "pending", "payment_status": "demo_deferred",
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


@router.get("/bookings")
async def my_bookings(status: str = "", user=Depends(current_user)):
    q = role_filter(user)
    if status:
        q["status"] = status
    return await db.bookings.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, user=Depends(current_user)):
    b = await db.bookings.find_one({"booking_id": booking_id, **role_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    return b


@router.post("/bookings/{booking_id}/status")
async def update_status(booking_id: str, payload: StatusUpdate, user=Depends(current_user)):
    role = user.get("role", "customer")
    b = await db.bookings.find_one({"booking_id": booking_id, **role_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    if payload.status not in TRANSITIONS.get(role, {}).get(b["status"], []):
        raise HTTPException(400, f"Status tidak dapat diubah dari {b['status']} ke {payload.status}")
    if payload.status == "accepted" and await conflicts(b["photographer_id"], b["date"], b["time"], b["duration"], ignore_booking=booking_id):
        raise HTTPException(409, "Jadwal bentrok dengan pesanan atau blokir lain")
    entry = {"status": payload.status, "by": role, "note": payload.note, "at": now()}
    await db.bookings.update_one({"booking_id": booking_id}, {"$set": {"status": payload.status, "updated_at": now()}, "$push": {"history": entry}})
    await audit(user, f"booking.{payload.status}", booking_id, payload.note)
    return await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0})
