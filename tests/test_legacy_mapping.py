from datetime import UTC, datetime

import pytest

import legacy_mapping
import transforms


def legacy_row(hour, **overrides):
    row = {
        "city_code": 1,
        "obs_time": datetime(2022, 10, 1, hour),
        "temp_c": 25.5,
        "humidity_pct": 80.0,
        "rain_mm": 0.5,
        "wind_kmh": 10.0,
        "pm25": 30.0,
    }
    return {**row, **overrides}


def test_local_to_utc_subtracts_seven_hours():
    assert legacy_mapping.local_to_utc(datetime(2022, 10, 1, 7)) == datetime(
        2022, 10, 1, 0, tzinfo=UTC
    )


def test_local_to_utc_crosses_midnight_backwards():
    assert legacy_mapping.local_to_utc(datetime(2022, 10, 1, 0)) == datetime(
        2022, 9, 30, 17, tzinfo=UTC
    )


def test_local_to_utc_rejects_aware_datetime():
    with pytest.raises(ValueError, match="naive"):
        legacy_mapping.local_to_utc(datetime(2022, 10, 1, 7, tzinfo=UTC))


def test_legacy_to_silver_rows_renames_columns_and_converts_time():
    rows = legacy_mapping.legacy_to_silver_rows([legacy_row(7)])
    assert rows == [
        {
            "city_id": 1,
            "ts": datetime(2022, 10, 1, 0, tzinfo=UTC),
            "temperature_2m": 25.5,
            "relative_humidity_2m": 80.0,
            "precipitation": 0.5,
            "wind_speed_10m": 10.0,
            "pm2_5": 30.0,
        }
    ]


def test_legacy_to_silver_rows_keeps_null_pm25():
    rows = legacy_mapping.legacy_to_silver_rows([legacy_row(7, pm25=None)])
    assert rows[0]["pm2_5"] is None


def test_legacy_to_silver_rows_sorts_by_city_and_time():
    rows = legacy_mapping.legacy_to_silver_rows(
        [legacy_row(9), legacy_row(8, city_code=2), legacy_row(7)]
    )
    assert [(row["city_id"], row["ts"].hour) for row in rows] == [(1, 0), (1, 2), (2, 1)]


def test_legacy_to_silver_rows_stops_on_duplicate_key():
    with pytest.raises(ValueError, match="Duplicate"):
        legacy_mapping.legacy_to_silver_rows([legacy_row(7), legacy_row(7)])


def test_legacy_to_silver_rows_names_a_missing_column():
    row = legacy_row(7)
    del row["wind_kmh"]
    with pytest.raises(ValueError, match="wind_kmh"):
        legacy_mapping.legacy_to_silver_rows([row])


def test_gold_local_time_matches_the_legacy_time():
    legacy = [legacy_row(7), legacy_row(23)]
    silver = legacy_mapping.legacy_to_silver_rows(legacy)
    gold = transforms.build_gold_rows(silver, source="legacy")
    assert [row["ts_local"] for row in gold] == [row["obs_time"] for row in legacy]
    assert {row["source"] for row in gold} == {"legacy"}


def test_silver_columns_match_the_silver_schema():
    import schemas

    rows = legacy_mapping.legacy_to_silver_rows([legacy_row(7)])
    assert list(rows[0]) == schemas.column_names(schemas.SILVER_DDL)
