"""Fetch yearly World Bank indicators for one country; shape them into Silver and Gold rows."""

import logging
from collections.abc import Callable

from http_json import HttpJsonError, get_json

logger = logging.getLogger(__name__)

API_ROOT = "https://api.worldbank.org/v2"
PER_PAGE = 100
MAX_PAGES = 20  # Vietnam has ~66 yearly rows per indicator; a higher page count is an API fault
KEY_COLUMNS = ("country_code", "indicator_code", "year")  # merge key of Silver and Gold


class WorldBankError(Exception):
    """Raised when the World Bank API fails, returns an error body, or returns incomplete data."""


def parse_indicator_config(config: dict) -> tuple[str, dict[str, str]]:
    """Return (country code, {indicator code: indicator name}) from the parsed config file."""
    try:
        country = config["country"]
        names_by_code = {item["code"]: item["name"] for item in config["indicators"]}
    except (KeyError, TypeError) as error:
        raise WorldBankError(f"Invalid indicator config: {error!r}") from error
    if not names_by_code:
        raise WorldBankError("Indicator config lists no indicators")
    return country, names_by_code


def build_indicator_url(country: str, indicator: str, page: int, per_page: int = PER_PAGE) -> str:
    """Build the URL of one page of an indicator's yearly values for a country."""
    return (
        f"{API_ROOT}/country/{country}/indicator/{indicator}"
        f"?format=json&per_page={per_page}&page={page}"
    )


def _parse_page(body: dict | list, indicator: str) -> tuple[dict, list[dict]]:
    """Return (paging info, rows) from one response; raise on the API's error shape."""
    if isinstance(body, list) and len(body) == 1 and "message" in body[0]:
        raise WorldBankError(f"API error for {indicator}: {body[0]['message']}")
    if not (isinstance(body, list) and len(body) == 2 and isinstance(body[0], dict)):
        raise WorldBankError(f"Unexpected response shape for {indicator}")
    meta, rows = body
    if not isinstance(meta.get("pages"), int) or not isinstance(meta.get("total"), int):
        raise WorldBankError(f"Response for {indicator} has no paging info")
    return meta, rows or []


def fetch_indicator(
    country: str,
    indicator: str,
    fetch: Callable[[str], dict | list] = get_json,
    per_page: int = PER_PAGE,
) -> list[dict]:
    """Fetch every page of one indicator and return the raw rows.

    Raises WorldBankError when a request fails or the rows fetched differ from the reported total.
    """
    rows, page = [], 1
    while True:
        try:
            body = fetch(build_indicator_url(country, indicator, page, per_page))
        except HttpJsonError as error:
            raise WorldBankError(f"Could not fetch {indicator} page {page}: {error}") from error
        meta, page_rows = _parse_page(body, indicator)
        rows += page_rows
        if page >= meta["pages"]:
            break
        page += 1
        if page > MAX_PAGES:
            raise WorldBankError(f"{indicator}: more than {MAX_PAGES} pages, stopping")
    if len(rows) != meta["total"]:
        raise WorldBankError(f"{indicator}: fetched {len(rows)} rows, API reports {meta['total']}")
    logger.info("Fetched %d rows of %s in %d page(s)", len(rows), indicator, page)
    return rows


def to_bronze_rows(raw_rows: list[dict], ingest_date: str) -> list[dict]:
    """Keep the raw values (the year stays a string) and add the ingest date."""
    try:
        return [
            {
                "country_code": row["countryiso3code"],
                "indicator_code": row["indicator"]["id"],
                "indicator_name": row["indicator"]["value"],
                "date": row["date"],
                "value": None if row["value"] is None else float(row["value"]),
                "ingest_date": ingest_date,
            }
            for row in raw_rows
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise WorldBankError(f"Malformed indicator row: {error!r}") from error


def build_silver_rows(bronze_rows: list[dict]) -> list[dict]:
    """One row per (country_code, indicator_code, year); years without a value are dropped.

    On duplicate keys the last row wins.
    """
    indexed = {}
    for row in bronze_rows:
        if row["value"] is None:
            continue
        try:
            year = int(row["date"])
        except ValueError as error:
            raise WorldBankError(f"Date is not a year: {row['date']!r}") from error
        key = (row["country_code"], row["indicator_code"], year)
        indexed[key] = {
            "country_code": key[0],
            "indicator_code": key[1],
            "year": key[2],
            "value": row["value"],
        }
    logger.info("Silver: %d rows from %d Bronze rows", len(indexed), len(bronze_rows))
    return [indexed[key] for key in sorted(indexed)]


def build_gold_rows(silver_rows: list[dict], names_by_code: dict[str, str]) -> list[dict]:
    """Add the configured indicator name; raise if a row has an indicator not in the config."""
    unknown = {row["indicator_code"] for row in silver_rows} - names_by_code.keys()
    if unknown:
        raise WorldBankError(f"Indicators not in the config: {sorted(unknown)}")
    return [{**row, "indicator_name": names_by_code[row["indicator_code"]]} for row in silver_rows]
