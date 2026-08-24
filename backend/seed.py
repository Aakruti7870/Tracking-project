"""Idempotent development seed data for the Tracking-project application.

This module is development/test only. It seeds complete master data so preview
flows exercise the same persisted rate-card, mix-design and inventory paths used
by production instead of relying on hard-coded fallbacks.
"""
import logging
import os
import re
from datetime import date, datetime, timezone

from bson import ObjectId

from database import (
    kyc_profiles,
    materials,
    mix_designs,
    orders,
    plants,
    rate_cards,
    users,
    vehicles,
)
from models import User
from roles import Role
from security import identifier_key

logger = logging.getLogger("seed")

DEMO_ACCOUNTS = [
    {"name": "Rajesh Kumar", "phone": "+919000000001", "role": Role.CUSTOMER.value},
    {"name": "Suresh Driver", "phone": "+919000000002", "role": Role.DRIVER.value},
    {"name": "Concrete King (Owner)", "email": "owner@trackmyrmc.test", "role": Role.PLANT_OWNER.value},
    {"name": "Plant Admin", "email": "admin@trackmyrmc.test", "role": Role.ADMIN.value},
    {"name": "Deepak Dispatcher", "email": "dispatcher@trackmyrmc.test", "role": Role.DISPATCHER.value},
    {"name": "Om Operator", "email": "operator@trackmyrmc.test", "role": Role.OPERATOR.value},
    {"name": "Sunil Supervisor", "email": "supervisor@trackmyrmc.test", "role": Role.SUPERVISOR.value},
    {"name": "Anita Accountant", "email": "accountant@trackmyrmc.test", "role": Role.ACCOUNTANT.value},
    {"name": "Qadir Quality", "email": "quality@trackmyrmc.test", "role": Role.QUALITY_ENGINEER.value},
    {"name": "Farhan Fleet", "email": "fleet@trackmyrmc.test", "role": Role.FLEET_MANAGER.value},
    {"name": "Sita Store", "email": "store@trackmyrmc.test", "role": Role.STORE_MANAGER.value},
    {"name": "Arjun Authority", "email": "authority@trackmyrmc.test", "role": Role.AUTHORITY.value},
    {"name": "Central Admin", "email": "central@trackmyrmc.test", "role": Role.CENTRAL_ADMIN.value},
]

_EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")


def _preview_accounts() -> list[dict]:
    accounts = list(DEMO_ACCOUNTS)
    authority_email = os.environ.get("PREVIEW_AUTHORITY_EMAIL", "").strip().lower()
    if authority_email:
        if not _EMAIL_RE.fullmatch(authority_email):
            raise RuntimeError("PREVIEW_AUTHORITY_EMAIL must be a valid email address")
        accounts.append({
            "name": os.environ.get("PREVIEW_AUTHORITY_NAME", "Preview Authority").strip() or "Preview Authority",
            "email": authority_email,
            "role": Role.AUTHORITY.value,
        })
    return accounts


PLANT_STAFF_ROLES = {
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
}

DEMO_MATERIALS = [
    {"code": "CEMENT", "name": "Cement (OPC 53)", "unit": "MT", "stock": 120, "reorder": 50},
    {"code": "FLY_ASH", "name": "Fly Ash", "unit": "MT", "stock": 45, "reorder": 35},
    {"code": "C_SAND", "name": "C-Sand", "unit": "MT", "stock": 90, "reorder": 40},
    {"code": "SAND", "name": "River Sand", "unit": "MT", "stock": 80, "reorder": 40},
    {"code": "AGGREGATE_20MM", "name": "20mm Aggregate", "unit": "MT", "stock": 100, "reorder": 40},
    {"code": "AGGREGATE_10MM", "name": "10mm Aggregate", "unit": "MT", "stock": 80, "reorder": 40},
    {"code": "ADMIXTURE", "name": "Admixture (SP)", "unit": "kg", "stock": 750, "reorder": 200},
    {"code": "WATER", "name": "Water", "unit": "KL", "stock": 100, "reorder": 25},
]

DEMO_PLANTS = [
    {
        "name": "Concrete King RMC - Kondapur",
        "city": "Hyderabad", "district": "Rangareddy",
        "address": "Plot 42, Kondapur Industrial Area, Hyderabad",
        "lat": 17.4615, "lng": 78.3648,
        "grades": ["M10", "M15", "M20", "M25", "M30", "M35", "M40"],
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

# Preview-only commercial data. Production values must be configured through
# the rate-card/master-data APIs and are never copied from this seed.
DEMO_RATES = {
    "M10": 4200,
    "M15": 4600,
    "M20": 4900,
    "M25": 5100,
    "M30": 5200,
    "M35": 5400,
    "M40": 5900,
}

# Preview-only mix designs. These exist to exercise automatic material
# consumption in tests; production plants must enter their approved designs.
DEMO_MIX_DESIGNS = {
    "M10": {"cement_kg": 165, "fly_ash_kg": 85, "c_sand_kg": 720, "aggregate_10mm_kg": 430, "aggregate_20mm_kg": 720, "admixture_kg": 2.5, "water_litre": 165},
    "M15": {"cement_kg": 185, "fly_ash_kg": 100, "c_sand_kg": 700, "aggregate_10mm_kg": 430, "aggregate_20mm_kg": 710, "admixture_kg": 2.8, "water_litre": 165},
    "M20": {"cement_kg": 240, "fly_ash_kg": 110, "c_sand_kg": 680, "aggregate_10mm_kg": 420, "aggregate_20mm_kg": 700, "admixture_kg": 3.5, "water_litre": 165},
    "M25": {"cement_kg": 270, "fly_ash_kg": 110, "c_sand_kg": 660, "aggregate_10mm_kg": 420, "aggregate_20mm_kg": 690, "admixture_kg": 3.8, "water_litre": 165},
    "M30": {"cement_kg": 310, "fly_ash_kg": 110, "c_sand_kg": 650, "aggregate_10mm_kg": 410, "aggregate_20mm_kg": 680, "admixture_kg": 4.2, "water_litre": 165},
    "M35": {"cement_kg": 360, "fly_ash_kg": 100, "c_sand_kg": 640, "aggregate_10mm_kg": 400, "aggregate_20mm_kg": 670, "admixture_kg": 4.6, "water_litre": 165},
    "M40": {"cement_kg": 390, "fly_ash_kg": 100, "c_sand_kg": 630, "aggregate_10mm_kg": 400, "aggregate_20mm_kg": 660, "admixture_kg": 5.0, "water_litre": 165},
}


async def run_seed() -> None:
    user_ids: dict[str, str] = {}
    for acc in _preview_accounts():
        value = acc.get("email") or acc.get("phone")
        key = identifier_key(value.lower() if "@" in value else value)
        existing = await users.find_one({"identifier_keys": key})
        if existing:
            user_ids[acc["role"]] = str(existing["_id"])
            continue
        u = User(
            name=acc["name"], email=acc.get("email"), phone=acc.get("phone"),
            identifier_keys=[key], roles=[acc["role"]], primary_role=acc["role"],
        )
        res = await users.insert_one(u.to_mongo())
        user_ids[acc["role"]] = str(res.inserted_id)
        logger.info("seeded user %s (%s)", acc["name"], acc["role"])

    owner_id = user_ids.get(Role.PLANT_OWNER.value)
    customer_id = user_ids.get(Role.CUSTOMER.value)
    driver_id = user_ids.get(Role.DRIVER.value)

    plant_ids: list[str] = []
    for p in DEMO_PLANTS:
        existing = await plants.find_one({"name": p["name"]})
        if existing:
            await plants.update_one({"_id": existing["_id"]}, {"$set": {"grades": p["grades"]}})
            plant_ids.append(str(existing["_id"]))
            continue
        doc = {**p, "owner_id": owner_id}
        res = await plants.insert_one(doc)
        plant_ids.append(str(res.inserted_id))

    if driver_id and plant_ids:
        await users.update_one({"_id": ObjectId(driver_id)}, {"$set": {"plant_id": plant_ids[0]}})
    if plant_ids:
        for role, uid in user_ids.items():
            if role in PLANT_STAFF_ROLES:
                await users.update_one({"_id": ObjectId(uid)}, {"$set": {"plant_id": plant_ids[0]}})

    # Upsert coded inventory so existing preview DBs are upgraded idempotently.
    if plant_ids:
        for material in DEMO_MATERIALS:
            existing = await materials.find_one({"plant_id": plant_ids[0], "name": material["name"]})
            if existing:
                await materials.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"code": material["code"], "unit": material["unit"]},
                     "$setOnInsert": {"stock": material["stock"], "reorder": material["reorder"]}},
                )
            else:
                await materials.insert_one({**material, "plant_id": plant_ids[0]})
        logger.info("ensured coded preview inventory")

        # Ensure each offered grade has a persistent current rate and mix design.
        today = date.today().isoformat()
        for grade, rate in DEMO_RATES.items():
            await rate_cards.update_one(
                {"plant_id": plant_ids[0], "grade": grade, "effective_from": today},
                {"$setOnInsert": {"rate_per_m3": rate, "gst_rate": 18.0, "active": True,
                                  "transport_rate_per_km": 0, "pumping_rate_per_m3": 0,
                                  "effective_to": None, "created_at": datetime.now(timezone.utc),
                                  "created_by": "development-seed"}},
                upsert=True,
            )
        for grade, values in DEMO_MIX_DESIGNS.items():
            await mix_designs.update_one(
                {"plant_id": plant_ids[0], "grade": grade, "version": 1},
                {"$setOnInsert": {**values, "active": True, "notes": "Development preview design",
                                  "created_at": datetime.now(timezone.utc), "created_by": "development-seed"}},
                upsert=True,
            )

    if plant_ids and await vehicles.count_documents({"plant_id": plant_ids[0]}) == 0:
        demo_vehicles = [
            {"plant_id": plant_ids[0], "tm_number": "TS09UB1234", "capacity_m3": 6, "status": "available"},
            {"plant_id": plant_ids[0], "tm_number": "TS09UB5678", "capacity_m3": 8, "status": "available"},
            {"plant_id": plant_ids[0], "tm_number": "TS09UB9012", "capacity_m3": 6, "status": "maintenance"},
        ]
        await vehicles.insert_many(demo_vehicles)

    if customer_id:
        await kyc_profiles.update_one(
            {"user_id": customer_id, "purpose": "CUSTOMER"},
            {"$setOnInsert": {"status": "VERIFIED"}}, upsert=True,
        )
    if driver_id:
        await kyc_profiles.update_one(
            {"user_id": driver_id, "purpose": "DRIVER"},
            {"$setOnInsert": {"status": "PENDING", "updated_at": datetime.now(timezone.utc)}}, upsert=True,
        )
    if owner_id:
        await kyc_profiles.update_one(
            {"user_id": owner_id, "purpose": "PLANT"},
            {"$setOnInsert": {"status": "PENDING", "updated_at": datetime.now(timezone.utc)}}, upsert=True,
        )

    if customer_id and plant_ids and await orders.count_documents({"customer_id": customer_id}) == 0:
        from database import next_sequence
        demo_orders = [
            {"customer_id": customer_id, "customer_name": "Rajesh Kumar",
             "plant_id": plant_ids[0], "plant_name": DEMO_PLANTS[0]["name"],
             "grade": "M25", "quantity": 12.0, "delivery_mode": "DELIVERY",
             "site_name": "Skyline Towers", "site_address": "Financial District, Hyderabad",
             "lat": 17.4213, "lng": 78.3421, "delivery_date": "2026-06-20", "delivery_time": "10:00",
             "status": "DISPATCHED", "payment_status": "PARTIAL"},
            {"customer_id": customer_id, "customer_name": "Rajesh Kumar",
             "plant_id": plant_ids[1], "plant_name": DEMO_PLANTS[1]["name"],
             "grade": "M30", "quantity": 8.0, "delivery_mode": "DELIVERY",
             "site_name": "Green Villa", "site_address": "Kokapet, Hyderabad",
             "lat": 17.4102, "lng": 78.3301, "delivery_date": "2026-06-10", "delivery_time": "14:00",
             "status": "DELIVERED", "payment_status": "PAID"},
            {"customer_id": customer_id, "customer_name": "Rajesh Kumar",
             "plant_id": plant_ids[0], "plant_name": DEMO_PLANTS[0]["name"],
             "grade": "M20", "quantity": 10.0, "delivery_mode": "ONLY_LOADING",
             "site_name": "Lake View Apartments", "site_address": "Narsingi, Hyderabad",
             "lat": 17.3915, "lng": 78.3475, "delivery_date": "2026-06-30", "delivery_time": "08:00",
             "status": "PENDING", "payment_status": "UNPAID"},
        ]
        for o in demo_orders:
            seq = await next_sequence("order_number")
            o["order_number"] = f"RMC-{1000 + seq}"
            o["created_at"] = datetime.now(timezone.utc)
            o["updated_at"] = o["created_at"]
        await orders.insert_many(demo_orders)
        logger.info("seeded %d demo orders", len(demo_orders))
