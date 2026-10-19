from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import os, uuid, httpx
from core import db, public, now

router = APIRouter()
SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


class OAuthSession(BaseModel):
    session_id: str


def admin_emails():
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


@router.post("/auth/session")
async def auth_session(payload: OAuthSession, response: Response):
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            result = await http.get(SESSION_URL, headers={"X-Session-ID": payload.session_id})
        if result.status_code >= 400:
            raise HTTPException(401, "Sesi Google tidak valid atau sudah kedaluwarsa")
        data = result.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Sesi Google tidak dapat diverifikasi")
    if not isinstance(data, dict) or not data.get("email") or not data.get("session_token"):
        raise HTTPException(401, "Respons autentikasi Google tidak lengkap")
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": data.get("name") or "Pengguna Jasa Kamera", "picture": data.get("picture", ""), "role": "customer", "created_at": now()}
        await db.users.insert_one(dict(user))
    updates = {"picture": data.get("picture", user.get("picture", ""))}
    if email in admin_emails():
        updates["role"] = "admin"
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    user.update(updates)
    token = data["session_token"]
    await db.user_sessions.delete_many({"user_id": user["user_id"]})
    await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token, "expires_at": datetime.now(timezone.utc) + timedelta(days=7), "created_at": now()})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return public(user)


async def current_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(401, "Silakan masuk terlebih dahulu")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(401, "Sesi berakhir")
    expires = session["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(401, "Sesi berakhir")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Pengguna tidak ditemukan")
    return user


def require_role(*roles):
    async def dep(request: Request):
        user = await current_user(request)
        if user.get("role", "customer") not in roles:
            raise HTTPException(403, "Akses tidak diizinkan untuk peran ini")
        return user
    return dep


@router.get("/auth/me")
async def auth_me(request: Request):
    return public(await current_user(request))


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}
