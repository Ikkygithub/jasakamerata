# Phase 4: Midtrans DEMO-mode gating, email logs, lazy expiry, deliver/cancel gating, admin integrations, SEO
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CUST, PH, ADMIN = "test_session_customer", "test_session_photographer", "test_session_admin"
RUN = uuid.uuid4().hex[:6]


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def rand_date():
    return (datetime(2027, 1, 1) + timedelta(days=random.randint(0, 900))).strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def mongo():
    env = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip('"')
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


@pytest.fixture(scope="module")
def ph01():
    r = requests.get(f"{API}/photographers/naya-visuals", timeout=20)
    assert r.status_code == 200
    return r.json()


def make_booking(ph01, tok=CUST):
    svc = ph01["services"][0]
    for _ in range(5):
        r = requests.post(f"{API}/bookings", json={"photographer_id": ph01["photographer_id"], "service_id": svc["service_id"], "date": rand_date(), "time": f"{random.randint(7, 15):02d}:00", "duration": 2, "location": f"TEST P4 {RUN}", "agree_policy": True}, headers=h(tok), timeout=20)
        if r.status_code != 409:
            break
    assert r.status_code == 200, r.text
    return r.json()


def wait_log(mongo, kind, ref, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        doc = mongo.email_logs.find_one({"kind": kind, "ref": ref}, {"_id": 0})
        if doc:
            return doc
        time.sleep(0.5)
    return None


# ---------- Payments config / disabled ----------
def test_payments_config_disabled():
    d = requests.get(f"{API}/payments/config", timeout=20).json()
    assert d["enabled"] is False and d["client_key"] == "" and d["is_production"] is True
    assert d["snap_url"] == "https://app.midtrans.com/snap/snap.js"


def test_payment_endpoints_503(ph01):
    b = make_booking(ph01)
    bid = b["booking_id"]
    assert requests.post(f"{API}/payments/bookings/{bid}/snap", headers=h(CUST), timeout=20).status_code == 503
    assert requests.post(f"{API}/payments/bookings/{bid}/check", headers=h(CUST), timeout=20).status_code == 503
    assert requests.post(f"{API}/payments/midtrans/notification", json={"order_id": "x"}, timeout=20).status_code == 503


# ---------- Demo flow + email logs ----------
def test_demo_flow_and_emails(ph01, mongo):
    t0 = time.time()
    b = make_booking(ph01)
    assert time.time() - t0 < 5
    bid = b["booking_id"]
    assert b["payment_status"] == "demo_deferred"
    log = wait_log(mongo, "booking_new", bid)
    assert log and log["to"] == "naya.test@example.com" and log["status"] == "disabled"
    assert "EMERGENT_EMAIL_KEY" in log["detail"]
    r = requests.post(f"{API}/bookings/{bid}/status", json={"status": "accepted"}, headers=h(PH), timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert "payment_due_at" not in r.json()  # demo bookings have no pay window
    r = requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "https://drive.google.com/x", "note": "TEST"}, headers=h(PH), timeout=20)
    assert r.status_code == 200, r.text
    log = wait_log(mongo, "booking_delivered", bid)
    assert log and log["to"] == "customer.test@example.com" and log["status"] == "disabled"
    before = mongo.ledger.count_documents({"ref": bid})
    r = requests.post(f"{API}/bookings/{bid}/status", json={"status": "completed"}, headers=h(CUST), timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "completed"
    types = sorted(e["type"] for e in mongo.ledger.find({"ref": bid}))
    assert before == 0 and len(types) == 2, types


# ---------- Lazy expiry ----------
def test_lazy_expiry(ph01, mongo):
    bid = f"JK-TESTEXP{RUN}".upper()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    mongo.bookings.insert_one({"booking_id": bid, "customer_id": "test_customer", "customer_name": "TEST", "photographer_id": "ph_01", "photographer_name": "Naya", "photographer_slug": "naya-visuals", "service_id": ph01["services"][0]["service_id"], "service": "TEST", "category": "Wedding", "date": rand_date(), "time": "06:00", "duration": 1, "location": "TEST", "notes": "", "total": 100000, "commission": 5000, "photographer_earning": 95000, "status": "accepted", "payment_status": "unpaid", "payment_due_at": past, "history": [], "created_at": past})
    r = requests.get(f"{API}/bookings", headers=h(ADMIN), timeout=20)
    assert r.status_code == 200
    b = mongo.bookings.find_one({"booking_id": bid})
    assert b["status"] == "cancelled" and b["payment_status"] == "expired"
    assert b["history"][-1]["by"] == "system"


def _inject(mongo, ph01, payment_status, due_hours=24):
    bid = f"JK-T{uuid.uuid4().hex[:7]}".upper()
    nowi = datetime.now(timezone.utc)
    mongo.bookings.insert_one({"booking_id": bid, "customer_id": "test_customer", "customer_name": "TEST", "photographer_id": "ph_01", "photographer_name": "Naya Visuals", "photographer_slug": "naya-visuals", "service_id": ph01["services"][0]["service_id"], "service": "TEST P4 svc", "category": "Wedding", "date": rand_date(), "time": "05:00", "duration": 1, "location": "TEST", "notes": "", "total": 100000, "commission": 5000, "photographer_earning": 95000, "status": "accepted", "payment_status": payment_status, "payment_due_at": (nowi + timedelta(hours=due_hours)).isoformat(), "history": [], "created_at": nowi.isoformat()})
    return bid


# ---------- Deliver / cancel gating ----------
def test_deliver_gating(ph01, mongo):
    bid = _inject(mongo, ph01, "unpaid")
    r = requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "https://drive.google.com/x"}, headers=h(PH), timeout=20)
    assert r.status_code == 400 and "setelah pembayaran" in r.json()["detail"]
    mongo.bookings.update_one({"booking_id": bid}, {"$set": {"payment_status": "paid"}})
    r = requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "https://drive.google.com/x"}, headers=h(PH), timeout=20)
    assert r.status_code == 200, r.text


def test_cancel_paid(ph01, mongo):
    bid = _inject(mongo, ph01, "paid")
    r = requests.post(f"{API}/bookings/{bid}/status", json={"status": "cancelled", "note": "x"}, headers=h(CUST), timeout=20)
    assert r.status_code == 400
    r = requests.post(f"{API}/bookings/{bid}/status", json={"status": "cancelled", "note": "TEST admin"}, headers=h(ADMIN), timeout=20)
    assert r.status_code == 200
    assert r.json()["payment_status"] == "refund_pending"


def test_photographer_cancel_paid_blocked(ph01, mongo):
    bid = _inject(mongo, ph01, "paid")
    r = requests.post(f"{API}/bookings/{bid}/status", json={"status": "cancelled", "note": "x"}, headers=h(PH), timeout=20)
    assert r.status_code == 400


# ---------- Admin ----------
def test_admin_overview_integrations():
    d = requests.get(f"{API}/admin/overview", headers=h(ADMIN), timeout=20).json()
    assert d["payments"]["enabled"] is False and d["payments"]["production"] is True
    assert "paid" in d["payments"] and "refund_pending" in d["payments"]
    assert d["email_enabled"] is False


def test_admin_emails():
    r = requests.get(f"{API}/admin/emails", headers=h(ADMIN), timeout=20)
    assert r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0
    assert all("_id" not in e for e in r.json())
    assert all(e["status"] != "sent" for e in r.json())
    for tok in (CUST, PH):
        assert requests.get(f"{API}/admin/emails", headers=h(tok), timeout=20).status_code == 403


# ---------- SEO ----------
def test_robots_sitemap():
    r = requests.get(f"{BASE_URL}/robots.txt", timeout=20)
    assert r.status_code == 200 and "jasakamerata.com" in r.text and "Sitemap" in r.text
    r = requests.get(f"{BASE_URL}/sitemap.xml", timeout=20)
    assert r.status_code == 200 and "https://jasakamerata.com" in r.text and "<urlset" in r.text


def test_index_canonical():
    r = requests.get(f"{BASE_URL}/", timeout=20)
    assert 'rel="canonical" href="https://jasakamerata.com/"' in r.text
    assert 'og:url' in r.text


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    yield
    mongo.bookings.delete_many({"$or": [{"location": f"TEST P4 {RUN}"}, {"service": "TEST P4 svc"}, {"booking_id": f"JK-TESTEXP{RUN}".upper()}]})
