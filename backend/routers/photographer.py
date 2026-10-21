import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from auth import current_user, require_role
from core import CATEGORIES, audit, db, encrypt, new_id, now, public
from ledger import MAX_PAYOUT, MIN_PAYOUT, available_balance, reserve_payout
from routers.availability import to_minutes, validate_date
from storage import DELIVERY_TYPES, IMAGE_TYPES, save_upload

router = APIRouter(prefix="/photographer")
me = require_role("photographer")
PENDING_EARNING = ["accepted", "delivered", "revision_requested", "disputed"]
OPEN_PAYOUT = ["requested", "approved", "processing"]


class Onboard(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str
    agree_policy: bool = False


class ProfileUpdate(BaseModel):
    bio: str | None = Field(None, max_length=1000)
    service_area: str | None = Field(None, max_length=200)
    profile_image: str | None = Field(None, max_length=500)
    min_duration: int | None = Field(None, ge=1, le=12)


class ServiceIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    price: int = Field(ge=50000, le=100000000)
    duration: str = Field(min_length=1, max_length=50)
    deliverables: str = Field(min_length=1, max_length=200)
    turnaround: str = Field("7 hari kerja", max_length=50)
    pricing_type: str = "per paket"


class UrlIn(BaseModel):
    url: str = Field(min_length=10, max_length=500)
    title: str = Field("", max_length=100)


class ItemUpdate(BaseModel):
    title: str = Field("", max_length=100)
    description: str = Field("", max_length=500)


class Reorder(BaseModel):
    ids: list[str]


class BlockIn(BaseModel):
    date: str
    start: str = "00:00"
    end: str = "23:59"
    reason: str = Field("", max_length=200)


class BankIn(BaseModel):
    bank_name: str = Field(min_length=2, max_length=60)
    holder_name: str = Field(min_length=2, max_length=80)
    account_number: str = Field(min_length=6, max_length=30)


class PayoutIn(BaseModel):
    amount: int


@router.post("/onboard")
async def onboard(payload: Onboard, user=Depends(current_user)):
    if user.get("role", "customer") != "customer" or user.get("photographer_id"):
        raise HTTPException(400, "Akun ini sudah terdaftar sebagai fotografer atau admin")
    if payload.category not in CATEGORIES:
        raise HTTPException(400, "Pilih salah satu dari empat kategori yang tersedia")
    if not payload.agree_policy:
        raise HTTPException(400, "Setujui syarat dan kebijakan fotografer terlebih dahulu")
    if await db.bookings.count_documents({"customer_id": user["user_id"], "status": {"$in": ["pending", "accepted", "delivered", "revision_requested", "disputed"]}}):
        raise HTTPException(400, "Selesaikan pesanan aktif sebagai customer sebelum menjadi fotografer")
    pid = f"ph_{new_id('x')[-8:]}"
    res = await db.users.update_one({"user_id": user["user_id"], "role": {"$in": ["customer", None]}, "photographer_id": {"$exists": False}}, {"$set": {"role": "photographer", "photographer_id": pid, "photographer_policy_agreed_at": now()}})
    if not res.modified_count:
        raise HTTPException(409, "Pendaftaran fotografer sedang diproses")
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") + "-" + pid[-4:]
    await db.photographers.insert_one({"photographer_id": pid, "user_id": user["user_id"], "slug": slug, "name": payload.name, "username": "@" + slug.replace("-", ""), "category": payload.category, "location": "Makassar, Sulawesi Selatan", "bio": "Profil baru di Jasakamerata.", "profile_image": user.get("picture", ""), "gallery": [], "verified": False, "demo": False, "listing_status": "pending", "verification": {"status": "not_submitted"}, "rating": None, "reviews": 0, "starting_price": 0, "min_duration": 2, "service_area": "Makassar dan sekitarnya", "services": [], "created_at": now()})
    await audit(user, "photographer.onboard", pid, payload.category)
    return {"ok": True, "photographer_id": pid}


async def profile_of(user):
    p = await db.photographers.find_one({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Profil fotografer belum terhubung")
    return p


def bank_view(user):
    b = user.get("bank")
    if b:
        return {"bank_name": b["bank_name"], "holder_name": b["holder_name"], "masked": b["masked"], "complete": True, "updated_at": b.get("updated_at")}
    if user.get("bank_account_encrypted"):
        return {"bank_name": "", "holder_name": "", "masked": user.get("bank_account_masked", "••••"), "complete": False, "legacy": True}
    return {"complete": False, "masked": None}


async def wallet_of(user):
    pid = user.get("photographer_id", "-")
    pending = 0
    async for b in db.bookings.find({"photographer_id": pid, "status": {"$in": PENDING_EARNING}}, {"photographer_earning": 1}):
        pending += b.get("photographer_earning", 0)
    sums = {}
    async for e in db.ledger.find({"photographer_id": pid}, {"type": 1, "amount": 1}):
        sums[e["type"]] = sums.get(e["type"], 0) + e["amount"]
    reserved = 0
    async for po in db.payouts.find({"photographer_id": pid, "status": {"$in": OPEN_PAYOUT}}, {"amount": 1}):
        reserved += po["amount"]
    paid = 0
    async for po in db.payouts.find({"photographer_id": pid, "status": "success"}, {"amount": 1}):
        paid += po["amount"]
    commission = 0
    async for b in db.bookings.find({"photographer_id": pid, "status": "completed"}, {"commission": 1}):
        commission += b.get("commission", 0)
    return {"earned": sums.get("earning", 0), "commission": commission, "pending": pending, "reserved": reserved, "paid_out": paid, "available": await available_balance(pid), "min": MIN_PAYOUT, "max": MAX_PAYOUT, "bank": bank_view(user), "note": "Pembayaran customer masih DITUNDA (DEMO). Saldo berasal dari pesanan DEMO yang selesai; transfer penarikan dilakukan manual oleh admin."}


async def recalc_price(pid):
    p = await db.photographers.find_one({"photographer_id": pid}, {"services": 1})
    prices = [s["price"] for s in p.get("services", [])]
    await db.photographers.update_one({"photographer_id": pid}, {"$set": {"starting_price": min(prices) if prices else 0}})


async def sync_gallery(pid):
    items = await db.portfolio_items.find({"photographer_id": pid, "is_deleted": False}, {"_id": 0}).sort([("is_cover", -1), ("order", 1)]).to_list(100)
    await db.photographers.update_one({"photographer_id": pid}, {"$set": {"gallery": [i["url"] for i in items]}})
    return items


def completeness(p, user):
    checks = {"Bio": len(p.get("bio", "")) > 30, "Foto profil": bool(p.get("profile_image")), "Minimal 3 portofolio": len(p.get("gallery", [])) >= 3, "Minimal 1 layanan": bool(p.get("services")), "Rekening bank": bool(user.get("bank"))}
    return {"percent": round(sum(checks.values()) / len(checks) * 100), "checks": checks}


@router.get("/me")
async def overview(user=Depends(me)):
    p = await profile_of(user)
    pid = p["photographer_id"]
    counts = {s: await db.bookings.count_documents({"photographer_id": pid, "status": s}) for s in ["pending", "accepted", "delivered", "revision_requested", "disputed", "completed", "declined", "cancelled"]}
    unread = 0
    async for c in db.conversations.find({"photographer_id": pid}, {"unread_photographer": 1}):
        unread += c.get("unread_photographer", 0)
    return {"profile": p, "counts": counts, "unread": unread, "wallet": await wallet_of(user), "completeness": completeness(p, user)}


@router.put("/profile")
async def update_profile(payload: ProfileUpdate, user=Depends(me)):
    p = await profile_of(user)
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if data.get("profile_image") and not data["profile_image"].startswith(("https://", "/api/media/")):
        raise HTTPException(400, "URL foto profil harus https://")
    if data:
        await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$set": data})
    return await profile_of(user)


@router.post("/services")
async def add_service(payload: ServiceIn, user=Depends(me)):
    p = await profile_of(user)
    svc = {"service_id": new_id("svc"), "category": p["category"], **payload.model_dump()}
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$push": {"services": svc}})
    await recalc_price(p["photographer_id"])
    return svc


@router.put("/services/{service_id}")
async def edit_service(service_id: str, payload: ServiceIn, user=Depends(me)):
    p = await profile_of(user)
    if not any(s["service_id"] == service_id for s in p.get("services", [])):
        raise HTTPException(404, "Layanan tidak ditemukan")
    sets = {f"services.$.{k}": v for k, v in payload.model_dump().items()}
    await db.photographers.update_one({"photographer_id": p["photographer_id"], "services.service_id": service_id}, {"$set": sets})
    await recalc_price(p["photographer_id"])
    return {"ok": True}


@router.delete("/services/{service_id}")
async def delete_service(service_id: str, user=Depends(me)):
    p = await profile_of(user)
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$pull": {"services": {"service_id": service_id}}})
    await recalc_price(p["photographer_id"])
    return {"ok": True}


@router.get("/portfolio")
async def list_portfolio(user=Depends(me)):
    return await sync_gallery((await profile_of(user))["photographer_id"])


async def add_item(pid, url, title="", description="", storage=None, item_id=None):
    if await db.portfolio_items.count_documents({"photographer_id": pid, "is_deleted": False}) >= 30:
        raise HTTPException(400, "Maksimal 30 foto portofolio")
    last = await db.portfolio_items.find_one({"photographer_id": pid}, sort=[("order", -1)])
    item = {"item_id": item_id or new_id("pf"), "photographer_id": pid, "url": url, "title": title, "description": description, "order": (last or {}).get("order", 0) + 1, "is_cover": False, "is_deleted": False, "created_at": now(), **(storage or {})}
    await db.portfolio_items.insert_one(dict(item))
    await sync_gallery(pid)
    return public(item)


@router.post("/portfolio")
async def upload_portfolio(file: UploadFile = File(...), title: str = Form(""), description: str = Form(""), user=Depends(me)):
    p = await profile_of(user)
    meta = await save_upload(file, f"portfolio/{p['photographer_id']}", IMAGE_TYPES, 8)
    item_id = new_id("pf")
    item = await add_item(p["photographer_id"], f"/api/media/{item_id}", title[:100], description[:500], meta, item_id)
    item.pop("storage_path", None)
    return item


@router.post("/portfolio/url")
async def add_portfolio_url(payload: UrlIn, user=Depends(me)):
    if not payload.url.startswith("https://"):
        raise HTTPException(400, "URL gambar harus diawali https://")
    p = await profile_of(user)
    return await add_item(p["photographer_id"], payload.url, payload.title)


async def own_item(item_id, user):
    it = await db.portfolio_items.find_one({"item_id": item_id, "photographer_id": user.get("photographer_id", "-"), "is_deleted": False}, {"_id": 0})
    if not it:
        raise HTTPException(404, "Portofolio tidak ditemukan")
    return it


@router.put("/portfolio/{item_id}")
async def update_item(item_id: str, payload: ItemUpdate, user=Depends(me)):
    await own_item(item_id, user)
    await db.portfolio_items.update_one({"item_id": item_id}, {"$set": payload.model_dump()})
    return {"ok": True}


@router.post("/portfolio/{item_id}/cover")
async def set_cover(item_id: str, user=Depends(me)):
    it = await own_item(item_id, user)
    await db.portfolio_items.update_many({"photographer_id": it["photographer_id"]}, {"$set": {"is_cover": False}})
    await db.portfolio_items.update_one({"item_id": item_id}, {"$set": {"is_cover": True}})
    return await sync_gallery(it["photographer_id"])


@router.post("/portfolio/reorder")
async def reorder(payload: Reorder, user=Depends(me)):
    pid = (await profile_of(user))["photographer_id"]
    for i, item_id in enumerate(payload.ids):
        await db.portfolio_items.update_one({"item_id": item_id, "photographer_id": pid}, {"$set": {"order": i}})
    return await sync_gallery(pid)


@router.delete("/portfolio/{item_id}")
async def delete_item(item_id: str, user=Depends(me)):
    it = await own_item(item_id, user)
    await db.portfolio_items.update_one({"item_id": item_id}, {"$set": {"is_deleted": True, "deleted_at": now()}})
    return await sync_gallery(it["photographer_id"])


@router.get("/availability")
async def list_blocks(user=Depends(me)):
    return await db.availability_blocks.find({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0}).sort("date", 1).to_list(500)


@router.post("/availability")
async def add_block(payload: BlockIn, user=Depends(me)):
    p = await profile_of(user)
    validate_date(payload.date)
    if to_minutes(payload.start) >= to_minutes(payload.end):
        raise HTTPException(400, "Jam selesai harus setelah jam mulai")
    blk = {"block_id": new_id("blk"), "photographer_id": p["photographer_id"], **payload.model_dump(), "created_at": now()}
    await db.availability_blocks.insert_one(dict(blk))
    return blk


@router.delete("/availability/{block_id}")
async def delete_block(block_id: str, user=Depends(me)):
    res = await db.availability_blocks.delete_one({"block_id": block_id, "photographer_id": user.get("photographer_id", "-")})
    if not res.deleted_count:
        raise HTTPException(404, "Blokir jadwal tidak ditemukan")
    return {"ok": True}


@router.get("/bank")
async def get_bank(user=Depends(me)):
    return bank_view(user)


@router.put("/bank")
async def set_bank(payload: BankIn, user=Depends(me)):
    digits = re.sub(r"\D", "", payload.account_number)
    if not 6 <= len(digits) <= 20:
        raise HTTPException(400, "Nomor rekening harus 6–20 digit angka")
    if await db.payouts.count_documents({"photographer_id": user.get("photographer_id", "-"), "status": {"$in": OPEN_PAYOUT}}):
        raise HTTPException(400, "Rekening tidak dapat diubah saat ada penarikan yang sedang diproses")
    bank = {"bank_name": payload.bank_name.strip(), "holder_name": payload.holder_name.strip(), "number_encrypted": encrypt(digits), "masked": "••••" + digits[-4:], "updated_at": now()}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"bank": bank, "bank_account_masked": bank["masked"]}})
    await audit(user, "bank.updated", user.get("photographer_id", ""), f"{bank['bank_name']} {bank['masked']}")
    return bank_view({"bank": bank})


@router.get("/ledger")
async def my_ledger(user=Depends(me)):
    return await db.ledger.find({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0, "key": 0}).sort("created_at", -1).to_list(200)


@router.get("/payouts")
async def list_payouts(user=Depends(me)):
    return await db.payouts.find({"photographer_id": user.get("photographer_id", "-")}, {"_id": 0, "bank_snapshot_encrypted": 0}).sort("created_at", -1).to_list(100)


@router.post("/payouts")
async def request_payout(payload: PayoutIn, user=Depends(me)):
    await profile_of(user)
    if not user.get("bank"):
        raise HTTPException(400, "Lengkapi rekening bank di menu Rekening terlebih dahulu")
    po_id = new_id("po")
    await reserve_payout(user["photographer_id"], po_id, payload.amount)
    b = user["bank"]
    po = {"payout_id": po_id, "photographer_id": user["photographer_id"], "photographer_name": user.get("name", ""), "amount": payload.amount, "bank_name": b["bank_name"], "holder_name": b["holder_name"], "bank_account_masked": b["masked"], "bank_snapshot_encrypted": b["number_encrypted"], "status": "requested", "history": [{"status": "requested", "by": "photographer", "at": now(), "note": ""}], "created_at": now()}
    await db.payouts.insert_one(dict(po))
    await audit(user, "payout.requested", po_id, str(payload.amount))
    return public(po)


@router.post("/verification")
async def submit_verification(experience: str = Form(""), links: str = Form(""), consent: bool = Form(False), id_document: UploadFile | None = File(None), supporting: UploadFile | None = File(None), user=Depends(me)):
    p = await profile_of(user)
    status = (p.get("verification") or {}).get("status", "not_submitted")
    if status in ("pending", "approved"):
        raise HTTPException(400, "Pengajuan sedang diperiksa atau sudah disetujui")
    problems = []
    if len(experience.strip()) < 30:
        problems.append("Ceritakan pengalaman fotografi minimal 30 karakter")
    if not consent:
        problems.append("Setujui kebijakan penyimpanan dokumen verifikasi")
    if not id_document:
        problems.append("Unggah dokumen identitas (KTP)")
    if len(p.get("gallery", [])) < 3:
        problems.append("Unggah minimal 3 foto portofolio")
    if problems:
        raise HTTPException(400, "; ".join(problems))
    docs = [{"doc_id": new_id("doc"), "kind": "id_document", **await save_upload(id_document, f"verification/{p['photographer_id']}", DELIVERY_TYPES, 8)}]
    if supporting:
        docs.append({"doc_id": new_id("doc"), "kind": "supporting", **await save_upload(supporting, f"verification/{p['photographer_id']}", DELIVERY_TYPES, 15)})
    sub = {"submission_id": new_id("ver"), "photographer_id": p["photographer_id"], "photographer_name": p["name"], "experience": experience.strip()[:2000], "links": links.strip()[:500], "documents": docs, "auto_checks": {"form_complete": True, "id_document": True, "portfolio_min_3": True}, "status": "pending", "created_at": now()}
    await db.verifications.insert_one(dict(sub))
    await db.photographers.update_one({"photographer_id": p["photographer_id"]}, {"$set": {"verification": {"status": "pending", "submitted_at": now(), "submission_id": sub["submission_id"]}}})
    await audit(user, "verification.submitted", sub["submission_id"])
    return {"ok": True, "status": "pending"}
