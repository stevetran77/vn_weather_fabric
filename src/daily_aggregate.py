"""Build the per-City daily aggregate from the hourly Gold fact (Spark SQL text, no pyspark)."""

# Forecast hours are still to come: a day's figures must not mix them with measured hours.
EXCLUDED_SOURCE = "forecast"


def build_daily_sql(hourly_view: str, pm2_5_threshold: float) -> str:
    """Return the Spark SQL that aggregates `hourly_view` to one row per (city_id, local date).

    - Days are cut on `ts_local` (Vietnam time), not UTC.
    - Forecast hours are left out.
    - `is_above_pm2_5_threshold` is true when the day's mean Model PM2.5 is above the
      threshold (the WHO 24-hour guideline compares daily means), and null when the day has no
      PM2.5 value at all.
    - Column names and order match `schemas.DAILY_DDL`.
    """
    return f"""
SELECT
    city_id,
    CAST(ts_local AS DATE) AS `date`,
    AVG(pm2_5) AS avg_pm2_5,
    MAX(pm2_5) AS max_pm2_5,
    AVG(temperature_2m) AS avg_temperature_2m,
    MIN(temperature_2m) AS min_temperature_2m,
    MAX(temperature_2m) AS max_temperature_2m,
    AVG(relative_humidity_2m) AS avg_relative_humidity_2m,
    AVG(wind_speed_10m) AS avg_wind_speed_10m,
    SUM(precipitation) AS total_precipitation,
    COUNT(*) AS hours_count,
    COUNT(pm2_5) AS pm2_5_hours_count,
    AVG(pm2_5) > {float(pm2_5_threshold)!r} AS is_above_pm2_5_threshold
FROM {hourly_view}
WHERE source <> '{EXCLUDED_SOURCE}'
GROUP BY city_id, CAST(ts_local AS DATE)
""".strip()
