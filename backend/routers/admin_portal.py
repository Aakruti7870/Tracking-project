"""Read-only data surface for the dedicated privileged web Control Center.

Every endpoint uses an explicit data permission. Central Admin role alone is not
a substitute for an assigned permission set. Projections deliberately omit
secrets and unnecessary location/contact details.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from control_center_security import Permission, control_center_admin, permissions_for, require_permission
from database import (
    account_deletion_requests,
    audit_logs,
    automation_worker_heartbeats,
    db,
    kyc_profiles,
    orders,
    payments,
    plan_payment_orders,
    plants,
    sessions,
    users,
)
from security import utcnow

router = APIRouter(prefix="/api/admin/portal", tags=["admin-portal"])
support_cases = db.support_cases


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _id(doc: dict) -> str:
    return str(doc.get("_id", ""))


def _safe_user(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "name": doc.get("name") or "User",
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "role": doc.get("primary_role"),
        "status": doc.get("status"),
        "plant_id": doc.get("plant_id"),
        "created_at": _iso(doc.get("created_at")),
    }


def _safe_plant(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "name": doc.get("name") or "RMC Plant",
        "city": doc.get("city"),
        "district": doc.get("district"),
        "status": doc.get("status"),
        "verified": bool(doc.get("verified")),
        "owner_id": doc.get("owner_id"),
        "created_at": _iso(doc.get("created_at")),
    }


def _safe_kyc(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "user_id": doc.get("user_id"),
        "purpose": doc.get("purpose"),
        "status": doc.get("status"),
        "updated_at": _iso(doc.get("updated_at")),
    }


def _safe_order(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "order_number": doc.get("order_number"),
        "customer_id": doc.get("customer_id"),
        "plant_id": doc.get("plant_id"),
        "plant_name": doc.get("plant_name"),
        "grade": doc.get("grade"),
        "quantity": doc.get("quantity"),
        "site_name": doc.get("site_name"),
        "delivery_date": doc.get("delivery_date"),
        "delivery_mode": doc.get("delivery_mode"),
        "status": doc.get("status"),
        "payment_status": doc.get("payment_status"),
        "created_at": _iso(doc.get("created_at")),
    }


def _safe_support_case(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "case_number": doc.get("case_number"),
        "customer_id": doc.get("customer_id"),
        "category": doc.get("category"),
        "status": doc.get("status"),
        "order_id": doc.get("order_id"),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def _safe_payment(doc: dict, kind: str) -> dict:
    if kind == "plan":
        return {
            "id": _id(doc),
            "kind": "PLAN",
            "reference": doc.get("order_number"),
            "plant_id": doc.get("plant_id"),
            "amount": doc.get("payable", 0),
            "method": "CASHFREE",
            "status": doc.get("status", "PAYMENT_PENDING"),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }
    return {
        "id": _id(doc),
        "kind": "INVOICE",
        "reference": doc.get("invoice_id") or doc.get("order_id"),
        "plant_id": doc.get("plant_id"),
        "amount": doc.get("amount", 0),
        "method": doc.get("method"),
        "status": doc.get("status") or "RECORDED",
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def _safe_audit(doc: dict) -> dict:
    return {
        "id": _id(doc),
        "actor_id": doc.get("actor_id"),
        "action": doc.get("action"),
        "entity_type": doc.get("entity_type"),
        "entity_id": doc.get("entity_id"),
        "created_at": _iso(doc.get("created_at")),
    }


@router.get("/summary")
async def summary(ctx: dict = Depends(control_center_admin)):
    """Return only KPI categories the caller is permitted to view."""
    granted = permissions_for(ctx)
    kpis = []
    if Permission.PLANT_VIEW in granted:
        kpis.append({"label": "Plants", "value": await plants.count_documents({"status": {"$ne": "deleted"}})})
    if Permission.USER_VIEW in granted:
        kpis.append({"label": "Users", "value": await users.count_documents({"status": {"$ne": "deleted"}})})
    if Permission.ORDER_VIEW in granted:
        active_orders = {"$nin": ["DELIVERED", "CANCELLED", "REJECTED"]}
        kpis.append({"label": "Active Orders", "value": await orders.count_documents({"status": active_orders})})
    if Permission.SUPPORT_VIEW in granted:
        kpis.append({"label": "Open Support", "value": await support_cases.count_documents({"status": {"$in": ["OPEN", "IN_PROGRESS"]}})})
    return {"kpis": kpis, "generated_at": utcnow().isoformat()}


@router.get("/plants")
async def list_plants(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.PLANT_VIEW)),
):
    docs = await plants.find({}, {"name": 1, "city": 1, "district": 1, "status": 1, "verified": 1, "owner_id": 1, "created_at": 1}).sort("created_at", -1).to_list(limit)
    return {"items": [_safe_plant(doc) for doc in docs]}


@router.get("/kyc")
async def list_kyc(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.KYC_VIEW)),
):
    docs = await kyc_profiles.find({}, {"user_id": 1, "purpose": 1, "status": 1, "updated_at": 1}).sort("updated_at", -1).to_list(limit)
    return {"items": [_safe_kyc(doc) for doc in docs]}


@router.get("/orders")
async def list_orders(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.ORDER_VIEW)),
):
    projection = {"order_number": 1, "customer_id": 1, "plant_id": 1, "plant_name": 1, "grade": 1, "quantity": 1, "site_name": 1, "delivery_date": 1, "delivery_mode": 1, "status": 1, "payment_status": 1, "created_at": 1}
    docs = await orders.find({}, projection).sort("created_at", -1).to_list(limit)
    return {"items": [_safe_order(doc) for doc in docs]}


@router.get("/payments")
async def list_payments(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.PAYMENT_VIEW)),
):
    invoice_docs = await payments.find({}, {"invoice_id": 1, "order_id": 1, "plant_id": 1, "amount": 1, "method": 1, "status": 1, "created_at": 1, "updated_at": 1}).sort("created_at", -1).to_list(limit)
    plan_docs = await plan_payment_orders.find({}, {"order_number": 1, "plant_id": 1, "payable": 1, "status": 1, "created_at": 1, "updated_at": 1}).sort("created_at", -1).to_list(limit)
    items = [*[_safe_payment(doc, "invoice") for doc in invoice_docs], *[_safe_payment(doc, "plan") for doc in plan_docs]]
    items.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    return {"items": items[:limit]}


@router.get("/support")
async def list_support(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.SUPPORT_VIEW)),
):
    projection = {"case_number": 1, "customer_id": 1, "category": 1, "status": 1, "order_id": 1, "created_at": 1, "updated_at": 1}
    docs = await support_cases.find({}, projection).sort("created_at", -1).to_list(limit)
    return {"items": [_safe_support_case(doc) for doc in docs]}


@router.get("/users")
async def list_users(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.USER_VIEW)),
):
    projection = {"name": 1, "email": 1, "phone": 1, "primary_role": 1, "status": 1, "plant_id": 1, "created_at": 1}
    docs = await users.find({}, projection).sort("created_at", -1).to_list(limit)
    return {"items": [_safe_user(doc) for doc in docs]}


@router.get("/audit")
async def list_audit(
    limit: int = Query(default=100, ge=1, le=200),
    _ctx: dict = Depends(require_permission(Permission.AUDIT_VIEW)),
):
    projection = {"actor_id": 1, "action": 1, "entity_type": 1, "entity_id": 1, "created_at": 1}
    docs = await audit_logs.find({}, projection).sort("created_at", -1).to_list(limit)
    return {"items": [_safe_audit(doc) for doc in docs]}


@router.get("/system")
async def system_status(_ctx: dict = Depends(require_permission(Permission.SYSTEM_VIEW))):
    now = utcnow()
    heartbeat_docs = await automation_worker_heartbeats.find({}, {"last_started_at": 1, "last_success_at": 1}).to_list(20)
    return {
        "generated_at": now.isoformat(),
        "active_sessions": await sessions.count_documents({"revoked": False, "expires_at": {"$gt": now}}),
        "pending_account_deletions": await account_deletion_requests.count_documents({"status": "PENDING"}),
        "automation_workers": [{
            "name": _id(doc),
            "last_started_at": _iso(doc.get("last_started_at")),
            "last_success_at": _iso(doc.get("last_success_at")),
        } for doc in heartbeat_docs],
    }
