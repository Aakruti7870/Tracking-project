"""Regression guards for retirement of legacy Google Plant Staff authentication."""

from request_security import RETIRED_AUTH_PATH_PREFIXES, is_retired_auth_path


def test_all_legacy_google_staff_auth_routes_are_retired():
    assert RETIRED_AUTH_PATH_PREFIXES == ("/api/auth/google/",)
    for path in (
        "/api/auth/google/start",
        "/api/auth/google/callback",
        "/api/auth/google/exchange",
    ):
        assert is_retired_auth_path(path)


def test_current_authentication_surfaces_are_not_blocked():
    for path in (
        "/api/auth/request-otp",
        "/api/auth/verify-otp",
        "/api/auth/staff/request-otp",
        "/api/auth/staff/verify-otp",
        "/api/auth/staff/mfa/verify-totp",
        "/api/auth/staff/passkey/authenticate/start",
        "/api/admin/auth/verify-totp",
    ):
        assert not is_retired_auth_path(path)


def test_google_prefix_match_cannot_be_bypassed_with_child_path():
    assert is_retired_auth_path("/api/auth/google/exchange/anything")
    assert not is_retired_auth_path("/api/auth/googleish/exchange")
