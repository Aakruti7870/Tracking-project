"""Account deletion integration coverage using disposable customer identities."""
from datetime import datetime, timedelta, timezone
import os
import time
import uuid

from jwt import decode
from pymongo import MongoClient
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
CENTRAL_ADMIN = "central@trackmyrmc.test"


def _login(session: requests.Session, identifier: str) -> str:
    r = session.post(f"{API}/auth/request-otp", json={"identifier": identifier}, timeout=15)
    if r.status_code == 429:
        time.sleep(1.1)
        r = session.post(f"{API}/auth/request-otp", json={"identifier": identifier}, timeout=15)
    assert r.status_code == 200, r.text
    code = r.json().get("dev_otp")
    assert code, r.json()
    v = session.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code}, timeout=15)
    assert v.status_code == 200, v.text
    return v.json()["access_token"]


def _h(token: str):
    return {"Authorization": f"Bearer {token}"}


def _mark_recent_admin_step_up(token: str) -> None:
    """Model the server-issued step-up marker in CI without provisioning a TOTP secret."""
    payload = decode(
        token,
        os.environ["JWT_SECRET"],
        algorithms=[os.environ.get("JWT_ALGORITHM", "HS256")],
    )
    now = datetime.now(timezone.utc)
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        result = client[os.environ["DB_NAME"]]["sessions"].update_one(
            {"_id": payload["sid"], "revoked": False},
            {
                "$set": {
                    "admin_step_up_at": now,
                    "admin_step_up_expires_at": now + timedelta(minutes=5),
                }
            },
        )
        assert result.matched_count == 1
    finally:
        client.close()


def test_account_deletion_request_cancel_and_legacy_admin_completion_is_blocked():
    session = requests.Session()
    mobile = f"+91872{uuid.uuid4().int % 10000000:07d}"
    customer = _login(session, mobile)

    empty = session.get(f"{API}/account-deletion/status", headers=_h(customer), timeout=15)
    assert empty.status_code == 200, empty.text
    assert empty.json()["request"] is None

    created = session.post(
        f"{API}/account-deletion/request",
        headers=_h(customer),
        json={"confirm": "DELETE", "reason": "TEST disposable account"},
        timeout=15,
    )
    assert created.status_code == 200, created.text
    assert created.json()["request"]["status"] == "PENDING"

    replay = session.post(
        f"{API}/account-deletion/request",
        headers=_h(customer),
        json={"confirm": "DELETE"},
        timeout=15,
    )
    assert replay.status_code == 200 and replay.json().get("idempotent") is True, replay.text

    cancelled = session.post(f"{API}/account-deletion/cancel", headers=_h(customer), timeout=15)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED", cancelled.text

    second = session.post(
        f"{API}/account-deletion/request",
        headers=_h(customer),
        json={"confirm": "DELETE", "reason": "TEST complete"},
        timeout=15,
    )
    assert second.status_code == 200, second.text
    request_id = second.json()["request"]["id"]

    central = _login(session, CENTRAL_ADMIN)
    listing = session.get(f"{API}/account-deletion/requests", headers=_h(central), timeout=15)
    assert listing.status_code == 403, listing.text

    # A Central Admin bootstrap must not regain access to the legacy
    # operational endpoint, even if its session has a recent step-up marker.
    _mark_recent_admin_step_up(central)
    blocked = session.post(
        f"{API}/account-deletion/requests/{request_id}/complete",
        headers=_h(central),
        json={"note": "TEST identity removal verified"},
        timeout=15,
    )
    assert blocked.status_code == 403, blocked.text
    assert blocked.json().get("detail") == "Central Admin must use the permission-gated Control Center route", blocked.text


def test_account_deletion_confirmation_is_required():
    session = requests.Session()
    mobile = f"+91873{uuid.uuid4().int % 10000000:07d}"
    customer = _login(session, mobile)
    r = session.post(
        f"{API}/account-deletion/request",
        headers=_h(customer),
        json={"confirm": "NO"},
        timeout=15,
    )
    assert r.status_code == 422, r.text
