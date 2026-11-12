# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "1e76f2d3-caeb-4936-9677-5dcb797c5f6c",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "b4bbefbb-d2f9-4682-b467-047fd79ab8da",
# META       "known_lakehouses": [
# META         {
# META           "id": "1e76f2d3-caeb-4936-9677-5dcb797c5f6c"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Welcome to your new notebook
# Type here in the cell editor to add code!
bronze_root = notebookutils.lakehouse.get("lh_bronze")["properties"]["abfsPath"]
for dataset in ("weather", "air_quality"):
    location = f"{bronze_root}/Files/bronze/open_meteo/{dataset}"
    spark.sql(f"CREATE TABLE IF NOT EXISTS raw_{dataset} USING PARQUET LOCATION '{location}'")
    spark.sql(f"MSCK REPAIR TABLE raw_{dataset}")
spark.sql("SHOW TABLES").show(truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.sql("""
    SELECT api, COUNT(*) AS rows, COUNT(DISTINCT city_id) AS cities, MIN(time) AS first_time, MAX(time) AS last_time
    FROM raw_weather GROUP BY api
""").show(truncate=False)
spark.sql("SELECT COUNT(*) AS rows, COUNT(DISTINCT city_id) AS cities FROM raw_air_quality").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
