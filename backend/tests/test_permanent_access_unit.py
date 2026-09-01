"""Regression coverage for removal of permanent authentication bypasses."""

from pathlib import Path

from routers import permanent_access


def test_compatibility_router_does_not_override_authentication_routes():
    paths = {route.path for route in permanent_access.router.routes}
    assert "/api/auth/request-otp" not in paths
    assert "/api/auth/verify-otp" not in paths
    assert "/api/auth/staff/request-otp" not in paths
    assert "/api/auth/staff/verify-otp" not in paths
    assert paths == {"/api/customer/kyc"}


def test_no_fixed_demo_otp_or_privileged_email_bootstrap_remains():
    source = Path(permanent_access.__file__).read_text(encoding="utf-8")
    assert "DEMO_OTP" not in source
    assert "PERMANENT_AUTHORITY_EMAILS" not in source
    assert "_ensure_authority" not in source
    assert "primary_role\": Role.AUTHORITY" not in source
