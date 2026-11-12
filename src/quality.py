"""Data quality checks on row lists; each check returns one result row for the results table."""

import logging
from datetime import datetime
from operator import itemgetter

from schemas import column_types
from transforms import KEY_COLUMNS

logger = logging.getLogger(__name__)

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

# Python types accepted per DDL type. None is always accepted: nulls are judged by their own check.
PYTHON_TYPES = {
    "long": (int,),
    "double": (float, int),
    "timestamp": (datetime,),
    "string": (str,),
}


class DataQualityError(Exception):
    """Raised when at least one check has status FAIL."""


def make_result(check_name: str, status: str, count: int, run_time: datetime) -> dict:
    """Build one row of the results table and log it (warnings and failures only)."""
    if status == WARN:
        logger.warning("Data quality %s: %d rows", check_name, count)
    elif status == FAIL:
        logger.error("Data quality %s: %d rows", check_name, count)
    return {"run_time": run_time, "check_name": check_name, "status": status, "count": count}


def _violates_schema(row: dict, types: dict[str, str]) -> bool:
    if set(row) != set(types):
        return True
    return any(
        value is not None and not isinstance(value, PYTHON_TYPES[types[column]])
        for column, value in row.items()
    )


def check_schema(name: str, rows: list[dict], ddl: str, run_time: datetime) -> dict:
    """FAIL when any row has missing or extra columns, or a value of the wrong type."""
    types = column_types(ddl)
    bad_rows = sum(_violates_schema(row, types) for row in rows)
    return make_result(f"{name}_schema", FAIL if bad_rows else PASS, bad_rows, run_time)


def check_duplicate_count(name: str, duplicates: int, run_time: datetime) -> dict:
    """FAIL when `duplicates` (rows beyond one per (city_id, ts) key) is above zero."""
    return make_result(f"{name}_duplicate_keys", FAIL if duplicates else PASS, duplicates, run_time)


def check_duplicate_keys(name: str, rows: list[dict], run_time: datetime) -> dict:
    """FAIL when the rows hold the same (city_id, ts) key more than once."""
    keys = {itemgetter(*KEY_COLUMNS)(row) for row in rows}
    return check_duplicate_count(name, len(rows) - len(keys), run_time)


def check_null_pm25(name: str, rows: list[dict], run_time: datetime) -> dict:
    """WARN (never FAIL) when Model PM2.5 is null: gaps are expected in the model data."""
    nulls = sum(row.get("pm2_5") is None for row in rows)
    return make_result(f"{name}_null_pm2_5", WARN if nulls else PASS, nulls, run_time)


def run_row_checks(name: str, rows: list[dict], ddl: str, run_time: datetime) -> list[dict]:
    """Run the schema, duplicate-key and null-PM2.5 checks on one dataset."""
    return [
        check_schema(name, rows, ddl, run_time),
        check_duplicate_keys(name, rows, run_time),
        check_null_pm25(name, rows, run_time),
    ]


def raise_on_failure(results: list[dict]) -> None:
    """Raise DataQualityError naming every failed check; do nothing when none failed."""
    failed = [f"{result['check_name']} ({result['count']})" for result in results
              if result["status"] == FAIL]
    if failed:
        raise DataQualityError(f"Data quality checks failed: {', '.join(failed)}")
