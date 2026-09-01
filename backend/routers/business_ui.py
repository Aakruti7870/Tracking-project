"""Business-management endpoints used by shared mobile operations screens.

These endpoints intentionally reuse the same plant-visibility/RBAC rules as the
core APIs. They do not create a parallel data model; they expose safe CRUD
operations for owner/admin workflows that previously existed only as UI
placeholders.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from validation import StrictModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, require_business_role, require_visible_plant
from database import materials, orders, users, vehicles, stock_movements
from models import MaterialBody, StockAdjustBody, User, VehicleBody, VehicleStatusBody
from roles import Role
from security import current_user, identifier_key, normalize_identifier

router = APIRouter(prefix="/api/business", tags=["business-management"])

OWNER_ADMIN = (Role.PLANT_OWNER.value, Role.ADMIN.value, Role.CENTRAL_ADMIN.value)
STORE_MANAGERS = (*OWNER_ADMIN, Role.STORE_MANAGER.value)
FLEET_MANAGERS = (*OWNER_ADMIN, Role.FLEET_MANAGER.value)

OWNER_STAFF_ROLES = {
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
}
ADMIN_STAFF_ROLES = OWNER_STAFF_ROLES - {Role.ADMIN.value}


class CreatePlantStaffBody(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(min_length=2, max_length=64)


@router.get("/plants/{plant_id}/customers")
async def plant_customers(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    order_docs = await orders.find({"plant_id": plant_id}).to_list(10000)
    stats: dict[str, dict] = {}
    for order in order_docs:
        customer_id = order.get("customer_id")
        if not customer_id:
            continue
        row = stats.setdefault(customer_id, {"orders": 0, "delivered_m3": 0.0})
        row["orders"] += 1
        if order.get("status") == "DELIVERED":
            row["delivered_m3"] += float(order.get("delivered_quantity") or order.get("quantity") or 0)
    customer_ids = list(stats)
    customer_docs = await users.find({"_id": {"$in": [oid(i) for i in customer_ids]}}).sort("name", 1).to_list(5000)
    return {
        "customers": [
            {
                "id": str(d["_id"]),
                "name": d.get("name"),
                "phone": d.get("phone"),
                "email": d.get("email"),
                "status": d.get("status", "active"),
                "orders": stats.get(str(d["_id"]), {}).get("orders", 0),
                "delivered_m3": round(stats.get(str(d["_id"]), {}).get("delivered_m3", 0.0), 3),
            }
            for d in customer_docs
        ]
    }


@router.post("/plants/{plant_id}/materials")
async def create_material(plant_id: str, body: MaterialBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *STORE_MANAGERS)
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc.update({"plant_id": plant_id, "created_at": now, "updated_at": now})
    try:
        result = await materials.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Material already exists for this plant")
    await write_audit(ctx["user_id"], "material.create", "material", str(result.inserted_id), {"plant_id": plant_id})
    return {"id": str(result.inserted_id)}


@router.post("/plants/{plant_id}/materials/{material_id}/adjust")
async def adjust_material(
    plant_id: str,
    material_id: str,
    body: StockAdjustBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, *STORE_MANAGERS)
    await require_visible_plant(ctx, plant_id)
    material = await materials.find_one({"_id": oid(material_id), "plant_id": plant_id})
    if not material:
        raise HTTPException(404, "Material not found")
    current = float(material.get("stock") or 0)
    target = current + float(body.delta)
    if target < -0.001:
        raise HTTPException(409, "Stock cannot become negative")
    now = datetime.now(timezone.utc)
    updated = await materials.find_one_and_update(
        {"_id": material["_id"], "plant_id": plant_id, "stock": material.get("stock", 0)},
        {"$inc": {"stock": body.delta}, "$set": {"updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Stock changed concurrently; reload and retry")
    await stock_movements.insert_one(
        {
            "plant_id": plant_id,
            "material_id": material_id,
            "material_name": material.get("name"),
            "delta": body.delta,
            "balance": updated.get("stock"),
            "note": body.note,
            "source": "manual_adjustment",
            "created_at": now,
            "created_by": ctx["user_id"],
        }
    )
    await write_audit(ctx["user_id"], "material.adjust", "material", material_id, {"delta": body.delta})
    return {"stock": updated.get("stock")}


@router.post("/plants/{plant_id}/vehicles")
async def create_vehicle(plant_id: str, body: VehicleBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *FLEET_MANAGERS)
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc.update({"plant_id": plant_id, "status": "available", "created_at": now, "updated_at": now})
    try:
        result = await vehicles.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Transit mixer number already exists for this plant")
    await write_audit(ctx["user_id"], "vehicle.create", "vehicle", str(result.inserted_id), {"plant_id": plant_id})
    return {"id": str(result.inserted_id)}


@router.post("/plants/{plant_id}/vehicles/{vehicle_id}/status")
async def set_vehicle_status(
    plant_id: str,
    vehicle_id: str,
    body: VehicleStatusBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, *FLEET_MANAGERS)
    await require_visible_plant(ctx, plant_id)
    vehicle = await vehicles.find_one({"_id": oid(vehicle_id), "plant_id": plant_id})
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")
    if vehicle.get("current_load_id") or vehicle.get("current_order_id"):
        raise HTTPException(409, "Vehicle assigned to an active order/load")
    await vehicles.update_one(
        {"_id": vehicle["_id"]},
        {"$set": {"status": body.status, "updated_at": datetime.now(timezone.utc)}},
    )
    await write_audit(ctx["user_id"], "vehicle.status", "vehicle", vehicle_id, {"status": body.status})
    return {"status": body.status}


@router.post("/plants/{plant_id}/people")
async def create_plant_staff(
    plant_id: str,
    body: CreatePlantStaffBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, Role.PLANT_OWNER.value, Role.ADMIN.value)
    await require_visible_plant(ctx, plant_id)
    allowed = OWNER_STAFF_ROLES if ctx["role"] == Role.PLANT_OWNER.value else ADMIN_STAFF_ROLES
    if body.role not in allowed:
        raise HTTPException(403, "This role cannot be created from Plant Staff Management")

    channel, email = normalize_identifier(body.email)
    if channel != "email":
        raise HTTPException(422, "Plant staff must use a valid email address")
    key = identifier_key(email)
    if await users.find_one({"identifier_keys": key}):
        raise HTTPException(409, "An account already exists for this email")

    now = datetime.now(timezone.utc)
    account = User(
        name=body.name.strip(),
        email=email,
        identifier_keys=[key],
        roles=[body.role],
        primary_role=body.role,
        plant_id=plant_id,
        created_at=now,
    )
    try:
        result = await users.insert_one(account.to_mongo())
    except DuplicateKeyError:
        raise HTTPException(409, "An account already exists for this email")
    await write_audit(
        ctx["user_id"], "staff.create", "user", str(result.inserted_id),
        {"plant_id": plant_id, "role": body.role},
    )
    return {"id": str(result.inserted_id), "status": "active", "role": body.role}


@router.post("/plants/{plant_id}/people/{user_id}/suspend")
async def suspend_staff(plant_id: str, user_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *OWNER_ADMIN)
    await require_visible_plant(ctx, plant_id)
    if user_id == ctx["user_id"]:
        raise HTTPException(409, "You cannot suspend your own account")
    person = await users.find_one({"_id": oid(user_id), "plant_id": plant_id})
    if not person:
        raise HTTPException(404, "Plant staff member not found")
    if person.get("primary_role") in (Role.CUSTOMER.value, Role.PLANT_OWNER.value, Role.CENTRAL_ADMIN.value):
        raise HTTPException(403, "This account cannot be suspended from the plant staff screen")
    await users.update_one({"_id": person["_id"]}, {"$set": {"status": "suspended", "updated_at": datetime.now(timezone.utc)}})
    await write_audit(ctx["user_id"], "staff.suspend", "user", user_id, {"plant_id": plant_id})
    return {"status": "suspended"}


@router.post("/plants/{plant_id}/people/{user_id}/activate")
async def activate_staff(plant_id: str, user_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *OWNER_ADMIN)
    await require_visible_plant(ctx, plant_id)
    person = await users.find_one({"_id": oid(user_id), "plant_id": plant_id})
    if not person:
        raise HTTPException(404, "Plant staff member not found")
    await users.update_one({"_id": person["_id"]}, {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}})
    await write_audit(ctx["user_id"], "staff.activate", "user", user_id, {"plant_id": plant_id})
    return {"status": "active"}
