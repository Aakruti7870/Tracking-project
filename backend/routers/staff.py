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

from audit import write_audit
from database import (
    driver_incidents,
    invoices,
    kyc_profiles,
    materials,
    notifications,
    orders,
    plants,
    production_batches,
    quality_tests,
    stock_movements,
    users,
    vehicles,
)
from models import (
    KycDecisionBody,
    MaterialBody,
    PaymentBody,
    QualityTestBody,
    StockAdjustBody,
    VehicleBody,
    VehicleStatusBody,
)
from notifications import record_notification
from order_service import (
    ACCEPTED,
    DISPATCHED,
    DRIVER_ASSIGNED,
    IN_PRODUCTION,
    PRODUCTION_COMPLETE,
    READY_TO_DISPATCH,
    TM_ASSIGNED,
    transition_order,
)
from database import challans, driver_trips, next_sequence, payments
from models import AssignDriverBody, AssignTmBody, ChallanBody
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
        # Missing tenant assignment must fail closed; never widen to all plants.
        raise HTTPException(403, "Staff account is not assigned to a plant")
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
        can_dispatch = ctx["role"] in DISPATCH_ROLES
        docs = await orders.find(
            {**base, "status": {"$in": ["READY_TO_DISPATCH", "ACCEPTED", "SCHEDULED", "PRODUCTION_COMPLETE", "TM_ASSIGNED", "DRIVER_ASSIGNED", *DISPATCHED_STATES]}}
        ).sort("updated_at", -1).to_list(500)
        items = []
        for o in docs:
            it = _order_item(o)
            if can_dispatch and o.get("status") not in ("DELIVERED",):
                it["nav"] = f"/dispatch-order/{o['_id']}"
            items.append(it)
        return {"title": "Dispatch Queue", "empty": "Nothing to dispatch", "items": items}

    if kind == "production":
        can_produce = ctx["role"] == Role.OPERATOR.value
        docs = await orders.find(
            {**base, "status": {"$in": ["ACCEPTED", "SCHEDULED", "IN_PRODUCTION", "PRODUCTION_COMPLETE"]}}
        ).sort("updated_at", -1).to_list(500)
        items = []
        for o in docs:
            it = _order_item(o)
            if can_produce:
                st = o.get("status")
                if st in ("ACCEPTED", "SCHEDULED"):
                    it["actions"] = [{"key": "start", "label": "Start Production", "style": "primary", "method": "POST", "path": f"/staff/orders/{o['_id']}/production/start"}]
                elif st == "IN_PRODUCTION":
                    it["actions"] = [{"key": "complete", "label": "Mark Complete", "style": "primary", "method": "POST", "path": f"/staff/orders/{o['_id']}/production/complete"}]
            items.append(it)
        return {"title": "Production Queue", "empty": "No orders in production", "items": items}

    if kind == "quality":
        can_test = ctx["role"] == Role.QUALITY_ENGINEER.value
        docs = await orders.find(
            {**base, "status": {"$in": ["IN_PRODUCTION", "PRODUCTION_COMPLETE", *DISPATCHED_STATES, "DELIVERED"]}}
        ).sort("updated_at", -1).to_list(500)
        items = []
        for o in docs:
            test = await quality_tests.find_one({"order_id": str(o["_id"])})
            if test:
                badge = f"QC {test.get('result', 'PASS')}"
                bstatus = "DELIVERED" if test.get("result") == "PASS" else "REJECTED"
                secondary = f"Slump {test.get('slump_mm', '—')}mm · 28d {test.get('cube_28d', '—')} MPa"
            else:
                badge = "Pending QC"
                bstatus = "PENDING"
                secondary = f"{o.get('quantity')} m³ — {o.get('site_name') or ''}"
            actions = []
            if can_test:
                actions = [{"key": "test", "label": "Record test" if not test else "Update test", "style": "primary", "input": "quality"}]
            items.append({
                "id": str(o["_id"]),
                "icon": "flask-outline",
                "primary": f"{o.get('grade')} · {o.get('order_number')}",
                "secondary": secondary,
                "meta": (o.get("status") or "").replace("_", " ").title(),
                "badge": badge,
                "badge_status": bstatus,
                "actions": actions,
            })
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
        can_manage = ctx["role"] == Role.FLEET_MANAGER.value
        docs = await vehicles.find(base).to_list(500)
        items = []
        for v in docs:
            st = v.get("status")
            actions = []
            if can_manage:
                if st == "available":
                    actions = [{"key": "maint", "label": "Set Maintenance", "style": "danger", "method": "POST", "path": f"/staff/vehicles/{v['_id']}/status", "body": {"status": "maintenance"}}]
                elif st == "maintenance":
                    actions = [{"key": "avail", "label": "Set Available", "style": "primary", "method": "POST", "path": f"/staff/vehicles/{v['_id']}/status", "body": {"status": "available"}}]
            items.append({
                "id": str(v["_id"]),
                "icon": "bus-outline",
                "primary": v.get("tm_number"),
                "secondary": f"Capacity {v.get('capacity_m3')} m³",
                "meta": None,
                "badge": st,
                "badge_status": "DELIVERED" if st == "available" else "DISPATCHED",
                "actions": actions,
            })
        resp = {"title": "Fleet", "empty": "No vehicles", "items": items}
        if can_manage:
            resp["create"] = {"label": "Add Transit Mixer", "path": "/staff/vehicles", "form": "vehicle"}
        return resp

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
        can_pay = ctx["role"] == Role.ACCOUNTANT.value
        docs = await invoices.find(base).sort("created_at", -1).to_list(500)
        items = []
        for d in docs:
            it = {
                "id": str(d["_id"]),
                "icon": "receipt-outline",
                "primary": f"{d.get('invoice_number')} · {d.get('customer_name') or ''}",
                "secondary": f"{d.get('grade')} — {d.get('quantity')} m³ · ₹{round(d.get('total', 0))}",
                "meta": f"Paid ₹{round(d.get('paid', 0))} · Bal ₹{round(d.get('total', 0) - d.get('paid', 0))}",
                "badge": d.get("status"),
                "badge_status": "DELIVERED" if d.get("status") == "PAID" else ("PENDING" if d.get("status") == "PARTIAL" else "REJECTED"),
            }
            if can_pay and d.get("status") != "PAID":
                it["actions"] = [{"key": "pay", "label": "Record Payment", "style": "primary", "method": "POST", "path": f"/staff/invoices/{d['_id']}/payment", "input": "amount", "sign": 1}]
            items.append(it)
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
        can_manage = ctx["role"] == Role.STORE_MANAGER.value
        docs = await materials.find(base).sort("name", 1).to_list(500)
        items = []
        for m in docs:
            low = m.get("stock", 0) <= m.get("reorder", 0)
            actions = []
            if can_manage:
                actions = [
                    {"key": "in", "label": "Stock In", "style": "primary", "method": "POST", "path": f"/staff/materials/{m['_id']}/adjust", "input": "amount", "sign": 1},
                    {"key": "out", "label": "Stock Out", "style": "outline", "method": "POST", "path": f"/staff/materials/{m['_id']}/adjust", "input": "amount", "sign": -1},
                ]
            items.append({
                "id": str(m["_id"]),
                "icon": "cube-outline",
                "primary": m.get("name"),
                "secondary": f"{m.get('stock')} {m.get('unit')} in stock",
                "meta": f"Reorder ≤ {m.get('reorder')} {m.get('unit')}",
                "badge": "LOW" if low else "OK",
                "badge_status": "REJECTED" if low else "DELIVERED",
                "actions": actions,
            })
        resp = {"title": "Stock Levels", "empty": "No materials tracked", "items": items}
        if can_manage:
            resp["create"] = {"label": "Add Material", "path": "/staff/materials", "form": "material"}
        return resp

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
            "owner_assigned": bool(p.get("owner_id")),
        } for p in docs]
        return {"title": "Plants", "empty": "No plants registered", "items": items}

    if kind == "kyc":
        docs = await kyc_profiles.find({"status": {"$in": ["PENDING", "VERIFIED", "REJECTED"]}}).sort("updated_at", -1).to_list(500)
        can_review = ctx["role"] == Role.AUTHORITY.value
        items = []
        for d in docs:
            u = await users.find_one({"_id": await _oid(d.get("user_id"))})
            actions = []
            if can_review and d.get("status") == "PENDING":
                actions = [
                    {"key": "approve", "label": "Approve", "style": "primary", "method": "POST", "path": f"/staff/kyc/{d['_id']}/approve"},
                    {"key": "reject", "label": "Reject", "style": "danger", "method": "POST", "path": f"/staff/kyc/{d['_id']}/reject", "input": "reason"},
                ]
            items.append({
                "id": str(d["_id"]),
                "icon": "id-card-outline",
                "primary": (u.get("name") if u else "User"),
                "secondary": f"{d.get('purpose', 'CUSTOMER').title()} KYC",
                "meta": (u.get("phone") or u.get("email")) if u else None,
                "badge": d.get("status"),
                "badge_status": "DELIVERED" if d.get("status") == "VERIFIED" else ("PENDING" if d.get("status") == "PENDING" else "REJECTED"),
                "actions": actions,
            })
        return {"title": "KYC Requests", "empty": "No KYC requests", "items": items}

    if kind == "users":
        can_manage = ctx["role"] == Role.CENTRAL_ADMIN.value
        docs = await users.find({}).sort("primary_role", 1).to_list(1000)
        items = []
        for u in docs:
            st = u.get("status") or "active"
            actions = []
            if can_manage and str(u["_id"]) != ctx["user_id"]:
                if st == "active":
                    actions = [{"key": "suspend", "label": "Suspend", "style": "danger", "method": "POST", "path": f"/staff/users/{u['_id']}/suspend"}]
                else:
                    actions = [{"key": "activate", "label": "Activate", "style": "primary", "method": "POST", "path": f"/staff/users/{u['_id']}/activate"}]
            items.append({
                "id": str(u["_id"]),
                "icon": "person-outline",
                "primary": u.get("name"),
                "secondary": ROLE_LABELS.get(u.get("primary_role"), u.get("primary_role")),
                "meta": u.get("phone") or u.get("email"),
                "badge": st.title(),
                "badge_status": "DELIVERED" if st == "active" else "REJECTED",
                "actions": actions,
            })
        return {"title": "Platform Users", "empty": "No users", "items": items}

    raise HTTPException(404, "Unknown collection")


# ------------------------------------------------------------ ACTIONS

def _authority_only(ctx: dict):
    if ctx["role"] != Role.AUTHORITY.value:
        raise HTTPException(403, "Only an Authority can review KYC")


@router.post("/kyc/{profile_id}/approve")
async def kyc_approve(profile_id: str, ctx: dict = Depends(staff_only)):
    _authority_only(ctx)
    prof = await kyc_profiles.find_one({"_id": await _oid(profile_id)})
    if not prof:
        raise HTTPException(404, "KYC profile not found")
    await kyc_profiles.update_one({"_id": prof["_id"]}, {"$set": {"status": "VERIFIED", "updated_at": datetime.now(timezone.utc)}})
    await write_audit(ctx["user_id"], "kyc.approve", "kyc_profile", profile_id)
    if prof.get("user_id"):
        await record_notification(prof["user_id"], "kyc", "KYC Verified", "Your KYC has been approved. You can now place live orders.")
    return {"status": "VERIFIED"}


@router.post("/kyc/{profile_id}/reject")
async def kyc_reject(profile_id: str, body: KycDecisionBody, ctx: dict = Depends(staff_only)):
    _authority_only(ctx)
    prof = await kyc_profiles.find_one({"_id": await _oid(profile_id)})
    if not prof:
        raise HTTPException(404, "KYC profile not found")
    await kyc_profiles.update_one({"_id": prof["_id"]}, {"$set": {"status": "REJECTED", "reject_reason": body.reason, "updated_at": datetime.now(timezone.utc)}})
    await write_audit(ctx["user_id"], "kyc.reject", "kyc_profile", profile_id, {"reason": body.reason})
    if prof.get("user_id"):
        await record_notification(prof["user_id"], "kyc", "KYC Rejected", body.reason or "Your KYC was rejected. Please re-submit.")
    return {"status": "REJECTED"}


def _central_only(ctx: dict):
    if ctx["role"] != Role.CENTRAL_ADMIN.value:
        raise HTTPException(403, "Only a Central Admin can manage users")


@router.post("/users/{user_id}/suspend")
async def user_suspend(user_id: str, ctx: dict = Depends(staff_only)):
    _central_only(ctx)
    if user_id == ctx["user_id"]:
        raise HTTPException(422, "You cannot suspend your own account")
    res = await users.update_one({"_id": await _oid(user_id)}, {"$set": {"status": "suspended"}})
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await write_audit(ctx["user_id"], "user.suspend", "user", user_id)
    return {"status": "suspended"}


@router.post("/users/{user_id}/activate")
async def user_activate(user_id: str, ctx: dict = Depends(staff_only)):
    _central_only(ctx)
    res = await users.update_one({"_id": await _oid(user_id)}, {"$set": {"status": "active"}})
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await write_audit(ctx["user_id"], "user.activate", "user", user_id)
    return {"status": "active"}


def _fleet_only(ctx: dict):
    if ctx["role"] != Role.FLEET_MANAGER.value:
        raise HTTPException(403, "Only a Fleet Manager can manage vehicles")


@router.post("/vehicles")
async def add_vehicle(body: VehicleBody, ctx: dict = Depends(staff_only)):
    _fleet_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    exists = await vehicles.find_one({"tm_number": body.tm_number})
    if exists:
        raise HTTPException(409, "A vehicle with this number already exists")
    doc = {"plant_id": plant_ids[0], "tm_number": body.tm_number, "capacity_m3": body.capacity_m3, "status": "available"}
    res = await vehicles.insert_one(doc)
    await write_audit(ctx["user_id"], "vehicle.add", "vehicle", str(res.inserted_id))
    return {"id": str(res.inserted_id)}


@router.post("/vehicles/{vehicle_id}/status")
async def set_vehicle_status(vehicle_id: str, body: VehicleStatusBody, ctx: dict = Depends(staff_only)):
    _fleet_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    v = await vehicles.find_one({"_id": await _oid(vehicle_id), "plant_id": {"$in": plant_ids}})
    if not v:
        raise HTTPException(404, "Vehicle not found")
    if body.status not in ("available", "maintenance"):
        raise HTTPException(422, "Status must be available or maintenance")
    if v.get("status") in ("loading", "dispatched"):
        raise HTTPException(409, "Vehicle is on an active trip")
    await vehicles.update_one({"_id": v["_id"]}, {"$set": {"status": body.status}})
    return {"status": body.status}


def _store_only(ctx: dict):
    if ctx["role"] != Role.STORE_MANAGER.value:
        raise HTTPException(403, "Only a Store Manager can manage stock")


@router.post("/materials")
async def add_material(body: MaterialBody, ctx: dict = Depends(staff_only)):
    _store_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    doc = {"plant_id": plant_ids[0], "name": body.name, "unit": body.unit, "stock": body.stock, "reorder": body.reorder}
    res = await materials.insert_one(doc)
    await write_audit(ctx["user_id"], "material.add", "material", str(res.inserted_id))
    return {"id": str(res.inserted_id)}


@router.post("/materials/{material_id}/adjust")
async def adjust_material(material_id: str, body: StockAdjustBody, ctx: dict = Depends(staff_only)):
    _store_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    m = await materials.find_one({"_id": await _oid(material_id), "plant_id": {"$in": plant_ids}})
    if not m:
        raise HTTPException(404, "Material not found")
    new_stock = round(m.get("stock", 0) + body.delta, 2)
    if new_stock < 0:
        raise HTTPException(422, "Insufficient stock for this stock-out")
    now = datetime.now(timezone.utc)
    await materials.update_one({"_id": m["_id"]}, {"$set": {"stock": new_stock}})
    await stock_movements.insert_one({
        "material_id": material_id, "plant_id": m["plant_id"], "delta": body.delta,
        "note": body.note, "balance": new_stock, "actor_id": ctx["user_id"], "created_at": now,
    })
    return {"stock": new_stock}


def _quality_only(ctx: dict):
    if ctx["role"] != Role.QUALITY_ENGINEER.value:
        raise HTTPException(403, "Only a Quality Engineer can record tests")


@router.post("/quality")
async def record_quality(body: QualityTestBody, ctx: dict = Depends(staff_only)):
    _quality_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    order = await orders.find_one({"_id": await _oid(body.order_id), "plant_id": {"$in": plant_ids}})
    if not order:
        raise HTTPException(404, "Order not found for this plant")
    now = datetime.now(timezone.utc)
    doc = {
        "order_id": body.order_id, "order_number": order.get("order_number"),
        "plant_id": order["plant_id"], "grade": order.get("grade"),
        "slump_mm": body.slump_mm, "cube_7d": body.cube_7d, "cube_28d": body.cube_28d,
        "actual_cement": body.actual_cement, "actual_water": body.actual_water,
        "result": body.result, "remarks": body.remarks,
        "engineer_id": ctx["user_id"], "updated_at": now,
    }
    await quality_tests.update_one({"order_id": body.order_id}, {"$set": doc}, upsert=True)
    await write_audit(ctx["user_id"], "quality.record", "order", body.order_id, {"result": body.result})
    return {"result": body.result}


# ------------------------------------------------------------ QUALITY DETAIL

@router.get("/quality/{order_id}")
async def quality_detail(order_id: str, ctx: dict = Depends(staff_only)):
    plant_ids = await _scope_plant_ids(ctx)
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": {"$in": plant_ids}})
    if not order:
        raise HTTPException(404, "Order not found")
    t = await quality_tests.find_one({"order_id": order_id})
    return {
        "order_number": order.get("order_number"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "site_name": order.get("site_name"),
        "test": {
            "slump_mm": t.get("slump_mm"), "cube_7d": t.get("cube_7d"), "cube_28d": t.get("cube_28d"),
            "actual_cement": t.get("actual_cement"), "actual_water": t.get("actual_water"),
            "result": t.get("result"), "remarks": t.get("remarks"),
        } if t else None,
    }


# ------------------------------------------------------- OPERATOR / ACCOUNTANT

def _operator_only(ctx: dict):
    if ctx["role"] != Role.OPERATOR.value:
        raise HTTPException(403, "Only a Plant Operator can run production")


async def _scoped_order(ctx: dict, order_id: str) -> dict:
    plant_ids = await _scope_plant_ids(ctx)
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": {"$in": plant_ids}})
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@router.post("/orders/{order_id}/production/start")
async def op_start_production(order_id: str, ctx: dict = Depends(staff_only)):
    _operator_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") not in (ACCEPTED, "SCHEDULED"):
        raise HTTPException(409, "Order must be approved before production")
    await transition_order(order_id, IN_PRODUCTION, ctx["user_id"], note="Production started",
                           notify_user_ids=[order["customer_id"]], event="production_started")
    return {"status": IN_PRODUCTION}


@router.post("/orders/{order_id}/production/complete")
async def op_complete_production(order_id: str, ctx: dict = Depends(staff_only)):
    _operator_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") != IN_PRODUCTION:
        raise HTTPException(409, "Order is not in production")
    await transition_order(order_id, PRODUCTION_COMPLETE, ctx["user_id"], note="Production complete",
                           notify_user_ids=[order["customer_id"]], event="production_complete")
    return {"status": PRODUCTION_COMPLETE}


def _accountant_only(ctx: dict):
    if ctx["role"] != Role.ACCOUNTANT.value:
        raise HTTPException(403, "Only an Accountant can record payments")


@router.post("/invoices/{invoice_id}/payment")
async def acc_record_payment(invoice_id: str, body: PaymentBody, ctx: dict = Depends(staff_only)):
    _accountant_only(ctx)
    plant_ids = await _scope_plant_ids(ctx)
    inv = await invoices.find_one({"_id": await _oid(invoice_id), "plant_id": {"$in": plant_ids}})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    balance = round(inv.get("total", 0) - inv.get("paid", 0), 2)
    if body.amount > balance + 0.01:
        raise HTTPException(422, f"Amount exceeds outstanding balance ({balance})")
    now = datetime.now(timezone.utc)
    await payments.insert_one({
        "invoice_id": invoice_id, "order_id": inv.get("order_id"), "plant_id": inv["plant_id"],
        "customer_id": inv.get("customer_id"), "amount": body.amount, "method": body.method,
        "note": body.note, "created_at": now,
    })
    new_paid = round(inv.get("paid", 0) + body.amount, 2)
    status_val = "PAID" if new_paid >= inv.get("total", 0) - 0.01 else "PARTIAL"
    await invoices.update_one({"_id": inv["_id"]}, {"$set": {"paid": new_paid, "status": status_val}})
    if inv.get("order_id"):
        await orders.update_one({"_id": await _oid(inv["order_id"])}, {"$set": {"payment_status": status_val}})
    await write_audit(ctx["user_id"], "payment.record", "invoice", invoice_id, {"amount": body.amount})
    return {"paid": new_paid, "status": status_val, "balance": round(inv.get("total", 0) - new_paid, 2)}


# ------------------------------------------------------------ DISPATCHER

DISPATCH_ROLES = {Role.DISPATCHER.value, Role.ADMIN.value}


def _dispatch_only(ctx: dict):
    if ctx["role"] not in DISPATCH_ROLES:
        raise HTTPException(403, "Only a Dispatcher can run dispatch")


@router.get("/fleet")
async def dispatch_fleet(ctx: dict = Depends(staff_only)):
    plant_ids = await _scope_plant_ids(ctx)
    docs = await vehicles.find({"plant_id": {"$in": plant_ids}}).to_list(200)
    return {"vehicles": [{"id": str(v["_id"]), "tm_number": v.get("tm_number"), "capacity_m3": v.get("capacity_m3"), "status": v.get("status")} for v in docs]}


@router.get("/drivers")
async def dispatch_drivers(ctx: dict = Depends(staff_only)):
    plant_ids = await _scope_plant_ids(ctx)
    docs = await users.find({"primary_role": "driver", "plant_id": {"$in": plant_ids}}).to_list(200)
    return {"drivers": [{"id": str(d["_id"]), "name": d.get("name"), "phone": d.get("phone")} for d in docs]}


@router.get("/orders/{order_id}")
async def dispatch_order_detail(order_id: str, ctx: dict = Depends(staff_only)):
    order = await _scoped_order(ctx, order_id)
    return {"order": {
        "id": str(order["_id"]),
        "order_number": order.get("order_number"),
        "customer_name": order.get("customer_name"),
        "customer_mobile": order.get("customer_mobile"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "site_name": order.get("site_name"),
        "site_address": order.get("site_address"),
        "status": order.get("status"),
        "tm_number": order.get("tm_number"),
        "driver_name": order.get("driver_name"),
        "challan_number": order.get("challan_number"),
        "invoice_number": order.get("invoice_number"),
    }}


@router.post("/orders/{order_id}/assign-tm")
async def dispatch_assign_tm(order_id: str, body: AssignTmBody, ctx: dict = Depends(staff_only)):
    _dispatch_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") not in (ACCEPTED, "SCHEDULED", PRODUCTION_COMPLETE, TM_ASSIGNED):
        raise HTTPException(409, "Order is not ready for transit mixer assignment")
    v = await vehicles.find_one({"_id": await _oid(body.vehicle_id), "plant_id": order["plant_id"]})
    if not v:
        raise HTTPException(404, "Vehicle not found for this plant")
    if v.get("status") not in ("available",) and v.get("current_order_id") != order_id:
        raise HTTPException(409, f"Vehicle is {v.get('status')} and cannot be assigned")
    await orders.update_one({"_id": order["_id"]}, {"$set": {"tm_id": str(v["_id"]), "tm_number": v.get("tm_number")}})
    await vehicles.update_one({"_id": v["_id"]}, {"$set": {"status": "loading", "current_order_id": order_id}})
    if order.get("status") != TM_ASSIGNED:
        await transition_order(order_id, TM_ASSIGNED, ctx["user_id"], note=f"TM {v.get('tm_number')} assigned")
    return {"status": TM_ASSIGNED}


@router.post("/orders/{order_id}/assign-driver")
async def dispatch_assign_driver(order_id: str, body: AssignDriverBody, ctx: dict = Depends(staff_only)):
    _dispatch_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") not in (TM_ASSIGNED, DRIVER_ASSIGNED):
        raise HTTPException(409, "Assign a transit mixer before a driver")
    d = await users.find_one({"_id": await _oid(body.driver_id), "primary_role": "driver", "plant_id": order["plant_id"]})
    if not d:
        raise HTTPException(404, "Driver not found for this plant")
    await orders.update_one({"_id": order["_id"]}, {"$set": {"driver_id": str(d["_id"]), "driver_name": d.get("name"), "driver_mobile": d.get("phone")}})
    existing_trip = await driver_trips.find_one({"order_id": order_id})
    trip_doc = {
        "order_id": order_id, "order_number": order.get("order_number"), "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"), "driver_id": str(d["_id"]), "vehicle_id": order.get("tm_id"),
        "tm_number": order.get("tm_number"), "grade": order.get("grade"), "quantity": order.get("quantity"),
        "site_name": order.get("site_name"), "site_address": order.get("site_address"),
        "status": "ASSIGNED", "updated_at": datetime.now(timezone.utc),
    }
    if existing_trip:
        await driver_trips.update_one({"_id": existing_trip["_id"]}, {"$set": trip_doc})
    else:
        trip_doc["created_at"] = datetime.now(timezone.utc)
        await driver_trips.insert_one(trip_doc)
    await record_notification(str(d["_id"]), "trip_assigned", f"New trip {order.get('order_number')}",
                              f"{order.get('quantity')} m³ of {order.get('grade')} to {order.get('site_name')}.")
    if order.get("status") != DRIVER_ASSIGNED:
        await transition_order(order_id, DRIVER_ASSIGNED, ctx["user_id"], note=f"Driver {d.get('name')} assigned")
    return {"status": DRIVER_ASSIGNED}


@router.post("/orders/{order_id}/challan")
async def dispatch_challan(order_id: str, ctx: dict = Depends(staff_only)):
    _dispatch_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") not in (DRIVER_ASSIGNED, READY_TO_DISPATCH):
        raise HTTPException(409, "Assign transit mixer & driver before generating challan")
    existing = await challans.find_one({"order_id": order_id})
    if not existing:
        seq = await next_sequence("challan_number")
        challan_number = f"CH-{2000 + seq}"
        now = datetime.now(timezone.utc)
        await challans.insert_one({
            "challan_number": challan_number, "order_id": order_id, "order_number": order.get("order_number"),
            "plant_id": order["plant_id"], "plant_name": order.get("plant_name"), "customer_name": order.get("customer_name"),
            "customer_mobile": order.get("customer_mobile"),
            "site_name": order.get("site_name"), "site_address": order.get("site_address"), "grade": order.get("grade"),
            "quantity": order.get("quantity"), "tm_number": order.get("tm_number"), "driver_name": order.get("driver_name"),
            "driver_mobile": order.get("driver_mobile"), "created_at": now,
        })
        await orders.update_one({"_id": order["_id"]}, {"$set": {"challan_number": challan_number}})
        if order.get("status") != READY_TO_DISPATCH:
            await transition_order(order_id, READY_TO_DISPATCH, ctx["user_id"], note=f"Challan {challan_number} generated")
    return {"status": READY_TO_DISPATCH}


@router.post("/orders/{order_id}/dispatch")
async def dispatch_dispatch(order_id: str, ctx: dict = Depends(staff_only)):
    _dispatch_only(ctx)
    order = await _scoped_order(ctx, order_id)
    if order.get("status") != READY_TO_DISPATCH:
        raise HTTPException(409, "Generate a challan before dispatching")
    now = datetime.now(timezone.utc)
    await orders.update_one({"_id": order["_id"]}, {"$set": {"dispatched_at": now}})
    if order.get("tm_id"):
        await vehicles.update_one({"_id": await _oid(order["tm_id"])}, {"$set": {"status": "dispatched"}})
    await driver_trips.update_one({"order_id": order_id}, {"$set": {"status": "DISPATCHED", "updated_at": now}})
    await transition_order(order_id, DISPATCHED, ctx["user_id"], note="Dispatched — live tracking available",
                           notify_user_ids=[order["customer_id"]], event="dispatched")
    return {"status": DISPATCHED}
