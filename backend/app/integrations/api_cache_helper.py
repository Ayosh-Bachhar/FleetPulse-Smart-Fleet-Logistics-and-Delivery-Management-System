from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

from app.models.external_api_cache import ExternalApiCache


def utc_datetime(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


async def get_cached_payload(
    cache_key: str,
    allow_expired: bool = False,
):
    record = await ExternalApiCache.find_one(
        ExternalApiCache.cache_key == cache_key
    )

    if record is None:
        return None

    if (
        not allow_expired
        and utc_datetime(record.expires_at)
        <= datetime.now(timezone.utc)
    ):
        return None

    return record.payload


async def save_cached_payload(
    cache_key: str,
    payload: dict,
    ttl_hours: int = 168,
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)

    record = await ExternalApiCache.find_one(
        ExternalApiCache.cache_key == cache_key
    )

    if record is None:
        record = ExternalApiCache(
            cache_key=cache_key,
            payload=payload,
            expires_at=expires_at,
        )

        try:
            await record.insert()
            return
        except DuplicateKeyError:
            record = await ExternalApiCache.find_one(
                ExternalApiCache.cache_key == cache_key
            )

    if record is not None:
        record.payload = payload
        record.expires_at = expires_at
        record.updated_at = now
        await record.save()