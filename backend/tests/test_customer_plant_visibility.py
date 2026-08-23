"""Regression coverage for customer RMC plant discovery visibility."""

from routers.customer import (
    CUSTOMER_HIDDEN_PLANT_STATUSES,
    _customer_visible_plant_filter,
    _plant_discovery_sort_key,
    _serialize_plant,
)


def test_customer_discovery_does_not_require_active_or_verified():
    query = _customer_visible_plant_filter()

    assert "verified" not in query
    assert query["status"]["$nin"] == list(CUSTOMER_HIDDEN_PLANT_STATUSES)
    assert "inactive" not in query["status"]["$nin"]


def test_plant_card_contract_separates_visibility_from_order_eligibility():
    active_verified = {
        "_id": "plant-a",
        "name": "Active Verified RMC",
        "city": "Panvel",
        "address": "Panvel, Maharashtra",
        "lat": 18.99,
        "lng": 73.11,
        "grades": ["M20", "M25"],
        "contact_phone": "+910000000000",
        "service_area_km": 25,
        "status": "active",
        "verified": True,
    }
    inactive_verified = {**active_verified, "_id": "plant-b", "name": "Inactive RMC", "status": "inactive"}
    active_unverified = {**active_verified, "_id": "plant-c", "name": "Pending RMC", "verified": False}

    assert _serialize_plant(active_verified)["order_enabled"] is True
    assert _serialize_plant(inactive_verified)["order_enabled"] is False
    assert _serialize_plant(active_unverified)["order_enabled"] is False

    rows = [active_unverified, inactive_verified, active_verified]
    rows.sort(key=_plant_discovery_sort_key)
    assert rows[0]["_id"] == "plant-a"


def test_map_ready_fields_are_returned_for_visible_plants():
    row = _serialize_plant(
        {
            "_id": "plant-map",
            "name": "Map Ready RMC",
            "city": "Navi Mumbai",
            "district": "Raigad",
            "address": "Navi Mumbai, Maharashtra",
            "lat": 19.02,
            "lng": 73.03,
            "grades": ["M30"],
            "contact_phone": "+910000000000",
            "service_area_km": 30,
            "status": "inactive",
            "verified": False,
        }
    )

    assert row["lat"] == 19.02
    assert row["lng"] == 73.03
    assert row["status"] == "inactive"
    assert row["verified"] is False
