from datetime import UTC, datetime

import pytest

import cutover
import quality

CUTOVER = datetime(2024, 1, 1, tzinfo=UTC)
LAST_BEFORE = datetime(2023, 12, 31, 23, tzinfo=UTC)
RUN_TIME = datetime(2026, 11, 13, tzinfo=UTC)


def test_parse_cutover_returns_midnight_utc():
    assert cutover.parse_cutover({"cutover_date": "2024-01-01"}) == CUTOVER


@pytest.mark.parametrize("config", [{}, {"cutover_date": "not a date"}, {"cutover_date": None}])
def test_parse_cutover_rejects_a_missing_or_invalid_date(config):
    with pytest.raises(cutover.CutoverError, match="Invalid cutover config"):
        cutover.parse_cutover(config)


def test_check_migration_range_accepts_an_end_on_the_cutover_date():
    cutover.check_migration_range("2024-01-01", CUTOVER)


def test_check_migration_range_refuses_an_end_after_the_cutover_date():
    with pytest.raises(cutover.CutoverError, match="after the Cutover date"):
        cutover.check_migration_range("2024-01-02", CUTOVER)


def test_check_backfill_range_accepts_a_start_on_the_cutover_date():
    cutover.check_backfill_range("2024-01-01", CUTOVER)


def test_check_backfill_range_refuses_a_start_before_the_cutover_date():
    with pytest.raises(cutover.CutoverError, match="before the Cutover date"):
        cutover.check_backfill_range("2023-12-31", CUTOVER)


def test_check_rows_before_refuses_a_row_at_the_cutover_date():
    cutover.check_rows_before([{"ts": LAST_BEFORE}], CUTOVER)
    with pytest.raises(cutover.CutoverError, match="1 Migration rows"):
        cutover.check_rows_before([{"ts": LAST_BEFORE}, {"ts": CUTOVER}], CUTOVER)


def test_check_rows_from_refuses_a_row_before_the_cutover_date():
    cutover.check_rows_from([{"ts": CUTOVER}], CUTOVER)
    with pytest.raises(cutover.CutoverError, match="1 Backfill rows"):
        cutover.check_rows_from([{"ts": CUTOVER}, {"ts": LAST_BEFORE}], CUTOVER)


def test_boundary_hours_are_the_last_hour_before_and_the_first_from_the_cutover_date():
    assert cutover.boundary_hours(CUTOVER) == (LAST_BEFORE, CUTOVER)


def boundary(city, before_source, after_source):
    rows = []
    if before_source:
        rows.append({"city_id": city, "ts": LAST_BEFORE, "source": before_source})
    if after_source:
        rows.append({"city_id": city, "ts": CUTOVER, "source": after_source})
    return rows


def by_name(results):
    return {r["check_name"]: r for r in results}


def test_check_continuity_passes_for_legacy_then_archive():
    rows = boundary(1, "legacy", "archive") + boundary(2, "legacy", "archive")
    results = by_name(cutover.check_continuity(rows, [1, 2], CUTOVER, RUN_TIME))
    assert {name: r["status"] for name, r in results.items()} == {
        "cutover_boundary_missing": quality.PASS,
        "cutover_source_mismatch": quality.PASS,
    }


def test_check_continuity_counts_missing_boundary_hours():
    rows = boundary(1, "legacy", None)  # City 1 lacks the first hour, City 2 has nothing
    results = by_name(cutover.check_continuity(rows, [1, 2], CUTOVER, RUN_TIME))
    assert results["cutover_boundary_missing"]["count"] == 3
    assert results["cutover_boundary_missing"]["status"] == quality.FAIL


def test_check_continuity_counts_a_wrong_source_on_either_side():
    rows = boundary(1, "archive", "archive") + boundary(2, "legacy", "legacy")
    results = by_name(cutover.check_continuity(rows, [1, 2], CUTOVER, RUN_TIME))
    assert results["cutover_source_mismatch"]["count"] == 2
    assert results["cutover_source_mismatch"]["status"] == quality.FAIL
    assert results["cutover_boundary_missing"]["status"] == quality.PASS
