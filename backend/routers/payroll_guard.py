"""Compatibility guard for the pre-PR32 direct payroll mutation route.

The historical finance endpoint allowed privileged callers to write DRAFT,
APPROVED or PAID directly. PR32 introduces separation of duties, so the old
mutation path must fail closed while its read endpoint remains available.
"""
from fastapi import APIRouter, Depends, HTTPException

from security import current_user

router = APIRouter(tags=["payroll-compatibility"])


@router.put("/api/ops/plants/{plant_id}/payroll", include_in_schema=False)
async def retired_direct_payroll_write(plant_id: str, ctx: dict = Depends(current_user)):
    del plant_id, ctx
    raise HTTPException(
        409,
        "Direct payroll writes are retired. Use Workforce Reports & Payroll: Accountant draft, Plant Owner approval, then Accountant payment posting.",
    )
