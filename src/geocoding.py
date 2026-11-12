"""Resolve the configured Vietnamese cities to coordinates with the Open-Meteo Geocoding API."""

import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
COUNTRY_CODE = "VN"
RESULT_COUNT = 10
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "cities.json"


class GeocodingError(Exception):
    """Raised when a city cannot be resolved to a trustworthy place."""


def load_cities(config_path: Path = DEFAULT_CONFIG_PATH) -> list[dict]:
    """Read the city list (province_code, name, search_name per city) from the JSON config."""
    with open(config_path, encoding="utf-8") as config_file:
        cities = json.load(config_file)["cities"]
    logger.info("Loaded %d cities from %s", len(cities), config_path)
    return cities


def build_search_url(search_name: str) -> str:
    """Build the geocoding request URL, restricted to Vietnam."""
    query = {
        "name": search_name,
        "count": RESULT_COUNT,
        "language": "en",
        "countryCode": COUNTRY_CODE,
        "format": "json",
    }
    return f"{GEOCODING_URL}?{urlencode(query)}"


def fetch_results(search_name: str) -> list[dict]:
    """Call the geocoding API and return its raw result list (empty when nothing matches)."""
    url = build_search_url(search_name)
    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 (fixed https URL)
        payload = json.load(response)
    return payload.get("results", [])


def pick_city(results: list[dict]) -> dict | None:
    """Pick the biggest populated place in Vietnam; return None when nothing qualifies.

    Villages and airports are skipped: only populated places (feature code starting with
    PPL) that report a population are candidates, and the highest population wins.
    """
    candidates = [
        result
        for result in results
        if result.get("country_code") == COUNTRY_CODE
        and str(result.get("feature_code", "")).startswith("PPL")
        and result.get("population")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda result: result["population"])


def resolve_city(city: dict, fetch: Callable[[str], list[dict]] = fetch_results) -> dict:
    """Resolve one configured city to its coordinates, raising GeocodingError on failure."""
    name = city["name"]
    try:
        results = fetch(city["search_name"])
    except OSError as error:
        logger.error("Lookup failed for %s: %s", name, error)
        raise GeocodingError(f"Lookup failed for {name}: {error}") from error
    picked = pick_city(results)
    if picked is None:
        logger.error("No major populated place found for %s (%d results)", name, len(results))
        raise GeocodingError(f"No major populated place found for {name}")
    logger.info("Resolved %s -> %s (%s)", name, picked["name"], picked["feature_code"])
    return {
        "province_code": city["province_code"],
        "name": name,
        "latitude": picked["latitude"],
        "longitude": picked["longitude"],
        "population": picked["population"],
        "feature_code": picked["feature_code"],
    }


def resolve_all(
    cities: list[dict], fetch: Callable[[str], list[dict]] = fetch_results
) -> list[dict]:
    """Resolve every configured city; the first failure stops the run."""
    return [resolve_city(city, fetch) for city in cities]


def format_table(resolved: list[dict]) -> str:
    """Format resolved cities as an aligned text table."""
    header = f"{'prov':>4}  {'city':<18}{'latitude':>10}{'longitude':>11}{'population':>12}"
    lines = [f"{header}  feature"]
    for city in resolved:
        lines.append(
            f"{city['province_code']:>4}  {city['name']:<18}"
            f"{city['latitude']:>10.4f}{city['longitude']:>11.4f}"
            f"{city['population']:>12}  {city['feature_code']}"
        )
    return "\n".join(lines)


def main() -> int:
    """Print the configured cities with their coordinates (manual check)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        resolved = resolve_all(load_cities())
    except GeocodingError as error:
        print(f"[FAIL] {error}")
        return 1
    print(format_table(resolved))
    print(f"[OK] resolved {len(resolved)} cities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
