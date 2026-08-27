"""Isolated Google Play reviewer fixtures.

Google Play review credentials must be reusable and bypass normal OTP / Google
OAuth. These records are created lazily only when PLAY_REVIEW_ACCESS_ENABLED is
explicitly enabled. They are clearly tagged so they can never be mistaken for
customer production data.
"""
from datetime import datetime, timezone

from bson import ObjectId

from database import driver_trips, kyc_profiles, orders, plants, users, vehicles
from models import User
from roles import Role
from security import identifier_key

REVIEW_ROLES = {
    Role.CUSTOMER.value,
    Role.PLANT_OWNER.value,
    Role.AUTHORITY.value,
    Role.DRIVER.value,
}

_REVIEW_IDENTITIES = {
    Role.CUSTOMER.value: {
        "name": "Google Play Review Customer",
        "phone": "+919000009901",
    },
    Role.DRIVER.value: {
        "name": "Google Play Review Driver",
        "phone": "+919000009902",
    },
    Role.PLANT_OWNER.value: {
        "name": "Google Play Review Owner",
        "email": "play-review-owner@trackmyrmc.test",
    },
    Role.AUTHORITY.value: {
        "name": "Google Play Review Authority",
        "email": "play-review-authority@trackmyrmc.test",
    },
}

REVIEW_PLANT_NAME = "TrackMyRMC Play Review Plant"
REVIEW_ORDER_NUMBER = "PLAY-REVIEW-001"
REVIEW_TM_NUMBER = "REVIEW-TM-01"


def _identity_value(identity: dict) -> str:
    return identity.get("email") or identity["phone"]


async def _ensure_user(role: str) -> dict:
    identity = _REVIEW_IDENTITIES[role]
    value = _identity_value(identity)
    key = identifier_key(value.lower() if "@" in value else value)
    existing = await users.find_one({"play_review_role": role})
    update = {
        "name": identity["name"],
        "email": identity.get("email"),
        "phone": identity.get("phone"),
        "identifier_keys": [key],
        "roles": [role],
        "primary_role": role,
        "status": "active",
        "play_review_role": role,
        "play_review_account": True,
    }
    if existing:
        await users.update_one({"_id": existing["_id"]}, {"$set": update})
        return await users.find_one({"_id": existing["_id"]})

    doc = User(
        name=identity["name"],
        email=identity.get("email"),
        phone=identity.get("phone"),
        identifier_keys=[key],
        roles=[role],
        primary_role=role,
    ).to_mongo()
    doc.update({"play_review_role": role, "play_review_account": True})
    result = await users.insert_one(doc)
    return await users.find_one({"_id": result.inserted_id})


async def _ensure_fixture() -> dict[str, dict]:
    accounts: dict[str, dict] = {}
    # Owner first because the isolated review plant references this account.
    for role in (
        Role.PLANT_OWNER.value,
        Role.CUSTOMER.value,
        Role.DRIVER.value,
        Role.AUTHORITY.value,
    ):
        accounts[role] = await _ensure_user(role)

    owner_id = str(accounts[Role.PLANT_OWNER.value]["_id"])
    customer_id = str(accounts[Role.CUSTOMER.value]["_id"])
    driver_id = str(accounts[Role.DRIVER.value]["_id"])

    plant = await plants.find_one({"play_review_fixture": True})
    plant_doc = {
        "name": REVIEW_PLANT_NAME,
        "owner_id": owner_id,
        "city": "Panvel",
        "district": "Raigad",
        "address": "Google Play review demo plant, Panvel, Maharashtra",
        "lat": 18.9894,
        "lng": 73.1175,
        "grades": ["M20", "M25", "M30", "M35", "M40"],
        "contact_phone": "+919000009900",
        "service_area_km": 30.0,
        "status": "active",
        "verified": True,
        "play_review_fixture": True,
    }
    if plant:
        await plants.update_one({"_id": plant["_id"]}, {"$set": plant_doc})
        plant_id = str(plant["_id"])
    else:
        result = await plants.insert_one(plant_doc)
        plant_id = str(result.inserted_id)

    await users.update_one(
        {"_id": accounts[Role.DRIVER.value]["_id"]},
        {"$set": {"plant_id": plant_id}},
    )

    for role, purpose in (
        (Role.CUSTOMER.value, "CUSTOMER"),
        (Role.DRIVER.value, "DRIVER"),
        (Role.PLANT_OWNER.value, "PLANT"),
    ):
        await kyc_profiles.update_one(
            {"user_id": str(accounts[role]["_id"]), "purpose": purpose},
            {"$set": {
                "status": "VERIFIED",
                "updated_at": datetime.now(timezone.utc),
                "play_review_fixture": True,
            }},
            upsert=True,
        )

    vehicle = await vehicles.find_one({"play_review_fixture": True})
    vehicle_doc = {
        "plant_id": plant_id,
        "tm_number": REVIEW_TM_NUMBER,
        "capacity_m3": 6.0,
        "status": "available",
        "play_review_fixture": True,
    }
    if vehicle:
        await vehicles.update_one({"_id": vehicle["_id"]}, {"$set": vehicle_doc})
        vehicle_id = str(vehicle["_id"])
    else:
        result = await vehicles.insert_one(vehicle_doc)
        vehicle_id = str(result.inserted_id)

    now = datetime.now(timezone.utc)
    order = await orders.find_one({"order_number": REVIEW_ORDER_NUMBER})
    order_doc = {
        "order_number": REVIEW_ORDER_NUMBER,
        "customer_id": customer_id,
        "customer_name": accounts[Role.CUSTOMER.value]["name"],
        "plant_id": plant_id,
        "plant_name": REVIEW_PLANT_NAME,
        "grade": "M25",
        "quantity": 6.0,
        "delivery_mode": "DELIVERY",
        "site_name": "Google Play Review Delivery Site",
        "site_address": "Panvel, Navi Mumbai, Maharashtra",
        "lat": 18.9890,
        "lng": 73.1090,
        "delivery_date": now.date().isoformat(),
        "delivery_time": "10:00",
        "status": "DISPATCHED",
        "payment_status": "PAID",
        "driver_id": driver_id,
        "tm_id": vehicle_id,
        "tm_number": REVIEW_TM_NUMBER,
        "updated_at": now,
        "play_review_fixture": True,
    }
    if order:
        await orders.update_one({"_id": order["_id"]}, {"$set": order_doc})
        order_id = str(order["_id"])
    else:
        order_doc["created_at"] = now
        result = await orders.insert_one(order_doc)
        order_id = str(result.inserted_id)

    trip = await driver_trips.find_one({"play_review_fixture": True})
    trip_doc = {
        "order_id": order_id,
        "order_number": REVIEW_ORDER_NUMBER,
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "tm_number": REVIEW_TM_NUMBER,
        "plant_id": plant_id,
        "status": "EN_ROUTE",
        "grade": "M25",
        "quantity": 6.0,
        "site_name": "Google Play Review Delivery Site",
        "site_address": "Panvel, Navi Mumbai, Maharashtra",
        "updated_at": now,
        "play_review_fixture": True,
    }
    if trip:
        await driver_trips.update_one({"_id": trip["_id"]}, {"$set": trip_doc})
    else:
        trip_doc["created_at"] = now
        await driver_trips.insert_one(trip_doc)

    return accounts


async def play_review_user(role: str) -> dict:
    if role not in REVIEW_ROLES:
        raise ValueError("Unsupported Google Play review role")
    accounts = await _ensure_fixture()
    return accounts[role]
