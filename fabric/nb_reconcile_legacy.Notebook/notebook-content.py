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

# PARAMETERS CELL ********************

# Parameters. The pipeline pl_legacy_migrate copied per-City-per-month aggregates computed in
# the Legacy source to Bronze under
# Files/bronze/legacy/reconciliation/ingest_date=<ingest_date>/city_code=<city_code>/.
# city_code 0 means every City. start_date and end_date are UTC dates (end exclusive).
ingest_date = ""  # empty means today (UTC)
city_code = 0
start_date = "2022-09-01"
end_date = "2024-01-01"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import logging
from datetime import UTC, datetime, timedelta

from delta.tables import DeltaTable
from pyspark.sql import functions as F

import legacy_reconciliation as recon
import quality
import schemas

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
spark.conf.set("spark.sql.session.timeZone", "UTC")


def lakehouse_root(name):
    return notebookutils.lakehouse.get(name)["properties"]["abfsPath"]


now = datetime.now(UTC)
run_ingest_date = ingest_date or now.date().isoformat()
aggregates_path = (
    f"{lakehouse_root('lh_bronze')}/Files/bronze/legacy/reconciliation/"
    f"ingest_date={run_ingest_date}/city_code={city_code}"
)
gold_root = lakehouse_root("lh_gold")
gold_path = f"{gold_root}/Tables/fact_weather_hourly"
dim_city_path = f"{gold_root}/Tables/dim_city"
dq_results_path = f"{gold_root}/Tables/dq_results"

print(f"[INFO] city_code={city_code}, range={start_date} to {end_date}, "
      f"ingest_date={run_ingest_date}")

window_start = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
window_end = datetime.fromisoformat(end_date).replace(tzinfo=UTC)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Legacy side: the aggregates computed by SQL Server (one row per City and month).
legacy_expected = {}
for row in spark.read.parquet(aggregates_path).collect():
    values = row.asDict()
    key = (values.pop("city_code"), values.pop("year_month"))
    legacy_expected[key] = values
if not legacy_expected:
    raise RuntimeError(f"No Legacy aggregates found under {aggregates_path}")
print(f"[OK] {len(legacy_expected)} Legacy City-month groups")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Gold side: the rows of the same range, aggregated by the month of the local time.
columns = ["city_id", "ts", "ts_local", "source", *recon.GOLD_MEASURE_COLUMNS]
gold_frame = spark.read.format("delta").load(gold_path).select(*columns).where(
    (F.col("ts") >= F.lit(window_start)) & (F.col("ts") < F.lit(window_end))
    & ((F.col("city_id") == city_code) if city_code != 0 else F.lit(True))
)
gold_rows = [row.asDict() for row in gold_frame.collect()]
gold_actual = recon.aggregate_by_city_month(
    gold_rows, "city_id", "ts_local", recon.GOLD_MEASURE_COLUMNS
)
print(f"[OK] {len(gold_rows)} Gold rows, {len(gold_actual)} City-month groups")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Compare, check key coverage and sources, save the results, and fail the run on a FAIL.
mismatches = recon.compare_aggregates(legacy_expected, gold_actual)

if city_code == 0:
    city_ids = [row["city_id"] for row in spark.read.format("delta").load(dim_city_path).collect()]
else:
    city_ids = [city_code]
# Spark returns `ts` without a time zone (the session time zone is UTC): mark it as UTC.
keys = {(row["city_id"], row["ts"].replace(tzinfo=UTC)) for row in gold_rows}
missing_hours = recon.count_missing_hours(
    keys, city_ids, window_start, window_end - timedelta(hours=1)
)
other_source_rows = sum(row["source"] != "legacy" for row in gold_rows)

results = recon.build_results(mismatches, missing_hours, other_source_rows, now)
results.append(quality.check_duplicate_count("legacy_gold", len(gold_rows) - len(keys), now))
(spark.createDataFrame(results, schemas.DQ_RESULTS_DDL)
    .write.format("delta").mode("append").save(dq_results_path))
for result in results:
    print(f"{result['status']} {result['check_name']}: {result['count']}")
print(f"first mismatches: {mismatches[:5]}")
quality.raise_on_failure(results)
print(f"[OK] {len(results)} reconciliation checks, no failure")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
