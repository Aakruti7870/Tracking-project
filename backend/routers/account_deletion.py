"""Verified account-deletion request workflow.

Signed-in users can create/cancel deletion requests. Logged-out users can also
initiate deletion after proving account ownership with the same one-time-code
challenge used by sign-in, without creating a login session. Central Admin can
complete a request after operational/legal checks. Completion revokes sessions
and anonymizes the login identity while retaining transaction records that may
be required for statutory/accounting purposes.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid
from database import (
    account_deletion_requests,
    customer_sites,
    notifications,
    otps,
    plants,
    sessions,
    users,
)
from push_notifications import device_push_tokens
from roles import Role
from security import (
    as_aware,
    current_user,
    identifier_key,
    normalize_identifier,
    require_role,
    utcnow,
    verify_code,
)

router = APIRouter(prefix="/api/account-deletion", tags=["account-deletion"])


class DeletionRequestBody(BaseModel):
    confirm: Literal["DELETE"]
    reason: Optional[str] = Field(default=None, max_length=2000)


class PublicDeletionRequestBody(DeletionRequestBody):
    identifier: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=4, max_length=8)


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


async def _create_request_for_user(user: dict, reason: str | None):
    user_id = str(user["_id"])
    if user.get("status") == "deleted":
        raise HTTPException(409, "Account is already deleted")
    existing = await account_deletion_requests.find_one({"user_id": user_id, "status": "PENDING"})
    if existing:
        return existing, True
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "user_name": user.get("name"),
        "role": user.get("primary_role"),
        "reason": reason,
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await account_deletion_requests.insert_one(doc)
    except DuplicateKeyError:
        existing = await account_deletion_requests.find_one({"user_id": user_id, "status": "PENDING"})
        return existing, True
    doc["_id"] = result.inserted_id
    return doc, False


@router.get("/status")
async def deletion_status(ctx: dict = Depends(current_user)):
    doc = await account_deletion_requests.find_one(
        {"user_id": ctx["user_id"]}, sort=[("created_at", -1)]
    )
    return {"request": _serialize(doc)}


@router.post("/request")
async def request_deletion(body: DeletionRequestBody, ctx: dict = Depends(current_user)):
    doc, idempotent = await _create_request_for_user(ctx["user"], body.reason)
    if not idempotent:
        await write_audit(ctx["user_id"], "account_deletion.request", "user", ctx["user_id"], {"request_id": str(doc["_id"])})
    return {"request": _serialize(doc), "idempotent": idempotent}


@router.post("/public-request")
async def public_request_deletion(body: PublicDeletionRequestBody):
    """Create a deletion request without login after OTP ownership verification."""
    _channel, value = normalize_identifier(body.identifier)
    key = identifier_key(value)
    user = await users.find_one({"identifier_keys": key})
    if not user:
        raise HTTPException(404, "No account found for this mobile number or email")
    if user.get("status") == "deleted":
        raise HTTPException(409, "Account is already deleted")

    doc = await otps.find_one(
        {"identifier_key": key, "consumed": False}, sort=[("created_at", -1)]
    )
    if not doc or as_aware(doc["expires_at"]) <= utcnow():
        raise HTTPException(400, "Invalid or expired code")
    if doc.get("attempts", 0) >= 5:
        raise HTTPException(429, "Too many attempts. Request a new code")

    if not verify_code(body.code, doc["code_hash"], str(doc["_id"])):
        attempted = await otps.find_one_and_update(
            {"_id": doc["_id"], "consumed": False, "attempts": {"$lt": 5}, "expires_at": {"$gt": utcnow()}},
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not attempted or attempted.get("attempts", 0) >= 5:
            raise HTTPException(429, "Too many attempts. Request a new code")
        raise HTTPException(400, "Invalid or expired code")

    consumed = await otps.find_one_and_update(
        {"_id": doc["_id"], "consumed": False, "attempts": {"$lt": 5}, "expires_at": {"$gt": utcnow()}},
        {"$set": {"consumed": True, "consumed_at": utcnow(), "consumed_for": "account_deletion"}},
        return_document=ReturnDocument.AFTER,
    )
    if not consumed:
        raise HTTPException(400, "Invalid or expired code")

    request_doc, idempotent = await _create_request_for_user(user, body.reason)
    if not idempotent:
        user_id = str(user["_id"])
        await write_audit(user_id, "account_deletion.public_request", "user", user_id, {"request_id": str(request_doc["_id"])})
    return {"request": _serialize(request_doc), "idempotent": idempotent}


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

    if user.get("primary_role") == Role.PLANT_OWNER.value:
        owned = await plants.count_documents({"owner_id": request["user_id"], "status": {"$ne": "disabled"}})
        if owned:
            raise HTTPException(409, "Transfer or disable owned plants before completing account deletion")

    now = datetime.now(timezone.utc)
    anonymized_name = f"Deleted User {request['user_id'][-6:]}"
    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "name": anonymized_name,
            "email": None,
            "phone": None,
            "identifier_keys": [],
            "roles": [],
            "primary_role": "deleted",
            "status": "deleted",
            "plant_id": None,
            "deleted_at": now,
        }},
    )
    await sessions.update_many({"user_id": request["user_id"]}, {"$set": {"revoked": True, "revoked_at": now}})
    await customer_sites.delete_many({"customer_id": request["user_id"]})
    await notifications.delete_many({"user_id": request["user_id"]})
    await device_push_tokens.delete_many({"user_id": request["user_id"]})
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
