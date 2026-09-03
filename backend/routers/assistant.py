"""Server-authorized conversational order and customer-support tools."""
from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from audit import write_audit
from database import db, kyc_profiles, orders
from models import CreateOrderBody
from routers.customer import create_order, customer_only, _oid, _serialize_order
from validation import StrictModel

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
order_intents = db.assistant_order_intents
support_cases = db.support_cases


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
    response = {"category": body.category, "guidance": "Use the secure in-app flow; never share passwords, OTPs, recovery codes, or payment secrets."}
    if order:
        response["order"] = _serialize_order(order)
    if body.escalate:
        case = {"case_number": "SUP-" + token_urlsafe(6), "customer_id": ctx["user_id"],
                "category": body.category, "message": body.message, "order_id": body.order_id,
                "status": "OPEN", "created_at": now}
        inserted = await support_cases.insert_one(case)
        response["case_id"] = str(inserted.inserted_id)
        await write_audit(ctx["user_id"], "support.case.create", "support_case", response["case_id"], {"category": body.category})
    return response
