import hashlib
import json
import math
from pathlib import Path

import httpx

from app.core.config import settings
from app.integrations.api_cache_helper import (
    get_cached_payload,
    save_cached_payload,
)


GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
ROUTING_URL = "https://api.geoapify.com/v1/routing"

FALLBACK_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "fallbacks"
    / "geoapify_sample_route.json"
)


class GeoapifyRouteError(Exception):
    pass


def normalize_address(address):
    return " ".join(address.strip().casefold().split())


def hashed_key(prefix, value):
    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()

    return f"geoapify:{prefix}:{digest}"


def load_demo_data():
    try:
        with FALLBACK_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (OSError, ValueError):
        return {}


def demo_coordinates(address):
    data = load_demo_data()

    if (
        settings.GEOAPIFY_COUNTRY_CODE.lower()
        != data.get("country", "").lower()
    ):
        return None

    locations = data.get("locations", {})
    coords = locations.get(normalize_address(address))

    if not isinstance(coords, list) or len(coords) != 2:
        return None

    return float(coords[0]), float(coords[1])


async def geocode_address(address):
    """
    Return (latitude, longitude, source).

    Source is geoapify, cache or demo.
    Only known sample addresses get offline fallback.
    """
    api_key = settings.GEOAPIFY_API_KEY.strip()

    if api_key:
        country = settings.GEOAPIFY_COUNTRY_CODE.lower()

        cache_key = hashed_key(
            "geocode",
            f"{country}:{normalize_address(address)}",
        )

        cached = await get_cached_payload(cache_key)

        if cached is not None:
            return (
                cached["latitude"],
                cached["longitude"],
                "cache",
            )

        try:
            async with httpx.AsyncClient(
                timeout=12.0
            ) as http:
                response = await http.get(
                    GEOCODE_URL,
                    params={
                        "text": address,
                        "format": "json",
                        "limit": 1,
                        "filter": (
                            f"countrycode:{country}"
                        ),
                        "apiKey": api_key,
                    },
                )

                response.raise_for_status()
                body = response.json()

            results = body.get("results", [])

            if not results:
                raise GeoapifyRouteError(
                    f"Address could not be located: {address}"
                )

            result = results[0]

            if result.get("result_type") in (
                "country",
                "state",
                "unknown",
            ):
                raise GeoapifyRouteError(
                    f"Address is too broad: {address}"
                )

            latitude = float(result["lat"])
            longitude = float(result["lon"])

            if not (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                raise GeoapifyRouteError(
                    "Geoapify returned invalid coordinates."
                )

            await save_cached_payload(
                cache_key,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                ttl_hours=24 * 30,
            )

            return latitude, longitude, "geoapify"

        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            GeoapifyRouteError,
        ):
            pass

    sample = demo_coordinates(address)

    if sample is not None:
        return sample[0], sample[1], "demo"

    if not api_key:
        raise GeoapifyRouteError(
            "A Geoapify API key is required to resolve "
            f"'{address}'. Only predefined demo addresses "
            "work without a key."
        )

    raise GeoapifyRouteError(
        f"Unable to geocode '{address}'. "
        "Check its address and your Geoapify configuration."
    )


def parse_geoapify_route(body):
    features = body.get("features")

    if not isinstance(features, list) or not features:
        raise GeoapifyRouteError(
            "Geoapify did not return a route."
        )

    feature = features[0]
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    try:
        distance_m = float(properties["distance"])
        duration_s = float(properties["time"])
    except (KeyError, ValueError, TypeError) as exc:
        raise GeoapifyRouteError(
            "Geoapify returned invalid route measurements."
        ) from exc

    if not (
        math.isfinite(distance_m)
        and math.isfinite(duration_s)
        and distance_m >= 0
        and duration_s >= 0
    ):
        raise GeoapifyRouteError(
            "Geoapify returned invalid route measurements."
        )

    if geometry.get("type") == "LineString":
        geometry = {
            "type": "MultiLineString",
            "coordinates": [
                geometry.get("coordinates", [])
            ],
        }

    if (
        geometry.get("type") != "MultiLineString"
        or not isinstance(
            geometry.get("coordinates"),
            list,
        )
        or not geometry["coordinates"]
    ):
        raise GeoapifyRouteError(
            "Geoapify returned invalid route geometry."
        )

    return {
        "distance_m": distance_m,
        "duration_s": duration_s,
        "geometry": geometry,
        "source": "geoapify",
    }


def haversine_m(lat1, lon1, lat2, lon2):
    radius_m = 6_371_000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return (
        2 * radius_m
        * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    )


def build_demo_estimate(stops):
    """
    Academic fallback only.

    Distance is straight-line distance multiplied
    by a sample factor, NOT a road-routing result.
    """
    demo = load_demo_data().get(
        "estimate_method",
        {},
    )

    multiplier = float(
        demo.get("road_distance_multiplier", 1.3)
    )

    speed_kmh = float(
        demo.get("average_speed_kmh", 20)
    )

    multiplier = max(1.0, multiplier)
    speed_kmh = max(1.0, speed_kmh)

    straight_distance_m = 0.0
    lines = []

    for first, second in zip(stops, stops[1:]):
        straight_distance_m += haversine_m(
            first.latitude,
            first.longitude,
            second.latitude,
            second.longitude,
        )

        lines.append([
            [first.longitude, first.latitude],
            [second.longitude, second.latitude],
        ])

    estimate_m = straight_distance_m * multiplier

    estimate_seconds = (
        (estimate_m / 1000) / speed_kmh * 3600
    )

    return {
        "distance_m": round(estimate_m, 2),
        "duration_s": round(estimate_seconds, 2),
        "geometry": {
            "type": "MultiLineString",
            "coordinates": lines,
        },
        "source": "demo_estimate",
    }


async def calculate_geoapify_route(
    stops,
    force_refresh=False,
    use_live_api=True,
):
    """
    Return route measurements and geometry.

    A real routing request is only attempted when:
    - an API key exists, and
    - no stop used approximate demo coordinates.
    """
    if len(stops) < 2:
        raise GeoapifyRouteError(
            "At least two route stops are required."
        )

    api_key = settings.GEOAPIFY_API_KEY.strip()

    if not api_key or not use_live_api:
        return build_demo_estimate(stops)

    waypoints = "|".join(
        f"{stop.latitude:.7f},{stop.longitude:.7f}"
        for stop in stops
    )

    cache_key = hashed_key(
        "route",
        f"drive:{waypoints}",
    )

    if not force_refresh:
        cached = await get_cached_payload(cache_key)

        if cached is not None:
            return cached

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as http:
            response = await http.get(
                ROUTING_URL,
                params={
                    "waypoints": waypoints,
                    "mode": "drive",
                    "apiKey": api_key,
                },
            )

            response.raise_for_status()
            body = response.json()

        route = parse_geoapify_route(body)

        await save_cached_payload(
            cache_key,
            route,
            ttl_hours=24 * 7,
        )

        return route

    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        GeoapifyRouteError,
    ):
        # The fallback is an estimate and must always
        # remain visibly labelled as such.
        return build_demo_estimate(stops)