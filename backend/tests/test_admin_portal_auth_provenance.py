import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import admin_auth, admin_portal


def _portal_ctx(role="central_admin", authenticated=True):
    session = {admin_auth.PORTAL_SESSION_FLAG: True} if authenticated else {}
    return {
        "user_id": "admin-1",
        "sid": "session-1",
        "role": role,
        "roles": [role],
        "plant_id": None,
        "user": {"_id": "admin-1", "primary_role": role},
        "session": session,
    }


def test_platform_admin_requires_portal_totp_provenance():
    with pytest.raises(HTTPException) as exc:
        admin_auth.platform_admin(_portal_ctx(authenticated=False))
    assert exc.value.status_code == 403
    assert "portal authentication" in exc.value.detail.lower()

    accepted = admin_auth.platform_admin(_portal_ctx(authenticated=True))
    assert accepted["role"] == "central_admin"


def test_authority_portal_session_cannot_use_central_admin_only_dependency():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(admin_portal.central_admin_only(_portal_ctx(role="authority", authenticated=True)))
    assert exc.value.status_code == 403

    accepted = asyncio.run(admin_portal.central_admin_only(_portal_ctx(role="central_admin", authenticated=True)))
    assert accepted["role"] == "central_admin"


def test_admin_totp_login_marks_server_side_session_provenance():
    source = Path(admin_auth.__file__).read_text(encoding="utf-8")
    assert 'PORTAL_SESSION_FLAG = "admin_portal_totp_authenticated"' in source
    assert "{PORTAL_SESSION_FLAG: True" in source
    assert "ctx.get(\"session\")" in source
    assert "Privileged portal authentication required" in source


def test_role_only_admin_session_can_establish_step_up_without_portal_access(monkeypatch):
    ctx = _portal_ctx(authenticated=False)
    update_filters = []

    monkeypatch.setattr(admin_auth.staff_mfa, "_mfa_doc", lambda user: {"totp_secret": "encrypted"})
    monkeypatch.setattr(admin_auth.staff_mfa, "_decrypt_secret", lambda value: "secret")
    monkeypatch.setattr(admin_auth.staff_mfa, "_verify_totp", lambda secret, code: True)

    async def fake_update_one(query, update):
        update_filters.append(query)
        ctx["session"].update(update["$set"])
        return SimpleNamespace(modified_count=1)

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(admin_auth.sessions, "update_one", fake_update_one)
    monkeypatch.setattr(admin_auth, "write_audit", fake_audit)

    result = asyncio.run(admin_auth.step_up(admin_auth.StepUpBody(code="123456"), ctx))
    assert result == {"status": "verified", "expires_in": admin_auth.ADMIN_STEP_UP_SECONDS}
    assert update_filters == [{"_id": "session-1", "user_id": "admin-1", "revoked": False}]
    assert admin_auth.PORTAL_SESSION_FLAG not in update_filters[0]

    accepted = asyncio.run(admin_auth.require_recent_admin_step_up(ctx))
    assert accepted["user_id"] == "admin-1"

    with pytest.raises(HTTPException) as exc:
        admin_auth.platform_admin(ctx)
    assert exc.value.status_code == 403
    assert "portal authentication" in exc.value.detail.lower()


def test_plan_payment_provider_is_cashfree_without_gateway_secret_projection():
    row = admin_portal._safe_payment(
        {"_id": "payment-1", "order_number": "PLAN-1", "plant_id": "plant-1", "payable": 2500, "status": "PAYMENT_PENDING"},
        "plan",
    )
    assert row["method"] == "CASHFREE"
    assert "payment_session_id" not in row
    assert "cashfree_order_id" not in row

    source = Path(admin_portal.__file__).read_text(encoding="utf-8")
    payment_section = source[source.index('@router.get("/payments")'):source.index('@router.get("/support")')]
    assert "payment_session_id" not in payment_section
    assert "cashfree_order_id" not in payment_section
