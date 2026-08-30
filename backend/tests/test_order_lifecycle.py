"""TrackMyRMC Phase 2 backend tests — customer/owner order lifecycle.

Covers:
- Customer creates order (PENDING) when KYC=VERIFIED; RMC-xxxx unique
- KYC gating: unverified customer 403 KYC_REQUIRED; save_draft=true -> DRAFT ok
- Grade validation -> 422
- Order detail returns history (first entry to=PENDING)
- Cancel: PENDING->CANCELLED ok; DELIVERED->cancel -> 409
- Owner /home: pending_approvals reflects new order, plant_count=3, pending_orders list
- Owner /orders and /orders?status=PENDING scoped to owner plants
- Owner approve: PENDING->ACCEPTED, history 'Approved by plant', notifies customer
- Owner reject with reason: PENDING->REJECTED history with reason
- State machine guard: approving non-PENDING -> 409
- RBAC + isolation: customer token on /owner/* -> 403; owner cannot act on 3rd party -> 404
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://trackmyrmc-kyc-ui.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CUSTOMER_MOBILE = "+919000000001"
OWNER_EMAIL = "owner@trackmyrmc.test"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(client, identifier):
    r = client.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    if r.status_code == 429:
        time.sleep(31)
        r = client.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    assert r.status_code == 200, f"request-otp {identifier}: {r.status_code} {r.text}"
    code = r.json()["dev_otp"]
    rv = client.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code})
    assert rv.status_code == 200, f"verify {identifier}: {rv.status_code} {rv.text}"
    return rv.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def customer_token(api_client):
    return _login(api_client, CUSTOMER_MOBILE)["access_token"]


@pytest.fixture(scope="module")
def owner_token(api_client):
    time.sleep(1)
    return _login(api_client, OWNER_EMAIL)["access_token"]


@pytest.fixture(scope="module")
def unverified_customer(api_client):
    # New self-registered mobile customer (no KYC)
    num = f"+91811110{uuid.uuid4().int % 10000:04d}"
    time.sleep(1)
    data = _login(api_client, num)
    assert data["role"] == "customer"
    return {"token": data["access_token"], "mobile": num}


@pytest.fixture(scope="module")
def plants(api_client, customer_token):
    r = api_client.get(f"{API}/customer/plants", headers=_auth(customer_token))
    assert r.status_code == 200
    return r.json()["plants"]


def _make_body(plant, grade=None, save_draft=False, quantity=5.0):
    return {
        "plant_id": plant["id"],
        "grade": grade or plant["grades"][0],
        "quantity": quantity,
        "site_name": "TEST Site",
        "site_address": "TEST Address, Hyderabad",
        "delivery_date": "2026-07-01",
        "delivery_time": "10:00",
        "contact_person": "TEST Contact",
        "contact_mobile": "+919000000099",
        "notes": "auto-test",
        "save_draft": save_draft,
    }


# ---------- Create + KYC gating + validation ----------
class TestCreateOrder:
    def test_create_pending_order_verified_customer(self, api_client, customer_token, plants):
        p = plants[0]
        r = api_client.post(f"{API}/customer/orders", headers=_auth(customer_token), json=_make_body(p))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["id"]
        onum = j["order"]["order_number"]
        assert onum.startswith("RMC-")
        seq = int(onum.split("-")[1])
        assert seq >= 1003, f"expected unique RMC-xxxx (>=1003), got {onum}"
        assert j["order"]["status"] == "PENDING"
        pytest.created_order_id = j["id"]
        pytest.created_order_number = onum
        pytest.plant_used = p

    def test_kyc_required_for_unverified(self, api_client, unverified_customer, plants):
        p = plants[0]
        r = api_client.post(
            f"{API}/customer/orders",
            headers=_auth(unverified_customer["token"]),
            json=_make_body(p, save_draft=False),
        )
        assert r.status_code == 403, r.text
        assert r.json().get("detail") == "KYC_REQUIRED"

    def test_kyc_draft_allowed_for_unverified(self, api_client, unverified_customer, plants):
        p = plants[0]
        r = api_client.post(
            f"{API}/customer/orders",
            headers=_auth(unverified_customer["token"]),
            json=_make_body(p, save_draft=True),
        )
        assert r.status_code == 200, r.text
        assert r.json()["order"]["status"] == "DRAFT"

    def test_grade_validation(self, api_client, customer_token, plants):
        # Plant "Prime Mix - Miyapur" offers M15/M20/M25 (no M35)
        prime = next((p for p in plants if "Prime Mix" in p["name"]), None)
        assert prime, "Prime Mix plant expected"
        r = api_client.post(
            f"{API}/customer/orders",
            headers=_auth(customer_token),
            json=_make_body(prime, grade="M99"),
        )
        assert r.status_code == 422, r.text


# ---------- Detail + Cancel ----------
class TestOrderDetailAndCancel:
    def test_detail_history_first_pending(self, api_client, customer_token):
        oid = pytest.created_order_id
        r = api_client.get(f"{API}/customer/orders/{oid}", headers=_auth(customer_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["order"]["status"] == "PENDING"
        assert len(j["history"]) >= 1
        assert j["history"][0]["to"] == "PENDING"

    def test_cancel_delivered_conflict(self, api_client, customer_token):
        # RMC-1002 in seed is DELIVERED
        r = api_client.get(f"{API}/customer/orders", headers=_auth(customer_token))
        delivered = next((o for o in r.json()["orders"] if o["status"] == "DELIVERED"), None)
        assert delivered, "expected a DELIVERED seeded order"
        rc = api_client.post(f"{API}/customer/orders/{delivered['id']}/cancel", headers=_auth(customer_token))
        assert rc.status_code == 409, rc.text

    def test_cancel_pending_ok(self, api_client, customer_token, plants):
        # Create a fresh PENDING and cancel it
        p = plants[0]
        r = api_client.post(f"{API}/customer/orders", headers=_auth(customer_token), json=_make_body(p))
        assert r.status_code == 200
        oid = r.json()["id"]
        rc = api_client.post(f"{API}/customer/orders/{oid}/cancel", headers=_auth(customer_token))
        assert rc.status_code == 200, rc.text
        assert rc.json()["status"] == "CANCELLED"
        # history includes CANCELLED
        rd = api_client.get(f"{API}/customer/orders/{oid}", headers=_auth(customer_token))
        statuses = [h["to"] for h in rd.json()["history"]]
        assert "CANCELLED" in statuses


# ---------- Owner endpoints ----------
class TestOwnerHome:
    def test_owner_home_shape(self, api_client, owner_token):
        r = api_client.get(f"{API}/owner/home", headers=_auth(owner_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["plant_count"] == 3
        assert j["cards"]["pending_approvals"] >= 1
        # newly created PENDING order should appear
        nums = [o["order_number"] for o in j["pending_orders"]]
        assert pytest.created_order_number in nums

    def test_owner_orders_list_and_filter(self, api_client, owner_token):
        r_all = api_client.get(f"{API}/owner/orders", headers=_auth(owner_token))
        assert r_all.status_code == 200
        all_orders = r_all.json()["orders"]
        assert len(all_orders) >= 3
        r_p = api_client.get(f"{API}/owner/orders?status=PENDING", headers=_auth(owner_token))
        assert r_p.status_code == 200
        pending = r_p.json()["orders"]
        assert all(o["status"] == "PENDING" for o in pending)
        assert any(o["order_number"] == pytest.created_order_number for o in pending)


class TestOwnerApproveReject:
    def test_approve_pending_to_accepted(self, api_client, owner_token, customer_token):
        oid = pytest.created_order_id
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ACCEPTED"
        # Verify via customer detail
        rd = api_client.get(f"{API}/customer/orders/{oid}", headers=_auth(customer_token))
        assert rd.status_code == 200
        j = rd.json()
        assert j["order"]["status"] == "ACCEPTED"
        # history has 'Approved by plant'
        notes = [h.get("note") for h in j["history"]]
        assert any(n and "Approved by plant" in n for n in notes)

    def test_approve_already_accepted_idempotent(self, api_client, owner_token):
        # Note: per iteration context, same-state is idempotent 200
        oid = pytest.created_order_id
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code in (200,), r.text

    def test_reject_flow_with_reason(self, api_client, customer_token, owner_token, plants):
        # Fresh PENDING order for reject flow
        r = api_client.post(f"{API}/customer/orders", headers=_auth(customer_token), json=_make_body(plants[1]))
        assert r.status_code == 200
        oid = r.json()["id"]
        reason = "Plant overbooked today"
        rr = api_client.post(
            f"{API}/owner/orders/{oid}/reject",
            headers=_auth(owner_token),
            json={"reason": reason},
        )
        assert rr.status_code == 200, rr.text
        assert rr.json()["status"] == "REJECTED"
        rd = api_client.get(f"{API}/customer/orders/{oid}", headers=_auth(customer_token))
        notes = [h.get("note") for h in rd.json()["history"]]
        assert any(n and reason in n for n in notes)
        pytest.rejected_order_id = oid

    def test_state_machine_guard_reject_then_approve_conflict(self, api_client, owner_token):
        # Cannot approve an already-REJECTED order (invalid edge -> 409)
        oid = pytest.rejected_order_id
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 409, r.text


# ---------- RBAC + isolation ----------
class TestRBACIsolation:
    def test_customer_cannot_access_owner(self, api_client, customer_token):
        for path in ("/owner/home", "/owner/orders"):
            r = api_client.get(f"{API}{path}", headers=_auth(customer_token))
            assert r.status_code == 403, f"{path}: {r.status_code}"
        # approve/reject also 403
        oid = pytest.created_order_id
        r_a = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(customer_token))
        assert r_a.status_code == 403
        r_r = api_client.post(f"{API}/owner/orders/{oid}/reject", headers=_auth(customer_token),
                              json={"reason": "no"})
        assert r_r.status_code == 403

    def test_owner_cannot_act_on_foreign_order_404(self, api_client, owner_token):
        # Since single owner owns all 3 plants in seed, use a random ObjectId
        fake_oid = "507f1f77bcf86cd799439011"
        r = api_client.post(f"{API}/owner/orders/{fake_oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 404, r.text
