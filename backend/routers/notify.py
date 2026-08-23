"""Durable notification feed plus authenticated native push-token lifecycle."""
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from database import notifications
from push_notifications import device_push_tokens, ensure_push_indexes
from security import current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class DeviceTokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: Literal["android", "ios"] = "android"
    device_id: Optional[str] = Field(default=None, max_length=256)
    app_version: Optional[str] = Field(default=None, max_length=64)


class DeviceTokenRemoveBody(BaseModel):
    token: str = Field(min_length=20, max_length=4096)


@router.on_event("startup")
async def initialize_push_token_indexes():
    await ensure_push_indexes()


async def _oid(v: str):
    try:
        return ObjectId(v)
    except Exception:
        return v


@router.post("/device/register")
async def register_device_token(body: DeviceTokenBody, ctx: dict = Depends(current_user)):
    now = datetime.now(timezone.utc)
    await device_push_tokens.update_one(
        {"token": body.token},
        {
            "$set": {
                "user_id": ctx["user_id"],
                "platform": body.platform,
                "device_id": body.device_id,
                "app_version": body.app_version,
                "active": True,
                "updated_at": now,
                "last_seen_at": now,
            },
            "$setOnInsert": {"created_at": now},
            "$unset": {"invalidated_at": ""},
        },
        upsert=True,
    )
    return {"ok": True}


@router.post("/device/unregister")
async def unregister_device_token(body: DeviceTokenRemoveBody, ctx: dict = Depends(current_user)):
    now = datetime.now(timezone.utc)
    await device_push_tokens.update_one(
        {"token": body.token, "user_id": ctx["user_id"]},
        {"$set": {"active": False, "updated_at": now, "unregistered_at": now}},
    )
    return {"ok": True}


@router.get("")
async def list_notifications(ctx: dict = Depends(current_user)):
    docs = await notifications.find({"user_id": ctx["user_id"]}).sort("created_at", -1).to_list(200)
    unread = await notifications.count_documents({"user_id": ctx["user_id"], "read": False})
    return {
        "unread": unread,
        "items": [
            {
                "id": str(d["_id"]),
                "event": d.get("event"),
                "title": d.get("title"),
                "body": d.get("body"),
                "data": d.get("data") or {},
                "read": d.get("read", False),
                "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
            }
            for d in docs
        ],
    }


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, ctx: dict = Depends(current_user)):
    await notifications.update_one(
        {"_id": await _oid(notification_id), "user_id": ctx["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(ctx: dict = Depends(current_user)):
    await notifications.update_many(
        {"user_id": ctx["user_id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True}
