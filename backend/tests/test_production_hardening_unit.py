"""Focused regression tests for production-readiness security invariants.

These tests are intentionally local/unit-level: they do not call preview or
production services and are safe to run in CI before the full API suites.
"""
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

import security
from models import CreateOrderBody, LocationBody, PaymentBody, PodBody, SosBody, VehicleStatusBody
from order_service import DELIVERED, DISPATCHED, can_transition
from routers.driver import _validate_pod_payload
from routers.maps import _valid_coords


class _FakeCollection:
    def __init__(self, value):
        self.value = value

    async def find_one(self, _query, **_kwargs):
        # Mirror Motor/PyMongo's real signature: find_one() accepts extra
        # keyword arguments (e.g. sort=[...]) that are forwarded to find().
        # The single-session guard queries the newest session with
        # sort=[("created_at", -1), ("_id", -1)]; the fake stores exactly one
        # session whose _id matches the issued token, so returning it honors
        # the "newest session is authoritative" contract for these unit tests.
        return self.value


def _auth_context_for(monkeypatch, *, role: str, plant_id=None):
    user_id = str(ObjectId())
    sid = "unit-test-session"
    token, expires = security.issue_jwt(user_id, sid, role)
    monkeypatch.setattr(
        security,
        "sessions",
        _FakeCollection(
            {
                "_id": sid,
                "user_id": user_id,
                "revoked": False,
                "expires_at": expires,
            }
        ),
    )
    monkeypatch.setattr(
        security,
        "users",
        _FakeCollection(
            {
                "_id": ObjectId(user_id),
                "name": "Unit Staff",
                "primary_role": role,
                "roles": [role],
                "status": "active",
                "plant_id": plant_id,
            }
        ),
    )
    return token


def test_unassigned_plant_staff_fails_closed(monkeypatch):
    token = _auth_context_for(monkeypatch, role="dispatcher", plant_id=None)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.current_user(authorization=f"Bearer {token}"))
    assert exc.value.status_code == 403
    assert "Plant assignment required" in str(exc.value.detail)


def test_assigned_plant_staff_keeps_tenant(monkeypatch):
    plant_id = str(ObjectId())
    token = _auth_context_for(monkeypatch, role="dispatcher", plant_id=plant_id)
    ctx = asyncio.run(security.current_user(authorization=f"Bearer {token}"))
    assert ctx["role"] == "dispatcher"
    assert ctx["plant_id"] == plant_id


def test_location_coordinates_are_bounded():
    assert LocationBody(lat=19.0, lng=73.0).lat == 19.0
    with pytest.raises(ValidationError):
        LocationBody(lat=91, lng=73)
    with pytest.raises(ValidationError):
        LocationBody(lat=19, lng=-181)
    assert _valid_coords(-90, -180)
    assert _valid_coords(90, 180)
    assert not _valid_coords(90.01, 0)


def test_vehicle_status_is_allowlisted():
    assert VehicleStatusBody(status="available").status == "available"
    with pytest.raises(ValidationError):
        VehicleStatusBody(status="deleted")


def test_business_enums_and_grade_are_allowlisted():
    assert SosBody(type="Emergency").type == "Emergency"
    assert PaymentBody(amount=100, method="upi").method == "upi"
    with pytest.raises(ValidationError):
        SosBody(type="Anything")
    with pytest.raises(ValidationError):
        PaymentBody(amount=100, method="crypto")
    with pytest.raises(ValidationError):
        CreateOrderBody(
            plant_id="p1",
            grade="M999",
            quantity=1,
            site_name="Site",
            site_address="Address",
            delivery_date="2026-09-01",
        )


def test_terminal_order_cannot_transition():
    assert can_transition(DISPATCHED, "EN_ROUTE")
    assert not can_transition(DELIVERED, "DISPATCHED")
    assert not can_transition(DELIVERED, "CANCELLED")


def test_pod_requires_pod_object_path_and_signature():
    good = PodBody(
        receiver_name="Site Engineer",
        delivered_quantity=6,
        photo_path="trackmyrmc/pod/abc.jpg",
        signature='["M1,1 L2,2"]',
    )
    _validate_pod_payload(good)

    with pytest.raises(HTTPException):
        _validate_pod_payload(
            PodBody(
                receiver_name="Site Engineer",
                delivered_quantity=6,
                photo_path=None,
                signature='["M1,1 L2,2"]',
            )
        )

    with pytest.raises(HTTPException):
        _validate_pod_payload(
            PodBody(
                receiver_name="Site Engineer",
                delivered_quantity=6,
                photo_path="trackmyrmc/uploads/user/abc.jpg",
                signature='["M1,1 L2,2"]',
            )
        )

    with pytest.raises(HTTPException):
        _validate_pod_payload(
            PodBody(
                receiver_name="Site Engineer",
                delivered_quantity=6,
                photo_path="trackmyrmc/pod/abc.jpg",
                signature="[]",
            )
        )


def _run_config_import(extra_env: dict[str, str]):
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "production",
            "MONGO_URL": "mongodb://127.0.0.1:27017",
            "DB_NAME": "unit_config",
            "JWT_SECRET": "",
            "OTP_PEPPER": "",
            "DEBUG_OTP": "false",
            "CORS_ORIGINS": "https://app.trackmyrmc.com",
            "GOOGLE_OAUTH_CLIENT_ID": "unit-google-client.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "unit-google-client-secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://app.trackmyrmc.com/api/auth/google/callback",
            "GOOGLE_OAUTH_APP_REDIRECT_URI": "trackmyrmc://auth/google",
        }
    )
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_production_config_rejects_missing_secrets():
    result = _run_config_import({})
    assert result.returncode != 0
    assert "Production security configuration" in (result.stdout + result.stderr)


def test_production_config_rejects_missing_google_oauth():
    result = _run_config_import(
        {
            "JWT_SECRET": "unit-production-secret-long-enough",
            "OTP_PEPPER": "unit-production-pepper-long-enough",
            "GOOGLE_OAUTH_CLIENT_SECRET": "",
        }
    )
    assert result.returncode != 0
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in (result.stdout + result.stderr)


def test_production_config_rejects_debug_otp():
    result = _run_config_import(
        {
            "JWT_SECRET": "unit-production-secret-long-enough",
            "OTP_PEPPER": "unit-production-pepper-long-enough",
            "DEBUG_OTP": "true",
        }
    )
    assert result.returncode != 0
    assert "DEBUG_OTP must be false" in (result.stdout + result.stderr)


def test_production_config_accepts_explicit_secure_values():
    result = _run_config_import(
        {
            "JWT_SECRET": "unit-production-secret-long-enough",
            "OTP_PEPPER": "unit-production-pepper-long-enough",
            "DEBUG_OTP": "false",
        }
    )
    assert result.returncode == 0, result.stdout + result.stderr
