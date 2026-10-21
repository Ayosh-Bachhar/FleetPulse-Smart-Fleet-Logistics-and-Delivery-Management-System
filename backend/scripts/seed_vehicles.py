"""Idempotently seed FleetPulse demonstration vehicles into MongoDB Atlas.

From the repository root:
    cd backend
    python -m scripts.seed_vehicles

Requires backend/.env to contain an authorized MongoDB Atlas connection.
Does not delete vehicles or overwrite existing records.
"""

import asyncio

from app.database.connection import connect_to_database, close_database_connection
from app.models.vehicle import Vehicle


DEMO_VEHICLES = (
    {"registration_number": "FP-DEMO-001", "vehicle_type": "Truck", "capacity_kg": 3500, "status": "available"},
    {"registration_number": "FP-DEMO-002", "vehicle_type": "Van", "capacity_kg": 1000, "status": "available"},
    {"registration_number": "FP-DEMO-003", "vehicle_type": "Truck", "capacity_kg": 5000, "status": "maintenance"},
    {"registration_number": "FP-DEMO-004", "vehicle_type": "Mini Van", "capacity_kg": 700, "status": "available"},
)


async def seed_vehicles():
    await connect_to_database()
    try:
        created = 0
        skipped = 0
        for data in DEMO_VEHICLES:
            existing = await Vehicle.find_one(Vehicle.registration_number == data["registration_number"])
            if existing is not None:
                skipped += 1
                print(f"Skipped existing vehicle: {data['registration_number']}")
                continue
            await Vehicle(**data).insert()
            created += 1
            print(f"Created vehicle: {data['registration_number']}")
        print(f"Vehicle seeding complete: {created} created, {skipped} skipped.")
        print(f"Total vehicles currently in database: {await Vehicle.count()}")
    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(seed_vehicles())