from fastapi import APIRouter, Depends

from database import kyc_profiles
from roles import ROLE_LABELS
from security import current_user

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
async def me(ctx: dict = Depends(current_user)):
    user = ctx["user"]
    kyc = await kyc_profiles.find_one({"user_id": ctx["user_id"], "purpose": "CUSTOMER"})
    return {
        "id": ctx["user_id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "role": ctx["role"],
        "role_label": ROLE_LABELS.get(ctx["role"], ctx["role"]),
        "roles": ctx["roles"],
        "plant_id": ctx.get("plant_id"),
        "status": user.get("status", "active"),
        "kyc_status": (kyc or {}).get("status", "NOT_STARTED"),
    }
