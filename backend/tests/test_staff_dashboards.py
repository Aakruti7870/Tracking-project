"""
Backend tests for the 10 staff role dashboards.
Covers:
  - Common EMAIL OTP login for each staff role
  - GET /api/staff/home (role-aware KPIs + primary)
  - GET /api/staff/collection/{kind} for supported kinds
  - RBAC 403 for customer / driver / plant_owner on /api/staff/*
"""
import os
import uuid

import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback to /app/frontend/.env value already exported into env; fail fast otherwise
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not set")

STAFF_IDS = {
    "admin": "admin@trackmyrmc.test",
    "dispatcher": "dispatcher@trackmyrmc.test",
    "operator": "operator@trackmyrmc.test",
    "supervisor": "supervisor@trackmyrmc.test",
    "accountant": "accountant@trackmyrmc.test",
    "quality_engineer": "quality@trackmyrmc.test",
    "fleet_manager": "fleet@trackmyrmc.test",
    "store_manager": "store@trackmyrmc.test",
    "authority": "authority@trackmyrmc.test",
    "central_admin": "central@trackmyrmc.test",
}

NON_STAFF_IDS = {
    "customer": "+919000000001",
    "driver": "+919000000002",
    "plant_owner": "owner@trackmyrmc.test",
}

# kind -> roles that will typically have visibility. We simply assert the
# endpoint returns 200 + expected schema for every kind for every staff role
# (the router does not gate by role, only by staff_only). Also assert
# non-staff -> 403.
COLLECTION_KINDS = [
    "orders", "dispatch", "production", "quality", "incidents",
    "fleet", "drivers", "invoices", "ledger", "inventory",
    "plants", "kyc", "users",
]


def _login(identifier: str) -> str:
    r = requests.post(f"{BASE}/api/auth/request-otp", json={"identifier": identifier}, timeout=15)
    assert r.status_code == 200, f"request-otp failed for {identifier}: {r.status_code} {r.text}"
    dev_otp = r.json().get("dev_otp")
    assert dev_otp, f"dev_otp missing for {identifier}: {r.text}"
    r2 = requests.post(
        f"{BASE}/api/auth/verify-otp",
        json={"identifier": identifier, "code": dev_otp},
        timeout=15,
    )
    assert r2.status_code == 200, f"verify-otp failed for {identifier}: {r2.status_code} {r2.text}"
    token = r2.json().get("access_token")
    assert token, f"access_token missing for {identifier}"
    return token


@pytest.fixture(scope="module")
def staff_tokens():
    return {role: _login(ident) for role, ident in STAFF_IDS.items()}


@pytest.fixture(scope="module")
def non_staff_tokens():
    return {role: _login(ident) for role, ident in NON_STAFF_IDS.items()}


# ---------- STAFF HOME ----------

EXPECTED_PRIMARY_KIND = {
    "admin": "orders",
    "dispatcher": "dispatch",
    "operator": "production",
    "supervisor": "incidents",
    "accountant": "invoices",
    "quality_engineer": "quality",
    "fleet_manager": "fleet",
    "store_manager": "inventory",
    "authority": "plants",
    "central_admin": "users",
}


@pytest.mark.parametrize("role,ident", list(STAFF_IDS.items()))
def test_staff_home_returns_kpis_and_primary(role, ident, staff_tokens):
    token = staff_tokens[role]
    r = requests.get(f"{BASE}/api/staff/home", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200, f"{role}: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("role") == role
    assert data.get("role_label")
    assert isinstance(data.get("kpis"), list)
    assert len(data["kpis"]) == 4, f"{role} kpis={data['kpis']}"
    for k in data["kpis"]:
        assert set(["label", "value", "icon"]).issubset(k.keys())
        assert "unit" in k  # may be None
    assert isinstance(data.get("primary"), dict)
    assert data["primary"].get("kind") == EXPECTED_PRIMARY_KIND[role]
    assert data["primary"].get("title")


# ---------- STAFF COLLECTIONS ----------

@pytest.mark.parametrize("kind", COLLECTION_KINDS)
def test_collection_admin_all_kinds(kind, staff_tokens):
    token = staff_tokens["admin"]
    r = requests.get(f"{BASE}/api/staff/collection/{kind}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200, f"{kind}: {r.status_code} {r.text}"
    data = r.json()
    assert "title" in data
    assert "empty" in data
    assert isinstance(data.get("items"), list)
    for it in data["items"]:
        for key in ("id", "primary"):
            assert key in it, f"item missing {key}: {it}"


def test_collection_unknown_returns_404(staff_tokens):
    token = staff_tokens["admin"]
    r = requests.get(f"{BASE}/api/staff/collection/nope", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 404


# ---------- SCOPING ----------

def test_authority_plants_platform_wide(staff_tokens):
    token = staff_tokens["authority"]
    r = requests.get(f"{BASE}/api/staff/collection/plants", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert len(items) >= 3, f"authority should see all seeded plants, got {len(items)}"


def test_central_admin_users_platform_wide(staff_tokens):
    token = staff_tokens["central_admin"]
    r = requests.get(f"{BASE}/api/staff/collection/users", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    items = r.json().get("items", [])
    # We seed 13 accounts (customer, driver, owner + 10 staff)
    assert len(items) >= 13, f"central_admin users list too small: {len(items)}"


def test_dispatcher_plant_scoped(staff_tokens):
    token = staff_tokens["dispatcher"]
    r = requests.get(f"{BASE}/api/staff/collection/plants", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    items = r.json().get("items", [])
    # plant-scoped role should see exactly its own plant (plant #1)
    assert len(items) == 1, f"dispatcher should be scoped to plant #1, saw {len(items)}"


def _create_low_stock_material(token: str, label: str) -> str:
    name = f"TEST_{label}_{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{BASE}/api/staff/materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "unit": "MT", "stock": 1, "reorder": 2},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return name


def test_store_manager_low_stock_item(staff_tokens):
    token = staff_tokens["store_manager"]
    name = _create_low_stock_material(token, "LowStock")
    r = requests.get(f"{BASE}/api/staff/collection/inventory", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items", [])
    assert items, "store_manager should see materials"
    low_item = next((x for x in items if x.get("primary") == name), None)
    assert low_item, f"controlled low-stock material not present: {[i.get('primary') for i in items]}"
    assert low_item.get("badge") == "LOW", f"controlled material should be LOW, got {low_item}"
    assert "1 MT" in (low_item.get("secondary") or ""), low_item.get("secondary")


def test_store_manager_home_low_stock_kpi(staff_tokens):
    token = staff_tokens["store_manager"]
    _create_low_stock_material(token, "LowStockKpiA")
    _create_low_stock_material(token, "LowStockKpiB")
    r = requests.get(f"{BASE}/api/staff/home", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    kpis = r.json().get("kpis", [])
    low = next((k for k in kpis if k["label"] == "Low Stock"), None)
    assert low and low["value"] >= 2, f"expected at least two controlled low-stock materials, got {low}"


# ---------- RBAC ----------

@pytest.mark.parametrize("role", ["customer", "driver", "plant_owner"])
def test_non_staff_home_forbidden(role, non_staff_tokens):
    token = non_staff_tokens[role]
    r = requests.get(f"{BASE}/api/staff/home", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 403, f"{role} expected 403 on /staff/home, got {r.status_code} {r.text}"


@pytest.mark.parametrize("role", ["customer", "driver", "plant_owner"])
def test_non_staff_collection_forbidden(role, non_staff_tokens):
    token = non_staff_tokens[role]
    r = requests.get(f"{BASE}/api/staff/collection/orders", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 403, f"{role} expected 403 on /staff/collection/orders, got {r.status_code} {r.text}"


def test_no_auth_forbidden():
    r = requests.get(f"{BASE}/api/staff/home", timeout=15)
    assert r.status_code in (401, 403), f"unauth expected 401/403 got {r.status_code} {r.text}"