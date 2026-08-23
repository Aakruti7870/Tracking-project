"""Plant Operator production actions that use the shared production service."""
from fastapi import APIRouter, Depends, HTTPException

from database import orders, production_batches
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


async def _operator_order(order_id: str, ctx: dict) -> dict:
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": ctx["plant_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@router.get("/orders/{order_id}/production")
async def operator_production_detail(order_id: str, ctx: dict = Depends(operator_only)):
    order = await _operator_order(order_id, ctx)
    rows = await production_batches.find({"order_id": order_id}).sort("created_at", 1).to_list(1000)
    produced = round(sum(float(r.get("quantity") or 0) for r in rows), 3)
    ordered = float(order.get("quantity") or 0)
    return {
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "grade": order.get("grade"),
        "status": order.get("status"),
        "ordered_quantity": ordered,
        "produced_quantity": produced,
        "remaining_quantity": round(max(0, ordered - produced), 3),
        "batches": [
            {
                "id": str(r["_id"]),
                "quantity": r.get("quantity"),
                "batch_reference": r.get("batch_reference"),
                "remarks": r.get("remarks"),
                "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                "consumed_materials": r.get("consumed_materials", []),
            }
            for r in rows
        ],
    }


@router.post("/orders/{order_id}/production/batch")
async def operator_add_batch(
    order_id: str,
    body: ProductionBatchBody,
    ctx: dict = Depends(operator_only),
):
    order = await _operator_order(order_id, ctx)
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
