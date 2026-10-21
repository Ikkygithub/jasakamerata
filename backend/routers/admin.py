from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from auth import require_role
from core import audit, cipher, db, now
from ledger import release_payout
from storage import load

router = APIRouter(prefix="/admin")
admin = require_role("admin")
PAYOUT_FLOW = {"requested": {"approve": "approved", "reject": "rejected"}, "approved": {"process": "processing", "reject": "rejected"}, "processing": {"success": "success", "fail": "failed"}}


class Decision(BaseModel):
    action: str
    note: str = Field("", max_length=500)
    reference: str = Field("", max_length=120)


@router.get("/overview")
async def overview(user=Depends(admin)):
    statuses = ["pending", "accepted", "delivered", "revision_requested", "disputed", "completed", "declined", "cancelled"]
    commission = 0
    async for e in db.ledger.find({"type": "platform_commission"}, {"amount": 1}):
        commission += e["amount"]
    gmv = 0
    async for b in db.bookings.find({"status": "completed"}, {"total": 1}):
        gmv += b.get("total", 0)
    return {
        "users": await db.users.count_documents({}),
        "photographers": await db.photographers.count_documents({}),
        "verified": await db.photographers.count_documents({"verified": True}),
        "pending_listing": await db.photographers.count_documents({"listing_status": "pending"}),
        "pending_verification": await db.verifications.count_documents({"status": "pending"}),
        "bookings": {s: await db.bookings.count_documents({"status": s}) for s in statuses},
        "completed_value": gmv,
        "commission": commission,
        "payouts_open": await db.payouts.count_documents({"status": {"$in": ["requested", "approved", "processing"]}}),
    }


@router.get("/photographers")
async def photographers(status: str = "", user=Depends(admin)):
    q = {"listing_status": status} if status else {}
    return await db.photographers.find(q, {"_id": 0, "services": 0}).sort("name", 1).to_list(500)


@router.post("/photographers/{pid}/listing")
async def listing(pid: str, payload: Decision, user=Depends(admin)):
    status = {"publish": "approved", "unpublish": "rejected"}.get(payload.action)
    if not status:
        raise HTTPException(400, "Aksi tidak dikenal")
    res = await db.photographers.update_one({"photographer_id": pid}, {"$set": {"listing_status": status, "listing_note": payload.note, "reviewed_at": now()}})
    if not res.matched_count:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    await audit(user, f"listing.{payload.action}", pid, payload.note)
    return {"ok": True}


@router.get("/verifications")
async def verifications(status: str = "pending", user=Depends(admin)):
    q = {"status": status} if status else {}
    return await db.verifications.find(q, {"_id": 0, "documents.storage_path": 0}).sort("created_at", -1).to_list(200)


@router.get("/verifications/{sid}/documents/{doc_id}")
async def verification_doc(sid: str, doc_id: str, user=Depends(admin)):
    v = await db.verifications.find_one({"submission_id": sid}, {"_id": 0})
    doc = next((d for d in (v or {}).get("documents", []) if d["doc_id"] == doc_id), None)
    if not doc:
        raise HTTPException(404, "Dokumen tidak ditemukan")
    await audit(user, "verification.document_viewed", sid, doc["kind"])
    return Response(content=await load(doc["storage_path"]), media_type=doc["content_type"], headers={"Cache-Control": "private, no-store"})


@router.post("/verifications/{sid}")
async def decide_verification(sid: str, payload: Decision, user=Depends(admin)):
    status = {"approve": "approved", "needs_fix": "needs_fix", "reject": "rejected"}.get(payload.action)
    if not status:
        raise HTTPException(400, "Aksi tidak dikenal")
    if status != "approved" and len(payload.note.strip()) < 5:
        raise HTTPException(400, "Tuliskan alasan keputusan")
    v = await db.verifications.find_one_and_update({"submission_id": sid, "status": "pending"}, {"$set": {"status": status, "note": payload.note, "decided_by": user["user_id"], "decided_at": now()}})
    if not v:
        raise HTTPException(404, "Pengajuan tidak ditemukan atau sudah diputuskan")
    sets = {"verification": {"status": status, "note": payload.note, "submission_id": sid, "decided_at": now()}, "verified": status == "approved"}
    if status == "approved":
        sets["listing_status"] = "approved"
    await db.photographers.update_one({"photographer_id": v["photographer_id"]}, {"$set": sets})
    await audit(user, f"verification.{status}", sid, payload.note)
    return {"ok": True, "status": status}


@router.get("/users")
async def users(user=Depends(admin)):
    return await db.users.find({}, {"_id": 0, "bank_account_encrypted": 0, "bank.number_encrypted": 0}).sort("created_at", -1).to_list(500)


@router.get("/ledger")
async def ledger(user=Depends(admin)):
    items = await db.ledger.find({}, {"_id": 0, "key": 0}).sort("created_at", -1).to_list(300)
    names = {p["photographer_id"]: p["name"] async for p in db.photographers.find({}, {"photographer_id": 1, "name": 1})}
    for e in items:
        e["photographer_name"] = names.get(e["photographer_id"], "Platform" if not e["photographer_id"] else e["photographer_id"])
    return items


@router.get("/payouts")
async def payouts(user=Depends(admin)):
    return await db.payouts.find({}, {"_id": 0, "bank_snapshot_encrypted": 0}).sort("created_at", -1).to_list(500)


@router.get("/payouts/{payout_id}/account")
async def payout_account(payout_id: str, user=Depends(admin)):
    po = await db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})
    if not po or po["status"] not in ("approved", "processing"):
        raise HTTPException(404, "Nomor rekening hanya dapat dilihat untuk penarikan yang disetujui")
    await audit(user, "payout.account_viewed", payout_id)
    return {"bank_name": po.get("bank_name"), "holder_name": po.get("holder_name"), "account_number": cipher.decrypt(po["bank_snapshot_encrypted"].encode()).decode()}


@router.post("/payouts/{payout_id}")
async def decide_payout(payout_id: str, payload: Decision, user=Depends(admin)):
    po = await db.payouts.find_one({"payout_id": payout_id}, {"_id": 0})
    if not po:
        raise HTTPException(404, "Permintaan penarikan tidak ditemukan")
    status = PAYOUT_FLOW.get(po["status"], {}).get(payload.action)
    if not status:
        raise HTTPException(400, f"Aksi {payload.action} tidak berlaku untuk status {po['status']}")
    if status == "success" and len(payload.reference.strip()) < 4:
        raise HTTPException(400, "Isi nomor referensi transfer bank setelah transfer benar-benar berhasil")
    if status in ("rejected", "failed") and len(payload.note.strip()) < 5:
        raise HTTPException(400, "Tuliskan alasan penolakan atau kegagalan")
    entry = {"status": status, "by": user.get("name", "admin"), "at": now(), "note": payload.note, "reference": payload.reference}
    res = await db.payouts.update_one({"payout_id": payout_id, "status": po["status"]}, {"$set": {"status": status, "note": payload.note, "transfer_reference": payload.reference or po.get("transfer_reference", ""), "updated_at": now()}, "$push": {"history": entry}})
    if not res.modified_count:
        raise HTTPException(409, "Status penarikan sudah berubah")
    if status in ("rejected", "failed"):
        await release_payout(po, f"Penarikan {status}: {payload.note}")
    await audit(user, f"payout.{status}", payout_id, payload.reference or payload.note)
    return {"ok": True, "status": status}


@router.get("/audit")
async def audit_logs(user=Depends(admin)):
    return await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
