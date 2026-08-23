"""Phase 6 backend tests: Driver SOS, Production, Invoice/Ledger, Live Tracking.

Covers the new endpoints in /api/driver and /api/owner as well as the
customer live-tracking endpoint.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://tracking-verify.preview.emergentagent.com").rstrip("/")

CUSTOMER = "+919000000001"
DRIVER = "+919000000002"
OWNER = "owner@trackmyrmc.test"
FLEET = "fleet@trackmyrmc.test"


def _wait_cooldown():
    time.sleep(2)


def _login(identifier: str) -> str:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/request-otp", json={"identifier": identifier}, timeout=15)
    if r.status_code == 429:
        time.sleep(2)
        r = s.post(f"{BASE_URL}/api/auth/request-otp", json={"identifier": identifier}, timeout=15)
    assert r.status_code == 200, f"request-otp failed for {identifier}: {r.status_code} {r.text}"
    dev_otp = r.json().get("dev_otp")
    assert dev_otp, f"dev_otp missing in {r.json()}"
    v = s.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": identifier, "code": dev_otp}, timeout=15)
    assert v.status_code == 200, f"verify-otp failed: {v.status_code} {v.text}"
    return v.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    d = _login(DRIVER)
    o = _login(OWNER)
    c = _login(CUSTOMER)
    f = _login(FLEET)
    return {"driver": d, "owner": o, "customer": c, "fleet": f}


def _h(t):
    return {"Authorization": f"Bearer {t}"}


class TestDriverSOS:
    def test_driver_can_raise_sos_and_supervisor_notified(self, tokens):
        payload = {"type": "Breakdown", "remark": "TEST_ sos breakdown", "lat": 17.4, "lng": 78.5}
        r = requests.post(f"{BASE_URL}/api/driver/sos", json=payload, headers=_h(tokens["driver"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "OPEN"
        assert body.get("supervisor_notified") is True, body
        pytest.sos_id = body["id"]

    def test_driver_sees_own_sos_history(self, tokens):
        r = requests.get(f"{BASE_URL}/api/driver/sos", headers=_h(tokens["driver"]), timeout=15)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["incidents"]]
        assert pytest.sos_id in ids

    def test_owner_sees_incident_scoped(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/incidents", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["incidents"]]
        assert pytest.sos_id in ids

    def test_customer_forbidden_on_owner_incidents(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/incidents", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 403

    def test_owner_resolve_incident(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/owner/incidents/{pytest.sos_id}/resolve",
            headers=_h(tokens["owner"]), timeout=15,
        )
        assert r.status_code == 200
        assert r.json().get("status") == "RESOLVED"
        r2 = requests.get(f"{BASE_URL}/api/owner/incidents", headers=_h(tokens["owner"]), timeout=15)
        row = next(i for i in r2.json()["incidents"] if i["id"] == pytest.sos_id)
        assert row["status"] == "RESOLVED"


def _find_or_create_approved_order(owner_token, customer_token) -> str:
    r = requests.get(f"{BASE_URL}/api/owner/orders", headers=_h(owner_token), timeout=15)
    for o in r.json().get("orders", []):
        if o.get("status") == "ACCEPTED":
            return o["id"]
    for o in r.json().get("orders", []):
        if o.get("status") == "PENDING":
            requests.post(f"{BASE_URL}/api/owner/orders/{o['id']}/approve", headers=_h(owner_token), timeout=15)
            return o["id"]
    plants = requests.get(f"{BASE_URL}/api/customer/plants", headers=_h(customer_token), timeout=15).json()["plants"]
    plant = plants[0]
    grade = "M25" if "M25" in plant["grades"] else plant["grades"][0]
    body = {
        "plant_id": plant["id"], "grade": grade, "quantity": 6,
        "site_name": "TEST_ site", "site_address": "TEST_ addr",
        "lat": 17.4, "lng": 78.5, "delivery_date": "2026-09-01", "delivery_time": "10:00",
    }
    cr = requests.post(f"{BASE_URL}/api/customer/orders", json=body, headers=_h(customer_token), timeout=15)
    assert cr.status_code == 200, cr.text
    oid = cr.json()["id"]
    requests.post(f"{BASE_URL}/api/owner/orders/{oid}/approve", headers=_h(owner_token), timeout=15)
    return oid


def _ensure_available_vehicle(tokens) -> dict:
    fleet = requests.get(f"{BASE_URL}/api/owner/fleet", headers=_h(tokens["owner"]), timeout=15).json()["vehicles"]
    avail = next((v for v in fleet if v["status"] == "available"), None)
    if avail:
        return avail
    tm = f"TSPH6{uuid.uuid4().hex[:8].upper()}"
    created = requests.post(
        f"{BASE_URL}/api/staff/vehicles", headers=_h(tokens["fleet"]),
        json={"tm_number": tm, "capacity_m3": 6.5}, timeout=15,
    )
    assert created.status_code == 200, created.text
    vid = created.json()["id"]
    fleet = requests.get(f"{BASE_URL}/api/owner/fleet", headers=_h(tokens["owner"]), timeout=15).json()["vehicles"]
    return next(v for v in fleet if v["id"] == vid and v["status"] == "available")


class TestProduction:
    def test_batch_before_start_returns_409(self, tokens):
        oid = _find_or_create_approved_order(tokens["owner"], tokens["customer"])
        pytest.prod_order_id = oid
        r = requests.post(
            f"{BASE_URL}/api/owner/orders/{oid}/production/batch",
            json={"quantity": 2}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r.status_code == 409, r.text

    def test_start_production(self, tokens):
        r = requests.post(f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/production/start", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PRODUCTION"
        r2 = requests.get(f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/production", headers=_h(tokens["owner"]), timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "IN_PRODUCTION"

    def test_add_batches_accumulate(self, tokens):
        r1 = requests.post(
            f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/production/batch",
            json={"quantity": 3}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["produced"] == 3
        r2 = requests.post(
            f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/production/batch",
            json={"quantity": 3}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["produced"] == 6
        assert isinstance(r2.json().get("material_consumption"), list)

    def test_complete_production_then_assign_tm(self, tokens):
        r = requests.post(f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/production/complete", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "PRODUCTION_COMPLETE"
        avail = _ensure_available_vehicle(tokens)
        r2 = requests.post(
            f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/assign-tm",
            json={"vehicle_id": avail["id"]}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "TM_ASSIGNED"


def _get_delivered_order(owner_token):
    r = requests.get(f"{BASE_URL}/api/owner/orders", headers=_h(owner_token), timeout=15)
    for o in r.json()["orders"]:
        if o.get("status") == "DELIVERED":
            return o
    return None


class TestInvoiceLedger:
    def test_invoice_on_non_delivered_returns_409(self, tokens):
        r = requests.post(f"{BASE_URL}/api/owner/orders/{pytest.prod_order_id}/invoice", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 409

    def test_create_invoice_on_delivered_order(self, tokens):
        do = _get_delivered_order(tokens["owner"])
        if not do:
            pytest.skip("No DELIVERED order in seed to invoice")
        pytest.inv_order = do
        r = requests.post(f"{BASE_URL}/api/owner/orders/{do['id']}/invoice", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200, r.text
        inv = r.json()["invoice"]
        assert inv["invoice_number"].startswith("INV-")
        assert inv["rate"] > 0
        assert inv["gst_rate"] == 18.0
        assert inv["subtotal"] >= round(inv["quantity"] * inv["rate"], 2)
        assert inv["gst"] == round(inv["subtotal"] * inv["gst_rate"] / 100, 2)
        assert inv["total"] == round(inv["subtotal"] + inv["gst"], 2)
        pytest.invoice_id = inv["id"]
        pytest.invoice_total = inv["total"]

    def test_list_invoices_and_summary(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/invoices", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "invoices" in body and "summary" in body
        s = body["summary"]
        for k in ("billed", "received", "outstanding"):
            assert k in s
        assert round(s["billed"] - s["received"], 2) == round(s["outstanding"], 2)

    def test_over_payment_returns_422(self, tokens):
        r = requests.post(
            f"{BASE_URL}/api/owner/invoices/{pytest.invoice_id}/payment",
            json={"amount": pytest.invoice_total + 1000}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r.status_code == 422, r.text

    def test_partial_then_full_payment(self, tokens):
        half = round(pytest.invoice_total / 2, 2)
        r1 = requests.post(
            f"{BASE_URL}/api/owner/invoices/{pytest.invoice_id}/payment",
            json={"amount": half}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "PARTIAL"
        rest = round(pytest.invoice_total - half, 2)
        r2 = requests.post(
            f"{BASE_URL}/api/owner/invoices/{pytest.invoice_id}/payment",
            json={"amount": rest}, headers=_h(tokens["owner"]), timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "PAID"
        od = requests.get(f"{BASE_URL}/api/owner/orders/{pytest.inv_order['id']}", headers=_h(tokens["owner"]), timeout=15).json()
        assert od["order"]["payment_status"] == "PAID"

    def test_ledger_groups_by_customer(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/ledger", headers=_h(tokens["owner"]), timeout=15)
        assert r.status_code == 200
        rows = r.json()["ledger"]
        assert isinstance(rows, list) and len(rows) >= 1
        for row in rows:
            assert set(("customer", "billed", "paid", "balance")).issubset(row.keys())
            assert round(row["billed"] - row["paid"], 2) == round(row["balance"], 2)


class TestTracking:
    def test_tracking_inactive_after_delivered(self, tokens):
        do = _get_delivered_order(tokens["owner"])
        if not do:
            pytest.skip("No DELIVERED order to check tracking")
        r = requests.get(f"{BASE_URL}/api/customer/orders/{do['id']}/tracking", headers=_h(tokens["customer"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["active"] is False
        assert body["status"] == "DELIVERED"

    def test_tracking_active_and_location(self, tokens):
        r = requests.get(f"{BASE_URL}/api/customer/orders", headers=_h(tokens["customer"]), timeout=15)
        active_statuses = {"DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING"}
        active = next((o for o in r.json()["orders"] if o["status"] in active_statuses), None)
        if not active:
            pytest.skip("No active tracked order")
        trips = requests.get(f"{BASE_URL}/api/driver/trips", headers=_h(tokens["driver"]), timeout=15).json()["trips"]
        trip = next((t for t in trips if t["order_id"] == active["id"]), None)
        if trip:
            if trip["status"] in {"DISPATCHED", "ASSIGNED", "ACCEPTED", "LOADING"}:
                started = requests.post(f"{BASE_URL}/api/driver/trips/{trip['id']}/start", headers=_h(tokens["driver"]), timeout=15)
                assert started.status_code == 200, started.text
            loc = requests.post(
                f"{BASE_URL}/api/driver/trips/{trip['id']}/location",
                json={"lat": 17.401, "lng": 78.501}, headers=_h(tokens["driver"]), timeout=15,
            )
            assert loc.status_code == 200, loc.text
        tr = requests.get(f"{BASE_URL}/api/customer/orders/{active['id']}/tracking", headers=_h(tokens["customer"]), timeout=15)
        assert tr.status_code == 200
        body = tr.json()
        assert body["active"] is True
        assert body["status"] in active_statuses
        assert "tm_number" in body
        assert "destination" in body and "site_name" in body["destination"]
        if trip:
            assert body.get("location") is not None
            assert body["location"]["lat"] == 17.401
