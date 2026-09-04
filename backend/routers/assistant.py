"""Server-authorized conversational order and customer-support tools."""
from datetime import datetime, timezone
import re
from secrets import token_urlsafe
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from database import db, kyc_profiles, orders
from models import CreateOrderBody
from routers.customer import create_order, customer_only, _oid, _serialize_order
from roles import Role
from security import require_role
from validation import StrictModel

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
order_intents = db.assistant_order_intents
support_cases = db.support_cases

SUPPORT_ROUTES = {
    "LOGIN": {"action": "OPEN_SECURE_LOGIN_HELP", "guidance": "Use secure sign-in recovery in the app. Never share an OTP, password, passkey, or recovery code."},
    "KYC": {"action": "OPEN_KYC", "guidance": "Review or restart KYC in the secure in-app KYC flow."},
    "ORDER": {"action": "OPEN_ORDERS", "guidance": "Review the authorized order details and plant status in My Orders."},
    "TRACKING": {"action": "OPEN_TRACKING", "guidance": "Live tracking is available only for your authorized dispatched order."},
    "PAYMENT": {"action": "OPEN_PAYMENTS", "guidance": "Review payment status in the app; never send payment credentials in chat."},
    "ACCOUNT_DELETION": {"action": "OPEN_ACCOUNT_DELETION", "guidance": "Start the authenticated account-deletion flow from Settings."},
    "PLANT_ONBOARDING": {"action": "OPEN_PLANT_ONBOARDING", "guidance": "Submit a plant inquiry through the verified onboarding flow."},
    "GENERAL": {"action": "OPEN_HELP", "guidance": "Describe the app issue without including credentials or payment secrets."},
}

SAFE_SECRET_MESSAGE = "Remove credentials, security codes, or secret tokens from the support message"

# Require either a credential label or a strong, recognizable secret structure. This
# avoids rejecting ordinary sentences such as "My password reset screen is blank."
SECRET_PATTERNS = (
    re.compile(r"\b(?:my\s+)?(?:otp|password|passkey|pin|cvv)\s*(?:is|[:=\-])\s*\S+", re.I),
    re.compile(r"\brecovery\s*code\s*(?:is|[:=\-])?\s*[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+", re.I),
    re.compile(r"\b(?:api|access|refresh|authorization|secret)\s*(?:key|token)\s*(?:is|[:=\-])\s*\S+", re.I),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:card|credit|debit)\b[^\n]{0,30}\b(?:\d[ -]?){13,19}\b", re.I),
)


def _safe_support_message(value: str) -> str:
    stripped = value.strip()
    if any(pattern.search(stripped) for pattern in SECRET_PATTERNS):
        raise ValueError(SAFE_SECRET_MESSAGE)
    return stripped


class PrepareOrderBody(StrictModel):
    order: CreateOrderBody


class ConfirmOrderBody(StrictModel):
    intent_token: str = Field(min_length=24, max_length=256)
    confirmed: bool


class SupportBody(StrictModel):
    category: Literal["LOGIN", "KYC", "ORDER", "TRACKING", "PAYMENT", "ACCOUNT_DELETION", "PLANT_ONBOARDING", "GENERAL"]
    message: str = Field(min_length=1, max_length=1000)
    order_id: Optional[str] = Field(default=None, max_length=128)
    escalate: bool = False
    request_id: Optional[str] = Field(default=None, min_length=12, max_length=128)

    @field_validator("message")
    @classmethod
    def reject_credentials(cls, value: str) -> str:
        return _safe_support_message(value)


class CaseReplyBody(StrictModel):
    message: str = Field(min_length=1, max_length=1000)
    internal: bool = False

    _reject_credentials = field_validator("message")(SupportBody.reject_credentials.__func__)


class CaseStatusBody(StrictModel):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]


support_staff = require_role(Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value)


def _public_case(case: dict, *, staff: bool = False) -> dict:
    messages = [m for m in case.get("messages", []) if staff or not m.get("internal")]
    return {
        "id": str(case["_id"]), "case_number": case["case_number"],
        "category": case["category"], "order_id": case.get("order_id"),
        "status": case.get("status", "OPEN"), "created_at": case.get("created_at"),
        "updated_at": case.get("updated_at", case.get("created_at")),
        "messages": messages,
        "latest_note": messages[-1].get("message") if messages else None,
    }


@router.post("/orders/prepare")
async def prepare_order(body: PrepareOrderBody, ctx: dict = Depends(customer_only)):
    kyc = await kyc_profiles.find_one({"user_id": ctx["user_id"], "purpose": "CUSTOMER"})
    if (kyc or {}).get("status") != "VERIFIED":
        raise HTTPException(403, "KYC_REQUIRED")
    if not body.order.idempotency_key:
        raise HTTPException(422, "idempotency_key is required")
    existing = await orders.find_one({"customer_id": ctx["user_id"], "idempotency_key": body.order.idempotency_key})
    if existing:
        return {"already_created": True, "order": _serialize_order(existing)}
    token = token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await order_intents.update_one(
        {"customer_id": ctx["user_id"], "idempotency_key": body.order.idempotency_key},
        {"$setOnInsert": {"customer_id": ctx["user_id"], "idempotency_key": body.order.idempotency_key,
         "token": token, "order": body.order.model_dump(), "state": "AWAITING_CONFIRMATION", "created_at": now}},
        upsert=True,
    )
    intent = await order_intents.find_one({"customer_id": ctx["user_id"], "idempotency_key": body.order.idempotency_key})
    safe = body.order.model_dump(exclude={"contact_person", "contact_mobile", "notes"})
    return {"intent_token": intent["token"], "requires_confirmation": True, "summary": safe}


@router.post("/orders/confirm")
async def confirm_order(body: ConfirmOrderBody, ctx: dict = Depends(customer_only)):
    if not body.confirmed:
        raise HTTPException(409, "Explicit customer confirmation is required")
    intent = await order_intents.find_one({"token": body.intent_token, "customer_id": ctx["user_id"]})
    if not intent:
        raise HTTPException(404, "Order intent not found")
    result = await create_order(CreateOrderBody(**intent["order"]), ctx)
    await order_intents.update_one({"_id": intent["_id"]}, {"$set": {"state": "COMPLETED", "order_id": result["id"]}})
    return result


@router.post("/support")
async def support(body: SupportBody, ctx: dict = Depends(customer_only)):
    order = None
    if body.order_id:
        order = await orders.find_one({"_id": await _oid(body.order_id),
                                       "customer_id": ctx["user_id"]})
        if not order:
            raise HTTPException(404, "Order not found")
    now = datetime.now(timezone.utc)
    route = SUPPORT_ROUTES[body.category]
    response = {"category": body.category, **route}
    if order:
        response["order"] = _serialize_order(order)
    if body.escalate:
        existing = None
        if body.request_id:
            existing = await support_cases.find_one({"customer_id": ctx["user_id"],
                                                     "request_id": body.request_id})
        if existing:
            response.update({"case_id": str(existing["_id"]),
                             "case_number": existing["case_number"],
                             "case_status": existing.get("status", "OPEN")})
            return response
        case = {"case_number": "SUP-" + token_urlsafe(6), "customer_id": ctx["user_id"],
                "category": body.category, "message": body.message, "order_id": body.order_id,
                "status": "OPEN", "created_at": now,
                "updated_at": now, "messages": [{"message": body.message, "author": "CUSTOMER",
                                                   "internal": False, "created_at": now}]}
        if body.request_id:
            case["request_id"] = body.request_id
        try:
            inserted = await support_cases.insert_one(case)
            response["case_id"] = str(inserted.inserted_id)
        except DuplicateKeyError:
            existing = await support_cases.find_one({"customer_id": ctx["user_id"],
                                                     "request_id": body.request_id})
            if not existing:
                raise
            response.update({"case_id": str(existing["_id"]),
                             "case_number": existing["case_number"],
                             "case_status": existing.get("status", "OPEN")})
            return response
        response["case_number"] = case["case_number"]
        response["case_status"] = "OPEN"
        await write_audit(ctx["user_id"], "support.case.create", "support_case", response["case_id"], {"category": body.category})
    return response


@router.get("/support/cases")
async def list_my_cases(ctx: dict = Depends(customer_only)):
    rows = await support_cases.find({"customer_id": ctx["user_id"]}).sort("created_at", -1).to_list(200)
    return {"cases": [_public_case(row) for row in rows]}


@router.get("/support/cases/{case_id}")
async def get_my_case(case_id: str, ctx: dict = Depends(customer_only)):
    row = await support_cases.find_one({"_id": await _oid(case_id), "customer_id": ctx["user_id"]})
    if not row:
        raise HTTPException(404, "Support case not found")
    return {"case": _public_case(row)}


@router.post("/support/cases/{case_id}/replies")
async def reply_to_my_case(case_id: str, body: CaseReplyBody, ctx: dict = Depends(customer_only)):
    if body.internal:
        raise HTTPException(403, "Customers cannot create internal notes")
    now = datetime.now(timezone.utc)
    result = await support_cases.update_one(
        {"_id": await _oid(case_id), "customer_id": ctx["user_id"],
         "status": {"$in": ["OPEN", "IN_PROGRESS"]}},
        {"$push": {"messages": {"message": body.message, "author": "CUSTOMER",
                                  "internal": False, "created_at": now}},
         "$set": {"updated_at": now}},
    )
    if result.modified_count != 1:
        raise HTTPException(409, "Support case is unavailable or closed")
    return {"status": "RECEIVED"}


@router.get("/support/staff/cases")
async def list_support_cases(ctx: dict = Depends(support_staff)):
    rows = await support_cases.find({}).sort("created_at", -1).to_list(500)
    return {"cases": [_public_case(row, staff=True) for row in rows]}


@router.get("/support/staff/cases/{case_id}")
async def get_support_case(case_id: str, ctx: dict = Depends(support_staff)):
    row = await support_cases.find_one({"_id": await _oid(case_id)})
    if not row:
        raise HTTPException(404, "Support case not found")
    return {"case": _public_case(row, staff=True)}


@router.patch("/support/staff/cases/{case_id}/status")
async def set_support_case_status(case_id: str, body: CaseStatusBody,
                                  ctx: dict = Depends(support_staff)):
    now = datetime.now(timezone.utc)
    result = await support_cases.update_one({"_id": await _oid(case_id)},
                                            {"$set": {"status": body.status, "updated_at": now}})
    if result.matched_count != 1:
        raise HTTPException(404, "Support case not found")
    await write_audit(ctx["user_id"], "support.case.status", "support_case", case_id,
                      {"status": body.status})
    return {"status": body.status}


@router.post("/support/staff/cases/{case_id}/replies")
async def reply_to_support_case(case_id: str, body: CaseReplyBody,
                                ctx: dict = Depends(support_staff)):
    now = datetime.now(timezone.utc)
    result = await support_cases.update_one(
        {"_id": await _oid(case_id)},
        {"$push": {"messages": {"message": body.message, "author": "SUPPORT",
                                  "internal": body.internal, "created_at": now}},
         "$set": {"updated_at": now}},
    )
    if result.matched_count != 1:
        raise HTTPException(404, "Support case not found")
    await write_audit(ctx["user_id"], "support.case.reply", "support_case", case_id,
                      {"internal": body.internal})
    return {"status": "RECEIVED"}
