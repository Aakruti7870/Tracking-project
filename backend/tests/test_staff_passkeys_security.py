"""Security invariants for Plant Staff WebAuthn/passkey support.

These tests intentionally cover fail-closed helpers without needing a browser or
live authenticator. End-to-end cryptographic verification is delegated to the
pinned py_webauthn implementation and the application CI still imports/boots the
full router with that exact dependency.
"""

import hashlib
import hmac

import pytest
from fastapi import HTTPException

from config import settings
from routers import staff_passkeys


def test_passkey_origins_are_explicit_and_never_wildcard(monkeypatch):
    monkeypatch.delenv("PLAY_SIGNING_SHA256", raising=False)
    origins = staff_passkeys._allowed_origins()
    assert origins == ["https://trackmyrmc.com"]
    assert "*" not in origins
    assert settings.PASSKEY_RP_ID == "trackmyrmc.com"
    assert settings.PASSKEY_WEB_ORIGIN == "https://trackmyrmc.com"


def test_android_origin_is_derived_from_exact_play_signing_fingerprint(monkeypatch):
    fingerprint = ":".join(["01"] * 32)
    monkeypatch.setenv("PLAY_SIGNING_SHA256", fingerprint)
    origin = staff_passkeys._android_apk_origin()
    assert origin is not None
    assert origin.startswith("android:apk-key-hash:")
    assert origin != "android:apk-key-hash:*"
    origins = staff_passkeys._allowed_origins()
    assert origins[0] == "https://trackmyrmc.com"
    assert origins[1] == origin


def test_invalid_play_fingerprint_never_widens_origin_trust(monkeypatch):
    monkeypatch.setenv("PLAY_SIGNING_SHA256", "not-a-sha256")
    assert staff_passkeys._android_apk_origin() is None
    assert staff_passkeys._allowed_origins() == ["https://trackmyrmc.com"]


def test_handoff_is_hmac_digest_not_raw_capability():
    capability = "correct-horse-battery-staple-passkey-handoff"
    digest = staff_passkeys._handoff_digest(capability)
    expected = hmac.new(
        settings.OTP_PEPPER.encode("utf-8"),
        f"staff-passkey-handoff:{capability}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert digest == expected
    assert capability not in digest
    assert len(digest) == 64


def test_only_active_passkeys_are_accepted():
    user = {
        "mfa": {
            "passkeys": [
                {"credential_id": "active-credential", "active": True},
                {"credential_id": "revoked-credential", "active": False},
                {"credential_id": "legacy-active-by-default"},
                "malformed",
            ]
        }
    }
    accepted = staff_passkeys._active_passkeys(user)
    assert [item["credential_id"] for item in accepted] == [
        "active-credential",
        "legacy-active-by-default",
    ]


def test_short_or_missing_credential_id_is_rejected():
    for credential in ({}, {"id": "too-short"}, {"rawId": "tiny"}):
        with pytest.raises(HTTPException) as exc:
            staff_passkeys._credential_id_from_response(credential)
        assert exc.value.status_code == 400


def test_browser_ceremony_capability_is_fragment_only():
    url = staff_passkeys._ceremony_url("authenticate", "A" * 32)
    assert url.startswith("https://trackmyrmc.com/passkey-ceremony#")
    before_fragment, fragment = url.split("#", 1)
    assert "request_id" not in before_fragment
    assert "request_id=" in fragment
