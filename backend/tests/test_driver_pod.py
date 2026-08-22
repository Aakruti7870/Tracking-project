"""Driver + POD + Upload backend tests.

Covers:
- Image upload (multipart) auth + happy path + non-image 422 + no-auth 401.
- Files GET with token param round-trip returns bytes.
- Driver /home shape, RBAC (customer token on driver route -> 403).
- Full driver progression: dispatch fresh order -> start -> arrive -> unload -> pod -> DELIVERED.
- Invalid order transitions (arrive before start) -> 409.
- Post-POD: order status DELIVERED, vehicle back to available, order history includes EN_ROUTE/AT_SITE/UNLOADING/POD_PENDING/DELIVERED.
- Attendance: checkin, double checkin 409, checkout before checkin (fresh day/driver) 409, GET returns today.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "https://rmc-fleet-ops.preview.emergentagent.com"
API = f"{BASE_URL}/api"

CUSTOMER_MOBILE = "+919000000001"
DRIVER_MOBILE = "+919000000002"
OWNER_EMAIL = "owner@trackmyrmc.test"


def _req_otp(s, identifier):
    r = s.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    if r.status_code == 429:
        time.sleep(31)
        r = s.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    return r


def _login(s, identifier):
    r = _req_otp(s, identifier)
    assert r.status_code == 200, f"request-otp {identifier}: {r.status_code} {r.text}"
    code = r.json()["dev_otp"]
    v = s.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code})
    assert v.status_code == 200, f"verify {identifier}: {v.text}"
    return v.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def session():
    return requests.Session()


@pytest.fixture(scope="module")
def customer_tok(session):
    return _login(session, CUSTOMER_MOBILE)


@pytest.fixture(scope="module")
def driver_tok(session):
    return _login(session, DRIVER_MOBILE)


@pytest.fixture(scope="module")
def owner_tok(session):
    return _login(session, OWNER_EMAIL)


def _tiny_jpeg_bytes():
    # 1x1 white JPEG (smallest valid)
    from base64 import b64decode
    return b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
        "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
        "2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QA"
        "HwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF"
        "BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK"
        "FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1"
        "dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
        "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oACAEBAAA/APVI"
        "6P/Z"
    )


# ---------- Upload / Files ----------
class TestUpload:
    def test_upload_no_auth_401(self, session):
        r = session.post(f"{API}/upload", files={"file": ("x.jpg", b"x", "image/jpeg")})
        assert r.status_code == 401

    def test_upload_non_image_422(self, session, driver_tok):
        r = session.post(
            f"{API}/upload",
            headers=_h(driver_tok),
            files={"file": ("x.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 422, r.text

    def test_upload_and_serve_roundtrip(self, session, driver_tok):
        jpg = _tiny_jpeg_bytes()
        r = session.post(
            f"{API}/upload",
            headers=_h(driver_tok),
            files={"file": ("t.jpg", jpg, "image/jpeg")},
        )
        assert r.status_code == 200, r.text
        path = r.json()["path"]
        assert path.startswith("trackmyrmc/uploads/")
        # Serve with ?token=
        g = session.get(f"{BASE_URL}/api/files/{path}", params={"token": driver_tok})
        assert g.status_code == 200
        assert len(g.content) > 0
        # No token -> 401
        g0 = session.get(f"{BASE_URL}/api/files/{path}")
        assert g0.status_code == 401


# ---------- Driver home + RBAC ----------
class TestDriverHome:
    def test_driver_home_ok(self, session, driver_tok):
        r = session.get(f"{API}/driver/home", headers=_h(driver_tok))
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("name", "vehicle", "active_trip", "completed_today", "checked_in"):
            assert k in j

    def test_customer_forbidden_on_driver(self, session, customer_tok):
        r = session.get(f"{API}/driver/home", headers=_h(customer_tok))
        assert r.status_code == 403


# ---------- Full driver progression ----------
def _fresh_dispatched_trip(session, customer_tok, owner_tok, driver_tok):
    """Ensure driver has a DISPATCHED trip. Prefer creating a fresh one; if
    the fleet is exhausted from prior test runs, resume the existing active
    trip through challan+dispatch as needed."""
    order_id, vehicle_id = None, None
    plants = session.get(f"{API}/customer/plants", headers=_h(customer_tok)).json()["plants"]
    plant_id = plants[0]["id"]

    veh = session.get(f"{API}/owner/fleet", headers=_h(owner_tok))
    assert veh.status_code == 200, veh.text
    available = [v for v in veh.json().get("vehicles", []) if v.get("status") == "available"]

    if available:
        payload = {
            "plant_id": plant_id,
            "grade": "M20",
            "quantity": 6,
            "delivery_date": "2026-01-30",
            "delivery_time": "10:00",
            "site_name": f"Site TEST-{uuid.uuid4().hex[:6]}",
            "site_address": "Test Address",
            "lat": 17.4,
            "lng": 78.5,
            "contact_person": "Cust",
            "contact_mobile": "+919000000001",
        }
        r = session.post(f"{API}/customer/orders", headers=_h(customer_tok), json=payload)
        assert r.status_code in (200, 201), r.text
        order_id = r.json()["id"]
        assert session.post(f"{API}/owner/orders/{order_id}/approve", headers=_h(owner_tok)).status_code == 200
        vehicle_id = available[0]["id"]
        assert session.post(f"{API}/owner/orders/{order_id}/assign-tm", headers=_h(owner_tok), json={"vehicle_id": vehicle_id}).status_code == 200
        drivers = session.get(f"{API}/owner/drivers", headers=_h(owner_tok)).json().get("drivers", [])
        assert drivers
        assert session.post(f"{API}/owner/orders/{order_id}/assign-driver", headers=_h(owner_tok), json={"driver_id": drivers[0]["id"]}).status_code == 200
    else:
        # Fallback: resume the driver's active trip.
        home = session.get(f"{API}/driver/home", headers=_h(driver_tok)).json()
        assert home.get("active_trip"), "no available vehicles and no active trip to resume"
        order_id = home["active_trip"]["order_id"]
        # find its vehicle_id via fleet
        for v in veh.json().get("vehicles", []):
            if v.get("current_order_id") == order_id:
                vehicle_id = v["id"]
                break

    # Ensure challan + dispatch for order_id
    od = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok)).json()["order"]
    if od.get("status") in ("DRIVER_ASSIGNED",):
        r = session.post(f"{API}/owner/orders/{order_id}/challan", headers=_h(owner_tok), json={"batcher": "B1", "supervisor": "S1", "quality_engineer": "Q1", "remarks": None})
        assert r.status_code == 200, r.text
    od = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok)).json()["order"]
    if od.get("status") == "READY_TO_DISPATCH":
        r = session.post(f"{API}/owner/orders/{order_id}/dispatch", headers=_h(owner_tok))
        assert r.status_code == 200, r.text
    return order_id, vehicle_id


class TestDriverProgression:
    def test_full_flow(self, session, customer_tok, driver_tok, owner_tok):
        order_id, vehicle_id = _fresh_dispatched_trip(session, customer_tok, owner_tok, driver_tok)
        # Get trip for driver
        trips = session.get(f"{API}/driver/home", headers=_h(driver_tok)).json()
        assert trips.get("active_trip"), f"no active trip: {trips}"
        trip_id = trips["active_trip"]["id"]

        # arrive before start -> 409
        r = session.post(f"{API}/driver/trips/{trip_id}/arrive", headers=_h(driver_tok))
        assert r.status_code == 409, r.text

        # start
        r = session.post(f"{API}/driver/trips/{trip_id}/start", headers=_h(driver_tok))
        assert r.status_code == 200 and r.json()["status"] == "EN_ROUTE", r.text
        # arrive
        r = session.post(f"{API}/driver/trips/{trip_id}/arrive", headers=_h(driver_tok))
        assert r.status_code == 200 and r.json()["status"] == "ARRIVED"
        # unload
        r = session.post(f"{API}/driver/trips/{trip_id}/unload", headers=_h(driver_tok))
        assert r.status_code == 200 and r.json()["status"] == "UNLOADING"
        # pod
        r = session.post(
            f"{API}/driver/trips/{trip_id}/pod",
            headers=_h(driver_tok),
            json={
                "receiver_name": "TEST_receiver",
                "delivered_quantity": 6,
                "signature": '["M10,10 L20,20"]',
                "remarks": "ok",
                "photo_path": None,
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "DELIVERED"

        # verify order status and history
        od = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok))
        assert od.status_code == 200, od.text
        payload_json = od.json()
        j = payload_json.get("order", payload_json)
        assert j["status"] == "DELIVERED", j
        history_statuses = [h.get("to") or h.get("to_status") for h in payload_json.get("history", [])]
        for expected in ("EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING", "DELIVERED"):
            assert expected in history_statuses, f"missing {expected} in {history_statuses}"

        # vehicle back to available (via owner)
        vlist = session.get(f"{API}/owner/fleet", headers=_h(owner_tok))
        if vlist.status_code == 200:
            match = next((v for v in vlist.json().get("vehicles", []) if v.get("id") == vehicle_id), None)
            if match is not None:
                assert match.get("status") == "available", match


# ---------- Attendance ----------
class TestAttendance:
    def test_attendance_get(self, session, driver_tok):
        r = session.get(f"{API}/driver/attendance", headers=_h(driver_tok))
        assert r.status_code == 200
        assert "date" in r.json()

    def test_checkout_before_checkin_or_double_checkin(self, session, driver_tok):
        # If not checked in today -> checkout should be 409
        cur = session.get(f"{API}/driver/attendance", headers=_h(driver_tok)).json()
        if not cur.get("check_in"):
            r = session.post(f"{API}/driver/attendance/checkout", headers=_h(driver_tok), json={"lat": 17.4, "lng": 78.5})
            assert r.status_code == 409
            # Then checkin
            r = session.post(f"{API}/driver/attendance/checkin", headers=_h(driver_tok), json={"lat": 17.4, "lng": 78.5})
            assert r.status_code == 200, r.text
        # Double checkin -> 409
        r = session.post(f"{API}/driver/attendance/checkin", headers=_h(driver_tok), json={"lat": 17.4, "lng": 78.5})
        assert r.status_code == 409, r.text
