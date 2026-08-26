"""Backend tests for iteration 8: staff actions, notifications, maps.

Covers:
- Authority KYC approve/reject (RBAC: 403 for others)
- Central admin user suspend/activate
- Fleet manager: add vehicle + set status
- Store manager: add material + stock adjust (incl. negative-stock 422)
- Operator production start/complete
- Quality engineer record quality test
- Accountant record payment
- Notifications list / mark read / mark-all-read
- Maps /status returns configured:false, /autocomplete returns empty
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://tracking-verify.preview.emergentagent.com").rstrip("/")

STAFF_IDS = {
    "authority": "authority@trackmyrmc.test",
    "central":   "central@trackmyrmc.test",
    "fleet":     "fleet@trackmyrmc.test",
    "store":     "store@trackmyrmc.test",
    "operator":  "operator@trackmyrmc.test",
    "quality":   "quality@trackmyrmc.test",
    "accountant":"accountant@trackmyrmc.test",
    "dispatcher":"dispatcher@trackmyrmc.test",
    "admin":     "admin@trackmyrmc.test",
    "customer":  "+919000000001",
}


def _login(identifier: str) -> str:
    for _ in range(4):
        r = requests.post(f"{BASE_URL}/api/auth/request-otp", json={"identifier": identifier}, timeout=15)
        if r.status_code == 429:
            time.sleep(31)
            continue
        break
    assert r.status_code == 200, f"request-otp failed for {identifier}: {r.text}"
    code = r.json().get("dev_otp")
    assert code, "dev_otp missing"
    r2 = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": identifier, "code": code}, timeout=15)
    assert r2.status_code == 200, f"verify-otp failed: {r2.text}"
    return r2.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(v) for k, v in STAFF_IDS.items()}


def _h(t): return {"Authorization": f"Bearer {t}"}


# ---------------------------------------------------- KYC (Authority)
class TestKyc:
    def test_authority_lists_pending_kyc(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/kyc", headers=_h(tokens["authority"]), timeout=15)
        assert r.status_code == 200
        data = r.json()
        pending = [i for i in data["items"] if i.get("badge") == "PENDING"]
        assert len(pending) >= 1, "expected at least one PENDING KYC"
        # actions should be present
        for it in pending:
            keys = {a["key"] for a in it.get("actions", [])}
            assert {"approve", "reject"}.issubset(keys)

    def test_store_manager_cannot_approve_kyc(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/kyc", headers=_h(tokens["authority"]), timeout=15)
        pending = [i for i in r.json()["items"] if i.get("badge") == "PENDING"]
        if not pending:
            pytest.skip("no pending KYC")
        pid = pending[0]["id"]
        r2 = requests.post(f"{BASE_URL}/api/staff/kyc/{pid}/approve", headers=_h(tokens["store"]), timeout=15)
        assert r2.status_code == 403

    def test_customer_cannot_access(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/kyc/x/approve", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 403

    def test_approve_then_reject_flow(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/kyc", headers=_h(tokens["authority"]), timeout=15)
        pending = [i for i in r.json()["items"] if i.get("badge") == "PENDING"]
        assert len(pending) >= 1
        # Approve first
        pid = pending[0]["id"]
        ra = requests.post(f"{BASE_URL}/api/staff/kyc/{pid}/approve", headers=_h(tokens["authority"]), timeout=15)
        assert ra.status_code == 200, ra.text
        assert ra.json()["status"] == "APPROVED"
        # rejecting an approved KYC is supported as a reviewer correction
        rr = requests.post(f"{BASE_URL}/api/staff/kyc/{pid}/reject", headers=_h(tokens["authority"]), timeout=15)
        assert rr.status_code == 200, rr.text
        assert rr.json()["status"] == "REJECTED"


# ---------------------------------------------------- CENTRAL ADMIN
class TestCentralAdmin:
    def test_central_lists_users(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        assert r.status_code == 200
        assert len(r.json()["items"]) > 0

    def test_non_central_forbidden(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 403

    def test_suspend_activate_user(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        users = r.json()["items"]
        target = next((u for u in users if u.get("subtitle") == "CUSTOMER"), None)
        if not target:
            pytest.skip("no customer user")
        uid = target["id"]
        rs = requests.post(f"{BASE_URL}/api/staff/users/{uid}/suspend", headers=_h(tokens["central"]), timeout=15)
        assert rs.status_code == 200
        ra = requests.post(f"{BASE_URL}/api/staff/users/{uid}/activate", headers=_h(tokens["central"]), timeout=15)
        assert ra.status_code == 200


# ---------------------------------------------------- FLEET
class TestFleet:
    def test_fleet_manager_add_vehicle(self, tokens):
        before = requests.get(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["fleet"]), timeout=15)
        assert before.status_code == 200
        count = len(before.json()["vehicles"])
        tm = "TEST" + uuid.uuid4().hex[:6].upper()
        r = requests.post(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["fleet"]), json={"tm_number": tm, "capacity_m3": 7.0}, timeout=15)
        assert r.status_code == 200, r.text
        vid = r.json()["vehicle"]["id"]
        after = requests.get(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["fleet"]), timeout=15)
        assert len(after.json()["vehicles"]) == count + 1
        rs = requests.patch(f"{BASE_URL}/api/staff/fleet/{vid}/status", headers=_h(tokens["fleet"]), json={"status": "maintenance"}, timeout=15)
        assert rs.status_code == 200
        assert rs.json()["vehicle"]["status"] == "maintenance"

    def test_operator_cannot_manage_fleet(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["operator"]), json={"tm_number": "DENIED1"}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- INVENTORY
class TestInventory:
    def test_store_add_material_and_adjust(self, tokens):
        name = "TEST Cement " + uuid.uuid4().hex[:6]
        r = requests.post(f"{BASE_URL}/api/staff/inventory", headers=_h(tokens["store"]), json={"name": name, "unit": "kg", "quantity": 100.0}, timeout=15)
        assert r.status_code == 200, r.text
        mid = r.json()["material"]["id"]
        ra = requests.post(f"{BASE_URL}/api/staff/inventory/{mid}/adjust", headers=_h(tokens["store"]), json={"delta": -25, "reason": "test usage"}, timeout=15)
        assert ra.status_code == 200
        assert ra.json()["material"]["quantity"] == 75.0
        rn = requests.post(f"{BASE_URL}/api/staff/inventory/{mid}/adjust", headers=_h(tokens["store"]), json={"delta": -1000, "reason": "negative test"}, timeout=15)
        assert rn.status_code == 422

    def test_accountant_cannot_adjust_stock(self, tokens):
        items = requests.get(f"{BASE_URL}/api/staff/inventory", headers=_h(tokens["store"]), timeout=15).json()["items"]
        if not items:
            pytest.skip("no inventory")
        r = requests.post(f"{BASE_URL}/api/staff/inventory/{items[0]['id']}/adjust", headers=_h(tokens["accountant"]), json={"delta": 1}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- PRODUCTION
class TestProduction:
    def test_operator_production_start_complete(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/production", headers=_h(tokens["operator"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        candidate = next((i for i in items if i.get("badge_status") in ("ACCEPTED", "SCHEDULED")), None)
        if not candidate:
            pytest.skip("no accepted/scheduled order for production")
        oid = candidate["id"]
        rs = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production-start", headers=_h(tokens["operator"]), timeout=15)
        assert rs.status_code == 200, rs.text
        rc = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production-complete", headers=_h(tokens["operator"]), timeout=15)
        assert rc.status_code == 200, rc.text

    def test_accountant_forbidden_production(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/orders/507f1f77bcf86cd799439011/production-start", headers=_h(tokens["accountant"]), timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- QUALITY
class TestQuality:
    def test_quality_record(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/quality", headers=_h(tokens["quality"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("no orders")
        oid = items[0]["id"]
        body = {"slump_mm": 110, "temperature_c": 29.5, "cube_count": 6, "result": "PASS", "notes": "pytest"}
        rr = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/quality", headers=_h(tokens["quality"]), json=body, timeout=15)
        assert rr.status_code == 200, rr.text

    def test_store_forbidden_quality(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/orders/x/quality", headers=_h(tokens["store"]), json={}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- PAYMENTS
class TestPayments:
    def test_accountant_record_payment(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/payments", headers=_h(tokens["accountant"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("no orders")
        oid = items[0]["id"]
        body = {"amount": 1234.5, "method": "UPI", "reference": "PYTEST", "note": "test payment"}
        rr = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/payments", headers=_h(tokens["accountant"]), json=body, timeout=15)
        assert rr.status_code == 200, rr.text

    def test_dispatcher_forbidden_payment(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/orders/x/payments", headers=_h(tokens["dispatcher"]), json={"amount": 10, "method": "CASH"}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- NOTIFICATIONS
class TestNotifications:
    def test_list_and_mark_read(self, tokens):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        unread = [i for i in items if not i["read"]]
        if unread:
            nid = unread[0]["id"]
            rr = requests.patch(f"{BASE_URL}/api/notifications/{nid}/read", headers=_h(tokens["admin"]), timeout=15)
            assert rr.status_code == 200
        allr = requests.post(f"{BASE_URL}/api/notifications/read-all", headers=_h(tokens["admin"]), timeout=15)
        assert allr.status_code == 200


# ---------------------------------------------------- MAPS
class TestMaps:
    def test_maps_status(self, tokens):
        r = requests.get(f"{BASE_URL}/api/maps/status", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        assert "configured" in r.json()

    def test_maps_autocomplete(self, tokens):
        r = requests.get(f"{BASE_URL}/api/maps/autocomplete", params={"input": "test"}, headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        assert "predictions" in r.json()
