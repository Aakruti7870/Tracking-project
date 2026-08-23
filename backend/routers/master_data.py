"""Persistent master-data APIs for real RMC plant operations."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from business_access import oid, require_business_role, require_visible_plant
from business_models import (
    CustomerSiteBody,
    MixDesignBody,
    PlantBusinessProfileBody,
    RateCardBody,
    SupplierBody,
)
from database import (
    customer_sites,
    mix_designs,
    plant_business_profiles,
    plants,
    rate_cards,
    suppliers,
)
from roles import Role
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
