import json
from pathlib import Path

import httpx

from app.core.config import settings
from app.integrations.api_cache_helper import (
    get_cached_payload,
    save_cached_payload,
)


CALENDARIFIC_URL = "https://calendarific.com/api/v2/holidays"

FALLBACK_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "fallbacks"
    / "calendarific_sample_holidays.json"
)


def load_sample_holidays(year: int, country: str):
    if country != "BD":
        return [], "unavailable"

    try:
        with FALLBACK_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        holidays = [
            item
            for item in data.get("holidays", [])
            if item.get("date", "").startswith(f"{year}-")
        ]

        return holidays, "sample"

    except (OSError, ValueError, TypeError):
        return [], "unavailable"


async def fetch_calendarific_holidays(
    year: int,
    country: str,
):
    params = {
        "api_key": settings.CALENDARIFIC_API_KEY,
        "country": country,
        "year": year,
        "type": "national",
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            CALENDARIFIC_URL,
            params=params,
        )

        response.raise_for_status()
        body = response.json()

    if body.get("meta", {}).get("code") != 200:
        raise ValueError("Calendarific returned an API error.")

    raw_holidays = body.get("response", {}).get("holidays")

    if not isinstance(raw_holidays, list):
        raise ValueError("Invalid Calendarific response.")

    holidays = []

    for item in raw_holidays:
        holiday_date = item.get("date", {}).get("iso")
        name = item.get("name")

        if not isinstance(holiday_date, str) or not name:
            continue

        holidays.append({
            "date": holiday_date[:10],
            "name": str(name),
        })

    return holidays


async def get_holidays_for_year(year: int):
    country = settings.CALENDARIFIC_COUNTRY.upper()

    cache_key = f"calendarific:{country}:{year}:national"

    cached = await get_cached_payload(cache_key)

    if cached is not None:
        return cached.get("holidays", []), "cache"

    if settings.CALENDARIFIC_API_KEY.strip():
        try:
            holidays = await fetch_calendarific_holidays(
                year,
                country,
            )

            await save_cached_payload(
                cache_key,
                {"holidays": holidays},
                ttl_hours=168,
            )

            return holidays, "calendarific"

        except (httpx.HTTPError, ValueError, TypeError):
            pass

    stale = await get_cached_payload(
        cache_key,
        allow_expired=True,
    )

    if stale is not None:
        return stale.get("holidays", []), "stale-cache"

    return load_sample_holidays(year, country)