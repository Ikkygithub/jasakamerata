# In-process unit tests for Midtrans webhook (signature SHA512, apply_status idempotency/amount/stale guards) with FAKE keys set only in this process
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

os.environ["MIDTRANS_SERVER_KEY"] = "SB-Mid-server-FAKE"
os.environ["MIDTRANS_CLIENT_KEY"] = "SB-Mid-client-FAKE"

import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402
import server  # noqa: E402

SK = os.environ["MIDTRANS_SERVER_KEY"]
RUN = uuid.uuid4().hex[:6].upper()
BID = f"JK-TWH{RUN}"
OID = f"{BID}-1"


def sig(o, c, g):
    return hashlib.sha512(f"{o}{c}{g}{SK}".encode()).hexdigest()


def note(status, code="200", gross="350000.00", tid="tx1", fraud="accept", order=OID, signature=None):
    return {"order_id": order, "status_code": code, "gross_amount": gross, "transaction_status": status, "fraud_status": fraud, "transaction_id": tid, "signature_key": signature or sig(order, code, gross)}


@pytest.fixture(scope="module")
def env():
    mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    nowi = datetime.now(timezone.utc)
    mdb.bookings.insert_one({"booking_id": BID, "customer_id": "test_customer", "customer_name": "TEST", "photographer_id": "ph_01", "photographer_name": "Naya", "photographer_slug": "naya-visuals", "service_id": "x", "service": "TEST WH", "category": "Wedding", "date": "2027-05-05", "time": "04:00", "duration": 1, "location": "TEST", "total": 350000, "commission": 17500, "photographer_earning": 332500, "status": "accepted", "payment_status": "unpaid", "payment_due_at": (nowi + timedelta(hours=20)).isoformat(), "history": [], "created_at": nowi.isoformat()})
    mdb.payments.insert_one({"order_id": OID, "booking_id": BID, "customer_id": "test_customer", "gross_amount": 350000, "token": "t", "transaction_status": "created", "production": True, "expires_at": (nowi + timedelta(hours=20)).isoformat(), "created_at": nowi.isoformat()})
    with TestClient(server.app) as c:
        yield c, mdb
    mdb.bookings.delete_one({"booking_id": BID})
    mdb.payments.delete_one({"order_id": OID})
    mdb.payment_events.delete_many({"order_id": OID})
    mdb.audit_logs.delete_many({"target": OID})
    mdb.email_logs.delete_many({"ref": BID})


def test_config_enabled_in_process(env):
    c, _ = env
    d = c.get("/api/payments/config").json()
    assert d["enabled"] is True and d["client_key"] == "SB-Mid-client-FAKE"


def test_bad_signature(env):
    c, _ = env
    r = c.post("/api/payments/midtrans/notification", json=note("settlement", signature="deadbeef"))
    assert r.status_code == 401


def test_missing_fields(env):
    c, _ = env
    assert c.post("/api/payments/midtrans/notification", json={"order_id": OID}).status_code == 400


def test_unknown_order(env):
    c, _ = env
    assert c.post("/api/payments/midtrans/notification", json=note("settlement", order="JK-NOPE-1")).status_code == 404


def test_amount_mismatch(env):
    c, mdb = env
    r = c.post("/api/payments/midtrans/notification", json=note("settlement", gross="1000.00"))
    assert r.status_code == 400
    assert mdb.bookings.find_one({"booking_id": BID})["payment_status"] == "unpaid"


def test_settlement_bad_fraud(env):
    c, _ = env
    assert c.post("/api/payments/midtrans/notification", json=note("capture", fraud="challenge")).status_code == 400


def test_pending_then_settlement_then_dup_then_stale(env):
    c, mdb = env
    r = c.post("/api/payments/midtrans/notification", json=note("pending", code="201", tid="tx1"))
    assert r.status_code == 200 and r.json()["result"] == "ok"
    assert mdb.bookings.find_one({"booking_id": BID})["payment_status"] == "pending"
    r = c.post("/api/payments/midtrans/notification", json=note("settlement", tid="tx1"))
    assert r.status_code == 200 and r.json()["result"] == "ok"
    b = mdb.bookings.find_one({"booking_id": BID})
    assert b["payment_status"] == "paid" and b["payment_order_id"] == OID
    r = c.post("/api/payments/midtrans/notification", json=note("settlement", tid="tx1"))
    assert r.json()["result"] == "duplicate"
    assert sum(1 for h in mdb.bookings.find_one({"booking_id": BID})["history"] if h["by"] == "midtrans") == 1
    r = c.post("/api/payments/midtrans/notification", json=note("pending", code="201", tid="tx2"))
    assert r.json()["result"] == "stale"
    assert mdb.bookings.find_one({"booking_id": BID})["payment_status"] == "paid"
    assert mdb.payments.find_one({"order_id": OID})["transaction_status"] == "settlement"


def test_paid_email_logged(env):
    import time
    _, mdb = env
    for _ in range(10):
        log = mdb.email_logs.find_one({"kind": "booking_paid", "ref": BID})
        if log:
            break
        time.sleep(0.3)
    assert log and log["to"] == "naya.test@example.com" and log["status"] == "disabled"


def test_refund_after_settlement_reverses(env):
    c, mdb = env
    r = c.post("/api/payments/midtrans/notification", json=note("cancel", tid="tx3"))
    assert r.status_code == 200
    assert mdb.bookings.find_one({"booking_id": BID})["payment_status"] == "reversed"
