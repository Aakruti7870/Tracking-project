"""Focused unit coverage for Plant Staff Authenticator MFA helpers."""
import base64

from routers.staff_auth import _staff_mfa_enabled
from routers.staff_mfa import (
    _normalize_recovery_code,
    _totp_at,
    _verify_totp,
)
from security import MFA_BOOTSTRAP_ALLOWED_PATHS


def test_totp_matches_rfc6238_truncation_vector():
    # RFC 6238 SHA1 test secret: ASCII "12345678901234567890".
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    # RFC's 8-digit result at unix time 59 is 94287082; this app intentionally
    # uses the standard 6-digit form, therefore the expected suffix is 287082.
    assert _totp_at(secret, 59) == "287082"
    assert _verify_totp(secret, "287082", now_ts=59) is True
    assert _verify_totp(secret, "000000", now_ts=59) is False


def test_totp_accepts_one_period_of_clock_skew_only():
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    previous = _totp_at(secret, 30)
    assert _verify_totp(secret, previous, now_ts=60) is True
    assert _verify_totp(secret, previous, now_ts=120) is False


def test_staff_mfa_requires_enabled_flag_and_encrypted_secret():
    assert _staff_mfa_enabled({"mfa": {"enabled": True, "totp_secret": "encrypted"}}) is True
    assert _staff_mfa_enabled({"mfa": {"enabled": True}}) is False
    assert _staff_mfa_enabled({"mfa": {"totp_secret": "encrypted"}}) is False
    assert _staff_mfa_enabled({}) is False


def test_recovery_codes_are_normalized_for_hyphen_and_case_variations():
    assert _normalize_recovery_code("abcd-efgh-jklm") == "ABCDEFGHJKLM"
    assert _normalize_recovery_code("ABCD EFGH JKLM") == "ABCDEFGHJKLM"


def test_bootstrap_session_can_only_reach_identity_and_mfa_setup_routes():
    assert "/api/me" in MFA_BOOTSTRAP_ALLOWED_PATHS
    assert "/api/auth/staff/mfa/enroll/start" in MFA_BOOTSTRAP_ALLOWED_PATHS
    assert "/api/auth/staff/mfa/enroll/confirm" in MFA_BOOTSTRAP_ALLOWED_PATHS
    assert "/api/orders" not in MFA_BOOTSTRAP_ALLOWED_PATHS
    assert "/api/owner/staff" not in MFA_BOOTSTRAP_ALLOWED_PATHS
