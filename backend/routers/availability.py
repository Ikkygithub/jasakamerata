from fastapi import HTTPException
from datetime import date as Date, datetime, timezone
import re
from core import db

BLOCKING_STATUSES = ["accepted", "delivered", "revision_requested", "disputed", "completed"]


def to_minutes(t: str) -> int:
    try:
        h, m = (int(x) for x in t.split(":"))
    except Exception:
        raise HTTPException(400, "Format waktu harus JJ:MM")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise HTTPException(400, "Jam harus antara 00:00 dan 23:59")
    return h * 60 + m


def validate_month(month: str):
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(400, "Format bulan harus YYYY-MM")


def validate_date(d: str):
    try:
        Date.fromisoformat(d)
    except Exception:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD")


def overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


async def expire_overdue():
    cutoff = datetime.now(timezone.utc).isoformat()
    entry = {"status": "cancelled", "by": "system", "note": "Batas waktu pembayaran 24 jam terlewati", "at": cutoff}
    await db.bookings.update_many({"status": "accepted", "payment_status": {"$in": ["unpaid", "failed", "pending"]}, "payment_due_at": {"$lt": cutoff}}, {"$set": {"status": "cancelled", "payment_status": "expired"}, "$push": {"history": entry}})


async def conflicts(photographer_id, date, time, duration, ignore_booking=None):
    await expire_overdue()
    validate_date(date)
    start = to_minutes(time)
    end = start + duration * 60
    if end > 24 * 60:
        raise HTTPException(400, "Sesi tidak boleh melewati tengah malam")
    found = []
    q = {"photographer_id": photographer_id, "date": date, "status": {"$in": BLOCKING_STATUSES}}
    if ignore_booking:
        q["booking_id"] = {"$ne": ignore_booking}
    async for b in db.bookings.find(q, {"_id": 0}):
        bs = to_minutes(b["time"])
        if overlaps(start, end, bs, bs + b["duration"] * 60):
            found.append({"type": "booking", "start": b["time"], "duration": b["duration"]})
    async for blk in db.availability_blocks.find({"photographer_id": photographer_id, "date": date}, {"_id": 0}):
        if overlaps(start, end, to_minutes(blk["start"]), to_minutes(blk["end"])):
            found.append({"type": "block", "start": blk["start"], "end": blk["end"]})
    return found


async def is_free(photographer_id, date, time, duration):
    return not await conflicts(photographer_id, date, time, duration)


async def busy_slots(photographer_id, month: str):
    validate_month(month)
    slots = []
    async for b in db.bookings.find({"photographer_id": photographer_id, "date": {"$regex": f"^{month}"}, "status": {"$in": BLOCKING_STATUSES}}, {"_id": 0, "date": 1, "time": 1, "duration": 1}):
        end = to_minutes(b["time"]) + b["duration"] * 60
        slots.append({"date": b["date"], "start": b["time"], "end": f"{end // 60:02d}:{end % 60:02d}", "type": "booked"})
    async for blk in db.availability_blocks.find({"photographer_id": photographer_id, "date": {"$regex": f"^{month}"}}, {"_id": 0}):
        slots.append({"date": blk["date"], "start": blk["start"], "end": blk["end"], "type": "blocked"})
    return sorted(slots, key=lambda s: (s["date"], s["start"]))
