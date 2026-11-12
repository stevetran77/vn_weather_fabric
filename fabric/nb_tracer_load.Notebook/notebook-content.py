# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

# MAGIC %pip install --force-reinstall --no-deps https://github.com/stevetran77/vn_weather_fabric/archive/refs/heads/main.zip

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Parameters: one City and one date range (tracer: Hanoi, one week).
province_code = 1
city_name = "Hanoi"
search_name = "Hanoi"
start_date = "2026-10-20"
end_date = "2026-10-26"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark",
# META   "tags": [
# META     "parameters"
# META   ]
# META }

# CELL ********************

import logging
from datetime import date

from delta.tables import DeltaTable
from pyspark.sql import types as T

import geocoding
import open_meteo
import transforms

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")


def lakehouse_root(name):
    return notebookutils.lakehouse.get(name)["properties"]["abfsPath"]


bronze_root = lakehouse_root("lh_bronze")
silver_path = f"{lakehouse_root('lh_silver')}/Tables/observation"
gold_path = f"{lakehouse_root('lh_gold')}/Tables/fact_weather_hourly"


def double_fields(columns):
    return [T.StructField(column, T.DoubleType()) for column in columns]


def bronze_schema(variables):
    return T.StructType([
        T.StructField("city_id", T.LongType()),
        T.StructField("city_name", T.StringType()),
        T.StructField("latitude", T.DoubleType()),
        T.StructField("longitude", T.DoubleType()),
        T.StructField("api", T.StringType()),
        T.StructField("ingest_date", T.StringType()),
        T.StructField("time", T.StringType()),
        *double_fields(variables),
    ])


SILVER_SCHEMA = T.StructType([
    T.StructField("city_id", T.LongType()),
    T.StructField("ts", T.TimestampType()),
    *double_fields(open_meteo.WEATHER_VARIABLES + open_meteo.AIR_QUALITY_VARIABLES),
])
GOLD_SCHEMA = T.StructType(SILVER_SCHEMA.fields + [
    T.StructField("ts_local", T.TimestampType()),
    T.StructField("source", T.StringType()),
])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Fetch Observations and write them to Bronze (raw Parquet, partitioned by ingest date).
city = geocoding.resolve_city(
    {"province_code": province_code, "name": city_name, "search_name": search_name}
)
ingest_date = date.today().isoformat()
lat, lon = [city["latitude"]], [city["longitude"]]

weather_url = open_meteo.build_weather_url(lat, lon, start_date, end_date)
air_url = open_meteo.build_air_quality_url(lat, lon, start_date, end_date)
weather_raw = open_meteo.fetch_hourly(weather_url)[0]
air_raw = open_meteo.fetch_hourly(air_url)[0]

bronze_weather = transforms.to_bronze_rows(city, "archive", weather_raw, ingest_date)
bronze_air = transforms.to_bronze_rows(city, "air_quality", air_raw, ingest_date)


def write_bronze(rows, variables, dataset):
    path = f"{bronze_root}/Files/bronze/open_meteo/{dataset}"
    (spark.createDataFrame(rows, bronze_schema(variables))
        .write.mode("overwrite").partitionBy("ingest_date").parquet(path))
    return path


weather_path = write_bronze(bronze_weather, open_meteo.WEATHER_VARIABLES, "weather")
air_path = write_bronze(bronze_air, open_meteo.AIR_QUALITY_VARIABLES, "air_quality")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Build Silver and Gold, and merge both on (city_id, ts) so a rerun adds no duplicates.
def read_bronze(path):
    frame = spark.read.parquet(path).where(f"ingest_date = '{ingest_date}'")
    return [row.asDict() for row in frame.collect()]


def merge_delta(rows, schema, path):
    frame = spark.createDataFrame(rows, schema)
    if DeltaTable.isDeltaTable(spark, path):
        (DeltaTable.forPath(spark, path).alias("t")
            .merge(frame.alias("s"), transforms.build_merge_condition())
            .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        frame.write.format("delta").save(path)


silver_rows = transforms.build_silver_rows(read_bronze(weather_path), read_bronze(air_path))
gold_rows = transforms.build_gold_rows(silver_rows, source="archive")
merge_delta(silver_rows, SILVER_SCHEMA, silver_path)
merge_delta(gold_rows, GOLD_SCHEMA, gold_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Check the Gold table: the row count must equal the distinct key count, also after a rerun.
gold = spark.read.format("delta").load(gold_path)
print("rows:", gold.count(), "| distinct keys:", gold.select("city_id", "ts").distinct().count())
gold.orderBy("ts").show(5, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
