from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core import db, new_id, now

MIN_PAYOUT = 100_000
MAX_PAYOUT = 10_000_000


async def post_entry(key, photographer_id, type_, amount, ref, note=""):
    """Insert an idempotent ledger entry; returns False when the key already exists."""
    try:
        await db.ledger.insert_one({"entry_id": new_id("led"), "key": key, "photographer_id": photographer_id, "type": type_, "amount": amount, "ref": ref, "note": note, "created_at": now()})
    except DuplicateKeyError:
        return False
    if photographer_id:
        await db.wallets.update_one({"photographer_id": photographer_id}, {"$inc": {"available": amount}}, upsert=True)
    return True


async def credit_completed_booking(b):
    await post_entry(f"earning:{b['booking_id']}", b["photographer_id"], "earning", b["photographer_earning"], b["booking_id"], "Pendapatan 95% pesanan selesai")
    await post_entry(f"commission:{b['booking_id']}", None, "platform_commission", b["commission"], b["booking_id"], "Komisi platform 5%")


async def reserve_payout(photographer_id, payout_id, amount):
    if not (MIN_PAYOUT <= amount <= MAX_PAYOUT):
        raise HTTPException(400, "Nominal penarikan harus Rp100.000 – Rp10.000.000")
    await db.wallets.update_one({"photographer_id": photographer_id}, {"$setOnInsert": {"available": 0}}, upsert=True)
    res = await db.wallets.update_one({"photographer_id": photographer_id, "available": {"$gte": amount}}, {"$inc": {"available": -amount}})
    if not res.modified_count:
        raise HTTPException(400, "Saldo yang dapat ditarik tidak mencukupi")
    try:
        await db.ledger.insert_one({"entry_id": new_id("led"), "key": f"reserve:{payout_id}", "photographer_id": photographer_id, "type": "payout_reserve", "amount": -amount, "ref": payout_id, "note": "Dana dicadangkan untuk penarikan", "created_at": now()})
    except DuplicateKeyError:
        await db.wallets.update_one({"photographer_id": photographer_id}, {"$inc": {"available": amount}})
        raise HTTPException(409, "Permintaan penarikan ganda")


async def release_payout(po, reason):
    await post_entry(f"release:{po['payout_id']}", po["photographer_id"], "payout_release", po["amount"], po["payout_id"], reason)


async def available_balance(photographer_id):
    w = await db.wallets.find_one({"photographer_id": photographer_id}, {"available": 1})
    return (w or {}).get("available", 0)


async def backfill():
    await db.ledger.create_index("key", unique=True)
    await db.wallets.create_index("photographer_id", unique=True)
    async for b in db.bookings.find({"status": "completed"}, {"_id": 0}):
        await credit_completed_booking(b)
    async for po in db.payouts.find({}, {"_id": 0}):
        res = await db.ledger.find_one({"key": f"reserve:{po['payout_id']}"})
        if not res:
            await post_entry(f"reserve:{po['payout_id']}", po["photographer_id"], "payout_reserve", -po["amount"], po["payout_id"], "Migrasi permintaan lama")
            if po["status"] in ("rejected", "failed"):
                await release_payout(po, "Migrasi: permintaan lama ditolak")
