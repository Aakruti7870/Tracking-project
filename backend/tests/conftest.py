"""Shared pytest fixtures for legacy backend integration coverage.

The production auth contract is intentionally split:
- Customer/Driver -> mobile OTP
- Plant/platform staff -> Google OAuth

Several older integration modules pre-date that split and use an email-OTP
helper only as a convenient way to obtain a staff bearer token before testing
unrelated dispatch, payroll, dashboard, POD and order behavior.  Re-enabling
staff OTP in the application would weaken the production contract, so these
legacy modules receive a CI-only persisted session from the test process
instead.  Auth-policy regression tests are deliberately excluded and continue
to exercise the real HTTP auth routes.
"""

import json as jsonlib
import os
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

from roles import GOOGLE_LOGIN_ROLES
from security import identifier_key, issue_jwt, new_session_id, normalize_identifier, utcnow


# Only modules whose login helper is test setup for non-auth behavior belong
# here.  Dedicated auth tests must always hit the real /api/auth routes.
LEGACY_STAFF_SESSION_MODULES = {
    "test_account_deletion.py",
    "test_dispatch_workflow.py",
    "test_driver_pod.py",
    "test_iteration9_dispatch_rbac_insights.py",
    "test_multiload_delivery.py",
    "test_order_lifecycle.py",
    "test_phase6_sos_prod_invoice_track.py",
    "test_staff_actions.py",
    "test_staff_dashboards.py",
}

_TEST_OTP = "909090"


def _json_response(status_code: int, payload: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers["Content-Type"] = "application/json"
    response._content = jsonlib.dumps(payload).encode("utf-8")
    response.encoding = "utf-8"
    return response


def _find_google_staff(identifier: str):
    """Resolve a provisioned Google-only staff user from the CI Mongo database."""
    try:
        channel, normalized = normalize_identifier(identifier)
    except Exception:
        return None
    if channel != "email":
        return None

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return None

    client = MongoClient(mongo_url)
    try:
        user = client[db_name].users.find_one(
            {"identifier_keys": identifier_key(normalized)}
        )
        if not user or user.get("primary_role") not in GOOGLE_LOGIN_ROLES:
            return None
        return user
    finally:
        client.close()


def _staff_session_payload(user: dict) -> dict:
    """Create the same persisted session shape consumed by current_user()."""
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    role = user["primary_role"]
    sid = new_session_id()
    token, expires = issue_jwt(str(user["_id"]), sid, role)

    client = MongoClient(mongo_url)
    try:
        client[db_name].sessions.insert_one(
            {
                "_id": sid,
                "user_id": str(user["_id"]),
                "role": role,
                "revoked": False,
                "created_at": utcnow(),
                "expires_at": expires,
            }
        )
    finally:
        client.close()

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "role": role,
        "name": user.get("name"),
    }


def _legacy_staff_auth_response(url: str, kwargs: dict):
    """Return a CI-only auth response for a provisioned Google staff login."""
    body = kwargs.get("json") or {}
    identifier = str(body.get("identifier") or "").strip()
    user = _find_google_staff(identifier) if identifier else None
    if not user:
        return None

    endpoint = url.rstrip("/")
    if endpoint.endswith("/api/auth/request-otp"):
        return _json_response(
            200,
            {
                "status": "OTP_SENT",
                "channel": "email",
                "expires_in": 300,
                "delivery": {"configured": False},
                "dev_otp": _TEST_OTP,
            },
        )

    if endpoint.endswith("/api/auth/verify-otp"):
        if str(body.get("code") or "") != _TEST_OTP:
            return _json_response(400, {"detail": "Invalid or expired code"})
        return _json_response(200, _staff_session_payload(user))

    return None


@pytest.fixture(scope="module", autouse=True)
def pre_aab_e2e_vehicle_capacity(request):
    """Guarantee one isolated available mixer for the deterministic E2E flow.

    The normal full backend suite intentionally leaves some dispatch/production
    vehicles occupied while exercising state guards.  Without an isolated mixer,
    a later pre-AAB E2E test could fail for test-ordering reasons rather than an
    application defect.  This fixture only applies to that E2E module.
    """
    test_path = Path(str(request.fspath)).name
    if test_path != "test_pre_aab_e2e.py":
        yield
        return

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        yield
        return

    client = MongoClient(mongo_url)
    try:
        db = client[db_name]
        plant = db.plants.find_one({"name": {"$regex": "Kondapur", "$options": "i"}})
        assert plant, "seeded Kondapur plant is missing for pre-AAB E2E"
        db.vehicles.update_one(
            {"tm_number": "PREAABE2E01"},
            {
                "$set": {
                    "plant_id": str(plant["_id"]),
                    "capacity_m3": 6.5,
                    "status": "available",
                    "current_order_id": None,
                    "current_load_id": None,
                }
            },
            upsert=True,
        )
    finally:
        client.close()

    yield


@pytest.fixture(scope="module", autouse=True)
def legacy_staff_session_adapter(request):
    """Adapt legacy staff email-OTP setup without touching production auth.

    The adapter is module-scoped because the legacy bearer-token fixtures it
    supports are also module-scoped.  It covers both ``requests.Session.post``
    and the module-level ``requests.post`` helper because the legacy integration
    modules use both styles.

    Customer/Driver mobile OTP calls and all requests from dedicated auth test
    modules pass through unchanged.  For the explicitly listed legacy modules,
    only provisioned Google staff email identifiers are intercepted.
    """
    test_path = Path(str(request.fspath)).name
    if test_path not in LEGACY_STAFF_SESSION_MODULES:
        yield
        return

    original_session_post = requests.Session.post
    original_post = requests.post

    def patched_session_post(session, url, *args, **kwargs):
        response = _legacy_staff_auth_response(url, kwargs)
        if response is not None:
            return response
        return original_session_post(session, url, *args, **kwargs)

    def patched_post(url, *args, **kwargs):
        response = _legacy_staff_auth_response(url, kwargs)
        if response is not None:
            return response
        return original_post(url, *args, **kwargs)

    patcher = pytest.MonkeyPatch()
    patcher.setattr(requests.Session, "post", patched_session_post)
    patcher.setattr(requests, "post", patched_post)
    try:
        yield
    finally:
        patcher.undo()
