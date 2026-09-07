"""Backend tests for iteration 8: staff actions, notifications, maps.

Covers:
- Authority KYC approve/reject (RBAC: 403 for others)
- Central Admin isolation from legacy staff user-management routes
- Fleet manager: add vehicle + set status
- Store manager: add material + stock adjust (incl. negative-stock 422)
- Operator production start/batch/complete lifecycle
- Quality engineer record quality test
- Accountant record payment
- Notifications list / mark read / mark-all-read
- Maps /status and /autocomplete response contracts
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://trackmyrmc-kyc-ui.preview.emergentagent.com").rstrip("/")

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
        pid = pending[0]["id"]
        ra = requests.post(f"{BASE_URL}/api/staff/kyc/{pid}/approve", headers=_h(tokens["authority"]), timeout=15)
        assert ra.status_code == 200, ra.text
        assert ra.json()["status"] == "VERIFIED"
        rr = requests.post(
            f"{BASE_URL}/api/staff/kyc/{pid}/reject",
            headers=_h(tokens["authority"]),
            json={"reason": "pytest reviewer correction"},
            timeout=15,
        )
        assert rr.status_code == 200, rr.text
        assert rr.json()["status"] == "REJECTED"


# ---------------------------------------------------- CENTRAL ADMIN
class TestCentralAdmin:
    def test_central_cannot_list_users_via_legacy_staff_api(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        assert r.status_code == 403

    def test_non_central_forbidden(self, tokens):
        fake = "507f1f77bcf86cd799439011"
        r = requests.post(f"{BASE_URL}/api/staff/users/{fake}/suspend", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 403

    def test_central_cannot_mutate_users_via_legacy_staff_api(self, tokens):
        uid = "507f1f77bcf86cd799439011"
        rs = requests.post(f"{BASE_URL}/api/staff/users/{uid}/suspend", headers=_h(tokens["central"]), timeout=15)
        assert rs.status_code == 403


# ---------------------------------------------------- FLEET
class TestFleet:
    def test_fleet_manager_add_vehicle(self, tokens):
        before = requests.get(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["fleet"]), timeout=15)
        assert before.status_code == 200
        count = len(before.json()["vehicles"])
        tm = "TEST" + uuid.uuid4().hex[:6].upper()
        r = requests.post(
            f"{BASE_URL}/api/staff/vehicles",
            headers=_h(tokens["fleet"]),
            json={"tm_number": tm, "capacity_m3": 7.0},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        after = requests.get(f"{BASE_URL}/api/staff/fleet", headers=_h(tokens["fleet"]), timeout=15)
        assert len(after.json()["vehicles"]) == count + 1
        rs = requests.post(
            f"{BASE_URL}/api/staff/vehicles/{vid}/status",
            headers=_h(tokens["fleet"]),
            json={"status": "maintenance"},
            timeout=15,
        )
        assert rs.status_code == 200
        assert rs.json()["status"] == "maintenance"

    def test_operator_cannot_manage_fleet(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/staff/vehicles",
            headers=_h(tokens["operator"]),
            json={"tm_number": "DENIED1", "capacity_m3": 7.0},
            timeout=15,
        )
        assert r.status_code == 403


# ---------------------------------------------------- INVENTORY
class TestInventory:
    def test_store_add_material_and_adjust(self, tokens):
        name = "TEST Cement " + uuid.uuid4().hex[:6]
        r = requests.post(
            f"{BASE_URL}/api/staff/materials",
            headers=_h(tokens["store"]),
            json={"name": name, "unit": "kg", "stock": 100.0, "reorder": 20.0},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        ra = requests.post(
            f"{BASE_URL}/api/staff/materials/{mid}/adjust",
            headers=_h(tokens["store"]),
            json={"delta": -25, "note": "test usage"},
            timeout=15,
        )
        assert ra.status_code == 200
        assert ra.json()["stock"] == 75.0
        rn = requests.post(
            f"{BASE_URL}/api/staff/materials/{mid}/adjust",
            headers=_h(tokens["store"]),
            json={"delta": -1000, "note": "negative test"},
            timeout=15,
        )
        assert rn.status_code == 422

    def test_accountant_cannot_adjust_stock(self, tokens):
        collection = requests.get(
            f"{BASE_URL}/api/staff/collection/inventory",
            headers=_h(tokens["store"]),
            timeout=15,
        )
        assert collection.status_code == 200
        items = collection.json()["items"]
        if not items:
            pytest.skip("no inventory")
        r = requests.post(
            f"{BASE_URL}/api/staff/materials/{items[0]['id']}/adjust",
            headers=_h(tokens["accountant"]),
            json={"delta": 1, "note": "RBAC test"},
            timeout=15,
        )
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
        rs = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production/start", headers=_h(tokens["operator"]), timeout=15)
        assert rs.status_code == 200, rs.text

        detail = requests.get(f"{BASE_URL}/api/staff/orders/{oid}/production", headers=_h(tokens["operator"]), timeout=15)
        assert detail.status_code == 200, detail.text
        remaining = float(detail.json()["remaining_quantity"])
        assert remaining > 0

        rb = requests.post(
            f"{BASE_URL}/api/staff/orders/{oid}/production/batch",
            headers=_h(tokens["operator"]),
            json={
                "quantity": remaining,
                "batch_reference": "PYTEST-COMPLETE",
                "remarks": "production lifecycle regression",
                "consume_materials": False,
            },
            timeout=15,
        )
        assert rb.status_code == 200, rb.text

        rc = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production/complete", headers=_h(tokens["operator"]), timeout=15)
        assert rc.status_code == 200, rc.text

    def test_accountant_forbidden_production(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/staff/orders/507f1f77bcf86cd799439011/production/start",
            headers=_h(tokens["accountant"]),
            timeout=15,
        )
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
        body = {"order_id": oid, "slump_mm": 110, "result": "PASS", "remarks": "pytest"}
        rr = requests.post(f"{BASE_URL}/api/staff/quality", headers=_h(tokens["quality"]), json=body, timeout=15)
        assert rr.status_code == 200, rr.text
        assert rr.json()["result"] == "PASS"

    def test_store_forbidden_quality(self, tokens):
        body = {"order_id": "507f1f77bcf86cd799439011", "result": "PASS"}
        r = requests.post(f"{BASE_URL}/api/staff/quality", headers=_h(tokens["store"]), json=body, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- PAYMENTS
class TestPayments:
    def test_accountant_record_payment(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/invoices", headers=_h(tokens["accountant"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        candidate = next((i for i in items if i.get("actions")), None)
        if not candidate:
            pytest.skip("no outstanding invoice")
        invoice_id = candidate["id"]
        body = {"amount": 0.01, "method": "upi", "note": "test payment"}
        rr = requests.post(f"{BASE_URL}/api/staff/invoices/{invoice_id}/payment", headers=_h(tokens["accountant"]), json=body, timeout=15)
        assert rr.status_code == 200, rr.text
        assert rr.json()["paid"] >= 0.01

    def test_dispatcher_forbidden_payment(self, tokens):
        body = {"amount": 10, "method": "cash", "note": "RBAC test"}
        r = requests.post(
            f"{BASE_URL}/api/staff/invoices/507f1f77bcf86cd799439011/payment",
            headers=_h(tokens["dispatcher"]),
            json=body,
            timeout=15,
        )
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
        assert "suggestions" in r.json()