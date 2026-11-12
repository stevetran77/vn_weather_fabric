"""Fetch hourly Observations (weather and Model PM2.5) from the Open-Meteo historical APIs."""

import json
import logging
from collections.abc import Callable, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_VARIABLES = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m")
AIR_QUALITY_VARIABLES = ("pm2_5",)
REQUEST_TIMEOUT_SECONDS = 60


class OpenMeteoError(Exception):
    """Raised when an Open-Meteo request fails or returns an unexpected payload."""


def _build_url(
    base_url: str,
    latitudes: Sequence[float],
    longitudes: Sequence[float],
    start_date: str,
    end_date: str,
    variables: Sequence[str],
) -> str:
    """Build a request URL; several locations are sent as comma-separated lists."""
    if len(latitudes) != len(longitudes):
        raise ValueError("latitudes and longitudes must have the same length")
    query = {
        "latitude": ",".join(str(value) for value in latitudes),
        "longitude": ",".join(str(value) for value in longitudes),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "GMT",
    }
    return f"{base_url}?{urlencode(query, safe=',')}"


def build_weather_url(
    latitudes: Sequence[float], longitudes: Sequence[float], start_date: str, end_date: str
) -> str:
    """Build the historical (ERA5) weather request URL; dates are YYYY-MM-DD."""
    return _build_url(ARCHIVE_URL, latitudes, longitudes, start_date, end_date, WEATHER_VARIABLES)


def build_air_quality_url(
    latitudes: Sequence[float], longitudes: Sequence[float], start_date: str, end_date: str
) -> str:
    """Build the air quality (Model PM2.5) request URL; dates are YYYY-MM-DD."""
    return _build_url(
        AIR_QUALITY_URL, latitudes, longitudes, start_date, end_date, AIR_QUALITY_VARIABLES
    )


def fetch_json(url: str) -> dict | list:
    """GET a URL and return the decoded JSON body."""
    logger.info("GET %s", url)
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 (fixed https URL)
            return json.load(response)
    except OSError as error:
        raise OpenMeteoError(f"Request failed: {error}") from error


def split_locations(payload: dict | list) -> list[dict]:
    """Return one response object per requested location (a multi-location call returns a list)."""
    return payload if isinstance(payload, list) else [payload]


def hourly_to_rows(location_payload: dict) -> list[dict]:
    """Turn the columnar `hourly` block (a time array plus value arrays) into one dict per hour."""
    hourly = location_payload.get("hourly")
    if not hourly or "time" not in hourly:
        raise OpenMeteoError("Response has no hourly block")
    times = hourly["time"]
    columns = {name: values for name, values in hourly.items() if name != "time"}
    for name, values in columns.items():
        if len(values) != len(times):
            raise OpenMeteoError(f"Column {name} has {len(values)} values for {len(times)} hours")
    names = ("time", *columns)
    hours = zip(times, *columns.values(), strict=True)
    return [dict(zip(names, values, strict=True)) for values in hours]


def fetch_hourly(
    url: str, fetch: Callable[[str], dict | list] = fetch_json
) -> list[list[dict]]:
    """Fetch one URL and return the hourly rows of each requested location, in request order."""
    payload = fetch(url)
    locations = [hourly_to_rows(location) for location in split_locations(payload)]
    logger.info("Fetched %d locations", len(locations))
    return locations
