"""Cutover date guards: the Migration writes before it, the Backfill from it, with no gap."""

import logging
from datetime import UTC, date, datetime, timedelta

import quality

logger = logging.getLogger(__name__)

CONFIG_KEY = "cutover_date"
CHECK_MISSING = "cutover_boundary_missing"
CHECK_SOURCE = "cutover_source_mismatch"
LEGACY_SOURCE = "legacy"


class CutoverError(Exception):
    """Raised when a load would write outside its side of the Cutover date."""


def parse_cutover(config: dict) -> datetime:
    """Return the Cutover date of the parsed config file as midnight UTC."""
    try:
        day = date.fromisoformat(config[CONFIG_KEY])
    except (KeyError, TypeError, ValueError) as error:
        raise CutoverError(f"Invalid cutover config: {error!r}") from error
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _refuse(message: str) -> None:
    logger.error(message)
    raise CutoverError(message)


def check_migration_range(end_date: str, cutover: datetime) -> None:
    """Stop when an exclusive end date lies after the Cutover date."""
    if date.fromisoformat(end_date) > cutover.date():
        _refuse(f"Migration end_date {end_date} is after the Cutover date {cutover.date()}")


def check_backfill_range(start_date: str, cutover: datetime) -> None:
    """Stop when an inclusive start date lies before the Cutover date."""
    if date.fromisoformat(start_date) < cutover.date():
        _refuse(f"Backfill start_date {start_date} is before the Cutover date {cutover.date()}")


def check_rows_before(rows: list[dict], cutover: datetime) -> None:
    """Stop when any row (with a UTC `ts`) is on or after the Cutover date."""
    late = sum(row["ts"] >= cutover for row in rows)
    if late:
        _refuse(f"{late} Migration rows have ts on or after the Cutover date {cutover.date()}")


def check_rows_from(rows: list[dict], cutover: datetime) -> None:
    """Stop when any row (with a UTC `ts`) is before the Cutover date."""
    early = sum(row["ts"] < cutover for row in rows)
    if early:
        _refuse(f"{early} Backfill rows have ts before the Cutover date {cutover.date()}")


def boundary_hours(cutover: datetime) -> tuple[datetime, datetime]:
    """Return the last hour before the Cutover date and the first hour from it."""
    return cutover - timedelta(hours=1), cutover


def check_continuity(
    boundary_rows: list[dict], city_ids: list[int], cutover: datetime, run_time: datetime
) -> list[dict]:
    """Check both boundary hours exist per City, legacy before the Cutover date and not after.

    `boundary_rows` holds city_id, ts (UTC) and source of the two boundary hours.
    """
    last_before, first_after = boundary_hours(cutover)
    source_of = {(row["city_id"], row["ts"]): row["source"] for row in boundary_rows}
    missing = wrong = 0
    for city_id in city_ids:
        for hour, is_legacy in ((last_before, True), (first_after, False)):
            source = source_of.get((city_id, hour))
            if source is None:
                missing += 1
            elif (source == LEGACY_SOURCE) != is_legacy:
                wrong += 1
    def result(name: str, count: int) -> dict:
        return quality.make_result(name, quality.FAIL if count else quality.PASS, count, run_time)

    return [result(CHECK_MISSING, missing), result(CHECK_SOURCE, wrong)]
