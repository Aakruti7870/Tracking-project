"""TrackMyRMC Phase 3 backend tests — Assign & Dispatch workflow.

Covers:
- GET /api/owner/fleet returns 3 vehicles (2 available, 1 maintenance)
- GET /api/owner/drivers returns seeded driver Suresh (linked to plant)
- Full happy path: PENDING -> ACCEPTED -> TM_ASSIGNED -> DRIVER_ASSIGNED
  -> READY_TO_DISPATCH (challan) -> DISPATCHED
- State guards:
    * dispatch before challan -> 409
    * challan before driver -> 409
    * assign-driver before TM -> 409
    * assigning a vehicle in 'maintenance' -> 409
- Plant isolation: foreign vehicle_id (fake ObjectId) -> 404
- RBAC: customer token on /api/owner/* -> 403
- After dispatch, customer detail exposes tm/driver/challan + 6-step history
- Both owner & customer /orders/{id}/challan return the same challan;
  fetching challan before generation -> 404
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://trackmyrmc-kyc-ui.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

CUSTOMER = "+919000000001"
OWNER = "owner@trackmyrmc.test"


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
    assert rv.status_code == 200, rv.text
    return rv.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def customer_token(api_client):
    return _login(api_client, CUSTOMER)["access_token"]


@pytest.fixture(scope="module")
def owner_token(api_client):
    time.sleep(1)
    return _login(api_client, OWNER)["access_token"]


@pytest.fixture(scope="module")
def plants(api_client, customer_token):
    r = api_client.get(f"{API}/customer/plants", headers=_auth(customer_token))
    assert r.status_code == 200
    return r.json()["plants"]


def _kondapur(plants):
    """The first seed plant (owns the 3 vehicles + driver)."""
    p = next((x for x in plants if "Kondapur" in x["name"]), None)
    assert p, "Expected Kondapur plant in seed"
    return p


def _new_order(client, customer_token, plant, grade=None):
    body = {
        "plant_id": plant["id"],
        "grade": grade or plant["grades"][0],
        "quantity": 6.0,
        "site_name": "TEST Dispatch Site",
        "site_address": "TEST Address, Hyderabad",
        "delivery_date": "2026-07-15",
        "delivery_time": "10:00",
        "contact_person": "TEST",
        "contact_mobile": "+919000000099",
        "notes": "dispatch-test",
        "save_draft": False,
    }
    r = client.post(f"{API}/customer/orders", headers=_auth(customer_token), json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"], r.json()["order"]["order_number"]


# ---------- Fleet & drivers ----------
class TestFleetAndDrivers:
    def test_fleet_returns_three_vehicles(self, api_client, owner_token):
        r = api_client.get(f"{API}/owner/fleet", headers=_auth(owner_token))
        assert r.status_code == 200, r.text
        vehicles = r.json()["vehicles"]
        # Kondapur has 3 seeded; owner may own other plants with 0 vehicles
        tm_numbers = {v["tm_number"] for v in vehicles}
        assert {"TS09UB1234", "TS09UB5678", "TS09UB9012"}.issubset(tm_numbers)
        statuses = {v["tm_number"]: v["status"] for v in vehicles}
        # 9012 must be maintenance; others start 'available' (may be 'loading'/'dispatched' from prior runs)
        assert statuses["TS09UB9012"] == "maintenance"
        pytest.fleet = vehicles

    def test_drivers_returns_seeded_driver(self, api_client, owner_token):
        r = api_client.get(f"{API}/owner/drivers", headers=_auth(owner_token))
        assert r.status_code == 200, r.text
        drivers = r.json()["drivers"]
        assert any(d["name"] == "Suresh Driver" and d["phone"] == "+919000000002" for d in drivers), drivers
        pytest.drivers = drivers


# ---------- Full happy path ----------
class TestHappyPathDispatch:
    def test_full_chain_pending_to_dispatched(self, api_client, customer_token, owner_token, plants):
        p = _kondapur(plants)
        oid, onum = _new_order(api_client, customer_token, p)
        pytest.disp_oid = oid
        pytest.disp_onum = onum

        # Approve
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 200 and r.json()["status"] == "ACCEPTED"

        # Pick an available vehicle (may need to look up fresh state — some prior test may have marked TMs 'loading'/'dispatched')
        fr = api_client.get(f"{API}/owner/fleet", headers=_auth(owner_token))
        available = [v for v in fr.json()["vehicles"] if v["status"] == "available"]
        if not available:
            pytest.skip("No available vehicles left in DB from prior runs; re-seed to run happy path")
        veh = available[0]

        r = api_client.post(f"{API}/owner/orders/{oid}/assign-tm",
                            headers=_auth(owner_token), json={"vehicle_id": veh["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "TM_ASSIGNED"
        assert r.json()["tm_number"] == veh["tm_number"]

        # Assign driver (Suresh)
        suresh = next(d for d in pytest.drivers if d["name"] == "Suresh Driver")
        r = api_client.post(f"{API}/owner/orders/{oid}/assign-driver",
                            headers=_auth(owner_token), json={"driver_id": suresh["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "DRIVER_ASSIGNED"

        # Generate challan
        r = api_client.post(f"{API}/owner/orders/{oid}/challan",
                            headers=_auth(owner_token), json={})
        assert r.status_code == 200, r.text
        ch = r.json()["challan"]
        assert ch["challan_number"].startswith("CH-")
        pytest.disp_challan_number = ch["challan_number"]

        # After challan, status should be READY_TO_DISPATCH
        rd = api_client.get(f"{API}/owner/orders/{oid}", headers=_auth(owner_token))
        assert rd.json()["order"]["status"] == "READY_TO_DISPATCH"

        # Dispatch
        r = api_client.post(f"{API}/owner/orders/{oid}/dispatch", headers=_auth(owner_token))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "DISPATCHED"

    def test_customer_detail_after_dispatch(self, api_client, customer_token):
        oid = pytest.disp_oid
        r = api_client.get(f"{API}/customer/orders/{oid}", headers=_auth(customer_token))
        assert r.status_code == 200, r.text
        j = r.json()
        o = j["order"]
        assert o["status"] == "DISPATCHED"
        assert o["tm_number"]
        assert o["driver_name"] == "Suresh Driver"
        assert o["driver_mobile"] == "+919000000002"
        assert o["challan_number"] == pytest.disp_challan_number
        # 6-step history
        tos = [h["to"] for h in j["history"]]
        for expected in ["PENDING", "ACCEPTED", "TM_ASSIGNED", "DRIVER_ASSIGNED",
                         "READY_TO_DISPATCH", "DISPATCHED"]:
            assert expected in tos, f"missing {expected} in {tos}"

    def test_challan_visible_to_both_and_matches(self, api_client, customer_token, owner_token):
        oid = pytest.disp_oid
        rc = api_client.get(f"{API}/customer/orders/{oid}/challan", headers=_auth(customer_token))
        ro = api_client.get(f"{API}/owner/orders/{oid}/challan", headers=_auth(owner_token))
        assert rc.status_code == 200 and ro.status_code == 200
        assert rc.json()["challan"]["challan_number"] == ro.json()["challan"]["challan_number"]
        assert rc.json()["challan"]["challan_number"] == pytest.disp_challan_number


# ---------- State guards ----------
class TestStateGuards:
    def _fresh_accepted(self, api_client, customer_token, owner_token, plants):
        p = _kondapur(plants)
        oid, _ = _new_order(api_client, customer_token, p)
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 200
        return oid

    def test_assign_driver_before_tm_conflict(self, api_client, customer_token, owner_token, plants):
        oid = self._fresh_accepted(api_client, customer_token, owner_token, plants)
        # any driver id (won't reach the plant check because status guard runs first)
        drv = next(d for d in pytest.drivers if d["name"] == "Suresh Driver")
        r = api_client.post(f"{API}/owner/orders/{oid}/assign-driver",
                            headers=_auth(owner_token), json={"driver_id": drv["id"]})
        assert r.status_code == 409, r.text

    def test_challan_before_driver_conflict(self, api_client, customer_token, owner_token, plants):
        oid = self._fresh_accepted(api_client, customer_token, owner_token, plants)
        # Assign a TM first, then try challan (skip driver)
        fr = api_client.get(f"{API}/owner/fleet", headers=_auth(owner_token))
        available = [v for v in fr.json()["vehicles"] if v["status"] == "available"]
        if not available:
            pytest.skip("no available vehicles for guard test")
        veh = available[0]
        r = api_client.post(f"{API}/owner/orders/{oid}/assign-tm",
                            headers=_auth(owner_token), json={"vehicle_id": veh["id"]})
        assert r.status_code == 200
        r = api_client.post(f"{API}/owner/orders/{oid}/challan",
                            headers=_auth(owner_token), json={})
        assert r.status_code == 409, r.text

    def test_dispatch_before_challan_conflict(self, api_client, customer_token, owner_token, plants):
        oid = self._fresh_accepted(api_client, customer_token, owner_token, plants)
        r = api_client.post(f"{API}/owner/orders/{oid}/dispatch", headers=_auth(owner_token))
        assert r.status_code == 409, r.text

    def test_assign_maintenance_vehicle_conflict(self, api_client, customer_token, owner_token, plants):
        oid = self._fresh_accepted(api_client, customer_token, owner_token, plants)
        fr = api_client.get(f"{API}/owner/fleet", headers=_auth(owner_token))
        maint = next((v for v in fr.json()["vehicles"] if v["status"] == "maintenance"), None)
        assert maint, "expected a maintenance vehicle in seed"
        r = api_client.post(f"{API}/owner/orders/{oid}/assign-tm",
                            headers=_auth(owner_token), json={"vehicle_id": maint["id"]})
        assert r.status_code == 409, r.text

    def test_challan_before_generation_404(self, api_client, customer_token, owner_token, plants):
        oid = self._fresh_accepted(api_client, customer_token, owner_token, plants)
        rc = api_client.get(f"{API}/customer/orders/{oid}/challan", headers=_auth(customer_token))
        assert rc.status_code == 404
        ro = api_client.get(f"{API}/owner/orders/{oid}/challan", headers=_auth(owner_token))
        assert ro.status_code == 404


# ---------- Isolation & RBAC ----------
class TestIsolationRBAC:
    def test_foreign_vehicle_404(self, api_client, customer_token, owner_token, plants):
        p = _kondapur(plants)
        oid, _ = _new_order(api_client, customer_token, p)
        r = api_client.post(f"{API}/owner/orders/{oid}/approve", headers=_auth(owner_token))
        assert r.status_code == 200
        fake_vid = "507f1f77bcf86cd799439011"
        r = api_client.post(f"{API}/owner/orders/{oid}/assign-tm",
                            headers=_auth(owner_token), json={"vehicle_id": fake_vid})
        assert r.status_code == 404, r.text

    def test_customer_forbidden_on_owner_dispatch(self, api_client, customer_token):
        # any oid will do — 403 comes first from role check
        fake = "507f1f77bcf86cd799439011"
        endpoints = [
            ("GET", "/owner/fleet"),
            ("GET", "/owner/drivers"),
            ("POST", f"/owner/orders/{fake}/assign-tm"),
            ("POST", f"/owner/orders/{fake}/assign-driver"),
            ("POST", f"/owner/orders/{fake}/challan"),
            ("POST", f"/owner/orders/{fake}/dispatch"),
        ]
        for method, path in endpoints:
            if method == "GET":
                r = api_client.get(f"{API}{path}", headers=_auth(customer_token))
            else:
                r = api_client.post(f"{API}{path}", headers=_auth(customer_token), json={})
            assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
