from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from core import db, now, audit
from auth import require_role

router = APIRouter(prefix="/admin")
admin = require_role("admin")


class Decision(BaseModel):
    action: str
    note: str = ""


@router.get("/overview")
async def overview(user=Depends(admin)):
    statuses = ["pending", "accepted", "completed", "declined", "cancelled"]
    commission = 0
    async for b in db.bookings.find({"status": "completed"}, {"commission": 1}):
        commission += b.get("commission", 0)
    return {
        "users": await db.users.count_documents({}),
        "customers": await db.users.count_documents({"role": {"$in": ["customer", None]}}),
        "photographers": await db.photographers.count_documents({}),
        "pending_verification": await db.photographers.count_documents({"listing_status": "pending"}),
        "bookings": {s: await db.bookings.count_documents({"status": s}) for s in statuses},
        "commission_demo": commission,
        "payouts_requested": await db.payouts.count_documents({"status": "requested"}),
    }


@router.get("/photographers")
async def photographers(status: str = "", user=Depends(admin)):
    q = {"listing_status": status} if status else {}
    return await db.photographers.find(q, {"_id": 0, "services": 0}).sort("name", 1).to_list(500)


@router.post("/photographers/{pid}/verify")
async def verify(pid: str, payload: Decision, user=Depends(admin)):
    updates = {"approve": {"listing_status": "approved", "verified": True}, "reject": {"listing_status": "rejected", "verified": False}, "unverify": {"verified": False}, "suspend": {"listing_status": "rejected"}}
    if payload.action not in updates:
        raise HTTPException(400, "Aksi tidak dikenal")
    res = await db.photographers.update_one({"photographer_id": pid}, {"$set": {**updates[payload.action], "reviewed_at": now()}})
    if not res.matched_count:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    await audit(user, f"photographer.{payload.action}", pid, payload.note)
    return await db.photographers.find_one({"photographer_id": pid}, {"_id": 0, "services": 0})


@router.get("/users")
async def users(user=Depends(admin)):
    return await db.users.find({}, {"_id": 0, "bank_account_encrypted": 0}).sort("created_at", -1).to_list(500)


@router.get("/payouts")
async def payouts(user=Depends(admin)):
    return await db.payouts.find({}, {"_id": 0, "bank_snapshot_encrypted": 0}).sort("created_at", -1).to_list(500)


@router.post("/payouts/{payout_id}")
async def decide_payout(payout_id: str, payload: Decision, user=Depends(admin)):
    status = {"approve": "approved", "reject": "rejected"}.get(payload.action)
    if not status:
        raise HTTPException(400, "Aksi tidak dikenal")
    res = await db.payouts.update_one({"payout_id": payout_id, "status": "requested"}, {"$set": {"status": status, "reviewed_at": now(), "note": payload.note}})
    if not res.matched_count:
        raise HTTPException(404, "Permintaan pencairan tidak ditemukan atau sudah diproses")
    await audit(user, f"payout.{status}", payout_id, payload.note)
    return {"ok": True, "status": status}


@router.get("/audit")
async def audit_logs(user=Depends(admin)):
    return await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
