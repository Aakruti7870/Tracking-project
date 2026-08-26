"""Pre-AAB end-to-end smoke test for the complete TrackMyRMC delivery lifecycle.

This test deliberately runs through real HTTP routes against a live CI backend
and a fresh Mongo database. Customer/Driver use the production mobile-OTP path.
Plant Owner auth remains Google-only; the test first proves email OTP is rejected
for the owner and then creates a CI-only persisted owner session directly in the
test database so no production authentication route is weakened.

Lifecycle covered:
customer login -> order -> owner approval -> production -> TM + driver ->
challan -> dispatch -> driver trip/location -> customer live tracking ->
arrival/unloading -> authenticated POD upload -> delivery -> invoice -> payment.
"""
from base64 import b64decode
import os
import uuid

from pymongo import MongoClient
import requests

from security import identifier_key, issue_jwt, new_session_id, utcnow


BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
CUSTOMER = "+919000000001"
DRIVER = "+919000000002"
OWNER = "owner@trackmyrmc.test"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mobile_login(session: requests.Session, identifier: str, expected_role: str) -> str:
    request = session.post(
        f"{API}/auth/request-otp", json={"identifier": identifier}, timeout=15
    )
    assert request.status_code == 200, request.text
    body = request.json()
    assert body["channel"] == "sms", body
    code = body.get("dev_otp")
    assert code, "CI must expose dev_otp only in APP_ENV=test with DEBUG_OTP=true"

    verify = session.post(
        f"{API}/auth/verify-otp",
        json={"identifier": identifier, "code": code},
        timeout=15,
    )
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload["role"] == expected_role, payload
    return payload["access_token"]


def _assert_owner_is_google_only(session: requests.Session) -> None:
    request = session.post(
        f"{API}/auth/request-otp", json={"identifier": OWNER}, timeout=15
    )
    assert request.status_code == 200, request.text
    code = request.json().get("dev_otp")
    assert code, request.json()

    verify = session.post(
        f"{API}/auth/verify-otp",
        json={"identifier": OWNER, "code": code},
        timeout=15,
    )
    assert verify.status_code == 403, verify.text
    assert verify.json().get("detail") == "This account must sign in with Google"

    google = session.get(f"{API}/auth/google/start", timeout=15)
    # CI does not contain live Google secrets. The production route must fail closed.
    assert google.status_code == 503, google.text
    assert google.json().get("detail") == "Google sign-in is not configured"


def _ci_owner_session() -> str:
    """Persist the same session shape current_user() consumes, without HTTP auth bypasses."""
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ["DB_NAME"]]
        user = db.users.find_one({"identifier_keys": identifier_key(OWNER)})
        assert user, "seeded plant owner is missing"
        assert user.get("primary_role") == "plant_owner", user

        sid = new_session_id()
        token, expires = issue_jwt(str(user["_id"]), sid, "plant_owner")
        db.sessions.insert_one(
            {
                "_id": sid,
                "user_id": str(user["_id"]),
                "role": "plant_owner",
                "revoked": False,
                "created_at": utcnow(),
                "expires_at": expires,
            }
        )
        return token
    finally:
        client.close()


def _tiny_jpeg_bytes() -> bytes:
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


def test_pre_aab_complete_order_to_paid_delivery_e2e():
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    health = session.get(f"{API}/health", timeout=15)
    assert health.status_code == 200, health.text
    assert health.json().get("status") == "healthy"

    customer_token = _mobile_login(session, CUSTOMER, "customer")
    driver_token = _mobile_login(session, DRIVER, "driver")
    _assert_owner_is_google_only(session)
    owner_token = _ci_owner_session()

    # Discover the seeded plant through the same customer API used by the app.
    plant_response = session.get(
        f"{API}/customer/plants", headers=_auth(customer_token), timeout=15
    )
    assert plant_response.status_code == 200, plant_response.text
    plants = plant_response.json().get("plants", [])
    plant = next((p for p in plants if "Kondapur" in p.get("name", "")), None)
    assert plant, plants
    grade = "M25" if "M25" in plant.get("grades", []) else plant["grades"][0]

    # Customer places a verified, six-cubic-metre delivery order.
    order_payload = {
        "plant_id": plant["id"],
        "grade": grade,
        "quantity": 6.0,
        "delivery_mode": "DELIVERY",
        "site_name": f"E2E Site {uuid.uuid4().hex[:8]}",
        "site_address": "E2E Delivery Address, Navi Mumbai",
        "lat": 19.0330,
        "lng": 73.0297,
        "delivery_date": "2026-09-01",
        "delivery_time": "10:00",
        "contact_person": "E2E Receiver",
        "contact_mobile": CUSTOMER,
        "notes": "pre-AAB deterministic lifecycle",
        "save_draft": False,
    }
    created = session.post(
        f"{API}/customer/orders",
        headers=_auth(customer_token),
        json=order_payload,
        timeout=15,
    )
    assert created.status_code in (200, 201), created.text
    order_id = created.json()["id"]
    assert created.json()["order"]["status"] == "PENDING"

    # Owner accepts and completes production before assigning fleet resources.
    approved = session.post(
        f"{API}/owner/orders/{order_id}/approve", headers=_auth(owner_token), timeout=15
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACCEPTED"

    started = session.post(
        f"{API}/owner/orders/{order_id}/production/start",
        headers=_auth(owner_token),
        timeout=15,
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "IN_PRODUCTION"

    batch = session.post(
        f"{API}/owner/orders/{order_id}/production/batch",
        headers=_auth(owner_token),
        json={
            "quantity": 6.0,
            "batch_reference": "PRE-AAB-E2E",
            "remarks": "complete deterministic E2E batch",
            "consume_materials": False,
        },
        timeout=15,
    )
    assert batch.status_code == 200, batch.text
    assert float(batch.json().get("produced", 0)) >= 6.0, batch.json()

    completed = session.post(
        f"{API}/owner/orders/{order_id}/production/complete",
        headers=_auth(owner_token),
        timeout=15,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "PRODUCTION_COMPLETE"

    fleet = session.get(f"{API}/owner/fleet", headers=_auth(owner_token), timeout=15)
    assert fleet.status_code == 200, fleet.text
    vehicle = next(
        (v for v in fleet.json().get("vehicles", []) if v.get("status") == "available"),
        None,
    )
    assert vehicle, fleet.json()

    assigned_tm = session.post(
        f"{API}/owner/orders/{order_id}/assign-tm",
        headers=_auth(owner_token),
        json={"vehicle_id": vehicle["id"]},
        timeout=15,
    )
    assert assigned_tm.status_code == 200, assigned_tm.text
    assert assigned_tm.json()["status"] == "TM_ASSIGNED"

    drivers = session.get(f"{API}/owner/drivers", headers=_auth(owner_token), timeout=15)
    assert drivers.status_code == 200, drivers.text
    driver = next(
        (d for d in drivers.json().get("drivers", []) if d.get("phone") == DRIVER), None
    )
    assert driver, drivers.json()

    assigned_driver = session.post(
        f"{API}/owner/orders/{order_id}/assign-driver",
        headers=_auth(owner_token),
        json={"driver_id": driver["id"]},
        timeout=15,
    )
    assert assigned_driver.status_code == 200, assigned_driver.text
    assert assigned_driver.json()["status"] == "DRIVER_ASSIGNED"

    challan = session.post(
        f"{API}/owner/orders/{order_id}/challan",
        headers=_auth(owner_token),
        json={
            "batcher": "E2E Batcher",
            "supervisor": "E2E Supervisor",
            "quality_engineer": "E2E Quality",
            "remarks": "pre-AAB E2E",
        },
        timeout=15,
    )
    assert challan.status_code == 200, challan.text
    assert challan.json()["challan"]["challan_number"].startswith("CH-")

    dispatched = session.post(
        f"{API}/owner/orders/{order_id}/dispatch",
        headers=_auth(owner_token),
        timeout=15,
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "DISPATCHED"

    # Driver accepts the assigned operational flow and sends live location.
    trip_list = session.get(f"{API}/driver/trips", headers=_auth(driver_token), timeout=15)
    assert trip_list.status_code == 200, trip_list.text
    trip = next(
        (t for t in trip_list.json().get("trips", []) if t.get("order_id") == order_id),
        None,
    )
    assert trip, trip_list.json()
    trip_id = trip["id"]

    trip_start = session.post(
        f"{API}/driver/trips/{trip_id}/start", headers=_auth(driver_token), timeout=15
    )
    assert trip_start.status_code == 200, trip_start.text
    assert trip_start.json()["status"] == "EN_ROUTE"

    location = session.post(
        f"{API}/driver/trips/{trip_id}/location",
        headers=_auth(driver_token),
        json={"lat": 19.0335, "lng": 73.0301, "accuracy": 7},
        timeout=15,
    )
    assert location.status_code == 200, location.text

    tracking = session.get(
        f"{API}/customer/orders/{order_id}/tracking",
        headers=_auth(customer_token),
        timeout=15,
    )
    assert tracking.status_code == 200, tracking.text
    tracked = tracking.json()
    assert tracked["active"] is True, tracked
    assert tracked.get("location"), tracked
    assert abs(float(tracked["location"]["lat"]) - 19.0335) < 0.00001

    arrived = session.post(
        f"{API}/driver/trips/{trip_id}/arrive", headers=_auth(driver_token), timeout=15
    )
    assert arrived.status_code == 200, arrived.text
    assert arrived.json()["status"] == "ARRIVED"

    unloading = session.post(
        f"{API}/driver/trips/{trip_id}/unload", headers=_auth(driver_token), timeout=15
    )
    assert unloading.status_code == 200, unloading.text
    assert unloading.json()["status"] == "UNLOADING"

    upload = session.post(
        f"{API}/upload",
        headers=_auth(driver_token),
        data={"purpose": "POD", "trip_id": trip_id},
        files={"file": ("pre-aab-e2e.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
        timeout=15,
    )
    assert upload.status_code == 200, upload.text
    photo_path = upload.json()["path"]
    assert photo_path.startswith("trackmyrmc/pod/"), upload.json()

    pod = session.post(
        f"{API}/driver/trips/{trip_id}/pod",
        headers=_auth(driver_token),
        json={
            "receiver_name": "E2E Receiver",
            "delivered_quantity": 6.0,
            "signature": '["M10,10 L20,20"]',
            "remarks": "pre-AAB delivered",
            "photo_path": photo_path,
        },
        timeout=15,
    )
    assert pod.status_code == 200, pod.text
    assert pod.json()["status"] == "DELIVERED"

    customer_detail = session.get(
        f"{API}/customer/orders/{order_id}", headers=_auth(customer_token), timeout=15
    )
    assert customer_detail.status_code == 200, customer_detail.text
    detail = customer_detail.json()
    assert detail["order"]["status"] == "DELIVERED", detail
    assert detail.get("pod"), detail
    assert float(detail["pod"]["delivered_quantity"]) == 6.0

    tracking_after = session.get(
        f"{API}/customer/orders/{order_id}/tracking",
        headers=_auth(customer_token),
        timeout=15,
    )
    assert tracking_after.status_code == 200, tracking_after.text
    assert tracking_after.json()["active"] is False, tracking_after.json()

    # Complete the commercial lifecycle: invoice and full payment.
    invoice_response = session.post(
        f"{API}/owner/orders/{order_id}/invoice", headers=_auth(owner_token), timeout=15
    )
    assert invoice_response.status_code == 200, invoice_response.text
    invoice = invoice_response.json()["invoice"]
    assert invoice["invoice_number"].startswith("INV-")
    assert float(invoice["total"]) > 0

    payment = session.post(
        f"{API}/owner/invoices/{invoice['id']}/payment",
        headers=_auth(owner_token),
        json={"amount": invoice["total"], "method": "bank_transfer", "note": "pre-AAB full payment"},
        timeout=15,
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["status"] == "PAID"
    assert abs(float(payment.json()["balance"])) < 0.01

    final_owner = session.get(
        f"{API}/owner/orders/{order_id}", headers=_auth(owner_token), timeout=15
    )
    assert final_owner.status_code == 200, final_owner.text
    final_order = final_owner.json()["order"]
    assert final_order["status"] == "DELIVERED"
    assert final_order["payment_status"] == "PAID"

    final_fleet = session.get(f"{API}/owner/fleet", headers=_auth(owner_token), timeout=15)
    assert final_fleet.status_code == 200, final_fleet.text
    released_vehicle = next(
        v for v in final_fleet.json()["vehicles"] if v["id"] == vehicle["id"]
    )
    assert released_vehicle["status"] == "available", released_vehicle
    assert not released_vehicle.get("current_order_id"), released_vehicle
