"""Map rows of the Legacy source (SQL Server) to Silver rows."""

import logging
from datetime import UTC, datetime
from operator import itemgetter

from transforms import KEY_COLUMNS, LOCAL_ZONE

logger = logging.getLogger(__name__)

# Legacy column name -> Silver column name (the measures only; city and time are handled apart).
LEGACY_MEASURE_COLUMNS = {
    "temp_c": "temperature_2m",
    "humidity_pct": "relative_humidity_2m",
    "rain_mm": "precipitation",
    "wind_kmh": "wind_speed_10m",
    "pm25": "pm2_5",
}


def local_to_utc(obs_time: datetime) -> datetime:
    """Convert a naive local time (Asia/Ho_Chi_Minh, UTC+7, no daylight saving) to aware UTC."""
    if obs_time.tzinfo is not None:
        raise ValueError("obs_time must be a naive local datetime")
    return obs_time.replace(tzinfo=LOCAL_ZONE).astimezone(UTC)


def _to_silver_row(row: dict) -> dict:
    """Rename one Legacy row to the Silver shape; a missing legacy column raises ValueError."""
    needed = ("city_code", "obs_time", *LEGACY_MEASURE_COLUMNS)
    missing = [column for column in needed if column not in row]
    if missing:
        raise ValueError(f"Legacy row is missing columns: {missing}")
    return {
        "city_id": row["city_code"],
        "ts": local_to_utc(row["obs_time"]),
        **{silver: row[legacy] for legacy, silver in LEGACY_MEASURE_COLUMNS.items()},
    }


def legacy_to_silver_rows(legacy_rows: list[dict]) -> list[dict]:
    """Turn Legacy rows into Silver rows, sorted by (city_id, ts).

    A duplicate (city_id, ts) stops the load with ValueError, as the data quality rules require.
    """
    key_of = itemgetter(*KEY_COLUMNS)
    silver_rows = sorted((_to_silver_row(row) for row in legacy_rows), key=key_of)
    keys = {key_of(row) for row in silver_rows}
    if len(keys) != len(silver_rows):
        raise ValueError("Duplicate (city_id, ts) keys in the Legacy rows")
    logger.info("Mapped %d Legacy rows to Silver rows", len(silver_rows))
    return silver_rows
