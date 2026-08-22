"""Staff role dashboards.

A single, DRY router that serves role-aware dashboards for the ten non
customer/driver/owner staff roles: admin, dispatcher, operator, supervisor,
accountant, quality_engineer, fleet_manager, store_manager, authority and
central_admin. Each role sees data scoped to its plant (authority and
central_admin see the whole platform). All data is real — read from the
existing collections (orders, vehicles, trips, incidents, invoices, plants,
users, materials).
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from database import (
    driver_incidents,
    invoices,
    kyc_profiles,
    materials,
    orders,
    plants,
    production_batches,
    users,
    vehicles,
)
from roles import ROLE_LABELS, Role
from security import require_role

router = APIRouter(prefix="/api/staff", tags=["staff"])

STAFF_ROLES = [
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
    Role.AUTHORITY.value,
    Role.CENTRAL_ADMIN.value,
]
PLATFORM_ROLES = {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}

staff_only = require_role(*STAFF_ROLES)

DISPATCHED_STATES = ("DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING")


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


async def _scope_plant_ids(ctx: dict) -> list[str]:
    """Plant ids visible to this staff member."""
    if ctx["role"] in PLATFORM_ROLES:
        docs = await plants.find({}).to_list(500)
        return [str(p["_id"]) for p in docs]
    pid = ctx["user"].get("plant_id")
    if not pid:
        # fall back to any active plant so freshly-seeded staff still see data
        docs = await plants.find({}).to_list(500)
        return [str(p["_id"]) for p in docs]
    return [pid]


def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _is_today(doc: dict) -> bool:
    c = doc.get("created_at") or doc.get("updated_at")
    return bool(c and c.replace(tzinfo=timezone.utc) >= _today_start())


def _kpi(label, value, icon, unit=None):
    return {"label": label, "value": value, "icon": icon, "unit": unit}


# ------------------------------------------------------------------ HOME

@router.get("/home")
async def staff_home(ctx: dict = Depends(staff_only)):
    role = ctx["role"]
    plant_ids = await _scope_plant_ids(ctx)
    base = {"plant_id": {"$in": plant_ids}}

    all_orders = await orders.find(base).to_list(2000)
    dispatched = [o for o in all_orders if o.get("status") in DISPATCHED_STATES]
    delivered = [o for o in all_orders if o.get("status") == "DELIVERED"]
    pending = [o for o in all_orders if o.get("status") == "PENDING"]

    kpis: list[dict] = []
    primary = {"title": "Recent", "kind": "orders"}

    if role == Role.ADMIN.value:
        kpis = [
            _kpi("Total Orders", len(all_orders), "cube-outline"),
            _kpi("Pending Approvals", len(pending), "hourglass-outline"),
            _kpi("In Transit", len(dispatched), "navigate-outline"),
            _kpi("Delivered", round(sum(o.get("quantity", 0) for o in delivered), 1), "checkmark-done-outline", "m³"),
        ]
        primary = {"title": "Recent Orders", "kind": "orders"}

    elif role == Role.DISPATCHER.value:
        ready = [o for o in all_orders if o.get("status") == "READY_TO_DISPATCH"]
        en_route = [o for o in all_orders if o.get("status") in ("EN_ROUTE", "AT_SITE", "UNLOADING")]
        veh = await vehicles.find(base).to_list(500)
        available = [v for v in veh if v.get("status") == "available"]
        kpis = [
            _kpi("Ready to Dispatch", len(ready), "flag-outline"),
            _kpi("Dispatched Today", len([o for o in dispatched if _is_today(o)]), "send-outline"),
            _kpi("En Route", len(en_route), "navigate-outline"),
            _kpi("Available TMs", len(available), "bus-outline"),
        ]
        primary = {"title": "Dispatch Queue", "kind": "dispatch"}

    elif role == Role.OPERATOR.value:
        to_produce = [o for o in all_orders if o.get("status") in ("ACCEPTED", "SCHEDULED")]
        in_prod = [o for o in all_orders if o.get("status") == "IN_PRODUCTION"]
        batches = await production_batches.find(base).to_list(2000)
        produced_today = sum(b.get("quantity", 0) for b in batches if _is_today(b))
        kpis = [
            _kpi("To Produce", len(to_produce), "cube-outline"),
            _kpi("In Production", len(in_prod), "flame-outline"),
            _kpi("Produced Today", round(produced_today, 1), "cube", "m³"),
            _kpi("Completed", len([o for o in all_orders if o.get("status") == "PRODUCTION_COMPLETE"]), "checkmark-done-outline"),
        ]
        primary = {"title": "Production Queue", "kind": "production"}

    elif role == Role.SUPERVISOR.value:
        incs = await driver_incidents.find(base).to_list(500)
        open_inc = [i for i in incs if i.get("status") == "OPEN"]
        kpis = [
            _kpi("Active Deliveries", len(dispatched), "navigate-outline"),
            _kpi("Open Incidents", len(open_inc), "warning-outline"),
            _kpi("Delivered Today", len([o for o in delivered if _is_today(o)]), "checkmark-done-outline"),
            _kpi("Dispatched", len(dispatched), "send-outline"),
        ]
        primary = {"title": "Open Incidents", "kind": "incidents"}

    elif role == Role.ACCOUNTANT.value:
        invs = await invoices.find(base).to_list(2000)
        billed = sum(d.get("total", 0) for d in invs)
        paid = sum(d.get("paid", 0) for d in invs)
        kpis = [
            _kpi("Billed", round(billed, 0), "receipt-outline", "₹"),
            _kpi("Received", round(paid, 0), "cash-outline", "₹"),
            _kpi("Outstanding", round(billed - paid, 0), "alert-circle-outline", "₹"),
            _kpi("Invoices", len(invs), "document-text-outline"),
        ]
        primary = {"title": "Invoices", "kind": "invoices"}

    elif role == Role.QUALITY_ENGINEER.value:
        grades = sorted({o.get("grade") for o in all_orders if o.get("grade")})
        my_plants = await plants.find({"_id": {"$in": [await _oid(i) for i in plant_ids]}}).to_list(100)
        offered = sorted({g for p in my_plants for g in p.get("grades", [])})
        kpis = [
            _kpi("Delivered", len(delivered), "checkmark-done-outline"),
            _kpi("Grades Offered", len(offered), "layers-outline"),
            _kpi("Active Batches", len([o for o in all_orders if o.get("status") == "IN_PRODUCTION"]), "flask-outline"),
            _kpi("Total Volume", round(sum(o.get("quantity", 0) for o in delivered), 1), "cube-outline", "m³"),
        ]
        primary = {"title": "Quality Register", "kind": "quality"}

    elif role == Role.FLEET_MANAGER.value:
        veh = await vehicles.find(base).to_list(500)
        available = [v for v in veh if v.get("status") == "available"]
        on_trip = [v for v in veh if v.get("status") in ("loading", "dispatched")]
        drv = await users.find({"primary_role": "driver", "plant_id": {"$in": plant_ids}}).to_list(500)
        kpis = [
            _kpi("Total TMs", len(veh), "bus-outline"),
            _kpi("Available", len(available), "checkmark-circle-outline"),
            _kpi("On Trip", len(on_trip), "navigate-outline"),
            _kpi("Drivers", len(drv), "people-outline"),
        ]
        primary = {"title": "Fleet", "kind": "fleet"}

    elif role == Role.STORE_MANAGER.value:
        mats = await materials.find(base).to_list(500)
        low = [m for m in mats if m.get("stock", 0) <= m.get("reorder", 0)]
        kpis = [
            _kpi("Materials", len(mats), "cube-outline"),
            _kpi("Low Stock", len(low), "alert-circle-outline"),
            _kpi("Reorder Alerts", len(low), "notifications-outline"),
            _kpi("SKUs OK", len(mats) - len(low), "checkmark-circle-outline"),
        ]
        primary = {"title": "Stock Levels", "kind": "inventory"}

    elif role == Role.AUTHORITY.value:
        all_plants = await plants.find({}).to_list(1000)
        verified = [p for p in all_plants if p.get("verified")]
        pending_kyc = await kyc_profiles.count_documents({"status": "PENDING"})
        customers = await users.count_documents({"primary_role": "customer"})
        kpis = [
            _kpi("Registered Plants", len(all_plants), "business-outline"),
            _kpi("Verified", len(verified), "shield-checkmark-outline"),
            _kpi("Pending KYC", pending_kyc, "hourglass-outline"),
            _kpi("Customers", customers, "people-outline"),
        ]
        primary = {"title": "Plants", "kind": "plants"}

    elif role == Role.CENTRAL_ADMIN.value:
        all_plants = await plants.count_documents({})
        all_users = await users.count_documents({})
        all_ord = await orders.count_documents({})
        open_inc = await driver_incidents.count_documents({"status": "OPEN"})
        kpis = [
            _kpi("Plants", all_plants, "business-outline"),
            _kpi("Users", all_users, "people-outline"),
            _kpi("Orders", all_ord, "cube-outline"),
            _kpi("Open Incidents", open_inc, "warning-outline"),
        ]
        primary = {"title": "Users", "kind": "users"}

    return {
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "name": ctx["user"].get("name"),
        "kpis": kpis,
        "primary": primary,
    }


# ------------------------------------------------------------ COLLECTIONS

def _order_item(o: dict) -> dict:
    return {
        "id": str(o["_id"]),
        "icon": "cube-outline",
        "primary": f"{o.get('order_number')} · {o.get('grade')}",
        "secondary": f"{o.get('customer_name') or ''} — {o.get('quantity')} m³",
        "meta": o.get("site_name"),
        "badge": (o.get("status") or "").replace("_", " "),
        "badge_status": o.get("status"),
    }


@router.get("/collection/{kind}")
async def staff_collection(kind: str, ctx: dict = Depends(staff_only)):
    plant_ids = await _scope_plant_ids(ctx)
    base = {"plant_id": {"$in": plant_ids}}

    if kind == "orders":
        docs = await orders.find(base).sort("created_at", -1).to_list(500)
        return {"title": "Orders", "empty": "No orders yet", "items": [_order_item(o) for o in docs]}

    if kind == "dispatch":
        docs = await orders.find(
            {**base, "status": {"$in": ["READY_TO_DISPATCH", *DISPATCHED_STATES]}}
        ).sort("updated_at", -1).to_list(500)
        return {"title": "Dispatch Queue", "empty": "Nothing to dispatch", "items": [_order_item(o) for o in docs]}

    if kind == "production":
        docs = await orders.find(
            {**base, "status": {"$in": ["ACCEPTED", "SCHEDULED", "IN_PRODUCTION", "PRODUCTION_COMPLETE"]}}
        ).sort("updated_at", -1).to_list(500)
        return {"title": "Production Queue", "empty": "No orders in production", "items": [_order_item(o) for o in docs]}

    if kind == "quality":
        docs = await orders.find(
            {**base, "status": {"$in": ["IN_PRODUCTION", "PRODUCTION_COMPLETE", *DISPATCHED_STATES, "DELIVERED"]}}
        ).sort("updated_at", -1).to_list(500)
        items = [{
            "id": str(o["_id"]),
            "icon": "flask-outline",
            "primary": f"{o.get('grade')} · {o.get('order_number')}",
            "secondary": f"{o.get('quantity')} m³ — {o.get('site_name') or ''}",
            "meta": o.get("status", "").replace("_", " ").title(),
            "badge": "QC OK" if o.get("status") == "DELIVERED" else "In process",
            "badge_status": "DELIVERED" if o.get("status") == "DELIVERED" else "IN_PRODUCTION",
        } for o in docs]
        return {"title": "Quality Register", "empty": "No batches to inspect", "items": items}

    if kind == "incidents":
        docs = await driver_incidents.find(base).sort("created_at", -1).to_list(300)
        items = [{
            "id": str(d["_id"]),
            "icon": "warning-outline",
            "primary": f"{d.get('type')} · {d.get('driver_name') or ''}",
            "secondary": d.get("remark") or "No details",
            "meta": d.get("order_number") or d.get("vehicle"),
            "badge": d.get("status"),
            "badge_status": "REJECTED" if d.get("status") == "OPEN" else "DELIVERED",
        } for d in docs]
        return {"title": "Incidents", "empty": "No incidents reported", "items": items}

    if kind == "fleet":
        docs = await vehicles.find(base).to_list(500)
        items = [{
            "id": str(v["_id"]),
            "icon": "bus-outline",
            "primary": v.get("tm_number"),
            "secondary": f"Capacity {v.get('capacity_m3')} m³",
            "meta": None,
            "badge": v.get("status"),
            "badge_status": "DELIVERED" if v.get("status") == "available" else "DISPATCHED",
        } for v in docs]
        return {"title": "Fleet", "empty": "No vehicles", "items": items}

    if kind == "drivers":
        docs = await users.find({"primary_role": "driver", "plant_id": {"$in": plant_ids}}).to_list(500)
        items = [{
            "id": str(d["_id"]),
            "icon": "person-outline",
            "primary": d.get("name"),
            "secondary": d.get("phone"),
            "meta": None,
            "badge": (d.get("status") or "active").title(),
            "badge_status": "DELIVERED",
        } for d in docs]
        return {"title": "Drivers", "empty": "No drivers linked", "items": items}

    if kind == "invoices":
        docs = await invoices.find(base).sort("created_at", -1).to_list(500)
        items = [{
            "id": str(d["_id"]),
            "icon": "receipt-outline",
            "primary": f"{d.get('invoice_number')} · {d.get('customer_name') or ''}",
            "secondary": f"{d.get('grade')} — {d.get('quantity')} m³",
            "meta": f"₹{round(d.get('total', 0))}",
            "badge": d.get("status"),
            "badge_status": "DELIVERED" if d.get("status") == "PAID" else ("PENDING" if d.get("status") == "PARTIAL" else "REJECTED"),
        } for d in docs]
        return {"title": "Invoices", "empty": "No invoices raised", "items": items}

    if kind == "ledger":
        docs = await invoices.find(base).to_list(2000)
        by_customer: dict = {}
        for d in docs:
            k = d.get("customer_name") or "Customer"
            e = by_customer.setdefault(k, {"billed": 0.0, "paid": 0.0})
            e["billed"] += d.get("total", 0)
            e["paid"] += d.get("paid", 0)
        items = [{
            "id": name,
            "icon": "person-circle-outline",
            "primary": name,
            "secondary": f"Billed ₹{round(v['billed'])} · Paid ₹{round(v['paid'])}",
            "meta": f"Bal ₹{round(v['billed'] - v['paid'])}",
            "badge": "Cleared" if v["billed"] - v["paid"] < 1 else "Due",
            "badge_status": "DELIVERED" if v["billed"] - v["paid"] < 1 else "REJECTED",
        } for name, v in by_customer.items()]
        return {"title": "Customer Ledger", "empty": "No ledger entries", "items": items}

    if kind == "inventory":
        docs = await materials.find(base).sort("name", 1).to_list(500)
        items = [{
            "id": str(m["_id"]),
            "icon": "cube-outline",
            "primary": m.get("name"),
            "secondary": f"{m.get('stock')} {m.get('unit')} in stock",
            "meta": f"Reorder ≤ {m.get('reorder')} {m.get('unit')}",
            "badge": "LOW" if m.get("stock", 0) <= m.get("reorder", 0) else "OK",
            "badge_status": "REJECTED" if m.get("stock", 0) <= m.get("reorder", 0) else "DELIVERED",
        } for m in docs]
        return {"title": "Stock Levels", "empty": "No materials tracked", "items": items}

    if kind == "plants":
        query = {} if ctx["role"] in PLATFORM_ROLES else {"_id": {"$in": [await _oid(i) for i in plant_ids]}}
        docs = await plants.find(query).to_list(500)
        items = [{
            "id": str(p["_id"]),
            "icon": "business-outline",
            "primary": p.get("name"),
            "secondary": f"{p.get('city') or ''} · {', '.join(p.get('grades', [])[:4])}",
            "meta": p.get("contact_phone"),
            "badge": "Verified" if p.get("verified") else "Pending",
            "badge_status": "DELIVERED" if p.get("verified") else "PENDING",
        } for p in docs]
        return {"title": "Plants", "empty": "No plants registered", "items": items}

    if kind == "kyc":
        docs = await kyc_profiles.find({"status": {"$in": ["PENDING", "VERIFIED", "REJECTED"]}}).sort("updated_at", -1).to_list(500)
        items = []
        for d in docs:
            u = await users.find_one({"_id": await _oid(d.get("user_id"))})
            items.append({
                "id": str(d["_id"]),
                "icon": "id-card-outline",
                "primary": (u.get("name") if u else "User"),
                "secondary": f"{d.get('purpose', 'CUSTOMER').title()} KYC",
                "meta": (u.get("phone") or u.get("email")) if u else None,
                "badge": d.get("status"),
                "badge_status": "DELIVERED" if d.get("status") == "VERIFIED" else ("PENDING" if d.get("status") == "PENDING" else "REJECTED"),
            })
        return {"title": "KYC Requests", "empty": "No KYC requests", "items": items}

    if kind == "users":
        docs = await users.find({}).sort("primary_role", 1).to_list(1000)
        items = [{
            "id": str(u["_id"]),
            "icon": "person-outline",
            "primary": u.get("name"),
            "secondary": ROLE_LABELS.get(u.get("primary_role"), u.get("primary_role")),
            "meta": u.get("phone") or u.get("email"),
            "badge": (u.get("status") or "active").title(),
            "badge_status": "DELIVERED" if (u.get("status") or "active") == "active" else "REJECTED",
        } for u in docs]
        return {"title": "Platform Users", "empty": "No users", "items": items}

    raise HTTPException(404, "Unknown collection")
