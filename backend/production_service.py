"""Production batch posting with mix-design driven inventory consumption."""
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument

from config import settings
from database import materials, mix_designs, production_batches, stock_movements

_COMPONENTS = (
    ("cement_kg", "CEMENT", "kg"),
    ("fly_ash_kg", "FLY_ASH", "kg"),
    ("c_sand_kg", "C_SAND", "kg"),
    ("sand_kg", "SAND", "kg"),
    ("aggregate_10mm_kg", "AGGREGATE_10MM", "kg"),
    ("aggregate_20mm_kg", "AGGREGATE_20MM", "kg"),
    ("admixture_kg", "ADMIXTURE", "kg"),
    ("water_litre", "WATER", "litre"),
)


def _convert_to_stock_unit(amount: float, source_unit: str, stock_unit: str) -> float:
    unit = (stock_unit or "").strip().lower().replace(" ", "")
    if source_unit == "kg":
        if unit in {"kg", "kgs", "kilogram", "kilograms"}:
            return amount
        if unit in {"t", "ton", "tons", "tonne", "tonnes", "mt"}:
            return amount / 1000.0
    if source_unit == "litre":
        if unit in {"l", "ltr", "litre", "litres", "liter", "liters"}:
            return amount
        if unit in {"kl", "kilolitre", "kilolitres", "kiloliter", "kiloliters"}:
            return amount / 1000.0
    raise HTTPException(422, f"Unsupported inventory unit '{stock_unit}' for {source_unit} consumption")


async def record_production_batch(
    *,
    order: dict,
    quantity: float,
    actor_id: str,
    remarks: str | None = None,
    batch_reference: str | None = None,
    consume_materials: bool = True,
) -> dict:
    """Post one production batch and its stock movements as one logical unit.

    Standalone Mongo deployments may not provide multi-document transactions,
    so every stock decrement has explicit compensation on a later failure.
    """
    order_id = str(order["_id"])
    ordered_qty = float(order.get("quantity") or 0)
    produced_rows = await production_batches.aggregate(
        [
            {"$match": {"order_id": order_id}},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}},
        ]
    ).to_list(1)
    already_produced = float(produced_rows[0]["total"] if produced_rows else 0)
    if already_produced + quantity > ordered_qty * 1.02 + 0.001:
        raise HTTPException(422, "Batch would exceed the order quantity tolerance")

    if not consume_materials and not settings.is_dev:
        raise HTTPException(422, "Material consumption cannot be bypassed outside development/test")

    design = None
    requirements: list[dict] = []
    if consume_materials:
        design = await mix_designs.find_one(
            {"plant_id": order["plant_id"], "grade": order.get("grade"), "active": True},
            sort=[("version", -1)],
        )
        if not design:
            raise HTTPException(409, f"No active mix design configured for {order.get('grade')}")

        for field, code, source_unit in _COMPONENTS:
            per_m3 = float(design.get(field) or 0)
            if per_m3 <= 0:
                continue
            material = await materials.find_one({"plant_id": order["plant_id"], "code": code})
            if not material:
                raise HTTPException(409, f"Inventory material code {code} is not configured for this plant")
            raw_amount = per_m3 * quantity
            stock_amount = round(_convert_to_stock_unit(raw_amount, source_unit, material.get("unit")), 6)
            if float(material.get("stock") or 0) + 1e-9 < stock_amount:
                raise HTTPException(
                    409,
                    f"Insufficient {material.get('name') or code} stock: need {stock_amount:g} {material.get('unit')}",
                )
            requirements.append(
                {
                    "material": material,
                    "code": code,
                    "amount": stock_amount,
                    "raw_amount": round(raw_amount, 6),
                    "source_unit": source_unit,
                }
            )

    now = datetime.now(timezone.utc)
    decremented: list[dict] = []
    try:
        for req in requirements:
            material = req["material"]
            updated = await materials.find_one_and_update(
                {"_id": material["_id"], "stock": {"$gte": req["amount"]}},
                {"$inc": {"stock": -req["amount"]}, "$set": {"updated_at": now}},
                return_document=ReturnDocument.AFTER,
            )
            if not updated:
                raise HTTPException(409, f"Inventory changed concurrently for {material.get('name')}")
            decremented.append(req)

        batch_doc = {
            "order_id": order_id,
            "plant_id": order["plant_id"],
            "grade": order.get("grade"),
            "quantity": quantity,
            "batch_reference": batch_reference,
            "remarks": remarks,
            "batcher_id": actor_id,
            "mix_design_id": str(design["_id"]) if design else None,
            "mix_design_version": design.get("version") if design else None,
            "material_consumption": [
                {
                    "material_id": str(req["material"]["_id"]),
                    "code": req["code"],
                    "name": req["material"].get("name"),
                    "stock_quantity": req["amount"],
                    "stock_unit": req["material"].get("unit"),
                    "design_quantity": req["raw_amount"],
                    "design_unit": req["source_unit"],
                }
                for req in requirements
            ],
            "created_at": now,
        }
        inserted = await production_batches.insert_one(batch_doc)
        batch_doc["_id"] = inserted.inserted_id

        if requirements:
            movement_docs = [
                {
                    "plant_id": order["plant_id"],
                    "material_id": str(req["material"]["_id"]),
                    "material_name": req["material"].get("name"),
                    "material_code": req["code"],
                    "delta": -req["amount"],
                    "reason": "PRODUCTION_BATCH",
                    "order_id": order_id,
                    "batch_id": str(inserted.inserted_id),
                    "created_at": now,
                    "actor_id": actor_id,
                }
                for req in requirements
            ]
            await stock_movements.insert_many(movement_docs)

    except Exception:
        for req in reversed(decremented):
            await materials.update_one(
                {"_id": req["material"]["_id"]},
                {"$inc": {"stock": req["amount"]}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            )
        if "batch_doc" in locals() and batch_doc.get("_id"):
            await production_batches.delete_one({"_id": batch_doc["_id"]})
        raise

    produced_total = round(already_produced + quantity, 6)
    return {
        "batch_id": str(batch_doc["_id"]),
        "produced": produced_total,
        "required": ordered_qty,
        "mix_design_version": design.get("version") if design else None,
        "material_consumption": batch_doc["material_consumption"],
    }
