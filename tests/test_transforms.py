from datetime import UTC, datetime

import transforms

CITY = {"province_code": 1, "name": "Hanoi", "latitude": 21.0245, "longitude": 105.84117}
WEATHER_COLUMNS = ("temperature_2m", "precipitation")
AIR_COLUMNS = ("pm2_5",)
WEATHER_RAW = [
    {"time": "2024-01-01T00:00", "temperature_2m": 17.5, "precipitation": 0.0},
    {"time": "2024-01-01T01:00", "temperature_2m": 17.1, "precipitation": 0.2},
]
AIR_RAW = [{"time": "2024-01-01T00:00", "pm2_5": 35.0}]


def bronze(raw_rows, api):
    return transforms.to_bronze_rows(CITY, api, raw_rows, "2024-02-01")


def silver():
    return transforms.build_silver_rows(
        bronze(WEATHER_RAW, "archive"), bronze(AIR_RAW, "air_quality"),
        WEATHER_COLUMNS, AIR_COLUMNS,
    )


def test_to_bronze_rows_adds_lineage_columns():
    rows = bronze(WEATHER_RAW, "archive")
    assert len(rows) == 2
    assert rows[0]["city_id"] == 1
    assert rows[0]["city_name"] == "Hanoi"
    assert rows[0]["api"] == "archive"
    assert rows[0]["ingest_date"] == "2024-02-01"
    assert rows[0]["time"] == "2024-01-01T00:00"
    assert rows[0]["temperature_2m"] == 17.5


def test_parse_utc_returns_aware_utc_datetime():
    assert transforms.parse_utc("2024-01-01T05:00") == datetime(2024, 1, 1, 5, tzinfo=UTC)


def test_build_silver_rows_joins_weather_and_pm25():
    rows = silver()
    assert rows[0] == {
        "city_id": 1, "ts": datetime(2024, 1, 1, 0, tzinfo=UTC),
        "temperature_2m": 17.5, "precipitation": 0.0, "pm2_5": 35.0,
    }


def test_build_silver_rows_keeps_hour_without_pm25():
    rows = silver()
    assert len(rows) == 2
    assert rows[1]["pm2_5"] is None


def test_build_silver_rows_collapses_duplicate_keys():
    duplicated = bronze(WEATHER_RAW, "archive") + bronze(WEATHER_RAW, "archive")
    rows = transforms.build_silver_rows(duplicated, [], WEATHER_COLUMNS, AIR_COLUMNS)
    assert len(rows) == 2


def test_build_silver_rows_is_sorted_by_key():
    reversed_weather = bronze(list(reversed(WEATHER_RAW)), "archive")
    rows = transforms.build_silver_rows(reversed_weather, [], WEATHER_COLUMNS, AIR_COLUMNS)
    assert [row["ts"].hour for row in rows] == [0, 1]


def test_build_gold_rows_adds_local_time_and_source():
    rows = transforms.build_gold_rows(silver(), source="archive")
    assert rows[0]["ts_local"] == datetime(2024, 1, 1, 7)
    assert rows[0]["ts_local"].tzinfo is None
    assert rows[0]["ts"] == datetime(2024, 1, 1, 0, tzinfo=UTC)
    assert rows[0]["source"] == "archive"


def test_build_merge_condition_matches_on_key():
    assert transforms.build_merge_condition() == "t.city_id = s.city_id AND t.ts = s.ts"
