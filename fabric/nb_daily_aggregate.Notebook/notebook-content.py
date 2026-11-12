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

import logging

import daily_aggregate

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
spark.conf.set("spark.sql.session.timeZone", "UTC")

gold_root = notebookutils.lakehouse.get("lh_gold")["properties"]["abfsPath"]
hourly_path = f"{gold_root}/Tables/fact_weather_hourly"
daily_path = f"{gold_root}/Tables/fact_weather_daily"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Rebuild the whole daily table from the hourly fact (about 34 Cities x 365 days x years rows,
# small), so late corrections to provisional hours are picked up. Overwrite keeps reruns safe.
spark.read.format("delta").load(hourly_path).createOrReplaceTempView("hourly")
sql = daily_aggregate.build_daily_sql("hourly", pm2_5_threshold)
daily = spark.sql(sql)
daily.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(daily_path)
print(f"[OK] wrote fact_weather_daily with threshold {pm2_5_threshold}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Check: one row per (city_id, date), and a day never has more than 24 hours.
daily = spark.read.format("delta").load(daily_path)
row_count = daily.count()
distinct_keys = daily.select("city_id", "date").distinct().count()
too_many_hours = daily.where("hours_count > 24").count()
print("rows:", row_count, "| distinct keys:", distinct_keys, "| days with >24 hours:", too_many_hours)
assert row_count == distinct_keys, "duplicate (city_id, date) rows"
assert too_many_hours == 0, "a day has more than 24 hourly rows"
print("[OK] daily table checks passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
