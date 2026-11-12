"""Table schemas as Spark DDL strings, shared by the notebooks (no pyspark import needed)."""

from open_meteo import AIR_QUALITY_VARIABLES, WEATHER_VARIABLES


def _ddl(columns: list[tuple[str, str]]) -> str:
    """Join (name, type) pairs into a DDL string; names are quoted so `date` or `day` are safe."""
    return ", ".join(f"`{name}` {data_type}" for name, data_type in columns)


def _doubles(names: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(name, "double") for name in names]


def column_types(ddl: str) -> dict[str, str]:
    """Return {column name: DDL type} for a DDL string built by this module."""
    pairs = (part.split() for part in ddl.split(", "))
    return {name.strip("`"): data_type for name, data_type in pairs}


def column_names(ddl: str) -> list[str]:
    """Return the column names of a DDL string built by this module, in order."""
    return list(column_types(ddl))


def bronze_ddl(variables: tuple[str, ...]) -> str:
    """Schema of a Bronze dataset: lineage columns, the raw time string, then the variables."""
    return _ddl(
        [
            ("city_id", "long"),
            ("city_name", "string"),
            ("latitude", "double"),
            ("longitude", "double"),
            ("api", "string"),
            ("ingest_date", "string"),
            ("time", "string"),
            *_doubles(variables),
        ]
    )


SILVER_DDL = _ddl(
    [("city_id", "long"), ("ts", "timestamp"), *_doubles(WEATHER_VARIABLES + AIR_QUALITY_VARIABLES)]
)

GOLD_DDL = SILVER_DDL + ", " + _ddl([("ts_local", "timestamp"), ("source", "string")])

DQ_RESULTS_DDL = _ddl(
    [
        ("run_time", "timestamp"),
        ("check_name", "string"),
        ("status", "string"),
        ("count", "long"),
    ]
)

DIM_CITY_DDL = _ddl(
    [
        ("city_id", "long"),
        ("city_name", "string"),
        ("latitude", "double"),
        ("longitude", "double"),
        ("province_code", "long"),
        ("province_name", "string"),
    ]
)

DIM_DATE_DDL = _ddl(
    [
        ("date_key", "int"),
        ("date", "date"),
        ("year", "int"),
        ("quarter", "int"),
        ("month", "int"),
        ("month_name", "string"),
        ("day", "int"),
        ("day_of_week", "int"),
        ("day_name", "string"),
        ("is_weekend", "boolean"),
    ]
)

DAILY_DDL = _ddl(
    [
        ("city_id", "long"),
        ("date", "date"),
        ("avg_pm2_5", "double"),
        ("max_pm2_5", "double"),
        ("avg_temperature_2m", "double"),
        ("min_temperature_2m", "double"),
        ("max_temperature_2m", "double"),
        ("avg_relative_humidity_2m", "double"),
        ("avg_wind_speed_10m", "double"),
        ("total_precipitation", "double"),
        ("hours_count", "long"),
        ("pm2_5_hours_count", "long"),
        ("is_above_pm2_5_threshold", "boolean"),
    ]
)
