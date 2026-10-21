# Phase 3 regression: branding API, onboarding, bank, portfolio upload, booking lifecycle, ledger, payouts, verification, admin
import io
import os
import random
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
RUN = uuid.uuid4().hex[:6]
CUST, CUST2, PH, ADMIN = "test_session_customer", "test_session_customer2", "test_session_photographer", "test_session_admin"


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def png_bytes(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, "PNG")
    return buf.getvalue()


def rand_date():
    d = datetime(2027, 1, 1) + timedelta(days=random.randint(0, 900))
    return d.strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def mongo():
    env = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip('"')
    c = MongoClient(env["MONGO_URL"])
    return c[env["DB_NAME"]]


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    yield
    uids = [u["user_id"] for u in mongo.users.find({"user_id": {"$regex": f"^TEST_.*_{RUN}$"}})]
    pids = [p["photographer_id"] for p in mongo.photographers.find({"user_id": {"$in": uids}})]
    mongo.photographers.delete_many({"photographer_id": {"$in": pids}})
    mongo.portfolio_items.delete_many({"photographer_id": {"$in": pids}})
    mongo.verifications.delete_many({"photographer_id": {"$in": pids}})
    mongo.user_sessions.delete_many({"user_id": {"$in": uids}})
    mongo.users.delete_many({"user_id": {"$in": uids}})


def fresh_customer(mongo, tag):
    uid = f"TEST_{tag}_{RUN}"
    tok = f"TEST_tok_{tag}_{RUN}"
    mongo.users.insert_one({"user_id": uid, "email": f"{uid.lower()}@example.com", "name": f"TEST {tag}", "role": "customer", "created_at": datetime.now(timezone.utc).isoformat()})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok, "expires_at": datetime.now(timezone.utc) + timedelta(days=1), "created_at": datetime.now(timezone.utc).isoformat()})
    return uid, tok


@pytest.fixture(scope="module")
def ph01():
    r = requests.get(f"{API}/photographers/naya-visuals", timeout=20)
    assert r.status_code == 200
    return r.json()


# ---------- Featured / branding ----------
def test_featured_max_two_per_category():
    r = requests.get(f"{API}/photographers/featured", timeout=20)
    assert r.status_code == 200
    counts = {}
    for p in r.json():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    assert counts and all(v <= 2 for v in counts.values()), counts
    assert set(counts) <= {"Wedding", "Commercial", "Event", "Graduation"}


def test_old_register_removed():
    r = requests.post(f"{API}/photographers/register", json={"name": "x", "email": "x@x.com", "category": "Wedding"}, timeout=20)
    assert r.status_code in (404, 405)


# ---------- Onboarding ----------
def test_onboarding_flow(mongo):
    uid, tok = fresh_customer(mongo, "onb")
    base = {"name": f"TEST Onb {RUN}", "category": "Event", "agree_policy": True}
    assert requests.post(f"{API}/photographer/onboard", json={**base, "category": "Fashion"}, headers=h(tok), timeout=20).status_code == 400
    assert requests.post(f"{API}/photographer/onboard", json={**base, "agree_policy": False}, headers=h(tok), timeout=20).status_code == 400
    r = requests.post(f"{API}/photographer/onboard", json=base, headers=h(tok), timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["photographer_id"].startswith("ph_")
    me = requests.get(f"{API}/auth/me", headers=h(tok), timeout=20).json()
    assert me.get("role") == "photographer"
    assert requests.post(f"{API}/photographer/onboard", json=base, headers=h(tok), timeout=20).status_code == 400
    assert requests.post(f"{API}/photographer/onboard", json=base, headers=h(ADMIN), timeout=20).status_code == 400
    assert requests.post(f"{API}/photographer/onboard", json=base, headers=h(PH), timeout=20).status_code == 400


# ---------- Bank ----------
def test_bank_masked_and_validation():
    r = requests.get(f"{API}/photographer/bank", headers=h(PH), timeout=20)
    assert r.status_code == 200
    assert "number_encrypted" not in r.text
    assert requests.get(f"{API}/photographer/bank", headers=h(CUST), timeout=20).status_code == 403
    bad = requests.put(f"{API}/photographer/bank", json={"bank_name": "BCA", "holder_name": "Naya", "account_number": "12ab"}, headers=h(PH), timeout=20)
    assert bad.status_code in (400, 422)
    ok = requests.put(f"{API}/photographer/bank", json={"bank_name": "BCA", "holder_name": "Naya", "account_number": "1234567890"}, headers=h(PH), timeout=20)
    assert ok.status_code == 200
    assert ok.json()["masked"].endswith("7890") and "number_encrypted" not in ok.text and "1234567890" not in ok.text


# ---------- Portfolio ----------
def test_portfolio_crud(mongo):
    files = {"file": ("t.png", png_bytes(), "image/png")}
    r = requests.post(f"{API}/photographer/portfolio", files=files, data={"title": f"TEST pf {RUN}", "description": "desc"}, headers=h(PH), timeout=60)
    assert r.status_code == 200, r.text
    item = r.json()
    assert "storage_path" not in item and item["url"] == f"/api/media/{item['item_id']}"
    img = requests.get(f"{BASE_URL}{item['url']}", timeout=30)
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    # txt renamed as png
    fake = requests.post(f"{API}/photographer/portfolio", files={"file": ("x.png", b"hello world text", "image/png")}, headers=h(PH), timeout=30)
    assert fake.status_code == 400
    bad_type = requests.post(f"{API}/photographer/portfolio", files={"file": ("x.txt", b"hello", "text/plain")}, headers=h(PH), timeout=30)
    assert bad_type.status_code == 400
    big = requests.post(f"{API}/photographer/portfolio", files={"file": ("b.png", b"\x89PNG" + b"0" * (8 * 1024 * 1024 + 10), "image/png")}, headers=h(PH), timeout=60)
    assert big.status_code == 400
    iid = item["item_id"]
    assert requests.put(f"{API}/photographer/portfolio/{iid}", json={"title": f"TEST edited {RUN}", "description": "d2"}, headers=h(PH), timeout=20).status_code == 200
    prof = requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()
    assert any(p["item_id"] == iid and p["title"] == f"TEST edited {RUN}" for p in prof["portfolio"])
    assert item["url"] in prof["gallery"]
    cov = requests.post(f"{API}/photographer/portfolio/{iid}/cover", headers=h(PH), timeout=20)
    assert cov.status_code == 200 and cov.json()[0]["item_id"] == iid
    ids = [i["item_id"] for i in requests.get(f"{API}/photographer/portfolio", headers=h(PH), timeout=20).json()]
    ro = requests.post(f"{API}/photographer/portfolio/reorder", json={"ids": list(reversed(ids))}, headers=h(PH), timeout=20)
    assert ro.status_code == 200
    requests.post(f"{API}/photographer/portfolio/reorder", json={"ids": ids}, headers=h(PH), timeout=20)  # restore original order
    # other users cannot edit
    _, otok = fresh_customer(mongo, "pfo")
    requests.post(f"{API}/photographer/onboard", json={"name": f"TEST Other {RUN}", "category": "Wedding", "agree_policy": True}, headers=h(otok), timeout=20)
    assert requests.put(f"{API}/photographer/portfolio/{iid}", json={"title": "hack"}, headers=h(otok), timeout=20).status_code == 404
    assert requests.delete(f"{API}/photographer/portfolio/{iid}", headers=h(otok), timeout=20).status_code == 404
    assert requests.delete(f"{API}/photographer/portfolio/{iid}", headers=h(CUST), timeout=20).status_code == 403
    d = requests.delete(f"{API}/photographer/portfolio/{iid}", headers=h(PH), timeout=20)
    assert d.status_code == 200
    assert mongo.portfolio_items.find_one({"item_id": iid})["is_deleted"] is True
    prof = requests.get(f"{API}/photographers/naya-visuals", timeout=20).json()
    assert item["url"] not in prof["gallery"]
    assert requests.get(f"{BASE_URL}{item['url']}", timeout=20).status_code == 404


# ---------- Booking + lifecycle + ledger + review ----------
def make_booking(ph01, tok=CUST, agree=True):
    svc = ph01["services"][0]
    return requests.post(f"{API}/bookings", json={"photographer_id": ph01["photographer_id"], "service_id": svc["service_id"], "date": rand_date(), "time": f"{random.randint(7, 15):02d}:00", "duration": 2, "location": "TEST Losari", "agree_policy": agree}, headers=h(tok), timeout=20)


def st(bid, status, tok, note=""):
    return requests.post(f"{API}/bookings/{bid}/status", json={"status": status, "note": note}, headers=h(tok), timeout=20)


def test_booking_policy_and_commission(ph01):
    assert make_booking(ph01, agree=False).status_code == 400
    r = make_booking(ph01)
    assert r.status_code == 200, r.text
    b = r.json()
    price = ph01["services"][0]["price"]
    assert b["commission"] == round(price * 0.05) and b["photographer_earning"] == price - b["commission"]
    st(b["booking_id"], "cancelled", CUST)


def test_full_lifecycle(ph01, mongo):
    b = make_booking(ph01).json()
    bid = b["booking_id"]
    assert st(bid, "accepted", PH).status_code == 200
    assert st(bid, "completed", PH).status_code == 400
    assert requests.post(f"{API}/bookings/{bid}/deliver", data={"note": "x"}, headers=h(PH), timeout=20).status_code == 400
    assert requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "http://x.com"}, headers=h(PH), timeout=20).status_code == 400
    d = requests.post(f"{API}/bookings/{bid}/deliver", data={"note": "hasil"}, files=[("files", ("h.png", png_bytes((1, 2, 3)), "image/png"))], headers=h(PH), timeout=60)
    assert d.status_code == 200, d.text
    lst = [x for x in requests.get(f"{API}/bookings", headers=h(CUST), timeout=20).json() if x["booking_id"] == bid][0]
    assert lst["status"] == "delivered"
    fid = lst["deliveries"][0]["files"][0]["file_id"]
    assert "storage_path" not in str(lst["deliveries"])
    dl = requests.get(f"{API}/bookings/{bid}/files/{fid}", headers=h(CUST), timeout=30)
    assert dl.status_code == 200 and dl.content.startswith(b"\x89PNG")
    assert requests.get(f"{API}/bookings/{bid}/files/{fid}", headers=h(CUST2), timeout=20).status_code == 404
    assert st(bid, "revision_requested", CUST, "abc").status_code == 400
    assert st(bid, "revision_requested", CUST, "tolong edit warna").status_code == 200
    d2 = requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "https://drive.example.com/x"}, headers=h(PH), timeout=20)
    assert d2.status_code == 200
    # review before completion
    assert requests.post(f"{API}/bookings/{bid}/review", json={"rating": 5, "comment": "x"}, headers=h(CUST), timeout=20).status_code == 400
    before = requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()["wallet"]["available"]
    assert st(bid, "completed", CUST).status_code == 200
    after = requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()["wallet"]["available"]
    assert after - before == b["photographer_earning"]
    entries = list(mongo.ledger.find({"ref": bid}))
    types = sorted(e["type"] for e in entries)
    assert types == ["earning", "platform_commission"], types
    # completed twice not possible
    assert st(bid, "completed", CUST).status_code == 400
    assert st(bid, "completed", ADMIN).status_code == 400
    # review
    assert requests.post(f"{API}/bookings/{bid}/review", json={"rating": 5, "comment": f"TEST review {RUN}"}, headers=h(PH), timeout=20).status_code == 403
    r1 = requests.post(f"{API}/bookings/{bid}/review", json={"rating": 5, "comment": f"TEST review {RUN}"}, headers=h(CUST), timeout=20)
    assert r1.status_code == 200
    assert requests.post(f"{API}/bookings/{bid}/review", json={"rating": 4, "comment": "again"}, headers=h(CUST), timeout=20).status_code == 409
    revs = requests.get(f"{API}/photographers/naya-visuals/reviews", timeout=20).json()
    assert any(r["comment"] == f"TEST review {RUN}" for r in revs)
    mongo.reviews.delete_many({"comment": f"TEST review {RUN}"})  # cleanup demo profile reviews


def test_dispute_and_admin_resolve(ph01, mongo):
    b = make_booking(ph01).json()
    bid = b["booking_id"]
    st(bid, "accepted", PH)
    requests.post(f"{API}/bookings/{bid}/deliver", data={"link": "https://drive.example.com/y"}, headers=h(PH), timeout=20)
    assert st(bid, "disputed", CUST, "no").status_code == 400
    assert st(bid, "disputed", CUST, "hasil tidak sesuai").status_code == 200
    assert st(bid, "completed", CUST).status_code == 400
    assert st(bid, "cancelled", ADMIN, "refund").status_code == 200
    assert mongo.ledger.count_documents({"ref": bid}) == 0


# ---------- Wallet / payouts ----------
def ledger_sum(mongo, pid):
    return sum(e["amount"] for e in mongo.ledger.find({"photographer_id": pid}))


def test_wallet_equals_ledger(mongo):
    me = requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()
    assert me["wallet"]["available"] == ledger_sum(mongo, "ph_01")


def test_payout_validation_and_admin_flow(mongo):
    pay = lambda amt: requests.post(f"{API}/photographer/payouts", json={"amount": amt}, headers=h(PH), timeout=20)
    avail = lambda: requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()["wallet"]["available"]
    a0 = avail()
    assert pay(99999).status_code == 400
    assert pay(10000001).status_code == 400
    if a0 < 10_000_000:
        assert pay(min(a0 + 1, 10_000_000)).status_code == 400
    r = pay(100000)
    assert r.status_code == 200, r.text
    po = r.json()["payout_id"]
    assert "bank_snapshot_encrypted" not in r.text
    assert avail() == a0 - 100000
    # bank blocked
    assert requests.put(f"{API}/photographer/bank", json={"bank_name": "BCA", "holder_name": "Naya", "account_number": "1234567890"}, headers=h(PH), timeout=20).status_code == 400
    act = lambda pid, a, **kw: requests.post(f"{API}/admin/payouts/{pid}", json={"action": a, **kw}, headers=h(ADMIN), timeout=20)
    assert requests.get(f"{API}/admin/payouts/{po}/account", headers=h(ADMIN), timeout=20).status_code == 404
    assert act(po, "success", reference="REF12345").status_code == 400
    assert act(po, "approve").status_code == 200
    acc = requests.get(f"{API}/admin/payouts/{po}/account", headers=h(ADMIN), timeout=20)
    assert acc.status_code == 200 and acc.json()["account_number"] == "1234567890"
    assert requests.get(f"{API}/admin/payouts/{po}/account", headers=h(PH), timeout=20).status_code == 403
    assert act(po, "process").status_code == 200
    assert act(po, "success", reference="ab").status_code == 400
    assert act(po, "success", reference="TEST-REF-1").status_code == 200
    assert avail() == a0 - 100000
    assert act(po, "fail", note="late fail").status_code == 400
    # reject releases
    po2 = pay(100000).json()["payout_id"]
    assert act(po2, "reject").status_code == 400
    assert act(po2, "reject", note="data salah").status_code == 200
    assert avail() == a0 - 100000
    # fail releases
    po3 = pay(100000).json()["payout_id"]
    act(po3, "approve"); act(po3, "process")
    assert act(po3, "fail", note="bank error").status_code == 200
    assert avail() == a0 - 100000
    assert avail() == ledger_sum(mongo, "ph_01")


def test_payout_no_bank(mongo):
    uid, tok = fresh_customer(mongo, "nobank")
    requests.post(f"{API}/photographer/onboard", json={"name": f"TEST NoBank {RUN}", "category": "Event", "agree_policy": True}, headers=h(tok), timeout=20)
    assert requests.post(f"{API}/photographer/payouts", json={"amount": 100000}, headers=h(tok), timeout=20).status_code == 400


def test_payout_concurrency(mongo):
    avail = requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()["wallet"]["available"]
    if avail < 200000:
        pytest.skip("balance too low")
    amt = min(10_000_000, avail // 2 + 50000)
    results = []

    def go():
        results.append(requests.post(f"{API}/photographer/payouts", json={"amount": amt}, headers=h(PH), timeout=30))
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 400], codes
    pid = next(r.json()["payout_id"] for r in results if r.status_code == 200)
    requests.post(f"{API}/admin/payouts/{pid}", json={"action": "reject", "note": "TEST cleanup"}, headers=h(ADMIN), timeout=20)
    assert requests.get(f"{API}/photographer/me", headers=h(PH), timeout=20).json()["wallet"]["available"] == avail


# ---------- Verification ----------
def test_verification_flow(mongo):
    uid, tok = fresh_customer(mongo, "ver")
    pid = requests.post(f"{API}/photographer/onboard", json={"name": f"TEST Ver {RUN}", "category": "Graduation", "agree_policy": True}, headers=h(tok), timeout=20).json()["photographer_id"]
    bad = requests.post(f"{API}/photographer/verification", data={"experience": "short", "consent": "false"}, headers=h(tok), timeout=20)
    assert bad.status_code == 400
    det = bad.json()["detail"]
    assert "30 karakter" in det and "KTP" in det and "3 foto" in det
    for i in range(3):
        assert requests.post(f"{API}/photographer/portfolio", files={"file": (f"{i}.png", png_bytes((i * 50, 0, 0)), "image/png")}, headers=h(tok), timeout=60).status_code == 200
    exp = "Saya memotret wisuda selama lima tahun di Makassar."
    ok = requests.post(f"{API}/photographer/verification", data={"experience": exp, "consent": "true"}, files={"id_document": ("ktp.png", png_bytes((9, 9, 9)), "image/png")}, headers=h(tok), timeout=60)
    assert ok.status_code == 200 and ok.json()["status"] == "pending", ok.text
    assert requests.get(f"{API}/admin/verifications", headers=h(PH), timeout=20).status_code == 403
    subs = requests.get(f"{API}/admin/verifications", headers=h(ADMIN), timeout=20).json()
    sub = next(s for s in subs if s["photographer_id"] == pid)
    assert "storage_path" not in str(sub)
    doc = requests.get(f"{API}/admin/verifications/{sub['submission_id']}/documents/{sub['documents'][0]['doc_id']}", headers=h(ADMIN), timeout=30)
    assert doc.status_code == 200 and doc.content.startswith(b"\x89PNG")
    assert requests.post(f"{API}/admin/verifications/{sub['submission_id']}", json={"action": "needs_fix"}, headers=h(ADMIN), timeout=20).status_code == 400
    assert requests.post(f"{API}/admin/verifications/{sub['submission_id']}", json={"action": "needs_fix", "note": "foto KTP buram"}, headers=h(ADMIN), timeout=20).status_code == 200
    # resubmit then approve
    ok2 = requests.post(f"{API}/photographer/verification", data={"experience": exp, "consent": "true"}, files={"id_document": ("ktp.png", png_bytes((8, 8, 8)), "image/png")}, headers=h(tok), timeout=60)
    assert ok2.status_code == 200
    sub2 = next(s for s in requests.get(f"{API}/admin/verifications", headers=h(ADMIN), timeout=20).json() if s["photographer_id"] == pid)
    assert requests.post(f"{API}/admin/verifications/{sub2['submission_id']}", json={"action": "approve"}, headers=h(ADMIN), timeout=20).status_code == 200
    p = mongo.photographers.find_one({"photographer_id": pid})
    assert p["verified"] is True and p["verification"]["status"] == "approved"


# ---------- Admin ----------
@pytest.mark.parametrize("path", ["overview", "photographers", "verifications", "users", "ledger", "payouts", "audit"])
def test_admin_endpoints(path):
    assert requests.get(f"{API}/admin/{path}", headers=h(ADMIN), timeout=20).status_code == 200
    assert requests.get(f"{API}/admin/{path}", headers=h(CUST), timeout=20).status_code == 403


def test_admin_users_no_encrypted():
    r = requests.get(f"{API}/admin/users", headers=h(ADMIN), timeout=20)
    assert "number_encrypted" not in r.text and "bank_account_encrypted" not in r.text


def test_admin_listing_toggle(mongo):
    uid, tok = fresh_customer(mongo, "lst")
    r = requests.post(f"{API}/photographer/onboard", json={"name": f"TEST Lst {RUN}", "category": "Commercial", "agree_policy": True}, headers=h(tok), timeout=20).json()
    pid = r["photographer_id"]
    slug = mongo.photographers.find_one({"photographer_id": pid})["slug"]
    assert requests.get(f"{API}/photographers/{slug}", timeout=20).status_code == 404
    assert requests.post(f"{API}/admin/photographers/{pid}/listing", json={"action": "publish"}, headers=h(ADMIN), timeout=20).status_code == 200
    assert requests.get(f"{API}/photographers/{slug}", timeout=20).status_code == 200
    assert requests.post(f"{API}/admin/photographers/{pid}/listing", json={"action": "unpublish"}, headers=h(ADMIN), timeout=20).status_code == 200
    assert requests.get(f"{API}/photographers/{slug}", timeout=20).status_code == 404
    assert requests.post(f"{API}/admin/photographers/{pid}/listing", json={"action": "x"}, headers=h(ADMIN), timeout=20).status_code == 400
