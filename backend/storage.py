import asyncio
import logging
import os
import uuid

import requests
from fastapi import HTTPException, UploadFile

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
PREFIX = os.environ.get("APP_STORAGE_PREFIX", "jasakamerata")
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DELIVERY_TYPES = {**IMAGE_TYPES, "application/pdf": "pdf", "application/zip": "zip", "application/x-zip-compressed": "zip"}
MAGIC = {"jpg": [b"\xff\xd8\xff"], "png": [b"\x89PNG"], "webp": [b"RIFF"], "pdf": [b"%PDF"], "zip": [b"PK\x03\x04"]}
_key = None
log = logging.getLogger("storage")


def _init(force=False):
    global _key
    if _key and not force:
        return _key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    r.raise_for_status()
    _key = r.json()["storage_key"]
    return _key


def _put(path, data, ctype):
    for attempt in range(2):
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": _init(force=attempt > 0), "Content-Type": ctype}, data=data, timeout=120)
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.json()


def _get(path):
    for attempt in range(2):
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": _init(force=attempt > 0)}, timeout=60)
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.content


def init_storage():
    try:
        _init()
        log.info("Storage initialized")
    except Exception as exc:  # noqa: BLE001
        log.error("Storage init failed: %s", exc)


async def save_upload(file: UploadFile, folder: str, allowed: dict, max_mb: int):
    ctype = (file.content_type or "").lower()
    if ctype not in allowed:
        raise HTTPException(400, f"Tipe file {file.filename} tidak didukung")
    data = await file.read()
    if not data:
        raise HTTPException(400, "File kosong")
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(400, f"Ukuran file maksimal {max_mb} MB")
    ext = allowed[ctype]
    if not any(data.startswith(m) for m in MAGIC[ext]) or (ext == "webp" and data[8:12] != b"WEBP"):
        raise HTTPException(400, f"Isi file {file.filename} tidak sesuai dengan tipenya")
    path = f"{PREFIX}/{folder}/{uuid.uuid4().hex}.{ext}"
    try:
        result = await asyncio.to_thread(_put, path, data, ctype)
    except Exception:  # noqa: BLE001
        raise HTTPException(502, "Penyimpanan file sedang bermasalah, coba lagi")
    return {"storage_path": result["path"], "content_type": ctype, "size": len(data), "original_filename": (file.filename or "")[:120]}


async def load(path):
    try:
        return await asyncio.to_thread(_get, path)
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "File tidak ditemukan")
