"""In-app notifications feed (durable records, available to every role)."""
from bson import ObjectId
from fastapi import APIRouter, Depends

from database import notifications
from security import current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def _oid(v: str):
    try:
        return ObjectId(v)
    except Exception:
        return v


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
