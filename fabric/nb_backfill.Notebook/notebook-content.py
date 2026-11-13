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

# Parameters. An empty city_names list loads all 34 Cities from the config.
# end_date must be at least 10 days in the past (the historical API lags about 5 days).
start_date = "2024-01-01"  # must not be before the Cutover date
end_date = "2024-01-31"
city_names = []
days_per_chunk = 366
daily_call_budget = 9000
config_url = "https://raw.githubusercontent.com/stevetran77/vn_weather_fabric/main/config/cities.json"
cutover_config_url = "https://raw.githubusercontent.com/stevetran77/vn_weather_fabric/main/config/cutover.json"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import logging
from datetime import UTC, date, datetime

from delta.tables import DeltaTable
from pyspark.sql import functions as F

import backfill
import cutover
import geocoding
import http_json
import open_meteo
import provinces
import quality
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
ingest_date = date.today().isoformat()


def overwrite_delta(rows, ddl, path):
    """Replace a small dimension table; rerunning gives the same table."""
    frame = spark.createDataFrame(rows, ddl)
    frame.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)


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

# The Backfill only writes from the Cutover date: stop before touching any data.
cutover_ts = cutover.parse_cutover(http_json.get_json(cutover_config_url))
cutover.check_backfill_range(start_date, cutover_ts)
print(f"[OK] start_date {start_date} is on or after the Cutover date {cutover_ts.date()}")

# Resolve the selected Cities, then build and write dim_city.
all_cities = http_json.get_json(config_url)["cities"]
unknown = set(city_names) - {city["name"] for city in all_cities}
if unknown:
    raise ValueError(f"Unknown city names: {sorted(unknown)}")
selected = [city for city in all_cities if not city_names or city["name"] in city_names]

resolved = geocoding.resolve_all(selected)
overwrite_delta(
    provinces.build_dim_city(resolved, provinces.fetch_provinces()),
    schemas.DIM_CITY_DDL,
    dim_city_path,
)
print(f"[OK] dim_city: {len(resolved)} Cities (dim_date is built by nb_daily_aggregate)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Estimate the Open-Meteo calls before loading, and stop if the plan exceeds the daily budget.
# The estimate is fitted to measured headers, not documented: treat it as a plan only.
plan = [
    request
    for city in resolved
    for request in backfill.plan_requests([city], start_date, end_date, days_per_chunk, 1)
]
estimated_calls = backfill.estimate_plan_cost(
    plan, len(open_meteo.WEATHER_VARIABLES)
) + backfill.estimate_plan_cost(plan, len(open_meteo.AIR_QUALITY_VARIABLES))
print(f"{len(plan)} chunks per API, about {estimated_calls:.0f} Open-Meteo calls (budget {daily_call_budget})")
if estimated_calls > daily_call_budget:
    raise RuntimeError("Planned calls exceed the daily budget: shorten the range or load fewer Cities")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Load one City at a time: fetch in chunks, write Bronze, merge Silver and Gold.
def fetch_city_rows(city):
    lat, lon = [city["latitude"]], [city["longitude"]]
    weather_rows, air_rows = [], []
    for chunk in backfill.plan_requests([city], start_date, end_date, days_per_chunk, 1):
        first, last = chunk["start_date"], chunk["end_date"]
        weather_url = open_meteo.build_weather_url(lat, lon, first, last)
        air_url = open_meteo.build_air_quality_url(lat, lon, first, last)
        weather_rows += open_meteo.fetch_hourly(weather_url)[0]
        air_rows += open_meteo.fetch_hourly(air_url)[0]
    return weather_rows, air_rows


def load_city(city):
    weather_rows, air_rows = fetch_city_rows(city)
    bronze_weather = transforms.to_bronze_rows(city, "archive", weather_rows, ingest_date)
    bronze_air = transforms.to_bronze_rows(city, "air_quality", air_rows, ingest_date)
    write_bronze(bronze_weather, open_meteo.WEATHER_VARIABLES, "weather")
    write_bronze(bronze_air, open_meteo.AIR_QUALITY_VARIABLES, "air_quality")
    silver_rows = transforms.build_silver_rows(bronze_weather, bronze_air)
    cutover.check_rows_from(silver_rows, cutover_ts)
    gold_rows = transforms.build_gold_rows(silver_rows, source="archive")
    merge_delta(silver_rows, schemas.SILVER_DDL, silver_path)
    merge_delta(gold_rows, schemas.GOLD_DDL, gold_path)
    return len(gold_rows)


failed = {}
for city in resolved:
    try:
        print(f"[OK] {city['name']}: {load_city(city)} rows")
    except Exception as error:  # keep going; failed Cities are listed and can be rerun
        logging.exception("Load failed for %s", city["name"])
        failed[city["name"]] = str(error)
if failed:
    raise RuntimeError(f"Failed Cities (rerun with city_names set to these): {failed}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Check row counts per City in Gold: rows must equal the expected hours and the distinct keys.
expected_hours = ((date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1) * 24
city_ids = [city["province_code"] for city in resolved]
summary = (
    spark.read.format("delta").load(gold_path)
    .where(F.col("city_id").isin(city_ids))
    .groupBy("city_id")
    .agg(
        F.count("*").alias("rows"),
        F.countDistinct("ts").alias("distinct_ts"),
        F.sum(F.col("pm2_5").isNull().cast("int")).alias("null_pm2_5"),
    )
    .withColumn("expected_rows", F.lit(expected_hours))
    .withColumn("gap", F.col("expected_rows") - F.col("rows"))
    .orderBy("city_id")
)
summary.show(50, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Continuity at the Cutover date: both boundary hours exist for every City, legacy before it and
# not legacy from it. The results go to dq_results and a FAIL stops the run.
run_time = datetime.now(UTC)
last_before, first_after = cutover.boundary_hours(cutover_ts)
boundary_rows = [
    row.asDict()
    for row in spark.read.format("delta").load(gold_path)
    .where(F.col("ts").isin([F.lit(last_before), F.lit(first_after)]))
    .select("city_id", "ts", "source").collect()
]
# Spark returns `ts` without a time zone (the session time zone is UTC): mark it as UTC.
for row in boundary_rows:
    row["ts"] = row["ts"].replace(tzinfo=UTC)
all_city_ids = [row["city_id"] for row in spark.read.format("delta").load(dim_city_path).collect()]
results = cutover.check_continuity(boundary_rows, all_city_ids, cutover_ts, run_time)
(spark.createDataFrame(results, schemas.DQ_RESULTS_DDL)
    .write.format("delta").mode("append").save(f"{gold_root}/Tables/dq_results"))
for result in results:
    print(f"{result['status']} {result['check_name']}: {result['count']}")
quality.raise_on_failure(results)
print(f"[OK] Cutover continuity for {len(all_city_ids)} Cities")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
