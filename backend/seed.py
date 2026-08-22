"""Idempotent development seed data for TrackMyRMC.

Deterministic demo accounts (Customer, Driver, Plant Owner, Admin) + a few
plants and orders so the Customer flow works end-to-end. Never run in prod.
"""
import logging

from database import kyc_profiles, orders, plants, users
from models import User
from roles import Role
from security import identifier_key

logger = logging.getLogger("seed")

DEMO_ACCOUNTS = [
    {"name": "Rajesh Kumar", "phone": "+919000000001", "role": Role.CUSTOMER.value},
    {"name": "Suresh Driver", "phone": "+919000000002", "role": Role.DRIVER.value},
    {"name": "Concrete King (Owner)", "email": "owner@trackmyrmc.test", "role": Role.PLANT_OWNER.value},
    {"name": "Plant Admin", "email": "admin@trackmyrmc.test", "role": Role.ADMIN.value},
]

DEMO_PLANTS = [
    {
        "name": "Concrete King RMC - Kondapur",
        "city": "Hyderabad", "district": "Rangareddy",
        "address": "Plot 42, Kondapur Industrial Area, Hyderabad",
        "lat": 17.4615, "lng": 78.3648,
        "grades": ["M10", "M15", "M20", "M25", "M30"],
        "contact_phone": "+914012345678", "service_area_km": 30,
        "status": "active", "verified": True,
    },
    {
        "name": "Sky RMC - Gachibowli",
        "city": "Hyderabad", "district": "Rangareddy",
        "address": "Survey 88, Gachibowli, Hyderabad",
        "lat": 17.4401, "lng": 78.3489,
        "grades": ["M20", "M25", "M30", "M35"],
        "contact_phone": "+914023456789", "service_area_km": 25,
        "status": "active", "verified": True,
    },
    {
        "name": "Prime Mix - Miyapur",
        "city": "Hyderabad", "district": "Medchal",
        "address": "NH-9, Miyapur X Roads, Hyderabad",
        "lat": 17.4968, "lng": 78.3617,
        "grades": ["M15", "M20", "M25"],
        "contact_phone": "+914034567890", "service_area_km": 20,
        "status": "active", "verified": True,
    },
]


async def run_seed() -> None:
    # Users
    user_ids: dict[str, str] = {}
    for acc in DEMO_ACCOUNTS:
        value = acc.get("email") or acc.get("phone")
        key = identifier_key(value.lower() if "@" in value else value)
        existing = await users.find_one({"identifier_keys": key})
        if existing:
            user_ids[acc["role"]] = str(existing["_id"])
            continue
        u = User(
            name=acc["name"],
            email=acc.get("email"),
            phone=acc.get("phone"),
            identifier_keys=[key],
            roles=[acc["role"]],
            primary_role=acc["role"],
        )
        res = await users.insert_one(u.to_mongo())
        user_ids[acc["role"]] = str(res.inserted_id)
        logger.info("seeded user %s (%s)", acc["name"], acc["role"])

    owner_id = user_ids.get(Role.PLANT_OWNER.value)
    customer_id = user_ids.get(Role.CUSTOMER.value)

    # Plants
    plant_ids: list[str] = []
    for p in DEMO_PLANTS:
        existing = await plants.find_one({"name": p["name"]})
        if existing:
            plant_ids.append(str(existing["_id"]))
            continue
        doc = {**p, "owner_id": owner_id}
        res = await plants.insert_one(doc)
        plant_ids.append(str(res.inserted_id))

    # Customer KYC -> VERIFIED (so demo customer can place orders)
    if customer_id:
        await kyc_profiles.update_one(
            {"user_id": customer_id, "purpose": "CUSTOMER"},
            {"$setOnInsert": {"status": "VERIFIED"}},
            upsert=True,
        )

    # Demo orders for the customer
    if customer_id and plant_ids and await orders.count_documents({"customer_id": customer_id}) == 0:
        from database import next_sequence

        demo_orders = [
            {
                "customer_id": customer_id, "customer_name": "Rajesh Kumar",
                "plant_id": plant_ids[0], "plant_name": DEMO_PLANTS[0]["name"],
                "grade": "M25", "quantity": 12.0,
                "site_name": "Skyline Towers", "site_address": "Financial District, Hyderabad",
                "lat": 17.4213, "lng": 78.3421,
                "delivery_date": "2026-06-20", "delivery_time": "10:00",
                "status": "DISPATCHED", "payment_status": "PARTIAL",
            },
            {
                "customer_id": customer_id, "customer_name": "Rajesh Kumar",
                "plant_id": plant_ids[1], "plant_name": DEMO_PLANTS[1]["name"],
                "grade": "M30", "quantity": 8.0,
                "site_name": "Green Villa", "site_address": "Kokapet, Hyderabad",
                "lat": 17.4102, "lng": 78.3301,
                "delivery_date": "2026-06-10", "delivery_time": "14:00",
                "status": "DELIVERED", "payment_status": "PAID",
            },
        ]
        from datetime import datetime, timezone

        for o in demo_orders:
            seq = await next_sequence("order_number")
            o["order_number"] = f"RMC-{1000 + seq}"
            o["created_at"] = datetime.now(timezone.utc)
            o["updated_at"] = o["created_at"]
        await orders.insert_many(demo_orders)
        logger.info("seeded %d demo orders", len(demo_orders))
