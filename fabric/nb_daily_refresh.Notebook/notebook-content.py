# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

# Same as the %pip magic, written as plain Python so the file always compiles.
get_ipython().run_line_magic(
    "pip",
    "install --force-reinstall --no-deps "
    "https://github.com/stevetran77/vn_weather_fabric/archive/refs/heads/main.zip",
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Parameters. run_date is empty for a normal run (today, UTC); set it to YYYY-MM-DD to test.
run_date = ""
cities_per_request = 34

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import logging
from datetime import date

from delta.tables import DeltaTable
from pyspark.sql import functions as F

import backfill
import open_meteo
import refresh
import schemas
import transforms

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")


def lakehouse_root(name):
    return notebookutils.lakehouse.get(name)["properties"]["abfsPath"]


bronze_root = lakehouse_root("lh_bronze")
silver_path = f"{lakehouse_root('lh_silver')}/Tables/observation"
gold_root = lakehouse_root("lh_gold")
gold_path = f"{gold_root}/Tables/fact_weather_hourly"
dim_city_path = f"{gold_root}/Tables/dim_city"


def merge_delta(rows, ddl, path):
    """Upsert rows on (city_id, ts); rerunning adds no duplicates."""
    frame = spark.createDataFrame(rows, ddl)
    if DeltaTable.isDeltaTable(spark, path):
        (DeltaTable.forPath(spark, path).alias("t")
            .merge(frame.alias("s"), transforms.build_merge_condition())
            .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        frame.write.format("delta").save(path)


def write_bronze(rows, variables, dataset):
    """Write raw Parquet partitioned by ingest date and city; a same-day rerun replaces it."""
    path = f"{bronze_root}/Files/bronze/open_meteo/{dataset}"
    (spark.createDataFrame(rows, schemas.bronze_ddl(variables))
        .write.mode("overwrite").partitionBy("ingest_date", "city_id").parquet(path))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Read the 34 Cities with their coordinates from dim_city (no geocoding call needed).
cities = [
    {
        "province_code": row["province_code"],
        "name": row["city_name"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
    }
    for row in spark.read.format("delta").load(dim_city_path).orderBy("city_id").collect()
]
today = date.fromisoformat(run_date) if run_date else date.today()
ingest_date = today.isoformat()
windows = refresh.refresh_windows(today)
print(f"{len(cities)} Cities; windows: {windows}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Fetch both windows for all Cities: Forecast API (provisional) and historical API (final).
def fetch_window(build_url, start_date, end_date):
    """Fetch one window; return {city_id: hourly rows}. One request covers a batch of Cities."""
    rows_by_city = {}
    for request in backfill.plan_requests(cities, start_date, end_date, 7, cities_per_request):
        batch = request["cities"]
        url = build_url(
            [city["latitude"] for city in batch],
            [city["longitude"] for city in batch],
            request["start_date"],
            request["end_date"],
        )
        locations = open_meteo.fetch_hourly(url)
        if len(locations) != len(batch):
            raise ValueError(f"Expected {len(batch)} locations, got {len(locations)}")
        for city, hourly in zip(batch, locations, strict=True):
            rows_by_city.setdefault(city["province_code"], []).extend(hourly)
    return rows_by_city


weather_builders = {
    "forecast": open_meteo.build_forecast_url,
    "archive": open_meteo.build_weather_url,
}
bronze_weather, bronze_air, silver_rows, gold_rows = [], [], [], []
for source, (start_date, end_date) in windows.items():
    weather = fetch_window(weather_builders[source], start_date, end_date)
    air = fetch_window(open_meteo.build_air_quality_url, start_date, end_date)
    source_weather, source_air = [], []
    for city in cities:
        city_id = city["province_code"]
        source_weather += transforms.to_bronze_rows(city, source, weather[city_id], ingest_date)
        source_air += transforms.to_bronze_rows(city, "air_quality", air[city_id], ingest_date)
    silver = transforms.build_silver_rows(source_weather, source_air)
    bronze_weather += source_weather
    bronze_air += source_air
    silver_rows += silver
    gold_rows += transforms.build_gold_rows(silver, source=source)
print(f"[OK] fetched {len(silver_rows)} hourly rows for {len(cities)} Cities")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write Bronze, then merge Silver and Gold. A day with no rows is skipped, not an error.
if not silver_rows:
    print("[OK] no rows returned, nothing to write")
else:
    write_bronze(bronze_weather, open_meteo.WEATHER_VARIABLES, "weather")
    write_bronze(bronze_air, open_meteo.AIR_QUALITY_VARIABLES, "air_quality")
    merge_delta(silver_rows, schemas.SILVER_DDL, silver_path)
    merge_delta(gold_rows, schemas.GOLD_DDL, gold_path)
    print(f"[OK] merged {len(gold_rows)} rows into Silver and Gold")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Register the new Bronze partitions. This needs lh_bronze as the default lakehouse of this
# notebook and the tables raw_weather and raw_air_quality to exist (approved in CLAUDE.md).
for dataset in ("weather", "air_quality"):
    spark.sql(f"MSCK REPAIR TABLE raw_{dataset}")
print("[OK] Bronze partitions registered")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Check Gold for the 14 refreshed days: expect 34 Cities x 24 h per day per source, no duplicates.
window_start = windows["archive"][0]
gold = spark.read.format("delta").load(gold_path).where(F.col("ts") >= F.lit(window_start).cast("timestamp"))
gold.groupBy("source", F.to_date("ts").alias("day")).count().orderBy("day").show(20, truncate=False)
print("rows:", gold.count(), "| distinct keys:", gold.select("city_id", "ts").distinct().count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
