import backfill
import open_meteo
import provinces
import schemas
import transforms

CITY = {"province_code": 1, "name": "Hanoi", "latitude": 21.0, "longitude": 105.8}
WEATHER_ROW = {"time": "2024-01-01T00:00", **{v: 1.0 for v in open_meteo.WEATHER_VARIABLES}}
AIR_ROW = {"time": "2024-01-01T00:00", **{v: 2.0 for v in open_meteo.AIR_QUALITY_VARIABLES}}


def test_column_names_strips_quotes():
    assert schemas.column_names("`a` long, `b` string") == ["a", "b"]


def test_ddl_quotes_every_column_name():
    assert schemas.DIM_DATE_DDL.startswith("`date_key` int, `date` date")


def test_bronze_ddl_matches_bronze_rows():
    rows = transforms.to_bronze_rows(CITY, "archive", [WEATHER_ROW], "2024-02-01")
    ddl = schemas.bronze_ddl(open_meteo.WEATHER_VARIABLES)
    assert set(schemas.column_names(ddl)) == set(rows[0])


def test_silver_ddl_matches_silver_rows():
    weather = transforms.to_bronze_rows(CITY, "archive", [WEATHER_ROW], "2024-02-01")
    air = transforms.to_bronze_rows(CITY, "air_quality", [AIR_ROW], "2024-02-01")
    silver = transforms.build_silver_rows(weather, air)
    assert set(schemas.column_names(schemas.SILVER_DDL)) == set(silver[0])


def test_gold_ddl_matches_gold_rows():
    weather = transforms.to_bronze_rows(CITY, "archive", [WEATHER_ROW], "2024-02-01")
    silver = transforms.build_silver_rows(weather, [])
    gold = transforms.build_gold_rows(silver, source="archive")
    assert set(schemas.column_names(schemas.GOLD_DDL)) == set(gold[0])


def test_dim_city_ddl_matches_dim_city_rows():
    rows = provinces.build_dim_city([CITY], [{"code": 1, "name": "Hanoi"}])
    assert set(schemas.column_names(schemas.DIM_CITY_DDL)) == set(rows[0])


def test_dim_date_ddl_matches_dim_date_rows():
    rows = backfill.build_dim_date("2024-01-01", "2024-01-01")
    assert set(schemas.column_names(schemas.DIM_DATE_DDL)) == set(rows[0])
