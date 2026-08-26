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


@pytest.fixture(autouse=True)
def legacy_staff_session_adapter(request, monkeypatch):
    """Adapt legacy staff email-OTP setup without touching production auth.

    Customer/Driver mobile OTP calls and all requests from dedicated auth test
    modules pass through unchanged.  For the explicitly listed legacy modules,
    only provisioned Google staff email identifiers are intercepted.
    """
    test_path = Path(str(request.fspath)).name
    if test_path not in LEGACY_STAFF_SESSION_MODULES:
        return

    original_post = requests.Session.post

    def patched_post(session, url, *args, **kwargs):
        body = kwargs.get("json") or {}
        identifier = str(body.get("identifier") or "").strip()
        user = _find_google_staff(identifier) if identifier else None

        if user and url.rstrip("/").endswith("/api/auth/request-otp"):
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

        if user and url.rstrip("/").endswith("/api/auth/verify-otp"):
            if str(body.get("code") or "") != _TEST_OTP:
                return _json_response(400, {"detail": "Invalid or expired code"})
            return _json_response(200, _staff_session_payload(user))

        return original_post(session, url, *args, **kwargs)

    monkeypatch.setattr(requests.Session, "post", patched_post)
