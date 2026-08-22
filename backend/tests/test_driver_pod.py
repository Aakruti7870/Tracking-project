"""Driver + POD + upload integration tests.

Exercises authenticated image storage, driver-only trip state progression,
live location, mandatory photo/signature POD, vehicle release and attendance.
"""
from base64 import b64decode
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
        time.sleep(2)
        r = s.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    return r


def _login(s, identifier):
    r = _req_otp(s, identifier)
    assert r.status_code == 200, f"request-otp {identifier}: {r.status_code} {r.text}"
    code = r.json()["dev_otp"]
    v = s.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code})
    assert v.status_code == 200, f"verify {identifier}: {v.text}"
    return v.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _tiny_jpeg_bytes():
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


def _upload_site_photo(session, driver_tok, trip_id):
    r = session.post(
        f"{API}/upload",
        headers=_h(driver_tok),
        data={"purpose": "POD", "trip_id": trip_id},
        files={"file": ("delivery.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    return r.json()["path"]


class TestUpload:
    def test_upload_no_auth_401(self, session):
        r = session.post(
            f"{API}/upload",
            data={"purpose": "POD", "trip_id": "missing"},
            files={"file": ("x.jpg", b"x", "image/jpeg")},
        )
        assert r.status_code == 401


class TestDriverHome:
    def test_driver_home_ok(self, session, driver_tok):
        r = session.get(f"{API}/driver/home", headers=_h(driver_tok))
        assert r.status_code == 200, r.text
        for key in ("name", "vehicle", "active_trip", "completed_today", "checked_in"):
            assert key in r.json()

    def test_customer_forbidden_on_driver(self, session, customer_tok):
        assert session.get(f"{API}/driver/home", headers=_h(customer_tok)).status_code == 403


def _fresh_dispatched_trip(session, customer_tok, owner_tok, driver_tok):
    plants = session.get(f"{API}/customer/plants", headers=_h(customer_tok)).json()["plants"]
    plant_id = plants[0]["id"]
    fleet = session.get(f"{API}/owner/fleet", headers=_h(owner_tok))
    assert fleet.status_code == 200, fleet.text
    available = [v for v in fleet.json().get("vehicles", []) if v.get("status") == "available"]

    if available:
        payload = {
            "plant_id": plant_id,
            "grade": "M20",
            "quantity": 6,
            "delivery_date": "2026-09-01",
            "delivery_time": "10:00",
            "site_name": f"TEST Site {uuid.uuid4().hex[:6]}",
            "site_address": "TEST Delivery Address",
            "lat": 19.03,
            "lng": 73.02,
            "contact_person": "TEST Contact",
            "contact_mobile": CUSTOMER_MOBILE,
        }
        created = session.post(f"{API}/customer/orders", headers=_h(customer_tok), json=payload)
        assert created.status_code in (200, 201), created.text
        order_id = created.json()["id"]
        assert session.post(f"{API}/owner/orders/{order_id}/approve", headers=_h(owner_tok)).status_code == 200
        vehicle_id = available[0]["id"]
        tm = session.post(
            f"{API}/owner/orders/{order_id}/assign-tm",
            headers=_h(owner_tok),
            json={"vehicle_id": vehicle_id},
        )
        assert tm.status_code == 200, tm.text
        drivers = session.get(f"{API}/owner/drivers", headers=_h(owner_tok)).json().get("drivers", [])
        assert drivers
        drv = session.post(
            f"{API}/owner/orders/{order_id}/assign-driver",
            headers=_h(owner_tok),
            json={"driver_id": drivers[0]["id"]},
        )
        assert drv.status_code == 200, drv.text
    else:
        home = session.get(f"{API}/driver/home", headers=_h(driver_tok)).json()
        assert home.get("active_trip"), "no available vehicle and no active trip"
        order_id = home["active_trip"]["order_id"]
        vehicle_id = None
        for v in fleet.json().get("vehicles", []):
            if v.get("current_order_id") == order_id:
                vehicle_id = v["id"]
                break

    order = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok)).json()["order"]
    if order.get("status") == "DRIVER_ASSIGNED":
        ch = session.post(
            f"{API}/owner/orders/{order_id}/challan",
            headers=_h(owner_tok),
            json={"batcher": "TEST B", "supervisor": "TEST S", "quality_engineer": "TEST Q"},
        )
        assert ch.status_code == 200, ch.text
    order = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok)).json()["order"]
    if order.get("status") == "READY_TO_DISPATCH":
        dispatch = session.post(f"{API}/owner/orders/{order_id}/dispatch", headers=_h(owner_tok))
        assert dispatch.status_code == 200, dispatch.text
    return order_id, vehicle_id


class TestDriverProgression:
    def test_full_flow_with_location_and_pod(self, session, customer_tok, driver_tok, owner_tok):
        order_id, vehicle_id = _fresh_dispatched_trip(session, customer_tok, owner_tok, driver_tok)
        home = session.get(f"{API}/driver/home", headers=_h(driver_tok)).json()
        assert home.get("active_trip"), home
        trip_id = home["active_trip"]["id"]

        assert session.post(f"{API}/driver/trips/{trip_id}/arrive", headers=_h(driver_tok)).status_code == 409

        start = session.post(f"{API}/driver/trips/{trip_id}/start", headers=_h(driver_tok))
        assert start.status_code == 200 and start.json()["status"] == "EN_ROUTE", start.text

        location = session.post(
            f"{API}/driver/trips/{trip_id}/location",
            headers=_h(driver_tok),
            json={"lat": 19.03, "lng": 73.02, "accuracy": 8},
        )
        assert location.status_code == 200, location.text

        arrive = session.post(f"{API}/driver/trips/{trip_id}/arrive", headers=_h(driver_tok))
        assert arrive.status_code == 200 and arrive.json()["status"] == "ARRIVED", arrive.text
        unload = session.post(f"{API}/driver/trips/{trip_id}/unload", headers=_h(driver_tok))
        assert unload.status_code == 200 and unload.json()["status"] == "UNLOADING", unload.text

        no_photo = session.post(
            f"{API}/driver/trips/{trip_id}/pod",
            headers=_h(driver_tok),
            json={
                "receiver_name": "TEST Receiver",
                "delivered_quantity": 6,
                "signature": '["M10,10 L20,20"]',
            },
        )
        assert no_photo.status_code == 422, no_photo.text

        bad_upload = session.post(
            f"{API}/upload",
            headers=_h(driver_tok),
            data={"purpose": "POD", "trip_id": trip_id},
            files={"file": ("x.txt", b"hello", "text/plain")},
        )
        assert bad_upload.status_code == 422, bad_upload.text

        photo_path = _upload_site_photo(session, driver_tok, trip_id)
        assert photo_path.startswith("trackmyrmc/pod/")

        media = session.get(f"{API}/files/{photo_path}", headers=_h(driver_tok))
        assert media.status_code == 200 and len(media.content) > 0
        assert session.get(f"{API}/files/{photo_path}", params={"token": driver_tok}).status_code == 401

        pod_payload = {
            "receiver_name": "TEST Receiver",
            "delivered_quantity": 6,
            "signature": '["M10,10 L20,20"]',
            "remarks": "TEST ok",
            "photo_path": photo_path,
        }
        pod = session.post(
            f"{API}/driver/trips/{trip_id}/pod",
            headers=_h(driver_tok),
            json=pod_payload,
        )
        assert pod.status_code == 200 and pod.json()["status"] == "DELIVERED", pod.text

        replay = session.post(
            f"{API}/driver/trips/{trip_id}/pod",
            headers=_h(driver_tok),
            json=pod_payload,
        )
        assert replay.status_code == 200 and replay.json().get("idempotent") is True, replay.text

        assert session.post(
            f"{API}/driver/trips/{trip_id}/location",
            headers=_h(driver_tok),
            json={"lat": 19.03, "lng": 73.02},
        ).status_code == 409

        detail = session.get(f"{API}/customer/orders/{order_id}", headers=_h(customer_tok))
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        order = payload.get("order", payload)
        assert order["status"] == "DELIVERED"
        assert payload.get("pod") and payload["pod"].get("delivered_quantity") == 6
        history = [h.get("to") or h.get("to_status") for h in payload.get("history", [])]
        for expected in ("EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING", "DELIVERED"):
            assert expected in history, f"missing {expected} in {history}"

        if vehicle_id:
            fleet = session.get(f"{API}/owner/fleet", headers=_h(owner_tok))
            match = next((v for v in fleet.json().get("vehicles", []) if v.get("id") == vehicle_id), None)
            if match:
                assert match.get("status") == "available", match


class TestAttendance:
    def test_attendance_lifecycle(self, session, driver_tok):
        current = session.get(f"{API}/driver/attendance", headers=_h(driver_tok))
        assert current.status_code == 200
        data = current.json()
        if not data.get("check_in"):
            before = session.post(
                f"{API}/driver/attendance/checkout",
                headers=_h(driver_tok),
                json={"lat": 19.0, "lng": 73.0},
            )
            assert before.status_code == 409
            checkin = session.post(
                f"{API}/driver/attendance/checkin",
                headers=_h(driver_tok),
                json={"lat": 19.0, "lng": 73.0},
            )
            assert checkin.status_code == 200, checkin.text
            duplicate = session.post(
                f"{API}/driver/attendance/checkin",
                headers=_h(driver_tok),
                json={"lat": 19.0, "lng": 73.0},
            )
            assert duplicate.status_code == 409
