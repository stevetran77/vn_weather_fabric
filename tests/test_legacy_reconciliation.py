from datetime import UTC, datetime

import pytest

import legacy_reconciliation as recon
import quality

RUN_TIME = datetime(2026, 11, 13, tzinfo=UTC)
LEGACY_MEASURES = {"temp_c": "temp_c", "pm25": "pm25"}


def legacy_row(city, day, hour, temp, pm25=None):
    return {
        "city_code": city,
        "obs_time": datetime(2022, 10, day, hour),
        "temp_c": temp,
        "pm25": pm25,
    }


def test_month_key_formats_year_and_month():
    assert recon.month_key(datetime(2022, 10, 31, 23)) == "2022-10"


def test_aggregate_counts_rows_and_stats_per_city_and_month():
    rows = [
        legacy_row(1, 1, 0, 20.0, 10.0),
        legacy_row(1, 1, 1, 30.0, None),
        legacy_row(2, 1, 0, 25.0, 5.0),
    ]
    result = recon.aggregate_by_city_month(rows, "city_code", "obs_time", LEGACY_MEASURES)
    assert result[(1, "2022-10")] == {
        "row_count": 2,
        "temp_c_sum": 50.0, "temp_c_min": 20.0, "temp_c_max": 30.0,
        "pm25_sum": 10.0, "pm25_min": 10.0, "pm25_max": 10.0,
    }
    assert result[(2, "2022-10")]["row_count"] == 1


def test_aggregate_gives_none_stats_when_every_value_is_null():
    rows = [legacy_row(1, 1, 0, 20.0, None)]
    result = recon.aggregate_by_city_month(rows, "city_code", "obs_time", LEGACY_MEASURES)
    assert result[(1, "2022-10")]["pm25_sum"] is None
    assert result[(1, "2022-10")]["pm25_min"] is None


def test_aggregate_renames_gold_columns_to_the_legacy_names():
    gold = [{"city_id": 1, "ts_local": datetime(2022, 10, 1, 7), "temperature_2m": 21.5}]
    result = recon.aggregate_by_city_month(
        gold, "city_id", "ts_local", {"temperature_2m": "temp_c"}
    )
    assert result[(1, "2022-10")]["temp_c_max"] == 21.5


def test_compare_aggregates_finds_no_mismatch_for_equal_input():
    stats = {(1, "2022-10"): {"row_count": 2, "temp_c_sum": 50.0, "temp_c_min": 20.0}}
    assert recon.compare_aggregates(stats, dict(stats)) == []


def test_compare_aggregates_reports_a_row_count_difference():
    expected = {(1, "2022-10"): {"row_count": 744}}
    actual = {(1, "2022-10"): {"row_count": 743}}
    assert recon.compare_aggregates(expected, actual) == [
        {"key": (1, "2022-10"), "column": "row_count", "expected": 744, "actual": 743}
    ]


def test_compare_aggregates_tolerates_float_noise_in_sums_only():
    expected = {(1, "2022-10"): {"temp_c_sum": 1000.0, "temp_c_max": 30.0}}
    noisy = {(1, "2022-10"): {"temp_c_sum": 1000.0 + 1e-8, "temp_c_max": 30.0}}
    assert recon.compare_aggregates(expected, noisy) == []
    off_max = {(1, "2022-10"): {"temp_c_sum": 1000.0, "temp_c_max": 30.0 + 1e-8}}
    assert [m["column"] for m in recon.compare_aggregates(expected, off_max)] == ["temp_c_max"]


def test_compare_aggregates_reports_a_sum_beyond_the_tolerance():
    expected = {(1, "2022-10"): {"temp_c_sum": 1000.0}}
    actual = {(1, "2022-10"): {"temp_c_sum": 1000.1}}
    assert len(recon.compare_aggregates(expected, actual)) == 1


def test_compare_aggregates_treats_none_and_value_as_a_mismatch():
    expected = {(1, "2022-10"): {"pm25_min": None}}
    actual = {(1, "2022-10"): {"pm25_min": 3.0}}
    assert len(recon.compare_aggregates(expected, actual)) == 1
    assert recon.compare_aggregates(expected, {(1, "2022-10"): {"pm25_min": None}}) == []


def test_compare_aggregates_reports_a_group_missing_on_one_side():
    key = (1, "2022-10")
    groups = {key: {"row_count": 5}}
    assert recon.compare_aggregates(groups, {}) == [
        {"key": key, "column": "row_count", "expected": 5, "actual": 0}
    ]
    assert recon.compare_aggregates({}, groups) == [
        {"key": key, "column": "row_count", "expected": 0, "actual": 5}
    ]


def hours(city, start_hour, count):
    return {
        (city, datetime(2022, 10, 1, start_hour + offset, tzinfo=UTC)) for offset in range(count)
    }


def test_count_missing_hours_is_zero_for_a_full_range():
    keys = hours(1, 0, 3) | hours(2, 0, 3)
    first, last = datetime(2022, 10, 1, 0, tzinfo=UTC), datetime(2022, 10, 1, 2, tzinfo=UTC)
    assert recon.count_missing_hours(keys, [1, 2], first, last) == 0


def test_count_missing_hours_counts_gaps_and_missing_cities():
    keys = hours(1, 0, 2)  # City 1 lacks hour 2; City 2 has nothing
    first, last = datetime(2022, 10, 1, 0, tzinfo=UTC), datetime(2022, 10, 1, 2, tzinfo=UTC)
    assert recon.count_missing_hours(keys, [1, 2], first, last) == 1 + 3


def test_count_missing_hours_rejects_a_reversed_range():
    first, last = datetime(2022, 10, 2, tzinfo=UTC), datetime(2022, 10, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="before"):
        recon.count_missing_hours(set(), [1], first, last)


def test_build_results_passes_when_everything_matches():
    results = recon.build_results([], 0, 0, RUN_TIME)
    assert {r["check_name"]: r["status"] for r in results} == {
        "legacy_row_counts": quality.PASS,
        "legacy_measure_stats": quality.PASS,
        "legacy_missing_hours": quality.PASS,
        "legacy_other_source_rows": quality.PASS,
    }


def test_build_results_splits_count_and_stat_mismatches():
    mismatches = [
        {"key": (1, "2022-10"), "column": "row_count", "expected": 2, "actual": 1},
        {"key": (1, "2022-10"), "column": "temp_c_sum", "expected": 1.0, "actual": 2.0},
        {"key": (2, "2022-10"), "column": "temp_c_max", "expected": 1.0, "actual": 2.0},
    ]
    by_name = {r["check_name"]: r for r in recon.build_results(mismatches, 5, 7, RUN_TIME)}
    assert (by_name["legacy_row_counts"]["status"], by_name["legacy_row_counts"]["count"]) == (
        quality.FAIL, 1,
    )
    assert by_name["legacy_measure_stats"]["count"] == 2
    assert by_name["legacy_missing_hours"]["count"] == 5
    assert by_name["legacy_other_source_rows"]["count"] == 7
    assert all(r["status"] == quality.FAIL for r in by_name.values())
    with pytest.raises(quality.DataQualityError, match="legacy_row_counts"):
        quality.raise_on_failure(list(by_name.values()))
