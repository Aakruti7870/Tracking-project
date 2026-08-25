"""Persistent master-data APIs for real RMC plant operations."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from business_access import oid, require_business_role, require_visible_plant, visible_plant_ids
from business_models import (
    CustomerSiteBody,
    MixDesignBody,
    PlantBusinessProfileBody,
    RateCardBody,
    SupplierBody,
)
from database import (
    customer_sites,
    invoices,
    materials,
    mix_designs,
    orders,
    plant_business_profiles,
    quotations,
    quotation_requests,
    plants,
    rate_cards,
    suppliers,
    users,
    vehicles,
)
from roles import ROLE_LABELS, Role
from security import current_user

router = APIRouter(prefix="/api/master", tags=["master-data"])


def _serialize(doc: dict) -> dict:
    out = {**doc, "id": str(doc["_id"])}
    out.pop("_id", None)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


async def _public_or_visible_plant(ctx: dict, plant_id: str) -> dict:
    plant = await plants.find_one({"_id": oid(plant_id)})
    if not plant:
        raise HTTPException(404, "Plant not found")
    if ctx.get("role") == Role.CUSTOMER.value:
        if plant.get("status") != "active" or not plant.get("verified"):
            raise HTTPException(404, "Plant not found")
        return plant
    await require_visible_plant(ctx, plant_id)
    return plant


@router.get("/my-plants")
async def my_plants(ctx: dict = Depends(current_user)):
    """Return the plant selector used by authenticated business screens."""
    ids = await visible_plant_ids(ctx)
    if not ids:
        return {"plants": []}
    docs = await plants.find({"_id": {"$in": [oid(i) for i in ids]}}).sort("name", 1).to_list(5000)
    return {
        "plants": [
            {
                "id": str(d["_id"]),
                "name": d.get("name"),
                "city": d.get("city"),
                "status": d.get("status"),
                "verified": bool(d.get("verified")),
                "grades": d.get("grades", []),
            }
            for d in docs
        ]
    }


@router.get("/plants/{plant_id}/resources")
async def plant_resources(plant_id: str, ctx: dict = Depends(current_user)):
    """Small reference lists for forms: materials, mixers and plant people."""
    await require_visible_plant(ctx, plant_id)
    material_docs = await materials.find({"plant_id": plant_id}).sort("name", 1).to_list(1000)
    vehicle_docs = await vehicles.find({"plant_id": plant_id}).sort("tm_number", 1).to_list(1000)
    people_docs = await users.find({"plant_id": plant_id, "status": "active"}).sort("name", 1).to_list(2000)
    return {
        "materials": [
            {
                "id": str(d["_id"]), "code": d.get("code"), "name": d.get("name"),
                "unit": d.get("unit"), "stock": d.get("stock", 0), "reorder": d.get("reorder", 0),
            }
            for d in material_docs
        ],
        "vehicles": [
            {
                "id": str(d["_id"]), "tm_number": d.get("tm_number"),
                "capacity_m3": d.get("capacity_m3"), "status": d.get("status"),
            }
            for d in vehicle_docs
        ],
        "people": [
            {
                "id": str(d["_id"]), "name": d.get("name"), "role": d.get("primary_role"),
                "role_label": ROLE_LABELS.get(d.get("primary_role"), d.get("primary_role")),
                "phone": d.get("phone"), "email": d.get("email"),
            }
            for d in people_docs
        ],
    }


@router.get("/plants/{plant_id}/people")
async def plant_people(
    plant_id: str,
    role: str | None = Query(default=None),
    ctx: dict = Depends(current_user),
):
    await require_visible_plant(ctx, plant_id)
    query: dict = {"plant_id": plant_id}
    if role:
        query["primary_role"] = role
    docs = await users.find(query).sort("name", 1).to_list(2000)
    return {
        "people": [
            {
                "id": str(d["_id"]), "name": d.get("name"), "role": d.get("primary_role"),
                "role_label": ROLE_LABELS.get(d.get("primary_role"), d.get("primary_role")),
                "phone": d.get("phone"), "email": d.get("email"), "status": d.get("status", "active"),
            }
            for d in docs
        ]
    }


@router.get("/plants/{plant_id}/summary")
async def plant_summary(plant_id: str, ctx: dict = Depends(current_user)):
    await require_visible_plant(ctx, plant_id)
    order_docs = await orders.find({"plant_id": plant_id}).to_list(5000)
    invoice_docs = await invoices.find({"plant_id": plant_id}).to_list(5000)
    material_docs = await materials.find({"plant_id": plant_id}).to_list(2000)
    vehicle_docs = await vehicles.find({"plant_id": plant_id}).to_list(2000)
    delivered = [o for o in order_docs if o.get("status") == "DELIVERED"]
    active = [o for o in order_docs if o.get("status") not in ("DELIVERED", "REJECTED", "CANCELLED")]
    billed = round(sum(float(i.get("total") or 0) for i in invoice_docs), 2)
    paid = round(sum(float(i.get("paid") or 0) for i in invoice_docs), 2)
    return {
        "orders": len(order_docs),
        "active_orders": len(active),
        "delivered_orders": len(delivered),
        "delivered_m3": round(sum(float(o.get("delivered_quantity") or o.get("quantity") or 0) for o in delivered), 3),
        "billed": billed,
        "received": paid,
        "outstanding": round(billed - paid, 2),
        "materials": len(material_docs),
        "low_stock": sum(1 for m in material_docs if float(m.get("stock") or 0) <= float(m.get("reorder") or 0)),
        "fleet": len(vehicle_docs),
        "available_mixers": sum(1 for v in vehicle_docs if v.get("status") == "available"),
    }


@router.get("/plants/{plant_id}/profile")
async def plant_profile(plant_id: str, ctx: dict = Depends(current_user)):
    await _public_or_visible_plant(ctx, plant_id)
    doc = await plant_business_profiles.find_one({"plant_id": plant_id})
    return {"profile": _serialize(doc) if doc else None}


@router.put("/plants/{plant_id}/profile")
async def put_plant_profile(
    plant_id: str,
    body: PlantBusinessProfileBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.CENTRAL_ADMIN.value)
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    payload = body.model_dump()
    payload.update({"plant_id": plant_id, "updated_at": now, "updated_by": ctx["user_id"]})
    await plant_business_profiles.update_one(
        {"plant_id": plant_id},
        {"$set": payload, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    doc = await plant_business_profiles.find_one({"plant_id": plant_id})
    return {"profile": _serialize(doc)}


@router.get("/plants/{plant_id}/rate-cards")
async def list_rate_cards(
    plant_id: str,
    active_only: bool = True,
    ctx: dict = Depends(current_user),
):
    await _public_or_visible_plant(ctx, plant_id)
    query: dict = {"plant_id": plant_id}
    if active_only:
        query["active"] = True
    docs = await rate_cards.find(query).sort([("grade", 1), ("effective_from", -1)]).to_list(500)
    return {"rate_cards": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/rate-cards")
async def create_rate_card(
    plant_id: str,
    body: RateCardBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value)
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    if body.active:
        await rate_cards.update_many(
            {"plant_id": plant_id, "grade": body.grade, "active": True},
            {"$set": {"active": False, "updated_at": now}},
        )
    doc = body.model_dump(mode="json")
    doc.update({"plant_id": plant_id, "created_at": now, "created_by": ctx["user_id"]})
    result = await rate_cards.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"rate_card": _serialize(doc)}


@router.get("/plants/{plant_id}/mix-designs")
async def list_mix_designs(
    plant_id: str,
    active_only: bool = True,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.OPERATOR.value,
        Role.QUALITY_ENGINEER.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    query: dict = {"plant_id": plant_id}
    if active_only:
        query["active"] = True
    docs = await mix_designs.find(query).sort([("grade", 1), ("version", -1)]).to_list(500)
    return {"mix_designs": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/mix-designs")
async def create_mix_design(
    plant_id: str,
    body: MixDesignBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.QUALITY_ENGINEER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    if body.active:
        await mix_designs.update_many(
            {"plant_id": plant_id, "grade": body.grade, "active": True},
            {"$set": {"active": False, "updated_at": now}},
        )
    doc = body.model_dump()
    doc.update({"plant_id": plant_id, "created_at": now, "created_by": ctx["user_id"]})
    result = await mix_designs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"mix_design": _serialize(doc)}


@router.get("/customer/sites")
async def list_customer_sites(ctx: dict = Depends(current_user)):
    require_business_role(ctx, Role.CUSTOMER.value)
    docs = await customer_sites.find({"customer_id": ctx["user_id"]}).sort("created_at", -1).to_list(500)
    return {"sites": [_serialize(d) for d in docs]}


@router.post("/customer/sites")
async def create_customer_site(body: CustomerSiteBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, Role.CUSTOMER.value)
    now = datetime.now(timezone.utc)
    if body.is_default:
        await customer_sites.update_many(
            {"customer_id": ctx["user_id"], "is_default": True},
            {"$set": {"is_default": False, "updated_at": now}},
        )
    doc = body.model_dump()
    doc.update({"customer_id": ctx["user_id"], "created_at": now, "updated_at": now})
    result = await customer_sites.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"site": _serialize(doc)}


@router.delete("/customer/sites/{site_id}")
async def delete_customer_site(site_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, Role.CUSTOMER.value)
    linked = (
        await orders.count_documents({"customer_id": ctx["user_id"], "site_id": site_id})
        + await quotations.count_documents({"customer_id": ctx["user_id"], "site_id": site_id})
        + await quotation_requests.count_documents({"customer_id": ctx["user_id"], "site_id": site_id})
    )
    if linked:
        raise HTTPException(409, "Site has linked orders or quotations and cannot be removed")
    result = await customer_sites.delete_one({"_id": oid(site_id), "customer_id": ctx["user_id"]})
    if result.deleted_count != 1:
        raise HTTPException(404, "Site not found")
    return {"status": "deleted"}


@router.get("/plants/{plant_id}/suppliers")
async def list_suppliers(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    docs = await suppliers.find({"plant_id": plant_id}).sort("name", 1).to_list(500)
    return {"suppliers": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/suppliers")
async def create_supplier(
    plant_id: str,
    body: SupplierBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc.update({"plant_id": plant_id, "created_at": now, "created_by": ctx["user_id"]})
    result = await suppliers.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"supplier": _serialize(doc)}
