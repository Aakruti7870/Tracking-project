"""Plant Premium subscriptions, promoted listings and Authority promo codes.

Premium and Promotion are intentionally independent products. Paid self-service
creates a payment order; entitlements are activated only by a verified payment
webhook or an audited Authority action.
"""
from datetime import datetime, timedelta, timezone
from secrets import token_hex

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from audit import write_audit
from database import (
    plan_payment_orders,
    plant_plan_subscriptions,
    plant_promotions,
    plants,
    promotion_codes,
)
from roles import Role
from security import current_user

router = APIRouter(prefix="/api/plant-plans", tags=["plant-plans"])
ALLOWED_ROLES = {Role.PLANT_OWNER.value, Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}

PROMOTION_PRICES = {7: 2500, 15: 4000, 30: 6000}
PREMIUM_PLANS = {
    "LAUNCH": {"months": 3, "price": 64500},
    "GROWTH": {"months": 6, "price": 129000},
    "SIGNATURE": {"months": 12, "price": 258000},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(422, "Invalid plant id")


async def allowed_ctx(ctx: dict = Depends(current_user)) -> dict:
    if ctx["role"] not in ALLOWED_ROLES:
        raise HTTPException(403, "Plant Owner or Authority access required")
    return ctx


async def scoped_plant(plant_id: str, ctx: dict) -> dict:
    plant = await plants.find_one({"_id": oid(plant_id), "status": {"$ne": "deleted"}})
    if not plant:
        raise HTTPException(404, "Plant not found")
    if ctx["role"] == Role.PLANT_OWNER.value and str(plant.get("owner_id")) != ctx["user_id"]:
        raise HTTPException(403, "This plant is not assigned to your owner account")
    return plant


def quote_amount(price: int, code: dict | None) -> tuple[int, int]:
    if not code:
        return price, 0
    if code.get("discount_type") == "PERCENT":
        discount = round(price * min(100, int(code.get("discount_value", 0))) / 100)
    else:
        discount = min(price, int(code.get("discount_value", 0)))
    return max(0, price - discount), discount


async def valid_code(raw: str | None, product: str) -> dict | None:
    if not raw:
        return None
    code = await promotion_codes.find_one({"code": raw.strip().upper(), "active": True})
    now = now_utc()
    if not code or code.get("product") not in (product, "ALL"):
        raise HTTPException(422, "Promo code is invalid for this plan")
    if code.get("starts_at") and code["starts_at"].replace(tzinfo=timezone.utc) > now:
        raise HTTPException(422, "Promo code is not active yet")
    if code.get("ends_at") and code["ends_at"].replace(tzinfo=timezone.utc) < now:
        raise HTTPException(422, "Promo code has expired")
    if code.get("max_uses") is not None and code.get("uses", 0) >= code["max_uses"]:
        raise HTTPException(422, "Promo code usage limit has been reached")
    return code


def serialize_active(doc: dict | None) -> dict | None:
    if not doc:
        return None
    return {
        "id": str(doc["_id"]), "status": doc.get("status"), "plan": doc.get("plan"),
        "starts_at": doc.get("starts_at"), "ends_at": doc.get("ends_at"),
        "activation_mode": doc.get("activation_mode"),
    }


@router.get("/context")
async def context(ctx: dict = Depends(allowed_ctx)):
    query = {} if ctx["role"] in (Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value) else {"owner_id": ctx["user_id"]}
    rows = await plants.find({**query, "status": {"$ne": "deleted"}}).sort("name", 1).to_list(500)
    result = []
    now = now_utc()
    for plant in rows:
        pid = str(plant["_id"])
        premium = await plant_plan_subscriptions.find_one({"plant_id": pid, "status": "ACTIVE", "ends_at": {"$gt": now}}, sort=[("ends_at", -1)])
        promotion = await plant_promotions.find_one({"plant_id": pid, "status": "ACTIVE", "ends_at": {"$gt": now}}, sort=[("ends_at", -1)])
        result.append({"id": pid, "name": plant.get("name"), "city": plant.get("city"), "premium": serialize_active(premium), "promotion": serialize_active(promotion)})
    return {"role": ctx["role"], "plants": result, "promotion_prices": PROMOTION_PRICES, "premium_plans": PREMIUM_PLANS}


class QuoteBody(BaseModel):
    plant_id: str
    product: str = Field(pattern="^(PROMOTION|PREMIUM)$")
    duration_days: int | None = None
    premium_plan: str | None = None
    promo_code: str | None = Field(default=None, max_length=40)


def product_price(body: QuoteBody) -> tuple[int, str]:
    if body.product == "PROMOTION":
        if body.duration_days not in PROMOTION_PRICES:
            raise HTTPException(422, "Promotion duration must be 7, 15 or 30 days")
        return PROMOTION_PRICES[body.duration_days], f"{body.duration_days}_DAYS"
    plan = (body.premium_plan or "").upper()
    if plan not in PREMIUM_PLANS:
        raise HTTPException(422, "Premium plan must be LAUNCH, GROWTH or SIGNATURE")
    return PREMIUM_PLANS[plan]["price"], plan


@router.post("/quote")
async def quote(body: QuoteBody, ctx: dict = Depends(allowed_ctx)):
    await scoped_plant(body.plant_id, ctx)
    price, plan = product_price(body)
    code = await valid_code(body.promo_code, body.product)
    payable, discount = quote_amount(price, code)
    return {"product": body.product, "plan": plan, "price": price, "discount": discount, "payable": payable, "promo_code": code.get("code") if code else None}


class ActivateBody(QuoteBody):
    activation_mode: str = Field(pattern="^(ONLINE_PAYMENT|OFFLINE_PAYMENT|AUTHORITY_FREE)$")
    payment_reference: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=500)


@router.post("/activate")
async def activate(body: ActivateBody, ctx: dict = Depends(allowed_ctx)):
    plant = await scoped_plant(body.plant_id, ctx)
    authority = ctx["role"] in (Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value)
    if body.activation_mode in ("OFFLINE_PAYMENT", "AUTHORITY_FREE") and not authority:
        raise HTTPException(403, "Only Authority can activate free or verify offline payment")
    if body.activation_mode == "AUTHORITY_FREE" and not (body.reason or "").strip():
        raise HTTPException(422, "Reason is required for free activation")
    if body.activation_mode == "OFFLINE_PAYMENT" and not (body.payment_reference or "").strip():
        raise HTTPException(422, "Payment reference is required for offline activation")

    price, plan = product_price(body)
    code = await valid_code(body.promo_code, body.product)
    payable, discount = quote_amount(price, code)
    now = now_utc()

    # Owner self-service never grants an entitlement merely because the app
    # created an order. A payment provider webhook must activate it later.
    if body.activation_mode == "ONLINE_PAYMENT":
        order_number = f"PLAN-{now:%Y%m%d}-{token_hex(4).upper()}"
        doc = {"order_number": order_number, "plant_id": body.plant_id, "owner_id": str(plant.get("owner_id") or ""), "product": body.product, "plan": plan, "price": price, "discount": discount, "payable": payable, "promo_code": code.get("code") if code else None, "status": "PAYMENT_PENDING", "created_by": ctx["user_id"], "created_at": now, "updated_at": now}
        await plan_payment_orders.insert_one(doc)
        return {"status": "PAYMENT_PENDING", "order_number": order_number, "payable": payable, "message": "Payment order created. Entitlement activates only after verified payment."}

    if body.product == "PROMOTION":
        days = int(plan.split("_")[0])
        ends = now + timedelta(days=days)
        collection = plant_promotions
    else:
        ends = now + timedelta(days=PREMIUM_PLANS[plan]["months"] * 30)
        collection = plant_plan_subscriptions
    await collection.update_many({"plant_id": body.plant_id, "status": "ACTIVE"}, {"$set": {"status": "SUPERSEDED", "updated_at": now}})
    activation = {"plant_id": body.plant_id, "product": body.product, "plan": plan, "status": "ACTIVE", "starts_at": now, "ends_at": ends, "price": price, "discount": discount, "payable": 0 if body.activation_mode == "AUTHORITY_FREE" else payable, "promo_code": code.get("code") if code else None, "activation_mode": body.activation_mode, "payment_reference": body.payment_reference, "reason": body.reason, "activated_by": ctx["user_id"], "created_at": now, "updated_at": now}
    result = await collection.insert_one(activation)
    if code:
        await promotion_codes.update_one({"_id": code["_id"]}, {"$inc": {"uses": 1}})
    await write_audit(ctx["user_id"], f"plant_{body.product.lower()}.activate", "plant", body.plant_id, {"activation_id": str(result.inserted_id), "plan": plan, "mode": body.activation_mode, "reason": body.reason})
    return {"status": "ACTIVE", "id": str(result.inserted_id), "starts_at": now, "ends_at": ends}


class PromoCodeBody(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    product: str = Field(pattern="^(PROMOTION|PREMIUM|ALL)$")
    discount_type: str = Field(pattern="^(PERCENT|FIXED)$")
    discount_value: int = Field(gt=0)
    max_uses: int | None = Field(default=None, gt=0)
    ends_at: datetime


@router.post("/promo-codes")
async def create_promo_code(body: PromoCodeBody, ctx: dict = Depends(allowed_ctx)):
    if ctx["role"] not in (Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value):
        raise HTTPException(403, "Only Authority can create promo codes")
    if body.discount_type == "PERCENT" and body.discount_value > 100:
        raise HTTPException(422, "Percentage discount cannot exceed 100")
    code = body.code.upper()
    if await promotion_codes.find_one({"code": code}):
        raise HTTPException(409, "Promo code already exists")
    now = now_utc()
    result = await promotion_codes.insert_one({**body.model_dump(), "code": code, "active": True, "uses": 0, "starts_at": now, "created_by": ctx["user_id"], "created_at": now, "updated_at": now})
    await write_audit(ctx["user_id"], "promo_code.create", "promotion_code", str(result.inserted_id), {"code": code, "product": body.product})
    return {"id": str(result.inserted_id), "code": code, "active": True}
