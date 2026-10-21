import os

from core import CATEGORIES, db, new_id, now
from ledger import backfill

IMAGES = [
    "https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1531058020387-3be344556be6?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1523580846011-d3a5bc25702b?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1511578314322-379afb476865?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1520857014576-2c4f4c972b57?q=80&w=1200&auto=format&fit=crop",
]
NAMES = ["Naya Visuals", "Ruang Rona", "Karsa Studio", "Arunika Photo", "Sora Works", "Lensa Selatan", "Mata Makassar", "Pijar Studio", "Kita Frame", "Bumi Visual", "Kanvas Event", "Siluet Co."]
TITLES = ["Cerita Pernikahan Intim", "Katalog Brand & Produk", "Dokumentasi Event", "Sesi Wisuda Personal"]
PRICES = [650000, 850000, 500000, 350000]
FULL_PRICES = [1250000, 1500000, 950000, 650000]


def photographer(i, name, category):
    slug = name.lower().replace(" ", "-").replace(".", "")
    gallery = [IMAGES[(i + j) % len(IMAGES)] for j in range(4)]
    return {
        "photographer_id": f"ph_{i:02d}", "slug": slug, "name": name, "username": "@" + slug.replace("-", ""),
        "category": category, "location": "Makassar, Sulawesi Selatan",
        "bio": "Fotografer freelance Makassar yang mengubah momen penting menjadi cerita visual yang hangat dan jujur.",
        "profile_image": gallery[1], "gallery": gallery, "verified": i % 4 != 0, "demo": True, "listing_status": "approved",
        "rating": 4.8 + (i % 3) / 10, "reviews": i % 5 + 2, "starting_price": PRICES[i % 4], "min_duration": 2,
        "service_area": "Makassar dan sekitarnya",
        "services": [
            {"service_id": f"svc_{i}1", "title": TITLES[CATEGORIES.index(category)], "category": category, "price": PRICES[i % 4], "pricing_type": "per paket", "duration": "2–4 jam", "deliverables": "80 foto edit berkualitas tinggi", "turnaround": "7 hari kerja"},
            {"service_id": f"svc_{i}2", "title": "Paket Lengkap " + category, "category": category, "price": FULL_PRICES[i % 4], "pricing_type": "per paket", "duration": "6 jam", "deliverables": "250 foto edit + galeri online", "turnaround": "10 hari kerja"},
        ],
    }


async def seed_data():
    if await db.photographers.count_documents({"demo": True}) < 12:
        await db.photographers.delete_many({"demo": True})
        await db.photographers.insert_many([photographer(i + 1, n, CATEGORIES[i % 4]) for i, n in enumerate(NAMES)])
    await db.photographers.update_many({"listing_status": {"$exists": False}}, {"$set": {"listing_status": "approved"}})
    await db.bookings.create_index([("photographer_id", 1), ("date", 1)])
    await db.conversations.create_index([("customer_id", 1), ("photographer_id", 1)], unique=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.favorites.create_index([("user_id", 1), ("photographer_id", 1)], unique=True)

    await db.portfolio_items.create_index([("photographer_id", 1), ("order", 1)])
    async for p in db.photographers.find({}, {"photographer_id": 1, "gallery": 1}):
        if await db.portfolio_items.count_documents({"photographer_id": p["photographer_id"]}):
            continue
        items = [{"item_id": new_id("pf"), "photographer_id": p["photographer_id"], "url": u, "title": "", "description": "", "order": i, "is_cover": i == 0, "is_deleted": False, "created_at": now()} for i, u in enumerate(p.get("gallery", []))]
        if items:
            await db.portfolio_items.insert_many(items)
    admins = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
    if admins:
        await db.users.update_many({"email": {"$in": admins}}, {"$set": {"role": "admin"}})
    await db.photographers.update_many({"verification": {"$exists": False}}, [{"$set": {"verification": {"status": {"$cond": ["$verified", "approved", "not_submitted"]}}}}])
    await backfill()
