from datetime import date

import pytest

import backfill

CITIES = [{"name": f"City{index}"} for index in range(5)]


def test_date_chunks_splits_range_into_consecutive_chunks():
    assert backfill.date_chunks("2024-01-01", "2024-01-10", 4) == [
        ("2024-01-01", "2024-01-04"),
        ("2024-01-05", "2024-01-08"),
        ("2024-01-09", "2024-01-10"),
    ]


def test_date_chunks_single_day():
    assert backfill.date_chunks("2024-01-01", "2024-01-01", 30) == [("2024-01-01", "2024-01-01")]


def test_date_chunks_crosses_leap_day():
    chunks = backfill.date_chunks("2024-02-28", "2024-03-01", 2)
    assert chunks == [("2024-02-28", "2024-02-29"), ("2024-03-01", "2024-03-01")]


def test_date_chunks_rejects_bad_input():
    with pytest.raises(ValueError):
        backfill.date_chunks("2024-01-10", "2024-01-01", 5)
    with pytest.raises(ValueError):
        backfill.date_chunks("2024-01-01", "2024-01-10", 0)


def test_plan_requests_covers_every_city_and_day_once():
    plan = backfill.plan_requests(CITIES, "2024-01-01", "2024-01-10", 5, 2)
    assert len(plan) == 3 * 2  # 3 city batches x 2 date chunks
    covered = [
        (city["name"], request["start_date"])
        for request in plan
        for city in request["cities"]
    ]
    assert len(covered) == len(set(covered)) == 5 * 2


def test_plan_requests_keeps_batches_within_limit():
    plan = backfill.plan_requests(CITIES, "2024-01-01", "2024-01-05", 5, 2)
    assert [len(request["cities"]) for request in plan] == [2, 2, 1]


def test_plan_requests_rejects_bad_batch_size():
    with pytest.raises(ValueError):
        backfill.plan_requests(CITIES, "2024-01-01", "2024-01-05", 5, 0)


def test_estimate_cost_matches_measured_headers():
    assert backfill.estimate_cost(1, 4, 7) == 1.0
    assert backfill.estimate_cost(3, 1, 7) == 3.0
    assert backfill.estimate_cost(1, 1, 365) == pytest.approx(2.607, abs=0.001)
    assert backfill.estimate_cost(1, 4, 365) == pytest.approx(10.429, abs=0.001)
    assert backfill.estimate_cost(1, 4, 1522) == pytest.approx(43.486, abs=0.001)


def test_estimate_plan_cost_sums_requests():
    plan = backfill.plan_requests(CITIES, "2022-09-01", "2026-10-31", 1522, 1)
    assert backfill.estimate_plan_cost(plan, 4) == pytest.approx(5 * 43.486, abs=0.01)


def test_build_dim_date_has_one_row_per_day_with_local_attributes():
    rows = backfill.build_dim_date("2024-02-28", "2024-03-03")
    assert [row["date"] for row in rows][:3] == [
        date(2024, 2, 28), date(2024, 2, 29), date(2024, 3, 1),
    ]
    assert len(rows) == 5
    leap_day = rows[1]
    assert leap_day["date_key"] == 20240229
    assert leap_day["quarter"] == 1
    assert leap_day["month_name"] == "February"
    assert leap_day["day_name"] == "Thursday"
    assert leap_day["day_of_week"] == 4
    assert leap_day["is_weekend"] is False


def test_build_dim_date_marks_weekends():
    rows = backfill.build_dim_date("2024-03-02", "2024-03-04")
    assert [row["is_weekend"] for row in rows] == [True, True, False]


def test_build_dim_date_rejects_reversed_range():
    with pytest.raises(ValueError):
        backfill.build_dim_date("2024-03-04", "2024-03-02")


def test_season_of_splits_dry_and_wet_months():
    assert backfill.season_of(11) == backfill.DRY_SEASON
    assert backfill.season_of(4) == backfill.DRY_SEASON
    assert backfill.season_of(5) == backfill.WET_SEASON
    assert backfill.season_of(10) == backfill.WET_SEASON


def test_season_labels_follow_the_month_split():
    assert backfill.WET_SEASON == "Wet (May-Oct)"
    assert backfill.DRY_SEASON == "Dry (Nov-Apr)"


def test_build_dim_date_sets_season():
    rows = backfill.build_dim_date("2024-04-30", "2024-05-01")
    assert [row["season"] for row in rows] == [backfill.DRY_SEASON, backfill.WET_SEASON]
