"""End-to-end conversational ordering and support authorization through HTTP."""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"


def _login(phone):
    requested = requests.post(f"{API}/auth/request-otp", json={"identifier": phone})
    assert requested.status_code == 200, requested.text
    verified = requests.post(f"{API}/auth/verify-otp", json={"identifier": phone, "code": requested.json()["dev_otp"]})
    assert verified.status_code == 200, verified.text
    return verified.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def customer_token():
    return _login("+919000000001")


def test_place_order_requires_kyc_confirmation_and_is_idempotent(customer_token):
    plants = requests.get(f"{API}/customer/plants", headers=_auth(customer_token)).json()["plants"]
    plant = next(row for row in plants if row.get("order_enabled"))
    key = "assistant-" + uuid.uuid4().hex
    order = {"plant_id": plant["id"], "grade": plant["grades"][0], "quantity": 5,
             "site_name": "Assistant E2E Site", "site_address": "Hyderabad",
             "delivery_date": "2026-12-01", "delivery_time": "10:00",
             "delivery_mode": "DELIVERY", "idempotency_key": key}
    prepared = requests.post(f"{API}/assistant/orders/prepare", headers=_auth(customer_token), json={"order": order})
    assert prepared.status_code == 200, prepared.text
    intent = prepared.json()
    assert intent["requires_confirmation"] is True

    refused = requests.post(f"{API}/assistant/orders/confirm", headers=_auth(customer_token),
                            json={"intent_token": intent["intent_token"], "confirmed": False})
    assert refused.status_code == 409
    confirmed = requests.post(f"{API}/assistant/orders/confirm", headers=_auth(customer_token),
                              json={"intent_token": intent["intent_token"], "confirmed": True})
    assert confirmed.status_code == 200, confirmed.text
    replay = requests.post(f"{API}/assistant/orders/confirm", headers=_auth(customer_token),
                           json={"intent_token": intent["intent_token"], "confirmed": True})
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == confirmed.json()["id"]
    assert replay.json()["idempotent_replay"] is True

    unverified = _login(f"+9182{uuid.uuid4().int % 100000000:08d}")
    denied = requests.post(f"{API}/assistant/orders/prepare", headers=_auth(unverified), json={"order": order})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "KYC_REQUIRED"


@pytest.mark.parametrize("category", [
    "LOGIN", "KYC", "ORDER", "TRACKING", "PAYMENT", "ACCOUNT_DELETION", "PLANT_ONBOARDING", "GENERAL",
])
def test_support_routes_are_authenticated_and_escalatable(customer_token, category):
    response = requests.post(f"{API}/assistant/support", headers=_auth(customer_token),
                             json={"category": category, "message": "Please help", "escalate": True})
    assert response.status_code == 200, response.text
    assert response.json()["action"].startswith("OPEN_")
    assert response.json()["case_id"]


def test_assistant_tools_fail_closed_without_authentication():
    response = requests.post(f"{API}/assistant/support",
                             json={"category": "GENERAL", "message": "Please help"})
    assert response.status_code == 401
