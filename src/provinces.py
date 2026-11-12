"""Map each configured City to its Province using provinces.open-api.vn (v2, 34 provinces)."""

import logging
from collections.abc import Callable

from http_json import HttpJsonError, get_json

logger = logging.getLogger(__name__)

PROVINCES_URL = "https://provinces.open-api.vn/api/v2/p/"


class ProvinceError(Exception):
    """Raised when the Province list cannot be fetched or does not cover every City."""


def fetch_provinces(fetch: Callable[[str], dict | list] = get_json) -> list[dict]:
    """Fetch the Province list (one request); each item has at least `code` and `name`."""
    try:
        provinces = fetch(PROVINCES_URL)
    except HttpJsonError as error:
        raise ProvinceError(f"Could not fetch provinces: {error}") from error
    if not isinstance(provinces, list) or not provinces:
        raise ProvinceError("Province response is not a non-empty list")
    logger.info("Fetched %d provinces", len(provinces))
    return provinces


def build_dim_city(resolved_cities: list[dict], provinces: list[dict]) -> list[dict]:
    """Build dim_city rows: one per City, with its Province name from the Province code.

    `city_id` is the Province code. The City name and Province name may differ (for example
    Nha Trang and Khanh Hoa). `division_type` is not copied because the API data is unverified.
    """
    names_by_code = {province["code"]: province["name"] for province in provinces}
    codes = {city["province_code"] for city in resolved_cities}
    missing = sorted(codes - names_by_code.keys())
    if missing:
        raise ProvinceError(f"Province codes not found in the API response: {missing}")
    return [
        {
            "city_id": city["province_code"],
            "city_name": city["name"],
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "province_code": city["province_code"],
            "province_name": names_by_code[city["province_code"]],
        }
        for city in resolved_cities
    ]
