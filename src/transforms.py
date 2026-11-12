"""Plain-Python transforms from raw Open-Meteo rows to Bronze, Silver, and Gold rows."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import cache
from operator import itemgetter
from zoneinfo import ZoneInfo

from open_meteo import AIR_QUALITY_VARIABLES, WEATHER_VARIABLES

logger = logging.getLogger(__name__)

KEY_COLUMNS = ("city_id", "ts")
LOCAL_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def to_bronze_rows(
    city: dict, api_name: str, hourly_rows: list[dict], ingest_date: str
) -> list[dict]:
    """Keep the raw hourly values and add lineage columns (city, API name, ingest date).

    `city_id` is the Province code of the City.
    """
    lineage = {
        "city_id": city["province_code"],
        "city_name": city["name"],
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "api": api_name,
        "ingest_date": ingest_date,
    }
    return [{**lineage, **row} for row in hourly_rows]


@cache
def parse_utc(raw_time: str) -> datetime:
    """Parse an Open-Meteo time string (for example 2024-01-01T00:00, GMT) as a UTC datetime."""
    return datetime.fromisoformat(raw_time).replace(tzinfo=UTC)


def _index_by_key(bronze_rows: list[dict], value_columns: tuple[str, ...]) -> dict:
    """Index Bronze rows by (city_id, ts); on duplicate keys the last row wins."""
    indexed = {}
    for row in bronze_rows:
        ts = parse_utc(row["time"])
        indexed[(row["city_id"], ts)] = {
            "city_id": row["city_id"],
            "ts": ts,
            **{column: row[column] for column in value_columns},
        }
    return indexed


def build_silver_rows(
    weather_rows: list[dict],
    air_quality_rows: list[dict],
    weather_columns: tuple[str, ...] = WEATHER_VARIABLES,
    air_quality_columns: tuple[str, ...] = AIR_QUALITY_VARIABLES,
) -> list[dict]:
    """Combine weather and Model PM2.5 Bronze rows into one Silver row per (city_id, ts).

    Weather decides which hours exist. A missing PM2.5 hour stays as None (a warning, not an
    error, per the data quality rules). Duplicate keys inside one input are collapsed.
    """
    weather = _index_by_key(weather_rows, weather_columns)
    air_quality = _index_by_key(air_quality_rows, air_quality_columns)
    missing_air_quality = 0
    for key, row in weather.items():
        air_row = air_quality.get(key)
        if air_row is None:
            missing_air_quality += 1
        for column in air_quality_columns:
            row[column] = air_row[column] if air_row else None
    if missing_air_quality:
        logger.warning("%d of %d hours have no PM2.5 value", missing_air_quality, len(weather))
    return sorted(weather.values(), key=itemgetter(*KEY_COLUMNS))


def build_gold_rows(
    silver_rows: list[dict], source: str | Callable[[datetime], str]
) -> list[dict]:
    """Shape Silver rows into the hourly fact: add the local-time column and the source tag.

    `source` is a label for every row, or a function of the row's `ts` that returns the label.
    It has no default so a caller cannot mislabel rows.
    """
    label = source if callable(source) else (lambda _ts: source)
    return [
        {
            **row,
            "ts_local": row["ts"].astimezone(LOCAL_ZONE).replace(tzinfo=None),
            "source": label(row["ts"]),
        }
        for row in silver_rows
    ]


def build_merge_condition(key_columns: tuple[str, ...] = KEY_COLUMNS) -> str:
    """Build the Delta MERGE match condition, `t.city_id = s.city_id AND t.ts = s.ts` by default.

    `t` is the target table alias and `s` the source alias.
    """
    return " AND ".join(f"t.{column} = s.{column}" for column in key_columns)
