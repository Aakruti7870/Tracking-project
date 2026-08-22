"""Iteration 9 — Dispatcher self-service dispatch + RBAC + Owner weekly insights.

Covers:
  - Dispatcher (and admin) can drive the full dispatch pipeline via
    /api/staff/orders/{id}/{assign-tm,assign-driver,challan,dispatch}
  - Operator/store/accountant get 403 on those endpoints
  - Owner /api/owner/insights returns the 7-day chart shape
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

STAFF_ROLES = {
    "dispatcher": "dispatcher@trackmyrmc.test",
    "admin": "admin@trackmyrmc.test",
    "operator": "operator@trackmyrmc.test",
    "store_manager": "store@trackmyrmc.test",
    "accountant": "accountant@trackmyrmc.test",
    "owner": "owner@trackmyrmc.test",
}


def _login(identifier: str) -> str:
    # 30s cooldown per identifier — retry once on 429
    for _ in range(2):
        r = requests.post(f"{BASE_URL}/api/auth/request-otp", json={"identifier": identifier})
        if r.status_code == 429:
            time.sleep(31)
            continue
        break
    assert r.status_code == 200, f"request-otp {identifier}: {r.status_code} {r.text}"
    otp = r.json().get("dev_otp")
    assert otp, f"dev_otp missing: {r.text}"
    v = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"identifier": identifier, "code": otp})
    assert v.status_code == 200, f"verify-otp {identifier}: {v.status_code} {v.text}"
    return v.json()["access_token"]


def _headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens() -> dict:
    out = {}
    for k, e in STAFF_ROLES.items():
        out[k] = _login(e)
        time.sleep(0.2)
    return out


# --------------------------------------------------------------- HELPERS

def _pick_dispatchable_order(dispatcher_tok: str) -> dict | None:
    r = requests.get(f"{BASE_URL}/api/staff/collection/dispatch", headers=_headers(dispatcher_tok))
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    # accept anything that is not DELIVERED/DISPATCHED-terminal — the panel supports resume
    for it in items:
        st = (it.get("badge_status") or "").upper()
        if st in ("ACCEPTED", "SCHEDULED", "PRODUCTION_COMPLETE", "TM_ASSIGNED", "DRIVER_ASSIGNED", "READY_TO_DISPATCH"):
            return it
    return None


def _fleet(tok: str) -> list[dict]:
    r = requests.get(f"{BASE_URL}/api/staff/fleet", headers=_headers(tok))
    assert r.status_code == 200, r.text
    return r.json()["vehicles"]


def _drivers(tok: str) -> list[dict]:
    r = requests.get(f"{BASE_URL}/api/staff/drivers", headers=_headers(tok))
    assert r.status_code == 200, r.text
    return r.json()["drivers"]


# --------------------------------------------------------------- DISPATCH FLOW

class TestDispatchFlow:
    def test_dispatch_lists_orders_with_nav(self, tokens):
        r = requests.get(f"{BASE_URL}/api/staff/collection/dispatch", headers=_headers(tokens["dispatcher"]))
        assert r.status_code == 200
        items = r.json()["items"]
        # dispatcher must see at least one row that carries a nav
        with_nav = [i for i in items if i.get("nav")]
        assert with_nav, f"no nav links returned for dispatcher: {items}"
        assert with_nav[0]["nav"].startswith("/dispatch-order/")

    def test_get_fleet_and_drivers(self, tokens):
        assert _fleet(tokens["dispatcher"])
        assert _drivers(tokens["dispatcher"])

    def test_full_dispatch_progression(self, tokens):
        d = tokens["dispatcher"]
        item = _pick_dispatchable_order(d)
        if not item:
            pytest.skip("no dispatchable order available (all consumed by earlier tests)")
        oid = item["id"]

        # 1. Order detail
        det = requests.get(f"{BASE_URL}/api/staff/orders/{oid}", headers=_headers(d))
        assert det.status_code == 200, det.text
        order = det.json()["order"]
        start_status = order["status"]

        # 2. Assign TM (if needed)
        if start_status in ("ACCEPTED", "SCHEDULED", "PRODUCTION_COMPLETE"):
            avail = [v for v in _fleet(d) if v["status"] == "available"]
            if not avail:
                pytest.skip("no available TM")
            r = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/assign-tm",
                              headers=_headers(d), json={"vehicle_id": avail[0]["id"]})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "TM_ASSIGNED"

        # 3. Assign driver
        det = requests.get(f"{BASE_URL}/api/staff/orders/{oid}", headers=_headers(d)).json()["order"]
        if det["status"] in ("TM_ASSIGNED", "DRIVER_ASSIGNED"):
            drv = _drivers(d)
            assert drv
            r = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/assign-driver",
                              headers=_headers(d), json={"driver_id": drv[0]["id"]})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "DRIVER_ASSIGNED"

        # 4. Challan
        det = requests.get(f"{BASE_URL}/api/staff/orders/{oid}", headers=_headers(d)).json()["order"]
        if det["status"] in ("DRIVER_ASSIGNED", "READY_TO_DISPATCH"):
            r = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/challan", headers=_headers(d))
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "READY_TO_DISPATCH"

        # 5. Dispatch
        det = requests.get(f"{BASE_URL}/api/staff/orders/{oid}", headers=_headers(d)).json()["order"]
        if det["status"] == "READY_TO_DISPATCH":
            r = requests.post(f"{BASE_URL}/api/staff/orders/{oid}/dispatch", headers=_headers(d))
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "DISPATCHED"

        # 6. Verify persisted
        final = requests.get(f"{BASE_URL}/api/staff/orders/{oid}", headers=_headers(d)).json()["order"]
        assert final["status"] in ("DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING", "DELIVERED"), final


# --------------------------------------------------------------- RBAC

DISPATCH_ENDPOINTS = [
    ("assign-tm", {"vehicle_id": "x"}),
    ("assign-driver", {"driver_id": "x"}),
    ("challan", {}),
    ("dispatch", {}),
]


class TestRBAC:
    @pytest.fixture(autouse=True)
    def _victim_order(self, tokens):
        # any order id from dispatch queue — we only need a scoped id; scope error should still be 403 before path resolution
        r = requests.get(f"{BASE_URL}/api/staff/collection/dispatch", headers=_headers(tokens["dispatcher"]))
        items = r.json().get("items", [])
        assert items, "seed dispatch queue is empty"
        self.oid = items[0]["id"]

    @pytest.mark.parametrize("role", ["operator", "store_manager", "accountant"])
    @pytest.mark.parametrize("ep,body", DISPATCH_ENDPOINTS)
    def test_forbidden_for_non_dispatch_roles(self, tokens, role, ep, body):
        r = requests.post(f"{BASE_URL}/api/staff/orders/{self.oid}/{ep}",
                          headers=_headers(tokens[role]), json=body)
        assert r.status_code == 403, f"{role} on {ep}: {r.status_code} {r.text}"

    @pytest.mark.parametrize("ep,body", DISPATCH_ENDPOINTS)
    def test_admin_not_forbidden(self, tokens, ep, body):
        r = requests.post(f"{BASE_URL}/api/staff/orders/{self.oid}/{ep}",
                          headers=_headers(tokens["admin"]), json=body)
        # admin is allowed → any code EXCEPT 403 is fine (409/422/404/200 all acceptable depending on order state)
        assert r.status_code != 403, f"admin unexpectedly blocked on {ep}: {r.text}"


# --------------------------------------------------------------- OWNER INSIGHTS

class TestOwnerInsights:
    def test_shape_and_totals(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/insights", headers=_headers(tokens["owner"]))
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("labels", "ordered", "delivered", "payments", "totals"):
            assert k in j, f"missing key: {k}"
        assert len(j["labels"]) == 7
        assert len(j["ordered"]) == 7
        assert len(j["delivered"]) == 7
        assert len(j["payments"]) == 7
        for k in ("ordered", "delivered", "payments"):
            assert k in j["totals"]
            assert isinstance(j["totals"][k], (int, float))
        # Totals should equal sum of series
        assert round(sum(j["ordered"]), 1) == round(j["totals"]["ordered"], 1)
        assert round(sum(j["delivered"]), 1) == round(j["totals"]["delivered"], 1)

    def test_insights_forbidden_for_non_owner(self, tokens):
        r = requests.get(f"{BASE_URL}/api/owner/insights", headers=_headers(tokens["dispatcher"]))
        assert r.status_code == 403
