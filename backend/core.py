from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import os, uuid, hashlib, base64

load_dotenv(Path(__file__).parent / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(mongo_url.encode()).digest()))

CATEGORIES = ["Wedding", "Commercial", "Event", "Graduation"]
COMMISSION_RATE = 0.05
HIDDEN_LISTING = ["pending", "rejected"]
SECRET_FIELDS = {"_id", "bank_account_encrypted", "bank_snapshot_encrypted"}


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def public(doc):
    if not doc:
        return None
    out = {k: v for k, v in doc.items() if k not in SECRET_FIELDS}
    if isinstance(out.get("bank"), dict):
        out["bank"] = {k: v for k, v in out["bank"].items() if k != "number_encrypted"}
    return out


def encrypt(value: str) -> str:
    return cipher.encrypt(value.encode()).decode()


async def audit(actor, action, target, detail=""):
    await db.audit_logs.insert_one({"log_id": new_id("log"), "actor_id": actor["user_id"], "actor_name": actor.get("name", ""), "actor_role": actor.get("role", ""), "action": action, "target": target, "detail": detail, "created_at": now()})
