from pymongo import AsyncMongoClient
from beanie import init_beanie
from app.models.vehicle import Vehicle

from app.core.config import settings


client = AsyncMongoClient(settings.MONGODB_URL)


async def connect_to_database():
    await client.admin.command("ping")

    database = client[settings.DATABASE_NAME]

    await init_beanie(
        database=database,
        document_models=[Vehicle],
    )

    print(f"Connected to MongoDB: {settings.DATABASE_NAME}")


async def close_database_connection():
    await client.close()