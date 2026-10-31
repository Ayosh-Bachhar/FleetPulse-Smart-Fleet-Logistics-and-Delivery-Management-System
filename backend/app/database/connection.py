from pymongo import AsyncMongoClient
from beanie import init_beanie

from app.core.config import settings

from app.models.vehicle import Vehicle
from app.models.user import User
from app.models.driver import Driver
from app.models.maintenance_record import MaintenanceRecord
from app.models.order import Order
from app.models.trip import Trip

from app.models.shift import Shift
from app.models.external_api_cache import ExternalApiCache


client = AsyncMongoClient(settings.MONGODB_URL)


async def connect_to_database():
    await client.admin.command("ping")

    database = client[settings.DATABASE_NAME]

    await init_beanie(
        database=database,
        document_models=[
            Vehicle,
            User,
            Driver,
            Shift,
            ExternalApiCache,
            MaintenanceRecord,
            Order,
            Trip,
        ],
    )

    print(f"Connected to MongoDB: {settings.DATABASE_NAME}")


async def close_database_connection():
    await client.close()