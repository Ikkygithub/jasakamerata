import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from auth import current_user
from core import db, now
from emailer import notify_paid

router = APIRouter(prefix="/payments")
SUCCESS = {"settlement", "capture"}
FAILED = {"deny", "cancel", "expire", "failure"}
PAY_WINDOW_HOURS = 24


def is_production():
    return os.environ.get("MIDTRANS_IS_PRODUCTION", "false").lower() == "true"


def server_key():
    return os.environ.get("MIDTRANS_SERVER_KEY", "").strip()


def client_key():
    return os.environ.get("MIDTRANS_CLIENT_KEY", "").strip()


def enabled():
    return bool(server_key() and client_key())


def _base(api=False):
    if api:
        return "https://api.midtrans.com" if is_production() else "https://api.sandbox.midtrans.com"
    return "https://app.midtrans.com" if is_production() else "https://app.sandbox.midtrans.com"


def _auth():
    return {"Authorization": "Basic " + base64.b64encode(f"{server_key()}:".encode()).decode(), "Accept": "application/json", "Content-Type": "application/json"}


def due_at():
    return (datetime.now(timezone.utc) + timedelta(hours=PAY_WINDOW_HOURS)).isoformat()


@router.get("/config")
async def config():
    return {"enabled": enabled(), "client_key": client_key() if enabled() else "", "is_production": is_production(), "snap_url": f"{_base()}/snap/snap.js"}


@router.post("/bookings/{booking_id}/snap")
async def create_snap(booking_id: str, user=Depends(current_user)):
    if not enabled():
        raise HTTPException(503, "Pembayaran online belum diaktifkan")
    b = await db.bookings.find_one({"booking_id": booking_id, "customer_id": user["user_id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    if b["status"] != "accepted" or b.get("payment_status") not in ("unpaid", "failed"):
        raise HTTPException(409, "Pesanan ini tidak dapat dibayar")
    due = datetime.fromisoformat(b.get("payment_due_at") or due_at())
    minutes = int((due - datetime.now(timezone.utc)).total_seconds() // 60)
    if minutes < 5:
        raise HTTPException(409, "Batas waktu pembayaran sudah lewat")
    open_pay = await db.payments.find_one({"booking_id": booking_id, "transaction_status": {"$in": ["created", "pending"]}, "expires_at": {"$gt": now()}}, {"_id": 0})
    if open_pay:
        return {"token": open_pay["token"], "order_id": open_pay["order_id"], "gross_amount": open_pay["gross_amount"]}
    attempt = await db.payments.count_documents({"booking_id": booking_id}) + 1
    order_id = f"{booking_id}-{attempt}"
    gross = int(b["total"])
    payload = {
        "transaction_details": {"order_id": order_id, "gross_amount": gross},
        "item_details": [{"id": b["service_id"][:50], "price": gross, "quantity": 1, "name": b["service"][:50]}],
        "customer_details": {"first_name": (user.get("name") or "Customer")[:50], "email": user["email"]},
        "expiry": {"unit": "minute", "duration": minutes},
        "callbacks": {"finish": f"{os.environ['PUBLIC_SITE_URL'].rstrip('/')}/customer/pesanan"},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{_base()}/snap/v1/transactions", json=payload, headers=_auth())
    if r.status_code != 201:
        raise HTTPException(502, "Gagal membuat transaksi Midtrans, coba lagi")
    token = r.json()["token"]
    await db.payments.insert_one({"order_id": order_id, "booking_id": booking_id, "customer_id": user["user_id"], "gross_amount": gross, "token": token, "transaction_status": "created", "production": is_production(), "expires_at": due.isoformat(), "created_at": now()})
    return {"token": token, "order_id": order_id, "gross_amount": gross}


async def apply_status(order_id, status_code, gross, status, fraud, transaction_id, source):
    payment = await db.payments.find_one({"order_id": order_id}, {"_id": 0})
    if not payment:
        raise HTTPException(404, "Order tidak dikenal")
    try:
        if Decimal(gross).quantize(Decimal("0.01")) != Decimal(str(payment["gross_amount"])).quantize(Decimal("0.01")):
            raise HTTPException(400, "Nominal tidak cocok")
    except InvalidOperation:
        raise HTTPException(400, "Nominal tidak valid")
    status = status.lower()
    if status in SUCCESS and (status_code != "200" or (fraud and fraud.lower() != "accept")):
        raise HTTPException(400, "Status sukses tidak konsisten")
    key = hashlib.sha256(f"{order_id}|{status_code}|{gross}|{status}|{transaction_id}".encode()).hexdigest()
    try:
        await db.payment_events.insert_one({"event_key": key, "order_id": order_id, "status": status, "source": source, "created_at": now()})
    except DuplicateKeyError:
        return "duplicate"
    current = payment.get("transaction_status")
    if current in SUCCESS and status == "pending":
        return "stale"
    await db.payments.update_one({"order_id": order_id}, {"$set": {"transaction_status": status, "status_code": status_code, "fraud_status": fraud, "transaction_id": transaction_id, "updated_at": now()}})
    bid = payment["booking_id"]
    entry = lambda note: {"status": "payment", "by": "midtrans", "note": note, "at": now()}  # noqa: E731
    if status in SUCCESS:
        res = await db.bookings.update_one({"booking_id": bid, "payment_status": {"$ne": "paid"}}, {"$set": {"payment_status": "paid", "payment_order_id": order_id, "paid_at": now()}, "$push": {"history": entry("Pembayaran terverifikasi Midtrans")}})
        if res.modified_count:
            b = await db.bookings.find_one({"booking_id": bid}, {"_id": 0})
            await notify_paid(b)
    elif status == "pending":
        await db.bookings.update_one({"booking_id": bid, "payment_status": {"$in": ["unpaid", "failed"]}}, {"$set": {"payment_status": "pending"}})
    elif status in FAILED:
        if current in SUCCESS:
            await db.bookings.update_one({"booking_id": bid}, {"$set": {"payment_status": "reversed"}, "$push": {"history": entry(f"Pembayaran dibatalkan Midtrans ({status}) — periksa manual")}})
        else:
            await db.bookings.update_one({"booking_id": bid, "payment_status": {"$ne": "paid"}}, {"$set": {"payment_status": "failed"}, "$push": {"history": entry(f"Pembayaran {status}")}})
    await db.audit_logs.insert_one({"log_id": key[:16], "actor_id": "midtrans", "actor_name": "Midtrans", "actor_role": "system", "action": f"payment.{status}", "target": order_id, "detail": source, "created_at": now()})
    return "ok"


@router.post("/midtrans/notification")
async def notification(request: Request):
    if not enabled():
        raise HTTPException(503, "Pembayaran belum diaktifkan")
    n = await request.json()
    if any(k not in n for k in ("order_id", "status_code", "gross_amount", "signature_key", "transaction_status")):
        raise HTTPException(400, "Field notifikasi tidak lengkap")
    expected = hashlib.sha512((str(n["order_id"]) + str(n["status_code"]) + str(n["gross_amount"]) + server_key()).encode()).hexdigest()
    if not hmac.compare_digest(expected, str(n["signature_key"])):
        raise HTTPException(401, "Signature tidak valid")
    result = await apply_status(str(n["order_id"]), str(n["status_code"]), str(n["gross_amount"]), str(n["transaction_status"]), str(n.get("fraud_status") or ""), str(n.get("transaction_id", "")), "webhook")
    return {"ok": True, "result": result}


@router.post("/bookings/{booking_id}/check")
async def check_status(booking_id: str, user=Depends(current_user)):
    if not enabled():
        raise HTTPException(503, "Pembayaran belum diaktifkan")
    q = {"booking_id": booking_id} if user.get("role") == "admin" else {"booking_id": booking_id, "customer_id": user["user_id"]}
    pay = await db.payments.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not pay:
        raise HTTPException(404, "Belum ada transaksi")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{_base(api=True)}/v2/{pay['order_id']}/status", headers=_auth())
    d = r.json() if r.status_code == 200 else {}
    if d.get("status_code") in ("200", "201", "202", "407") and d.get("transaction_status"):
        await apply_status(pay["order_id"], str(d["status_code"]), str(d["gross_amount"]), d["transaction_status"], str(d.get("fraud_status") or ""), str(d.get("transaction_id", "")), "status_api")
    b = await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0, "payment_status": 1})
    return {"payment_status": b["payment_status"]}


async def init_indexes():
    await db.payments.create_index("order_id", unique=True)
    await db.payment_events.create_index("event_key", unique=True)
