"""Complete preview master-data seeding for every development plant.

Production never runs this module. It prevents tests from depending on which
seeded plant is selected by ensuring every preview plant has coded inventory,
current rates and active mix designs for its offered grades.
"""
from datetime import date, datetime, timezone

from database import materials, mix_designs, plants, rate_cards
from seed import DEMO_MATERIALS, DEMO_MIX_DESIGNS, DEMO_RATES


async def run_business_seed() -> None:
    plant_docs = await plants.find({"status": "active", "verified": True}).to_list(500)
    today = date.today().isoformat()
    for plant in plant_docs:
        plant_id = str(plant["_id"])
        for material in DEMO_MATERIALS:
            await materials.update_one(
                {"plant_id": plant_id, "code": material["code"]},
                {
                    "$set": {"name": material["name"], "unit": material["unit"], "reorder": material["reorder"]},
                    "$setOnInsert": {"stock": material["stock"]},
                },
                upsert=True,
            )
        for grade in plant.get("grades", []):
            if grade in DEMO_RATES:
                await rate_cards.update_one(
                    {"plant_id": plant_id, "grade": grade, "effective_from": today},
                    {"$setOnInsert": {
                        "rate_per_m3": DEMO_RATES[grade], "gst_rate": 18.0,
                        "transport_rate_per_km": 0, "pumping_rate_per_m3": 0,
                        "effective_to": None, "active": True,
                        "created_at": datetime.now(timezone.utc), "created_by": "development-seed",
                    }},
                    upsert=True,
                )
            if grade in DEMO_MIX_DESIGNS:
                await mix_designs.update_one(
                    {"plant_id": plant_id, "grade": grade, "version": 1},
                    {"$setOnInsert": {
                        **DEMO_MIX_DESIGNS[grade], "active": True,
                        "notes": "Development preview design",
                        "created_at": datetime.now(timezone.utc), "created_by": "development-seed",
                    }},
                    upsert=True,
                )
