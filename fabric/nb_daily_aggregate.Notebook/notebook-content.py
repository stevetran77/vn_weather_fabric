# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
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

# Parameters. Days with a mean Model PM2.5 above this value (ug/m3) are flagged.
# 15 is the WHO 2021 24-hour guideline value.
pm2_5_threshold = 15.0

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import functions as F

import backfill
import daily_aggregate
import schemas
import transforms

spark.conf.set("spark.sql.session.timeZone", "UTC")

gold_root = notebookutils.lakehouse.get("lh_gold")["properties"]["abfsPath"]
hourly_path = f"{gold_root}/Tables/fact_weather_hourly"
daily_path = f"{gold_root}/Tables/fact_weather_daily"
dim_date_path = f"{gold_root}/Tables/dim_date"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Rebuild the whole daily table from the hourly fact (about 34 Cities x 365 days x years rows,
# small), so late corrections to provisional hours are picked up. Overwrite keeps reruns safe.
hourly = spark.read.format("delta").load(hourly_path)
assert not hourly.isEmpty(), "fact_weather_hourly is empty: nothing to aggregate"
hourly.createOrReplaceTempView("hourly")
sql = daily_aggregate.build_daily_sql("hourly", pm2_5_threshold)
# refreshed_at: when this rebuild ran, as Vietnam wall-clock time (shown in the report).
daily = spark.sql(sql).withColumn(
    "refreshed_at", F.from_utc_timestamp(F.current_timestamp(), transforms.LOCAL_ZONE.key)
)
daily.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(daily_path)
print(f"[OK] wrote fact_weather_daily with threshold {pm2_5_threshold}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Check: one row per (city_id, date), and a day never has more than 24 hours.
# One pass over the table also gives the date range used for dim_date below.
daily = spark.read.format("delta").load(daily_path)
stats = daily.agg(
    F.count("*").alias("row_count"),
    F.countDistinct("city_id", "date").alias("distinct_keys"),
    F.sum(F.when(F.col("hours_count") > 24, 1).otherwise(0)).alias("too_many_hours"),
    F.min("date").alias("first_date"),
    F.max("date").alias("last_date"),
).first()
print(stats.asDict())
assert stats.row_count > 0, "daily table is empty"
assert stats.row_count == stats.distinct_keys, "duplicate (city_id, date) rows"
assert stats.too_many_hours == 0, "a day has more than 24 hourly rows"
print("[OK] daily table checks passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Rebuild dim_date (with the season column) to cover exactly the days in the daily table.
# This notebook is the only writer of dim_date.
first_date, last_date = stats.first_date, stats.last_date
dim_date_rows = backfill.build_dim_date(first_date.isoformat(), last_date.isoformat())
(spark.createDataFrame(dim_date_rows, schemas.DIM_DATE_DDL)
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(dim_date_path))
print(f"[OK] dim_date: {first_date} to {last_date}, {len(dim_date_rows)} days")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
