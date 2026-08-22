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


@pytest.fixture(scope="session")
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
        approve_id = pending[0]["id"]
        ra = requests.post(f"{BASE_URL}/api/staff/kyc/{approve_id}/approve", headers=_h(tokens["authority"]), timeout=15)
        assert ra.status_code == 200, ra.text
        assert ra.json()["status"] == "VERIFIED"
        # Verify persisted
        r2 = requests.get(f"{BASE_URL}/api/staff/collection/kyc", headers=_h(tokens["authority"]), timeout=15)
        match = next((i for i in r2.json()["items"] if i["id"] == approve_id), None)
        assert match and match["badge"] == "VERIFIED"

        # Reject second if present
        pending2 = [i for i in r2.json()["items"] if i.get("badge") == "PENDING"]
        if pending2:
            rid = pending2[0]["id"]
            rr = requests.post(f"{BASE_URL}/api/staff/kyc/{rid}/reject",
                               headers=_h(tokens["authority"]), json={"reason": "TEST_reject_reason"}, timeout=15)
            assert rr.status_code == 200, rr.text
            assert rr.json()["status"] == "REJECTED"


# ---------------------------------------------------- Central admin: users
class TestUsers:
    def test_users_list_has_suspend_action(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        assert r.status_code == 200
        actionable = [u for u in r.json()["items"] if u.get("actions")]
        assert len(actionable) > 0

    def test_suspend_then_activate(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        # pick a non-central user
        target = next(u for u in r.json()["items"] if any(a["key"] == "suspend" for a in u.get("actions", [])) and "Central" not in (u.get("secondary") or ""))
        uid = target["id"]
        r1 = requests.post(f"{BASE_URL}/api/staff/users/{uid}/suspend", headers=_h(tokens["central"]), timeout=15)
        assert r1.status_code == 200 and r1.json()["status"] == "suspended"
        r2 = requests.get(f"{BASE_URL}/api/staff/collection/users", headers=_h(tokens["central"]), timeout=15)
        match = next(u for u in r2.json()["items"] if u["id"] == uid)
        assert match["badge"].lower() == "suspended"
        r3 = requests.post(f"{BASE_URL}/api/staff/users/{uid}/activate", headers=_h(tokens["central"]), timeout=15)
        assert r3.status_code == 200 and r3.json()["status"] == "active"

    def test_rbac_admin_cannot_suspend(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/users/xxx/suspend", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Fleet
class TestFleet:
    def test_add_vehicle_and_toggle_status(self, tokens):
        tm = f"TSTEST{uuid.uuid4().hex[:6].upper()}"
        r = requests.post(f"{BASE_URL}/api/staff/vehicles", headers=_h(tokens["fleet"]),
                          json={"tm_number": tm, "capacity_m3": 6.5}, timeout=15)
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        # Duplicate should 409
        r_dup = requests.post(f"{BASE_URL}/api/staff/vehicles", headers=_h(tokens["fleet"]),
                              json={"tm_number": tm, "capacity_m3": 6.5}, timeout=15)
        assert r_dup.status_code == 409
        # Toggle maintenance
        r2 = requests.post(f"{BASE_URL}/api/staff/vehicles/{vid}/status", headers=_h(tokens["fleet"]),
                           json={"status": "maintenance"}, timeout=15)
        assert r2.status_code == 200 and r2.json()["status"] == "maintenance"
        r3 = requests.post(f"{BASE_URL}/api/staff/vehicles/{vid}/status", headers=_h(tokens["fleet"]),
                           json={"status": "available"}, timeout=15)
        assert r3.status_code == 200 and r3.json()["status"] == "available"

    def test_rbac_store_cannot_add_vehicle(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/vehicles", headers=_h(tokens["store"]),
                          json={"tm_number": "TSFAIL", "capacity_m3": 6}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Inventory
class TestInventory:
    def test_add_material_and_adjust(self, tokens):
        name = f"TEST_Mat_{uuid.uuid4().hex[:5]}"
        r = requests.post(f"{BASE_URL}/api/staff/materials", headers=_h(tokens["store"]),
                          json={"name": name, "unit": "MT", "stock": 5, "reorder": 2}, timeout=15)
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        # Stock in
        r_in = requests.post(f"{BASE_URL}/api/staff/materials/{mid}/adjust", headers=_h(tokens["store"]),
                             json={"delta": 3}, timeout=15)
        assert r_in.status_code == 200 and r_in.json()["stock"] == 8
        # Excessive stock-out => 422
        r_out = requests.post(f"{BASE_URL}/api/staff/materials/{mid}/adjust", headers=_h(tokens["store"]),
                              json={"delta": -100}, timeout=15)
        assert r_out.status_code == 422
        # Reasonable stock-out
        r_ok = requests.post(f"{BASE_URL}/api/staff/materials/{mid}/adjust", headers=_h(tokens["store"]),
                             json={"delta": -3}, timeout=15)
        assert r_ok.status_code == 200 and r_ok.json()["stock"] == 5

    def test_rbac_fleet_cannot_adjust(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/materials/xxx/adjust", headers=_h(tokens["fleet"]),
                          json={"delta": 1}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Operator
class TestOperator:
    def test_production_start_complete(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/production", headers=_h(tokens["operator"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        # find an ACCEPTED order
        acc = next((i for i in items if any(a["key"] == "start" for a in i.get("actions", []))), None)
        if not acc:
            # try seeded orders being ACCEPTED via badge match — otherwise skip production path
            pytest.skip("no ACCEPTED order available for start")
        oid = acc["id"]
        r1 = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production/start", headers=_h(tokens["operator"]), timeout=15)
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "IN_PRODUCTION"
        r2 = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/production/complete", headers=_h(tokens["operator"]), timeout=15)
        assert r2.status_code == 200 and r2.json()["status"] == "PRODUCTION_COMPLETE"

    def test_rbac_admin_cannot_start(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/orders/xxx/production/start", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Quality
class TestQuality:
    def test_record_test(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/quality", headers=_h(tokens["quality"]), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("no quality candidates")
        oid = items[0]["id"]
        # detail endpoint
        rd = requests.get(f"{BASE_URL}/api/staff/quality/{oid}", headers=_h(tokens["quality"]), timeout=15)
        assert rd.status_code == 200
        body = {"order_id": oid, "slump_mm": 90, "cube_7d": 20, "cube_28d": 32, "result": "PASS", "remarks": "TEST_ok"}
        rp = requests.post(f"{BASE_URL}/api/staff/quality", headers=_h(tokens["quality"]), json=body, timeout=15)
        assert rp.status_code == 200 and rp.json()["result"] == "PASS"
        # verify persistence -> badge should be QC PASS
        r2 = requests.get(f"{BASE_URL}/api/staff/collection/quality", headers=_h(tokens["quality"]), timeout=15)
        match = next(i for i in r2.json()["items"] if i["id"] == oid)
        assert match["badge"] == "QC PASS"

    def test_rbac_operator_cannot_record(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/quality", headers=_h(tokens["operator"]),
                          json={"order_id": "x", "result": "PASS"}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Accountant
class TestAccountant:
    def test_record_payment_when_available(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/invoices", headers=_h(tokens["accountant"]), timeout=15)
        assert r.status_code == 200
        payable = [i for i in r.json()["items"] if any(a["key"] == "pay" for a in i.get("actions", []))]
        if not payable:
            pytest.skip("seeded invoice already PAID")
        inv = payable[0]
        r2 = requests.post(f"{BASE_URL}/api/staff/invoices/{inv['id']}/payment",
                           headers=_h(tokens["accountant"]), json={"amount": 100, "method": "cash"}, timeout=15)
        assert r2.status_code in (200, 422)

    def test_rbac_store_cannot_pay(self, tokens):
        r = requests.post(f"{BASE_URL}/api/staff/invoices/xxx/payment", headers=_h(tokens["store"]),
                          json={"amount": 1}, timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------- Notifications
class TestNotifications:
    def test_feed_and_read_all(self, tokens):
        # authority received a KYC notification via approve above (recipient is applicant)
        # Use authority itself to test structure
        r = requests.get(f"{BASE_URL}/api/notifications", headers=_h(tokens["authority"]), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "unread" in data and "items" in data
        # Even if empty for authority, ensure endpoints work
        r2 = requests.post(f"{BASE_URL}/api/notifications/read-all", headers=_h(tokens["authority"]), timeout=15)
        assert r2.status_code == 200

    def test_customer_gets_kyc_notification(self, tokens):
        # customer likely has notifications from approved KYC / order status
        r = requests.get(f"{BASE_URL}/api/notifications", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["items"], list)
        if data["items"]:
            nid = data["items"][0]["id"]
            r2 = requests.post(f"{BASE_URL}/api/notifications/{nid}/read", headers=_h(tokens["customer"]), timeout=15)
                
            assert r2.status_code == 200


# ---------------------------------------------------- Maps
class TestMaps:
    def test_status_not_configured(self, tokens):
        r = requests.get(f"{BASE_URL}/api/maps/status", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 200
        assert r.json() == {"configured": False}

    def test_autocomplete_graceful(self, tokens):
        r = requests.get(f"{BASE_URL}/api/maps/autocomplete", params={"input": "Hyd"},
                         headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is False
        assert d["suggestions"] == []

    def test_place_details_returns_409(self, tokens):
        r = requests.get(f"{BASE_URL}/api/maps/place/xxx", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 409
