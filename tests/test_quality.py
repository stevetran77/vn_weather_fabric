from datetime import UTC, datetime

import pytest

import quality
import schemas

RUN_TIME = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


def gold_row(city_id=1, hour=0, pm2_5=35.0, **overrides):
    row = {
        "city_id": city_id,
        "ts": datetime(2026, 11, 12, hour, tzinfo=UTC),
        **{name: 1.0 for name in schemas.column_names(schemas.GOLD_DDL)[2:-2]},
        "ts_local": datetime(2026, 11, 12, hour + 7),
        "source": "archive",
    }
    row["pm2_5"] = pm2_5
    return {**row, **overrides}


def test_gold_row_helper_matches_the_gold_schema():
    assert set(gold_row()) == set(schemas.column_names(schemas.GOLD_DDL))


def test_check_schema_passes_for_valid_rows():
    rows = [gold_row(), gold_row(hour=1)]
    result = quality.check_schema("gold", rows, schemas.GOLD_DDL, RUN_TIME)
    assert (result["check_name"], result["status"], result["count"]) == ("gold_schema", "PASS", 0)
    assert result["run_time"] == RUN_TIME


def test_check_schema_fails_on_a_missing_column():
    row = gold_row()
    del row["source"]
    result = quality.check_schema("gold", [row], schemas.GOLD_DDL, RUN_TIME)
    assert (result["status"], result["count"]) == ("FAIL", 1)


def test_check_schema_fails_on_an_extra_column():
    result = quality.check_schema("gold", [gold_row(extra=1)], schemas.GOLD_DDL, RUN_TIME)
    assert result["status"] == "FAIL"


def test_check_schema_fails_on_a_wrong_type():
    rows = [gold_row(temperature_2m="hot"), gold_row(hour=1)]
    result = quality.check_schema("gold", rows, schemas.GOLD_DDL, RUN_TIME)
    assert (result["status"], result["count"]) == ("FAIL", 1)


def test_check_schema_accepts_nulls():
    result = quality.check_schema("gold", [gold_row(pm2_5=None)], schemas.GOLD_DDL, RUN_TIME)
    assert result["status"] == "PASS"


def test_check_duplicate_keys_passes_for_unique_keys():
    result = quality.check_duplicate_keys("gold", [gold_row(hour=0), gold_row(hour=1)], RUN_TIME)
    assert (result["check_name"], result["status"], result["count"]) == (
        "gold_duplicate_keys", "PASS", 0,
    )


def test_check_duplicate_keys_fails_and_counts_extra_rows():
    rows = [gold_row(), gold_row(), gold_row(), gold_row(city_id=2)]
    result = quality.check_duplicate_keys("gold", rows, RUN_TIME)
    assert (result["status"], result["count"]) == ("FAIL", 2)


def test_check_duplicate_count_uses_the_given_number():
    assert quality.check_duplicate_count("gold_table", 0, RUN_TIME)["status"] == "PASS"
    assert quality.check_duplicate_count("gold_table", 5, RUN_TIME)["status"] == "FAIL"


def test_check_null_pm25_warns_and_never_fails():
    rows = [gold_row(pm2_5=None), gold_row(hour=1, pm2_5=None), gold_row(hour=2)]
    result = quality.check_null_pm25("gold", rows, RUN_TIME)
    assert (result["check_name"], result["status"], result["count"]) == (
        "gold_null_pm2_5", "WARN", 2,
    )


def test_check_null_pm25_passes_without_nulls():
    assert quality.check_null_pm25("gold", [gold_row()], RUN_TIME)["status"] == "PASS"


def test_run_row_checks_returns_three_results():
    results = quality.run_row_checks("gold", [gold_row()], schemas.GOLD_DDL, RUN_TIME)
    assert [result["check_name"] for result in results] == [
        "gold_schema", "gold_duplicate_keys", "gold_null_pm2_5",
    ]


def test_raise_on_failure_names_the_failed_checks():
    results = quality.run_row_checks("gold", [gold_row(), gold_row()], schemas.GOLD_DDL, RUN_TIME)
    with pytest.raises(quality.DataQualityError, match=r"gold_duplicate_keys \(1\)"):
        quality.raise_on_failure(results)


def test_raise_on_failure_ignores_warnings():
    results = quality.run_row_checks("gold", [gold_row(pm2_5=None)], schemas.GOLD_DDL, RUN_TIME)
    quality.raise_on_failure(results)  # WARN only: no exception

