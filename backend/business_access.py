"""Shared authorization helpers for plant-scoped business modules."""
from bson import ObjectId
from fastapi import HTTPException

from database import plants
from roles import Role

PLANT_STAFF = {
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
}
PLATFORM_ROLES = {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}


def oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


async def visible_plant_ids(ctx: dict) -> list[str]:
    """Return plant ids the current account may operate on."""
    role = ctx.get("role")
    if role == Role.PLANT_OWNER.value:
        docs = await plants.find({"owner_id": ctx["user_id"]}).to_list(500)
        return [str(doc["_id"]) for doc in docs]
    if role in PLANT_STAFF:
        plant_id = ctx.get("plant_id")
        if not plant_id:
            raise HTTPException(403, "Plant assignment required")
        return [plant_id]
    if role == Role.CENTRAL_ADMIN.value:
        docs = await plants.find({}).to_list(5000)
        return [str(doc["_id"]) for doc in docs]
    return []


async def require_visible_plant(ctx: dict, plant_id: str) -> None:
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


def require_business_role(ctx: dict, *roles: str) -> None:
    if ctx.get("role") not in roles:
        raise HTTPException(403, "Insufficient permissions")
