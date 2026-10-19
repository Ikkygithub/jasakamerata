import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def test_public_marketplace_endpoints():
    root = requests.get(f"{BASE_URL}/api/", timeout=20)
    assert root.status_code == 200
    assert root.json()["categories"] == ["Wedding", "Commercial", "Event", "Graduation"]

    photographers = requests.get(f"{BASE_URL}/api/photographers", timeout=20)
    assert photographers.status_code == 200
    people = photographers.json()
    assert len(people) == 12
    assert {p["category"] for p in people} == set(root.json()["categories"])
    assert all("_id" not in p and "bank_account_encrypted" not in p for p in people)

    filtered = requests.get(f"{BASE_URL}/api/photographers", params={"category": "Event"}, timeout=20)
    assert filtered.status_code == 200
    assert filtered.json() and all(p["category"] == "Event" for p in filtered.json())

    services = requests.get(f"{BASE_URL}/api/services", timeout=20)
    assert services.status_code == 200 and len(services.json()) >= 12


def test_profile_and_search():
    people = requests.get(f"{BASE_URL}/api/photographers", timeout=20).json()
    profile = requests.get(f"{BASE_URL}/api/photographers/{people[0]['slug']}", timeout=20)
    assert profile.status_code == 200
    assert profile.json()["name"] == people[0]["name"]
    assert requests.get(f"{BASE_URL}/api/photographers/not-real", timeout=20).status_code == 404


def test_registration_masks_account_and_rejects_invalid_category():
    import uuid
    payload = {"name": "TEST Fotografer", "email": f"test_reg_legacy_{uuid.uuid4().hex[:6]}@example.com", "category": "Event", "bank_account": "123456789012"}
    response = requests.post(f"{BASE_URL}/api/photographers/register", json=payload, timeout=20)
    assert response.status_code == 200
    body = response.json()
    assert body["bank_account_masked"].endswith("9012")
    assert "123456789012" not in response.text
    invalid = {**payload, "category": "Invalid"}
    assert requests.post(f"{BASE_URL}/api/photographers/register", json=invalid, timeout=20).status_code == 400


def test_protected_endpoints_require_session():
    session = requests.Session()
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 401
    assert session.get(f"{BASE_URL}/api/dashboard/summary", timeout=20).status_code == 401
    assert session.get(f"{BASE_URL}/api/chat/conversations", timeout=20).status_code == 401