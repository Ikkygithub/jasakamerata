from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from core import db, now, new_id, HIDDEN_LISTING
from auth import current_user

router = APIRouter()


class ConversationCreate(BaseModel):
    photographer_id: str


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def side(user):
    role = user.get("role", "customer")
    if role == "photographer":
        return "photographer", {"photographer_id": user.get("photographer_id", "-")}
    if role == "customer":
        return "customer", {"customer_id": user["user_id"]}
    raise HTTPException(403, "Chat hanya untuk customer dan fotografer")


async def load_conversation(cid, user):
    s, q = side(user)
    conv = await db.conversations.find_one({"conversation_id": cid, **q}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Percakapan tidak ditemukan")
    return s, conv


@router.post("/chat/conversations")
async def start_conversation(payload: ConversationCreate, user=Depends(current_user)):
    if side(user)[0] != "customer":
        raise HTTPException(403, "Hanya customer yang dapat memulai percakapan")
    existing = await db.conversations.find_one({"customer_id": user["user_id"], "photographer_id": payload.photographer_id}, {"_id": 0})
    if existing:
        return existing
    p = await db.photographers.find_one({"photographer_id": payload.photographer_id, "listing_status": {"$nin": HIDDEN_LISTING}}, {"_id": 0, "name": 1, "profile_image": 1, "slug": 1})
    if not p:
        raise HTTPException(404, "Fotografer tidak ditemukan")
    conv = {"conversation_id": new_id("conv"), "customer_id": user["user_id"], "customer_name": user.get("name", "Customer"), "customer_picture": user.get("picture", ""), "photographer_id": payload.photographer_id, "photographer_name": p["name"], "photographer_image": p.get("profile_image", ""), "photographer_slug": p["slug"], "last_message": "", "last_at": now(), "unread_customer": 0, "unread_photographer": 0, "created_at": now()}
    await db.conversations.insert_one(dict(conv))
    return conv


@router.get("/chat/conversations")
async def list_conversations(user=Depends(current_user)):
    _, q = side(user)
    return await db.conversations.find(q, {"_id": 0}).sort("last_at", -1).to_list(100)


@router.get("/chat/conversations/{cid}/messages")
async def list_messages(cid: str, user=Depends(current_user)):
    s, conv = await load_conversation(cid, user)
    await db.conversations.update_one({"conversation_id": cid}, {"$set": {f"unread_{s}": 0}})
    return await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(500)


@router.post("/chat/conversations/{cid}/messages")
async def send_message(cid: str, payload: MessageCreate, user=Depends(current_user)):
    s, conv = await load_conversation(cid, user)
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Pesan tidak boleh kosong")
    other = "photographer" if s == "customer" else "customer"
    msg = {"message_id": new_id("msg"), "conversation_id": cid, "sender_id": user["user_id"], "sender_role": s, "text": text, "created_at": now()}
    await db.messages.insert_one(dict(msg))
    await db.conversations.update_one({"conversation_id": cid}, {"$set": {"last_message": text[:120], "last_at": msg["created_at"]}, "$inc": {f"unread_{other}": 1}})
    return msg
