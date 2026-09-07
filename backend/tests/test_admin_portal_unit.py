import asyncio
from datetime import datetime, timezone
from pathlib import Path

from routers import admin_portal


FORBIDDEN = {
    "identifier_keys", "totp_secret", "passkeys", "lat", "lng", "address",
    "site_address", "contact_phone", "messages", "provider_payload", "api_key",
    "access_token", "refresh_token", "payment_session_id", "cashfree_order_id", "meta",
}


def _assert_minimized(row: dict):
    assert not FORBIDDEN.intersection(row), f"forbidden portal fields leaked: {FORBIDDEN.intersection(row)}"


def test_portal_serializers_minimize_privileged_data():
    now = datetime.now(timezone.utc)
    noisy = {
        "_id": "id-1", "name": "Example", "email": "user@example.com", "phone": "9999999999",
        "primary_role": "customer", "status": "active", "plant_id": "plant-1", "created_at": now,
        "identifier_keys": ["secret-hash"], "totp_secret": "secret", "passkeys": ["secret"],
        "city": "Panvel", "district": "Raigad", "verified": True, "owner_id": "owner-1",
        "lat": 1.2, "lng": 3.4, "address": "private", "contact_phone": "private",
        "user_id": "user-1", "purpose": "CUSTOMER", "updated_at": now,
        "provider_payload": {"aadhaar": "hidden"},
        "order_number": "ORD-1", "customer_id": "customer-1", "plant_name": "Plant",
        "grade": "M30", "quantity": 5, "site_name": "Site", "site_address": "private",
        "delivery_date": "2026-09-06", "delivery_mode": "DELIVERY", "payment_status": "UNPAID",
        "case_number": "SUP-1", "category": "LOGIN", "order_id": "order-1", "messages": [{"message": "private"}],
        "invoice_id": "inv-1", "amount": 100, "method": "UPI", "payment_session_id": "secret",
        "cashfree_order_id": "secret", "actor_id": "admin-1", "action": "test", "entity_type": "user",
        "entity_id": "user-1", "meta": {"token": "secret"},
    }
    for serializer in (
        admin_portal._safe_user,
        admin_portal._safe_plant,
        admin_portal._safe_kyc,
        admin_portal._safe_order,
        admin_portal._safe_support_case,
        admin_portal._safe_audit,
    ):
        row = serializer(noisy)
        _assert_minimized(row)
    _assert_minimized(admin_portal._safe_payment(noisy, "invoice"))
    _assert_minimized(admin_portal._safe_payment(noisy, "plan"))


def test_admin_portal_is_read_only_and_sensitive_lists_require_explicit_permissions():
    source = Path(admin_portal.__file__).read_text(encoding="utf-8")
    assert '@router.post(' not in source
    assert '@router.put(' not in source
    assert '@router.patch(' not in source
    assert '@router.delete(' not in source
    for route, permission in (
        ("/users", "USER_VIEW"),
        ("/audit", "AUDIT_VIEW"),
        ("/system", "SYSTEM_VIEW"),
    ):
        marker = f'@router.get("{route}")'
        start = source.index(marker)
        section = source[start:start + 500]
        expected = f"Depends(require_permission(Permission.{permission}))"
        assert expected in section, f"{route} must require {permission}"


class _CountCollection:
    def __init__(self, value): self.value = value; self.queries = []
    async def count_documents(self, query): self.queries.append(query); return self.value


def test_summary_uses_server_side_counts(monkeypatch):
    fake_plants = _CountCollection(3)
    fake_users = _CountCollection(11)
    fake_orders = _CountCollection(4)
    fake_support = _CountCollection(2)
    monkeypatch.setattr(admin_portal, "plants", fake_plants)
    monkeypatch.setattr(admin_portal, "users", fake_users)
    monkeypatch.setattr(admin_portal, "orders", fake_orders)
    monkeypatch.setattr(admin_portal, "support_cases", fake_support)

    result = asyncio.run(admin_portal.summary({
        "role": "central_admin",
        "user": {"email": "support@trackmyrmc.com"},
        "session": {
            "control_center_mfa_authenticated": True,
            "auth_surface": "control_center_web",
        },
    }))
    values = {item["label"]: item["value"] for item in result["kpis"]}
    assert values == {"Plants": 3, "Users": 11, "Active Orders": 4, "Open Support": 2}
    assert result["generated_at"]
