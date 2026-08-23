"""Plant Operator production actions that use the shared production service."""
from fastapi import APIRouter, Depends, HTTPException

from database import orders
from models import ProductionBatchBody
from order_service import IN_PRODUCTION
from production_service import record_production_batch
from roles import Role
from security import require_role

router = APIRouter(prefix="/api/staff", tags=["operator-production"])
operator_only = require_role(Role.OPERATOR.value)


async def _oid(value: str):
    from bson import ObjectId
    try:
        return ObjectId(value)
    except Exception:
        return value


@router.post("/orders/{order_id}/production/batch")
async def operator_add_batch(
    order_id: str,
    body: ProductionBatchBody,
    ctx: dict = Depends(operator_only),
):
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": ctx["plant_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") != IN_PRODUCTION:
        raise HTTPException(409, "Start production before adding a batch")
    return await record_production_batch(
        order=order,
        quantity=body.quantity,
        actor_id=ctx["user_id"],
        remarks=body.remarks,
        batch_reference=body.batch_reference,
        consume_materials=body.consume_materials,
    )
