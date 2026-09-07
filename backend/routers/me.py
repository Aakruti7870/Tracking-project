from fastapi import APIRouter, Depends

from config import settings
from database import kyc_profiles, users
from roles import ROLE_LABELS
from security import current_user

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
async def me(ctx: dict = Depends(current_user)):
    user = ctx["user"]
    kyc = await kyc_profiles.find_one({"user_id": ctx["user_id"], "purpose": "CUSTOMER"})

    # Historical verified records may already contain the minimal verified-name
    # metadata even though users.name was not updated. Reconcile only that
    # provider-derived value; never infer identity from login identifiers.
    stored_verified_name = " ".join(str((kyc or {}).get("kyc_verified_name") or (kyc or {}).get("kyc_name") or "").split())
    if kyc and kyc.get("status") == "VERIFIED" and stored_verified_name and not str(user.get("name") or "").strip():
        await users.update_one({"_id": user["_id"]}, {"$set": {"name": stored_verified_name}})
        user = {**user, "name": stored_verified_name}
    if kyc and kyc.get("status") == "VERIFIED" and not stored_verified_name and not kyc.get("provider_session_id"):
        await kyc_profiles.update_one(
            {"_id": kyc["_id"], "status": "VERIFIED"},
            {"$set": {"status": "REQUIRES_REVERIFICATION", "name_sync_pending": False}},
        )
        kyc = {**kyc, "status": "REQUIRES_REVERIFICATION", "name_sync_pending": False}

    # A few production KYC completions were finalized by the permanent-access
    # compatibility route before the verified DigiLocker name was copied into
    # users.name. Reconcile that safely whenever the profile is loaded so an
    # approved customer immediately sees their verified name after login.
    if (
        kyc
        and kyc.get("status") == "VERIFIED"
        and kyc.get("provider_session_id")
        and (kyc.get("name_sync_pending") or not kyc.get("kyc_name"))
    ):
        from routers.customer import _sync_customer_verified_name

        synced = await _sync_customer_verified_name(ctx["user_id"], kyc)
        if synced:
            refreshed = await users.find_one({"_id": user["_id"]})
            if refreshed:
                user = refreshed

    mfa = user.get("mfa") if isinstance(user.get("mfa"), dict) else {}
    passkeys = mfa.get("passkeys") if isinstance(mfa.get("passkeys"), list) else []
    active_passkeys = [
        item for item in passkeys if isinstance(item, dict) and item.get("active", True)
    ]
    return {
        "id": ctx["user_id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "mobile": user.get("phone"),
        "role": ctx["role"],
        "role_label": ROLE_LABELS.get(ctx["role"], ctx["role"]),
        "roles": ctx["roles"],
        "plant_id": ctx.get("plant_id"),
        "status": user.get("status", "active"),
        "kyc_status": (kyc or {}).get("status", "NOT_STARTED"),
        "mfa_enabled": bool(mfa.get("enabled") and mfa.get("totp_secret")),
        "mfa_configured": bool(settings.MFA_ENCRYPTION_KEY and len(settings.MFA_ENCRYPTION_KEY) >= 32),
        "passkey_enabled": bool(active_passkeys),
        "passkey_count": len(active_passkeys),
    }
