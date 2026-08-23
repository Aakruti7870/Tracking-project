"""Verified account-deletion request workflow.

A signed-in user can create/cancel a deletion request. Central Admin can complete
it after operational/legal checks. Completion revokes sessions and anonymizes
the login identity while retaining transaction records that may be required for
statutory/accounting purposes.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid
from database import (
    account_deletion_requests,
    customer_sites,
    notifications,
    plants,
    sessions,
    users,
)
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/account-deletion", tags=["account-deletion"])


class DeletionRequestBody(BaseModel):
    confirm: Literal["DELETE"]
    reason: Optional[str] = Field(default=None, max_length=2000)


class CompleteDeletionBody(BaseModel):
    note: str = Field(min_length=3, max_length=3000)


central_admin_only = require_role(Role.CENTRAL_ADMIN.value)


def _serialize(doc: dict | None):
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": doc.get("user_id"),
        "user_name": doc.get("user_name"),
        "role": doc.get("role"),
        "status": doc.get("status"),
        "reason": doc.get("reason"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        "completed_at": doc.get("completed_at").isoformat() if doc.get("completed_at") else None,
        "completion_note": doc.get("completion_note"),
    }


@router.get("/status")
async def deletion_status(ctx: dict = Depends(current_user)):
    doc = await account_deletion_requests.find_one(
        {"user_id": ctx["user_id"]}, sort=[("created_at", -1)]
    )
    return {"request": _serialize(doc)}


@router.post("/request")
async def request_deletion(body: DeletionRequestBody, ctx: dict = Depends(current_user)):
    if ctx["user"].get("status") == "deleted":
        raise HTTPException(409, "Account is already deleted")
    existing = await account_deletion_requests.find_one({"user_id": ctx["user_id"], "status": "PENDING"})
    if existing:
        return {"request": _serialize(existing), "idempotent": True}
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": ctx["user_id"],
        "user_name": ctx["user"].get("name"),
        "role": ctx.get("role"),
        "reason": body.reason,
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await account_deletion_requests.insert_one(doc)
    except DuplicateKeyError:
        existing = await account_deletion_requests.find_one({"user_id": ctx["user_id"], "status": "PENDING"})
        return {"request": _serialize(existing), "idempotent": True}
    doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "account_deletion.request", "user", ctx["user_id"], {"request_id": str(result.inserted_id)})
    return {"request": _serialize(doc)}


@router.post("/cancel")
async def cancel_deletion(ctx: dict = Depends(current_user)):
    now = datetime.now(timezone.utc)
    result = await account_deletion_requests.update_one(
        {"user_id": ctx["user_id"], "status": "PENDING"},
        {"$set": {"status": "CANCELLED", "updated_at": now, "cancelled_at": now}},
    )
    if result.modified_count != 1:
        raise HTTPException(404, "No pending deletion request")
    await write_audit(ctx["user_id"], "account_deletion.cancel", "user", ctx["user_id"])
    return {"status": "CANCELLED"}


@router.get("/requests")
async def list_deletion_requests(ctx: dict = Depends(central_admin_only)):
    docs = await account_deletion_requests.find({}).sort("created_at", -1).to_list(2000)
    return {"requests": [_serialize(d) for d in docs]}


@router.post("/requests/{request_id}/complete")
async def complete_deletion(
    request_id: str,
    body: CompleteDeletionBody,
    ctx: dict = Depends(central_admin_only),
):
    request = await account_deletion_requests.find_one({"_id": oid(request_id), "status": "PENDING"})
    if not request:
        raise HTTPException(404, "Pending deletion request not found")
    user = await users.find_one({"_id": oid(request["user_id"])})
    if not user:
        raise HTTPException(404, "User not found")

    # Plant ownership is a business/legal relationship and cannot be silently
    # orphaned by identity deletion. Force ownership transfer/plant closure first.
    if user.get("primary_role") == Role.PLANT_OWNER.value:
        owned = await plants.count_documents({"owner_id": request["user_id"], "status": {"$ne": "disabled"}})
        if owned:
            raise HTTPException(409, "Transfer or disable owned plants before completing account deletion")

    now = datetime.now(timezone.utc)
    anonymized_name = f"Deleted User {request['user_id'][-6:]}"
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "name": anonymized_name,
                "email": None,
                "phone": None,
                "identifier_keys": [],
                "roles": [],
                "primary_role": "deleted",
                "status": "deleted",
                "plant_id": None,
                "deleted_at": now,
            }
        },
    )
    await sessions.update_many({"user_id": request["user_id"]}, {"$set": {"revoked": True, "revoked_at": now}})
    await customer_sites.delete_many({"customer_id": request["user_id"]})
    await notifications.delete_many({"user_id": request["user_id"]})
    await account_deletion_requests.update_one(
        {"_id": request["_id"], "status": "PENDING"},
        {"$set": {
            "status": "COMPLETED",
            "updated_at": now,
            "completed_at": now,
            "completed_by": ctx["user_id"],
            "completion_note": body.note,
            "retained_records": "statutory_transaction_records",
        }},
    )
    await write_audit(
        ctx["user_id"], "account_deletion.complete", "user", request["user_id"],
        {"request_id": request_id, "retained_records": "statutory_transaction_records"},
    )
    return {"status": "COMPLETED"}
