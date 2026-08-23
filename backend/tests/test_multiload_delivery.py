"""End-to-end regression for one RMC order fulfilled by two mixer loads."""
from base64 import b64decode
import os
import time
import uuid

import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "https://tracking-verify.preview.emergentagent.com"
API = f"{BASE_URL}/api"
CUSTOMER = "+919000000001"
DRIVER = "+919000000002"
OWNER = "owner@trackmyrmc.test"
FLEET = "fleet@trackmyrmc.test"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _login(session, identifier):
    r = session.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    if r.status_code == 429:
        time.sleep(2)
        r = session.post(f"{API}/auth/request-otp", json={"identifier": identifier})
    assert r.status_code == 200, r.text
    code = r.json()["dev_otp"]
    v = session.post(f"{API}/auth/verify-otp", json={"identifier": identifier, "code": code})
    assert v.status_code == 200, v.text
    return v.json()["access_token"]


def _tiny_jpeg():
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


def _new_vehicle(session, fleet_token, capacity=6.0):
    tm = f"ML{uuid.uuid4().hex[:8].upper()}"
    r = session.post(
        f"{API}/staff/vehicles",
        headers=_h(fleet_token),
        json={"tm_number": tm, "capacity_m3": capacity},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload(session, driver_token, trip_id, suffix):
    r = session.post(
        f"{API}/upload",
        headers=_h(driver_token),
        data={"purpose": "POD", "trip_id": trip_id},
        files={"file": (f"delivery-{suffix}.jpg", _tiny_jpeg(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    return r.json()["path"]


def _deliver_load(session, driver_token, trip_id, quantity, suffix):
    for action, status in (("start", "EN_ROUTE"), ("arrive", "ARRIVED"), ("unload", "UNLOADING")):
        r = session.post(f"{API}/driver/trips/{trip_id}/{action}", headers=_h(driver_token))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == status
    loc = session.post(
        f"{API}/driver/trips/{trip_id}/location",
        headers=_h(driver_token),
        json={"lat": 19.01 + suffix / 1000, "lng": 73.01 + suffix / 1000, "accuracy": 6},
    )
    assert loc.status_code == 200, loc.text
    photo = _upload(session, driver_token, trip_id, suffix)
    pod = session.post(
        f"{API}/driver/trips/{trip_id}/pod",
        headers=_h(driver_token),
        json={
            "receiver_name": f"Receiver {suffix}",
            "delivered_quantity": quantity,
            "photo_path": photo,
            "signature": '["M10,10 L20,20"]',
            "remarks": "multi-load integration test",
        },
    )
    assert pod.status_code == 200, pod.text
    assert pod.json()["status"] == "DELIVERED"
    return pod.json()


def test_two_mixer_loads_finalize_one_commercial_order():
    s = requests.Session()
    customer = _login(s, CUSTOMER)
    owner = _login(s, OWNER)
    driver = _login(s, DRIVER)
    fleet = _login(s, FLEET)

    plants = s.get(f"{API}/customer/plants", headers=_h(customer)).json()["plants"]
    plant = next(p for p in plants if "M25" in p["grades"])
    created = s.post(
        f"{API}/customer/orders",
        headers=_h(customer),
        json={
            "plant_id": plant["id"], "grade": "M25", "quantity": 12,
            "site_name": f"Multi Load {uuid.uuid4().hex[:6]}",
            "site_address": "Panvel integration test site",
            "lat": 19.01, "lng": 73.01,
            "delivery_date": "2026-09-10", "delivery_time": "09:00",
            "delivery_mode": "DELIVERY",
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["id"]
    assert created.json()["order"]["delivery_mode"] == "DELIVERY"

    approved = s.post(f"{API}/owner/orders/{order_id}/approve", headers=_h(owner))
    assert approved.status_code == 200, approved.text
    assert s.post(f"{API}/owner/orders/{order_id}/production/start", headers=_h(owner)).status_code == 200
    batch = s.post(
        f"{API}/owner/orders/{order_id}/production/batch",
        headers=_h(owner), json={"quantity": 12, "batch_reference": f"ML-{uuid.uuid4().hex[:8]}"},
    )
    assert batch.status_code == 200, batch.text
    assert batch.json()["produced"] == 12
    assert batch.json()["material_consumption"]
    complete = s.post(f"{API}/owner/orders/{order_id}/production/complete", headers=_h(owner))
    assert complete.status_code == 200, complete.text

    drivers = s.get(f"{API}/owner/drivers", headers=_h(owner)).json()["drivers"]
    driver_id = drivers[0]["id"]
    vehicle1 = _new_vehicle(s, fleet, 6)
    vehicle2 = _new_vehicle(s, fleet, 6)

    load_ids = []
    for vehicle_id in (vehicle1, vehicle2):
        load = s.post(
            f"{API}/loads/orders/{order_id}", headers=_h(owner),
            json={"quantity_m3": 6, "vehicle_id": vehicle_id, "driver_id": driver_id},
        )
        assert load.status_code == 200, load.text
        assert load.json()["load"]["status"] == "ASSIGNED"
        load_ids.append(load.json()["load"]["id"])

    # First mixer load.
    prep1 = s.post(f"{API}/loads/{load_ids[0]}/prepare", headers=_h(owner), json={"batcher": "Batcher A"})
    assert prep1.status_code == 200, prep1.text
    trip1 = prep1.json()["trip_id"]
    assert prep1.json()["challan"]["load_id"] == load_ids[0]
    gp1 = s.post(
        f"{API}/loads/gate-pass", headers=_h(owner),
        json={"load_id": load_ids[0], "security_name": "Security A"},
    )
    assert gp1.status_code == 200, gp1.text
    assert s.post(f"{API}/loads/{load_ids[0]}/dispatch", headers=_h(owner)).status_code == 200
    result1 = _deliver_load(s, driver, trip1, 6, 1)
    assert result1["order"]["complete"] is False

    middle = s.get(f"{API}/customer/orders/{order_id}", headers=_h(customer))
    assert middle.status_code == 200
    middle_body = middle.json()
    assert middle_body["order"]["status"] == "DISPATCHED"
    assert middle_body["order"]["delivered_quantity"] == 6
    assert len(middle_body["pods"]) == 1

    # Same driver can take the second mixer only after the first trip completed.
    prep2 = s.post(f"{API}/loads/{load_ids[1]}/prepare", headers=_h(owner), json={"batcher": "Batcher B"})
    assert prep2.status_code == 200, prep2.text
    trip2 = prep2.json()["trip_id"]
    gp2 = s.post(
        f"{API}/loads/gate-pass", headers=_h(owner),
        json={"load_id": load_ids[1], "security_name": "Security B"},
    )
    assert gp2.status_code == 200, gp2.text
    assert s.post(f"{API}/loads/{load_ids[1]}/dispatch", headers=_h(owner)).status_code == 200
    result2 = _deliver_load(s, driver, trip2, 6, 2)
    assert result2["order"]["complete"] is True
    assert result2["order"]["order_status"] == "DELIVERED"
    assert result2["order"]["delivered_quantity"] == 12

    final = s.get(f"{API}/customer/orders/{order_id}", headers=_h(customer))
    assert final.status_code == 200, final.text
    body = final.json()
    assert body["order"]["status"] == "DELIVERED"
    assert body["order"]["delivered_quantity"] == 12
    assert len(body["loads"]) == 2
    assert all(load["status"] == "DELIVERED" for load in body["loads"])
    assert len(body["pods"]) == 2

    challans = s.get(f"{API}/customer/orders/{order_id}/challan", headers=_h(customer))
    assert challans.status_code == 200, challans.text
    assert len(challans.json()["challans"]) == 2

    invoice = s.post(f"{API}/owner/orders/{order_id}/invoice", headers=_h(owner))
    assert invoice.status_code == 200, invoice.text
    inv = invoice.json()["invoice"]
    assert inv["quantity"] == 12
    assert inv["rate"] > 0
    assert inv["total"] > inv["subtotal"]
