from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class ExternalApiCache(Document):
    cache_key: str
    payload: dict[str, Any]

    expires_at: datetime

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime | None = None

    class Settings:
        name = "external_api_cache"

        indexes = [
            IndexModel(
                [("cache_key", ASCENDING)],
                unique=True,
                name="unique_external_api_cache_key",
            ),
        ]