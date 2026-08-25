"""Plant Premium subscriptions, promoted listings and Authority promo codes.

Premium and Promotion are intentionally independent products. Paid self-service
creates a payment order; entitlements are activated only by a verified payment
webhook or an audited Authority action.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
from secrets import token_hex

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from audit import write_audit
from database import (
    audit_logs,
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


def cashfree_config() -> tuple[str, str, str]:
    app_id = os.getenv("CASHFREE_APP_ID", "").strip()
    secret = os.getenv("CASHFREE_SECRET_KEY", "").strip()
    environment = os.getenv("CASHFREE_ENV", "sandbox").strip().lower()
    if not app_id or not secret:
        raise HTTPException(503, "Cashfree payment gateway is not configured")
    if environment not in ("sandbox", "production"):
        raise HTTPException(503, "CASHFREE_ENV must be sandbox or production")
    return app_id, secret, environment


def verify_cashfree_signature(timestamp: str, raw_body: bytes, signature: str, secret: str) -> bool:
    if not timestamp or not signature:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)


async def grant_paid_entitlement(order: dict, payment_reference: str) -> str:
    """Idempotently grant exactly one entitlement for one verified payment."""
    if order.get("status") == "PAID" and order.get("activation_id"):
        return order["activation_id"]
    now = now_utc()
    if order["product"] == "PROMOTION":
        ends = now + timedelta(days=int(order["plan"].split("_")[0]))
        collection = plant_promotions
    else:
        ends = now + timedelta(days=PREMIUM_PLANS[order["plan"]]["months"] * 30)
        collection = plant_plan_subscriptions
    await collection.update_many({"plant_id": order["plant_id"], "status": "ACTIVE"}, {"$set": {"status": "SUPERSEDED", "updated_at": now}})
    result = await collection.insert_one({"plant_id": order["plant_id"], "product": order["product"], "plan": order["plan"], "status": "ACTIVE", "starts_at": now, "ends_at": ends, "price": order["price"], "discount": order["discount"], "payable": order["payable"], "promo_code": order.get("promo_code"), "activation_mode": "ONLINE_PAYMENT", "payment_reference": payment_reference, "activated_by": "cashfree_webhook", "created_at": now, "updated_at": now})
    activation_id = str(result.inserted_id)
    updated = await plan_payment_orders.update_one({"_id": order["_id"], "status": {"$ne": "PAID"}}, {"$set": {"status": "PAID", "activation_id": activation_id, "payment_reference": payment_reference, "paid_at": now, "updated_at": now}})
    if not updated.modified_count:
        await collection.delete_one({"_id": result.inserted_id})
        current = await plan_payment_orders.find_one({"_id": order["_id"]})
        return current.get("activation_id")
    if order.get("promo_code"):
        await promotion_codes.update_one({"code": order["promo_code"]}, {"$inc": {"uses": 1}})
    await write_audit("cashfree_webhook", f"plant_{order['product'].lower()}.activate", "plant", order["plant_id"], {"activation_id": activation_id, "order_number": order["order_number"], "payment_reference": payment_reference})
    return activation_id


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
        result.append({"id": pid, "name": plant.get("name"), "address": plant.get("address"), "city": plant.get("city"), "taluka": plant.get("taluka"), "district": plant.get("district"), "state": plant.get("state"), "premium": serialize_active(premium), "promotion": serialize_active(promotion)})
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
async def activate(body: ActivateBody, request: Request, ctx: dict = Depends(allowed_ctx)):
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
        if payable <= 0:
            raise HTTPException(422, "A zero-value plan must be activated by Authority")
        app_id, secret, environment = cashfree_config()
        order_number = f"PLAN-{now:%Y%m%d}-{token_hex(4).upper()}"
        doc = {"order_number": order_number, "plant_id": body.plant_id, "owner_id": str(plant.get("owner_id") or ""), "product": body.product, "plan": plan, "price": price, "discount": discount, "payable": payable, "promo_code": code.get("code") if code else None, "status": "PAYMENT_PENDING", "created_by": ctx["user_id"], "created_at": now, "updated_at": now}
        base = str(request.base_url).rstrip("/")
        cashfree_base = "https://sandbox.cashfree.com/pg" if environment == "sandbox" else "https://api.cashfree.com/pg"
        payload = {"order_id": order_number, "order_amount": payable, "order_currency": "INR", "customer_details": {"customer_id": ctx["user_id"][-40:], "customer_name": ctx["user"].get("name") or "Plant Owner", "customer_email": ctx["user"].get("email") or "payments@trackmyrmc.com", "customer_phone": ctx["user"].get("phone") or "9999999999"}, "order_meta": {"return_url": f"{base}/api/plant-plans/cashfree/return?order_id={{order_id}}", "notify_url": f"{base}/api/plant-plans/cashfree/webhook"}}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"{cashfree_base}/orders", headers={"x-client-id": app_id, "x-client-secret": secret, "x-api-version": "2025-01-01", "Content-Type": "application/json", "x-idempotency-key": token_hex(16)}, json=payload)
            response.raise_for_status()
            gateway = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "Cashfree could not create the payment session") from exc
        doc.update({"cashfree_order_id": gateway.get("order_id", order_number), "payment_session_id": gateway.get("payment_session_id")})
        await plan_payment_orders.insert_one(doc)
        return {"status": "PAYMENT_PENDING", "order_number": order_number, "payable": payable, "payment_session_id": gateway.get("payment_session_id"), "cashfree_environment": environment, "message": "Payment session created. Entitlement activates only after verified payment."}

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


@router.get("/authority-control")
async def authority_payment_control(ctx: dict = Depends(allowed_ctx)):
    """Read-only financial control centre for Authority and Central Admin."""
    if ctx["role"] not in (Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value):
        raise HTTPException(403, "Authority access required")

    plant_rows = await plants.find(
        {"status": {"$ne": "deleted"}},
        {"name": 1, "city": 1, "district": 1, "state": 1},
    ).to_list(500)
    plant_map = {
        str(row["_id"]): {
            "name": row.get("name") or "RMC Plant",
            "city": row.get("city"),
            "district": row.get("district"),
            "state": row.get("state"),
        }
        for row in plant_rows
    }

    online = await plan_payment_orders.find({}).sort("created_at", -1).to_list(500)
    premium = await plant_plan_subscriptions.find({}).sort("created_at", -1).to_list(500)
    promotions = await plant_promotions.find({}).sort("created_at", -1).to_list(500)
    promo_rows = await promotion_codes.find({}).sort("created_at", -1).to_list(500)
    audit_rows = await audit_logs.find({
        "action": {"$in": [
            "plant_premium.activate",
            "plant_promotion.activate",
            "promo_code.create",
        ]}
    }).sort("created_at", -1).to_list(500)

    def plant_info(plant_id: str | None) -> dict:
        return plant_map.get(plant_id or "", {"name": "RMC Plant", "city": None, "district": None, "state": None})

    def activation_row(row: dict, product: str) -> dict:
        info = plant_info(row.get("plant_id"))
        return {
            "id": str(row["_id"]),
            "plant_id": row.get("plant_id"),
            "plant_name": info["name"],
            "product": product,
            "plan": row.get("plan"),
            "status": row.get("status"),
            "activation_mode": row.get("activation_mode"),
            "price": row.get("price", 0),
            "discount": row.get("discount", 0),
            "payable": row.get("payable", 0),
            "promo_code": row.get("promo_code"),
            "payment_reference": row.get("payment_reference"),
            "reason": row.get("reason"),
            "activated_by": row.get("activated_by"),
            "starts_at": row.get("starts_at"),
            "ends_at": row.get("ends_at"),
            "created_at": row.get("created_at"),
        }

    return {
        "online_payments": [
            {
                "order_number": row.get("order_number"),
                "plant_id": row.get("plant_id"),
                "plant_name": plant_info(row.get("plant_id"))["name"],
                "product": row.get("product"),
                "plan": row.get("plan"),
                "status": row.get("status", "PAYMENT_PENDING"),
                "payable": row.get("payable", 0),
                "discount": row.get("discount", 0),
                "promo_code": row.get("promo_code"),
                "payment_reference": row.get("payment_reference"),
                "created_at": row.get("created_at"),
                "paid_at": row.get("paid_at"),
                "updated_at": row.get("updated_at"),
            }
            for row in online
        ],
        "activations": [
            *[activation_row(row, "PREMIUM") for row in premium],
            *[activation_row(row, "PROMOTION") for row in promotions],
        ],
        "promo_codes": [
            {
                "id": str(row["_id"]),
                "code": row.get("code"),
                "product": row.get("product"),
                "discount_type": row.get("discount_type"),
                "discount_value": row.get("discount_value"),
                "uses": row.get("uses", 0),
                "max_uses": row.get("max_uses"),
                "active": row.get("active", False),
                "starts_at": row.get("starts_at"),
                "ends_at": row.get("ends_at"),
                "created_by": row.get("created_by"),
                "created_at": row.get("created_at"),
            }
            for row in promo_rows
        ],
        "audit": [
            {
                "id": str(row["_id"]),
                "actor_id": row.get("actor_id"),
                "action": row.get("action"),
                "entity_type": row.get("entity_type"),
                "entity_id": row.get("entity_id"),
                "plant_name": plant_info(row.get("entity_id"))["name"] if row.get("entity_type") == "plant" else None,
                "meta": row.get("meta", {}),
                "created_at": row.get("created_at"),
            }
            for row in audit_rows
        ],
    }


@router.get("/payment-history")
async def payment_history(
    plant_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    ctx: dict = Depends(allowed_ctx),
):
    """Return recent plan payments, always scoped to the signed-in account."""
    limit = max(1, min(limit, 100))
    query: dict = {}
    if plant_id:
        await scoped_plant(plant_id, ctx)
        query["plant_id"] = plant_id
    elif ctx["role"] == Role.PLANT_OWNER.value:
        owned = await plants.find(
            {"owner_id": ctx["user_id"], "status": {"$ne": "deleted"}},
            {"_id": 1},
        ).to_list(500)
        query["plant_id"] = {"$in": [str(row["_id"]) for row in owned]}
    if status:
        normalized = status.strip().upper()
        if normalized not in {"PAYMENT_PENDING", "PAID", "FAILED", "USER_DROPPED"}:
            raise HTTPException(422, "Invalid payment status")
        query["status"] = normalized

    rows = await plan_payment_orders.find(query).sort("created_at", -1).to_list(limit)
    plant_ids = {row.get("plant_id") for row in rows if row.get("plant_id")}
    plant_rows = await plants.find(
        {"_id": {"$in": [oid(pid) for pid in plant_ids]}},
        {"name": 1},
    ).to_list(len(plant_ids) or 1)
    plant_names = {str(row["_id"]): row.get("name") or "RMC Plant" for row in plant_rows}

    return {
        "payments": [
            {
                "order_number": row.get("order_number"),
                "plant_id": row.get("plant_id"),
                "plant_name": plant_names.get(row.get("plant_id"), "RMC Plant"),
                "product": row.get("product"),
                "plan": row.get("plan"),
                "price": row.get("price", 0),
                "discount": row.get("discount", 0),
                "payable": row.get("payable", 0),
                "status": row.get("status", "PAYMENT_PENDING"),
                "promo_code": row.get("promo_code"),
                "payment_reference": row.get("payment_reference"),
                "activation_id": row.get("activation_id"),
                "created_at": row.get("created_at"),
                "paid_at": row.get("paid_at"),
                "updated_at": row.get("updated_at"),
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/cashfree/webhook")
async def cashfree_webhook(request: Request):
    _, secret, _ = cashfree_config()
    raw = await request.body()
    if not verify_cashfree_signature(request.headers.get("x-webhook-timestamp", ""), raw, request.headers.get("x-webhook-signature", ""), secret):
        raise HTTPException(401, "Invalid Cashfree webhook signature")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(400, "Invalid webhook payload") from exc
    data = payload.get("data") or {}
    order_data = data.get("order") or {}
    payment = data.get("payment") or {}
    order_number = order_data.get("order_id")
    if not order_number:
        raise HTTPException(400, "Cashfree order id is missing")
    order = await plan_payment_orders.find_one({"order_number": order_number})
    if not order:
        return {"status": "IGNORED"}
    payment_status = payment.get("payment_status")
    if payment_status == "SUCCESS":
        activation_id = await grant_paid_entitlement(order, str(payment.get("cf_payment_id") or order_number))
        return {"status": "PAID", "activation_id": activation_id}
    mapped = "FAILED" if payment_status == "FAILED" else "USER_DROPPED" if payment_status == "USER_DROPPED" else "PAYMENT_PENDING"
    await plan_payment_orders.update_one({"_id": order["_id"], "status": {"$ne": "PAID"}}, {"$set": {"status": mapped, "updated_at": now_utc()}})
    return {"status": mapped}


@router.get("/cashfree/return", response_class=HTMLResponse)
async def cashfree_return(order_id: str):
    order = await plan_payment_orders.find_one({"order_number": order_id})
    status = (order or {}).get("status", "PAYMENT_PENDING")
    return HTMLResponse(f"""<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>TrackMyRMC Payment</title></head><body style=\"font-family:system-ui;background:#01153e;color:white;display:grid;place-items:center;min-height:100vh;text-align:center\"><main><h1>Payment {status.replace('_', ' ').title()}</h1><p>Return to TrackMyRMC and refresh Plans &amp; Promotions.</p><a style=\"color:#ff8a00\" href=\"trackmyrmc://plans-promotions?order_id={order_id}\">Open TrackMyRMC</a></main></body></html>""")


@router.get("/orders/{order_number}")
async def payment_order_status(order_number: str, ctx: dict = Depends(allowed_ctx)):
    order = await plan_payment_orders.find_one({"order_number": order_number})
    if not order:
        raise HTTPException(404, "Payment order not found")
    await scoped_plant(order["plant_id"], ctx)
    return {"order_number": order_number, "status": order.get("status"), "product": order.get("product"), "plan": order.get("plan"), "payable": order.get("payable"), "activation_id": order.get("activation_id")}
