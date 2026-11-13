"""Reconcile the Legacy source with Gold: compare per-City-per-month aggregates and key coverage."""

import logging
import math
from datetime import datetime, timedelta

import quality
from legacy_mapping import LEGACY_MEASURE_COLUMNS

logger = logging.getLogger(__name__)

# Gold column -> legacy name, so both sides report the same aggregate column names.
GOLD_MEASURE_COLUMNS = {silver: legacy for legacy, silver in LEGACY_MEASURE_COLUMNS.items()}
SUM_REL_TOLERANCE = 1e-9


def month_key(moment: datetime) -> str:
    """Return the calendar month of a datetime as YYYY-MM."""
    return f"{moment.year:04d}-{moment.month:02d}"


def _stats(values: list[float | None]) -> dict:
    """Sum, min and max of the non-null values; all None when every value is null."""
    present = [value for value in values if value is not None]
    if not present:
        return {"sum": None, "min": None, "max": None}
    return {"sum": sum(present), "min": min(present), "max": max(present)}


def aggregate_by_city_month(
    rows: list[dict], city_column: str, time_column: str, measure_columns: dict[str, str]
) -> dict[tuple, dict]:
    """Aggregate rows by (city, month): row_count plus <name>_sum/_min/_max per measure.

    `measure_columns` maps a source column to the name used in the aggregate, so Legacy rows and
    Gold rows end up with the same keys. The month comes from `time_column`, which must hold a
    local time on both sides.
    """
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row[city_column], month_key(row[time_column])), []).append(row)
    result = {}
    for key, group in groups.items():
        aggregate = {"row_count": len(group)}
        for column, name in measure_columns.items():
            for stat, value in _stats([row[column] for row in group]).items():
                aggregate[f"{name}_{stat}"] = value
        result[key] = aggregate
    return result


def _same(column: str, expected, actual, rel_tol: float) -> bool:
    """Sums are compared with a tolerance (addition order); everything else exactly."""
    if expected is None or actual is None:
        return expected is None and actual is None
    if column.endswith("_sum"):
        return math.isclose(expected, actual, rel_tol=rel_tol)
    return expected == actual


def compare_aggregates(
    expected: dict[tuple, dict], actual: dict[tuple, dict], rel_tol: float = SUM_REL_TOLERANCE
) -> list[dict]:
    """List every difference between two aggregate sets; a group missing on one side counts as
    a row_count difference (0 rows on that side)."""
    mismatches = []
    for key in sorted(set(expected) | set(actual)):
        if key not in expected or key not in actual:
            mismatches.append(
                {
                    "key": key,
                    "column": "row_count",
                    "expected": expected.get(key, {}).get("row_count", 0),
                    "actual": actual.get(key, {}).get("row_count", 0),
                }
            )
            continue
        for column, value in expected[key].items():
            if not _same(column, value, actual[key].get(column), rel_tol):
                mismatches.append(
                    {"key": key, "column": column, "expected": value,
                     "actual": actual[key].get(column)}
                )
    return mismatches


def count_missing_hours(
    keys: set[tuple], city_ids: list[int], first_ts: datetime, last_ts: datetime
) -> int:
    """Count the (city_id, hour) pairs of the inclusive hourly range that are not in `keys`."""
    if last_ts < first_ts:
        raise ValueError("last_ts is before first_ts")
    hour_count = int((last_ts - first_ts) / timedelta(hours=1)) + 1
    hours = [first_ts + timedelta(hours=offset) for offset in range(hour_count)]
    return sum((city_id, hour) not in keys for city_id in city_ids for hour in hours)


def build_results(
    mismatches: list[dict], missing_hours: int, other_source_rows: int, run_time: datetime
) -> list[dict]:
    """Turn the reconciliation numbers into four rows for the data quality results table."""
    count_mismatches = sum(m["column"] == "row_count" for m in mismatches)
    stat_mismatches = len(mismatches) - count_mismatches

    def result(name: str, count: int) -> dict:
        status = quality.FAIL if count else quality.PASS
        return quality.make_result(f"legacy_{name}", status, count, run_time)

    return [
        result("row_counts", count_mismatches),
        result("measure_stats", stat_mismatches),
        result("missing_hours", missing_hours),
        result("other_source_rows", other_source_rows),
    ]
