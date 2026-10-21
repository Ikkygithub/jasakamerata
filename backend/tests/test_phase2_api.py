# Phase 2 regression: registration, bookings + conflicts, availability, chat, studio, admin, role guards
import os
import random
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TOK = {"cust": "test_session_customer", "cust2": "test_session_customer2", "ph": "test_session_photographer", "admin": "test_session_admin"}
RUN = uuid.uuid4().hex[:6]


def H(who):
    return {"Authorization": f"Bearer {TOK[who]}"}


def rand_date():
    # random future date in 2027 to avoid collisions across reruns
    return f"2027-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient("mongodb://localhost:27017")
    db = c["test_database"]
    yield db
    # cleanup TEST data
    db.bookings.delete_many({"location": {"$regex": "^TEST_"}})
    db.availability_blocks.delete_many({"reason": {"$regex": "^TEST_"}})
    for u in db.users.find({"email": {"$regex": "^test_reg_"}}):
        db.photographers.delete_many({"user_id": u["user_id"]})
    db.users.delete_many({"email": {"$regex": "^test_reg_"}})
    db.payouts.delete_many({"photographer_id": "ph_01", "amount": 50000, "status": {"$in": ["requested", "rejected", "approved"]}, "created_at": {"$gte": "2026-10-19"}, "_test": True})
    c.close()


@pytest.fixture(scope="session")
def ph01_service():
    p = requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()
    return p["photographer_id"], p["services"][0]["service_id"]


def book(who, pid, sid, date, time="10:00", duration=2):
    return requests.post(f"{API}/bookings", headers=H(who), json={"photographer_id": pid, "service_id": sid, "date": date, "time": time, "duration": duration, "location": f"TEST_{RUN}", "notes": "t", "agree_policy": True}, timeout=20)


# --- Public catalog & visibility
def test_public_list_and_hidden(mongo):
    r = requests.get(f"{API}/photographers", timeout=20)
    assert r.status_code == 200
    people = r.json()
    assert all(p.get("listing_status") not in ("pending", "rejected") for p in people)
    assert len([p for p in people if p.get("demo")]) == 12
    assert requests.get(f"{API}/photographers/foto-makassar", timeout=20).status_code == 404


# --- Registration
@pytest.mark.skip(reason='Obsolete after phase 3 (register removed / gallery->portfolio / ledger wallet); covered by test_phase3_api.py')
def test_registration_flow(mongo):
    email = f"test_reg_{RUN}@example.com"
    payload = {"name": f"TEST Reg {RUN}", "email": email, "category": "Event", "bank_account": "1234-5678-9012"}
    bad = requests.post(f"{API}/photographers/register", json={**payload, "category": "Fashion"}, timeout=20)
    assert bad.status_code == 400
    r = requests.post(f"{API}/photographers/register", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bank_account_masked"] == "••••9012"
    assert "bank_account_encrypted" not in body and "123456789012" not in r.text
    assert body["verification_status"] == "pending"
    dup = requests.post(f"{API}/photographers/register", json={**payload, "email": email.upper()}, timeout=20)
    assert dup.status_code == 409
    ph = mongo.photographers.find_one({"photographer_id": body["photographer_id"]})
    assert ph["listing_status"] == "pending"
    assert requests.get(f"{API}/photographers/{ph['slug']}", timeout=20).status_code == 404
    assert all(p["photographer_id"] != body["photographer_id"] for p in requests.get(f"{API}/photographers", timeout=20).json())


# --- Booking create guards
def test_booking_create_guards(ph01_service):
    pid, sid = ph01_service
    d = rand_date()
    assert requests.post(f"{API}/bookings", json={"photographer_id": pid, "service_id": sid, "date": d, "time": "10:00", "location": "TEST_x"}, timeout=20).status_code == 401
    assert book("ph", pid, sid, d).status_code == 403
    assert book("admin", pid, sid, d).status_code == 403
    assert book("cust", pid, sid, "2025-01-01").status_code == 400
    assert book("cust", pid, "svc_nope", d).status_code == 400
    assert book("cust", pid, sid, "2027-13-45").status_code == 400


# --- Booking lifecycle, conflict, alternatives, isolation
def test_booking_lifecycle_and_conflict(ph01_service):
    pid, sid = ph01_service
    d = rand_date()
    r = book("cust", pid, sid, d, "09:00", 3)
    if r.status_code == 409:
        d = rand_date(); r = book("cust", pid, sid, d, "09:00", 3)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "pending" and b["payment_status"] == "demo_deferred" and b["booking_id"].startswith("JK-")
    bid = b["booking_id"]
    # duplicate pending same slot
    assert book("cust", pid, sid, d, "09:00", 3).status_code == 409
    # other customer pending overlapping is allowed before acceptance
    r2 = book("cust2", pid, sid, d, "10:00", 2)
    assert r2.status_code == 200, r2.text
    bid2 = r2.json()["booking_id"]
    # customer cannot accept
    assert requests.post(f"{API}/bookings/{bid}/status", headers=H("cust"), json={"status": "accepted"}, timeout=20).status_code == 400
    # other customer cannot see
    assert requests.get(f"{API}/bookings/{bid}", headers=H("cust2"), timeout=20).status_code == 404
    assert requests.post(f"{API}/bookings/{bid}/status", headers=H("cust2"), json={"status": "cancelled"}, timeout=20).status_code == 404
    # photographer accepts
    a = requests.post(f"{API}/bookings/{bid}/status", headers=H("ph"), json={"status": "accepted", "note": "ok"}, timeout=20)
    assert a.status_code == 200 and a.json()["status"] == "accepted" and len(a.json()["history"]) == 2
    # new overlapping booking -> 409
    assert book("cust2", pid, sid, d, "11:00", 1).status_code == 409
    # accept re-check for previously pending overlapping booking
    assert requests.post(f"{API}/bookings/{bid2}/status", headers=H("ph"), json={"status": "accepted"}, timeout=20).status_code == 409
    # alternatives exclude ph_01
    alt = requests.get(f"{API}/photographers/available", params={"date": d, "time": "10:00", "duration": 2, "category": "Wedding", "exclude": pid}, timeout=20)
    assert alt.status_code == 200 and all(p["photographer_id"] != pid and p["category"] == "Wedding" for p in alt.json())
    # public availability shows booked slot, no customer data
    av = requests.get(f"{API}/photographers/naya-visuals/availability", params={"month": d[:7]}, timeout=20)
    assert av.status_code == 200
    slots = [s for s in av.json() if s["date"] == d]
    assert any(s["type"] == "booked" and s["start"] == "09:00" and s["end"] == "12:00" for s in slots)
    assert "customer" not in av.text and "Customer Uji" not in av.text
    # invalid transition accepted->declined
    assert requests.post(f"{API}/bookings/{bid}/status", headers=H("ph"), json={"status": "declined"}, timeout=20).status_code == 400
    # decline bid2
    assert requests.post(f"{API}/bookings/{bid2}/status", headers=H("ph"), json={"status": "declined"}, timeout=20).status_code == 200
    # complete bid
    # phase 3: photographer can no longer complete directly
    assert requests.post(f"{API}/bookings/{bid}/status", headers=H("ph"), json={"status": "completed"}, timeout=20).status_code == 400
    c = requests.post(f"{API}/bookings/{bid}/status", headers=H("cust"), json={"status": "cancelled"}, timeout=20)
    assert c.status_code == 200 and len(c.json()["history"]) == 3
    # cancelled no longer blocks
    assert book("cust2", pid, sid, d, "11:00", 1).status_code == 200


def test_customer_cancel(ph01_service):
    pid, sid = ph01_service
    d = rand_date()
    r = book("cust", pid, sid, d, "18:00", 1)
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        bid = r.json()["booking_id"]
        x = requests.post(f"{API}/bookings/{bid}/status", headers=H("cust"), json={"status": "cancelled"}, timeout=20)
        assert x.status_code == 200 and x.json()["status"] == "cancelled"
        assert any(b["booking_id"] == bid for b in requests.get(f"{API}/bookings", headers=H("cust"), timeout=20).json())


# --- Availability blocks
def test_availability_blocks(ph01_service):
    pid, sid = ph01_service
    d = rand_date()
    assert requests.post(f"{API}/photographer/availability", headers=H("ph"), json={"date": d, "start": "15:00", "end": "13:00"}, timeout=20).status_code == 400
    r = requests.post(f"{API}/photographer/availability", headers=H("ph"), json={"date": d, "start": "13:00", "end": "16:00", "reason": "TEST_blk"}, timeout=20)
    assert r.status_code == 200
    blk = r.json()["block_id"]
    assert any(b["block_id"] == blk for b in requests.get(f"{API}/photographer/availability", headers=H("ph"), timeout=20).json())
    assert book("cust", pid, sid, d, "14:00", 1).status_code == 409
    av = requests.get(f"{API}/photographers/naya-visuals/availability", params={"month": d[:7]}, timeout=20).json()
    assert any(s["type"] == "blocked" and s["date"] == d for s in av)
    assert requests.post(f"{API}/photographer/availability", headers=H("cust"), json={"date": d}, timeout=20).status_code == 403
    assert requests.delete(f"{API}/photographer/availability/{blk}", headers=H("ph"), timeout=20).status_code == 200
    assert requests.delete(f"{API}/photographer/availability/{blk}", headers=H("ph"), timeout=20).status_code == 404


# --- Chat
def test_chat_flow():
    c = requests.post(f"{API}/chat/conversations", headers=H("cust"), json={"photographer_id": "ph_01"}, timeout=20)
    assert c.status_code == 200
    cid = c.json()["conversation_id"]
    again = requests.post(f"{API}/chat/conversations", headers=H("cust"), json={"photographer_id": "ph_01"}, timeout=20)
    assert again.json()["conversation_id"] == cid
    # photographer reads first to reset
    requests.get(f"{API}/chat/conversations/{cid}/messages", headers=H("ph"), timeout=20)
    m = requests.post(f"{API}/chat/conversations/{cid}/messages", headers=H("cust"), json={"text": f"TEST halo {RUN}"}, timeout=20)
    assert m.status_code == 200 and m.json()["sender_role"] == "customer"
    convs = requests.get(f"{API}/chat/conversations", headers=H("ph"), timeout=20).json()
    conv = next(x for x in convs if x["conversation_id"] == cid)
    assert conv["unread_photographer"] >= 1 and RUN in conv["last_message"]
    msgs = requests.get(f"{API}/chat/conversations/{cid}/messages", headers=H("ph"), timeout=20).json()
    assert any(RUN in x["text"] for x in msgs)
    conv = next(x for x in requests.get(f"{API}/chat/conversations", headers=H("ph"), timeout=20).json() if x["conversation_id"] == cid)
    assert conv["unread_photographer"] == 0
    rep = requests.post(f"{API}/chat/conversations/{cid}/messages", headers=H("ph"), json={"text": "TEST balas"}, timeout=20)
    assert rep.status_code == 200
    assert requests.get(f"{API}/dashboard/summary", headers=H("cust"), timeout=20).json()["unread"] >= 1
    # non participants
    assert requests.get(f"{API}/chat/conversations/{cid}/messages", headers=H("cust2"), timeout=20).status_code == 404
    assert requests.get(f"{API}/chat/conversations", headers=H("admin"), timeout=20).status_code == 403
    assert requests.post(f"{API}/chat/conversations/{cid}/messages", headers=H("cust"), json={"text": "   "}, timeout=20).status_code == 400
    assert requests.get(f"{API}/chat/conversations", timeout=20).status_code == 401


# --- Favorites & customer dashboard
def test_favorites():
    assert requests.post(f"{API}/favorites", headers=H("cust"), json={"photographer_id": "ph_02"}, timeout=20).status_code == 200
    assert any(p["photographer_id"] == "ph_02" for p in requests.get(f"{API}/favorites", headers=H("cust"), timeout=20).json())
    s = requests.get(f"{API}/dashboard/summary", headers=H("cust"), timeout=20).json()
    assert s["favorites"] >= 1 and "active_bookings" in s
    requests.delete(f"{API}/favorites/ph_02", headers=H("cust"), timeout=20)
    assert all(p["photographer_id"] != "ph_02" for p in requests.get(f"{API}/favorites", headers=H("cust"), timeout=20).json())


# --- Studio
@pytest.mark.skip(reason='Obsolete after phase 3 (register removed / gallery->portfolio / ledger wallet); covered by test_phase3_api.py')
def test_studio_me_profile_services_gallery():
    me = requests.get(f"{API}/photographer/me", headers=H("ph"), timeout=20)
    assert me.status_code == 200
    body = me.json()
    assert body["profile"]["photographer_id"] == "ph_01" and "wallet" in body and "counts" in body
    assert "bank_account_encrypted" not in me.text
    assert requests.get(f"{API}/photographer/me", headers=H("cust"), timeout=20).status_code == 403
    old_bio = body["profile"]["bio"]
    p = requests.put(f"{API}/photographer/profile", headers=H("ph"), json={"bio": f"TEST bio {RUN}"}, timeout=20)
    assert p.status_code == 200 and p.json()["bio"] == f"TEST bio {RUN}"
    requests.put(f"{API}/photographer/profile", headers=H("ph"), json={"bio": old_bio}, timeout=20)
    s = requests.post(f"{API}/photographer/services", headers=H("ph"), json={"title": "TEST Paket Murah", "price": 50000, "duration": "1 jam", "deliverables": "10 foto"}, timeout=20)
    assert s.status_code == 200
    sid = s.json()["service_id"]
    assert requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()["starting_price"] == 50000
    e = requests.put(f"{API}/photographer/services/{sid}", headers=H("ph"), json={"title": "TEST Paket Edit", "price": 60000, "duration": "1 jam", "deliverables": "10 foto"}, timeout=20)
    assert e.status_code == 200
    prof = requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()
    assert prof["starting_price"] == 60000 and any(x["title"] == "TEST Paket Edit" for x in prof["services"])
    assert requests.put(f"{API}/photographer/services/svc_nope", headers=H("ph"), json={"title": "abc", "price": 60000, "duration": "1", "deliverables": "1"}, timeout=20).status_code == 404
    assert requests.delete(f"{API}/photographer/services/{sid}", headers=H("ph"), timeout=20).status_code == 200
    prof = requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()
    assert prof["starting_price"] == min(x["price"] for x in prof["services"])
    assert requests.post(f"{API}/photographer/gallery", headers=H("ph"), json={"url": "http://example.com/a.jpg"}, timeout=20).status_code == 400
    g = requests.post(f"{API}/photographer/gallery", headers=H("ph"), json={"url": f"https://example.com/test_{RUN}.jpg"}, timeout=20)
    assert g.status_code == 200 and g.json()[-1].endswith(f"test_{RUN}.jpg")
    idx = len(g.json()) - 1
    d = requests.delete(f"{API}/photographer/gallery/{idx}", headers=H("ph"), timeout=20)
    assert d.status_code == 200 and all(RUN not in u for u in d.json())
    assert requests.delete(f"{API}/photographer/gallery/999", headers=H("ph"), timeout=20).status_code == 404


@pytest.mark.skip(reason='Obsolete after phase 3 (register removed / gallery->portfolio / ledger wallet); covered by test_phase3_api.py')
def test_wallet_and_payout(mongo):
    w = requests.get(f"{API}/photographer/me", headers=H("ph"), timeout=20).json()["wallet"]
    assert w["available"] == max(w["earned"] - w["withdrawn_or_requested"], 0)
    assert requests.post(f"{API}/photographer/payouts", headers=H("ph"), json={"amount": w["available"] + 100000}, timeout=20).status_code == 400
    assert requests.post(f"{API}/photographer/payouts", headers=H("cust"), json={"amount": 50000}, timeout=20).status_code == 403
    if w["available"] >= 50000:
        r = requests.post(f"{API}/photographer/payouts", headers=H("ph"), json={"amount": 50000}, timeout=20)
        assert r.status_code == 200, r.text
        assert "bank_snapshot_encrypted" not in r.text and r.json()["status"] == "requested"
        pid = r.json()["payout_id"]
        w2 = requests.get(f"{API}/photographer/me", headers=H("ph"), timeout=20).json()["wallet"]
        assert w2["available"] == w["available"] - 50000
        # admin rejects -> restored
        a = requests.post(f"{API}/admin/payouts/{pid}", headers=H("admin"), json={"action": "reject"}, timeout=20)
        assert a.status_code == 200 and a.json()["status"] == "rejected"
        assert requests.post(f"{API}/admin/payouts/{pid}", headers=H("admin"), json={"action": "approve"}, timeout=20).status_code == 404
        mongo.payouts.delete_one({"payout_id": pid})


# --- Admin
@pytest.mark.skip(reason='Obsolete after phase 3 (register removed / gallery->portfolio / ledger wallet); covered by test_phase3_api.py')
def test_admin_endpoints(mongo):
    for path in ["overview", "photographers", "users", "payouts", "audit"]:
        assert requests.get(f"{API}/admin/{path}", headers=H("cust"), timeout=20).status_code == 403
        assert requests.get(f"{API}/admin/{path}", headers=H("ph"), timeout=20).status_code == 403
    o = requests.get(f"{API}/admin/overview", headers=H("admin"), timeout=20)
    assert o.status_code == 200 and "bookings" in o.json()
    u = requests.get(f"{API}/admin/users", headers=H("admin"), timeout=20)
    assert u.status_code == 200 and "bank_account_encrypted" not in u.text
    assert "bank_snapshot_encrypted" not in requests.get(f"{API}/admin/payouts", headers=H("admin"), timeout=20).text
    # register -> approve -> public -> unverify -> reject -> hidden
    email = f"test_reg_adm_{RUN}@example.com"
    reg = requests.post(f"{API}/photographers/register", json={"name": f"TEST Adm {RUN}", "email": email, "category": "Graduation", "bank_account": "9876543210"}, timeout=20).json()
    pid = reg["photographer_id"]
    pend = requests.get(f"{API}/admin/photographers", headers=H("admin"), params={"status": "pending"}, timeout=20).json()
    assert any(p["photographer_id"] == pid for p in pend)
    assert requests.post(f"{API}/admin/photographers/{pid}/verify", headers=H("admin"), json={"action": "bogus"}, timeout=20).status_code == 400
    ap = requests.post(f"{API}/admin/photographers/{pid}/verify", headers=H("admin"), json={"action": "approve"}, timeout=20)
    assert ap.status_code == 200 and ap.json()["listing_status"] == "approved" and ap.json()["verified"] is True
    slug = ap.json()["slug"]
    assert requests.get(f"{API}/photographers/{slug}", timeout=20).status_code == 200
    un = requests.post(f"{API}/admin/photographers/{pid}/verify", headers=H("admin"), json={"action": "unverify"}, timeout=20)
    assert un.json()["verified"] is False
    rj = requests.post(f"{API}/admin/photographers/{pid}/verify", headers=H("admin"), json={"action": "reject"}, timeout=20)
    assert rj.json()["listing_status"] == "rejected"
    assert requests.get(f"{API}/photographers/{slug}", timeout=20).status_code == 404
    logs = requests.get(f"{API}/admin/audit", headers=H("admin"), timeout=20).json()
    actions = {(l["action"], l["target"]) for l in logs}
    assert ("photographer.approve", pid) in actions and ("photographer.reject", pid) in actions
    assert requests.post(f"{API}/admin/photographers/ph_nope/verify", headers=H("admin"), json={"action": "approve"}, timeout=20).status_code == 404


def test_unauth_401():
    for path in ["auth/me", "dashboard/summary", "bookings", "favorites", "photographer/me", "admin/overview", "chat/conversations"]:
        assert requests.get(f"{API}/{path}", timeout=20).status_code == 401, path
