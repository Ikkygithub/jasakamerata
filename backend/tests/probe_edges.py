import os, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = lambda t: {"Authorization": f"Bearer {t}"}
p = requests.get(f"{API}/photographers/naya-visuals").json()
sid = p["services"][0]["service_id"]
for t in ["25:99", "abc", "23:30"]:
    r = requests.post(f"{API}/bookings", headers=H("test_session_customer"), json={"photographer_id": "ph_01", "service_id": sid, "date": "2027-03-03", "time": t, "duration": 12, "location": "TEST_probe"})
    print("time", t, r.status_code, r.text[:150])
r = requests.get(f"{API}/photographers/available", params={"date": "bad", "time": "10:00"})
print("available bad date", r.status_code, r.text[:100])
r = requests.get(f"{API}/photographers/naya-visuals/availability")
print("availability no month", r.status_code)
r = requests.get(f"{API}/photographers/naya-visuals/availability", params={"month": ".*"})
print("availability regex month", r.status_code, len(r.json()) if r.ok else r.text[:100])
r = requests.post(f"{API}/bookings/JK-NOPE/status", headers=H("test_session_customer"), json={"status": "bogus"})
print("bogus status", r.status_code)
r = requests.post(f"{API}/photographer/payouts", headers=H("test_session_photographer"), json={"amount": 10})
print("payout 10", r.status_code)
