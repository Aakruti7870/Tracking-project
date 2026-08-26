"""TrackMyRMC Phase 1 backend regression tests.

Covers:
- Health
- Passwordless OTP request/verify (dev_otp)
- Resend throttle, max attempts, wrong OTP
- RBAC (customer-only endpoints)
- Channel-per-role policy (customer/driver mobile OTP; staff Google-only)
- Customer home / orders / plants / kyc
- KYC start on already-VERIFIED customer -> 409
- Logout revokes session (subsequent /me -> 401)
- Protected endpoints without Authorization header -> 401
"""
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

from security import issue_jwt, new_session_id, utcnow

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://tracking-verify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CUSTOMER_MOBILE = "+919000000001"
DRIVER_MOBILE = "+919000000002"
ADMIN_EMAIL = "admin@trackmyrmc.test"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _request_otp(client, identifier):
    return client.post(f"{API}/auth/request-otp", json={"identifier": identifier})


def _verify(client, identifier, code):
    return client.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code})


def _login(client, identifier):
    """Full mobile OTP dance; returns access_token payload dict."""
    r = _request_otp(client, identifier)
    if r.status_code == 429:
        time.sleep(2)
        r = _request_otp(client, identifier)
    assert r.status_code == 200, f"request-otp failed: {r.status_code} {r.text}"
    code = r.json().get("dev_otp")
    assert code, f"dev_otp missing in response: {r.json()}"
    rv = _verify(client, identifier, code)
    assert rv.status_code == 200, f"verify failed: {rv.status_code} {rv.text}"
    return rv.json()


def _staff_test_token(role: str) -> str:
    """Create a CI-only authenticated session to test RBAC independently of OAuth.

    Google itself is not contacted by this integration suite. The production
    authentication route is covered separately; this helper only preserves the
    existing customer-endpoint RBAC assertion with a real persisted session.
    """
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(mongo_url)
    try:
        db = client[db_name]
        user = db.users.find_one({"primary_role": role, "status": {"$ne": "deleted"}})
        assert user, f"seeded {role} user not found"
        sid = new_session_id()
        token, expires = issue_jwt(str(user["_id"]), sid, role)
        db.sessions.insert_one(
            {
                "_id": sid,
                "user_id": str(user["_id"]),
                "role": role,
                "revoked": False,
                "created_at": utcnow(),
                "expires_at": expires,
            }
        )
        return token
    finally:
        client.close()


class TestHealth:
    def test_health(self, api_client):
        r = api_client.get(f"{API}/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert "notifications" in body
        assert body["notifications"]["configured"] is False


class TestAuth:
    def test_request_otp_returns_dev_otp(self, api_client):
        r = _request_otp(api_client, CUSTOMER_MOBILE)
        if r.status_code == 429:
            time.sleep(2)
            r = _request_otp(api_client, CUSTOMER_MOBILE)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "OTP_SENT"
        assert j["channel"] == "sms"
        assert "dev_otp" in j and len(j["dev_otp"]) == 6

    def test_resend_throttle_429(self, api_client):
        num = f"+91900000{uuid.uuid4().int % 10000:04d}"
        r1 = _request_otp(api_client, num)
        assert r1.status_code == 200
        r2 = _request_otp(api_client, num)
        assert r2.status_code == 429, f"expected 429 got {r2.status_code}: {r2.text}"

    def test_verify_wrong_then_correct(self, api_client):
        num = f"+91900000{uuid.uuid4().int % 10000:04d}"
        r = _request_otp(api_client, num)
        assert r.status_code == 200
        code = r.json()["dev_otp"]
        wrong = "000000" if code != "000000" else "111111"
        rw = _verify(api_client, num, wrong)
        assert rw.status_code == 400
        rc = _verify(api_client, num, code)
        assert rc.status_code == 200
        assert rc.json()["role"] == "customer"

    def test_verify_max_attempts_429(self, api_client):
        num = f"+91900000{uuid.uuid4().int % 10000:04d}"
        r = _request_otp(api_client, num)
        assert r.status_code == 200
        code = r.json()["dev_otp"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            _verify(api_client, num, wrong)
        rlast = _verify(api_client, num, wrong)
        assert rlast.status_code == 429, f"expected 429 after max attempts, got {rlast.status_code}: {rlast.text}"

    def test_customer_email_rejected(self, api_client):
        email = f"unknown_{uuid.uuid4().hex[:6]}@example.com"
        r = _request_otp(api_client, email)
        assert r.status_code == 200
        code = r.json()["dev_otp"]
        rv = _verify(api_client, email, code)
        assert rv.status_code == 403

    def test_admin_email_otp_requires_google(self, api_client):
        r = _request_otp(api_client, ADMIN_EMAIL)
        if r.status_code == 429:
            time.sleep(2)
            r = _request_otp(api_client, ADMIN_EMAIL)
        assert r.status_code == 200, r.text
        code = r.json().get("dev_otp")
        assert code
        rv = _verify(api_client, ADMIN_EMAIL, code)
        assert rv.status_code == 403
        assert "sign in with Google" in rv.text

    def test_admin_mobile_should_fail_channel(self, api_client):
        pytest.skip("Admin is Google-only and no Admin mobile identifier is provisioned.")


@pytest.fixture(scope="module")
def customer_token(api_client):
    data = _login(api_client, CUSTOMER_MOBILE)
    assert data["role"] == "customer"
    return data["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _staff_test_token("admin")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestMe:
    def test_me_customer(self, api_client, customer_token):
        r = api_client.get(f"{API}/me", headers=_auth(customer_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["role"] == "customer"
        assert j["kyc_status"] == "VERIFIED"
        assert j["phone"] == CUSTOMER_MOBILE

    def test_me_without_token_401(self, api_client):
        r = api_client.get(f"{API}/me")
        assert r.status_code == 401


class TestCustomer:
    def test_home_shape(self, api_client, customer_token):
        r = api_client.get(f"{API}/customer/home", headers=_auth(customer_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["kyc_status"] == "VERIFIED"
        assert j["active_order"] is not None
        assert j["active_order"]["order_number"] == "RMC-1001"
        assert j["active_order"]["status"] == "DISPATCHED"
        # Development seed intentionally contains three customer orders.
        assert len(j["recent_orders"]) == 3
        assert len(j["nearby_plants"]) == 3
        for p in j["nearby_plants"]:
            assert p["verified"] is True

    def test_orders(self, api_client, customer_token):
        r = api_client.get(f"{API}/customer/orders", headers=_auth(customer_token))
        assert r.status_code == 200
        assert len(r.json()["orders"]) == 3

    def test_plants(self, api_client, customer_token):
        r = api_client.get(f"{API}/customer/plants", headers=_auth(customer_token))
        assert r.status_code == 200
        plants = r.json()["plants"]
        assert len(plants) == 3
        for p in plants:
            assert p["verified"] is True

    def test_kyc_verified(self, api_client, customer_token):
        r = api_client.get(f"{API}/customer/kyc", headers=_auth(customer_token))
        assert r.status_code == 200
        assert r.json()["status"] == "VERIFIED"

    def test_kyc_start_conflict(self, api_client, customer_token):
        r = api_client.post(f"{API}/customer/kyc/start", headers=_auth(customer_token))
        assert r.status_code == 409

    def test_rbac_admin_cannot_access_customer(self, api_client, admin_token):
        for path in ("/customer/home", "/customer/orders", "/customer/plants", "/customer/kyc"):
            r = api_client.get(f"{API}{path}", headers=_auth(admin_token))
            assert r.status_code == 403, f"{path} expected 403 got {r.status_code}"
        r = api_client.post(f"{API}/customer/kyc/start", headers=_auth(admin_token))
        assert r.status_code == 403

    def test_customer_endpoints_no_auth_401(self, api_client):
        for path in ("/customer/home", "/customer/orders", "/customer/plants", "/customer/kyc"):
            r = api_client.get(f"{API}{path}")
            assert r.status_code == 401


class TestLogout:
    def test_logout_revokes_session(self, api_client):
        num = f"+91900000{uuid.uuid4().int % 10000:04d}"
        data = _login(api_client, num)
        tok = data["access_token"]
        r_ok = api_client.get(f"{API}/me", headers=_auth(tok))
        assert r_ok.status_code == 200
        rlo = api_client.post(f"{API}/auth/logout", headers=_auth(tok))
        assert rlo.status_code == 200
        r_after = api_client.get(f"{API}/me", headers=_auth(tok))
        assert r_after.status_code == 401
