# Seeds TEST_UI accepted+unpaid booking for test_customer/ph_01 (payment due in future) for UI checks
import os, sys
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
env = {}
for line in open("/app/backend/.env"):
    if "=" in line:
        k, v = line.strip().split("=", 1); env[k] = v.strip('"')
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
if sys.argv[1:] == ["clean"]:
    print(db.bookings.delete_many({"booking_id": "JK-TESTUIPAY"}).deleted_count); sys.exit()
n = datetime.now(timezone.utc)
db.bookings.delete_many({"booking_id": "JK-TESTUIPAY"})
db.bookings.insert_one({"booking_id": "JK-TESTUIPAY", "customer_id": "test_customer", "customer_name": "TEST Customer", "photographer_id": "ph_01", "photographer_name": "Naya Visuals", "photographer_slug": "naya-visuals", "service_id": "x", "service": "TEST UI Unpaid", "category": "Wedding", "date": "2027-09-09", "time": "03:00", "duration": 1, "location": "TEST", "notes": "", "total": 500000, "commission": 25000, "photographer_earning": 475000, "status": "accepted", "payment_status": "unpaid", "payment_due_at": (n + timedelta(hours=20)).isoformat(), "history": [], "created_at": (n + timedelta(days=1)).isoformat()})
print("seeded")
