# Notebooks and pipelines

What each Fabric notebook (`nb_*`) and Data Pipeline (`pl_*`) in `fabric/` does. Logic lives in `src/`; notebooks import and call it.

## Notebooks

| Notebook | What it does | Writes |
|---|---|---|
| `nb_tracer_load` | Tracer: one City, one week, Bronze to Gold | Bronze, Silver, Gold |
| `nb_backfill` | One-time load of 34 Cities from the Cutover date; builds `dim_city`; boundary check at the end | Bronze, Silver, Gold, `dim_city`, `dq_results` |
| `nb_daily_refresh` | Refreshes recent days (`archive`, `provisional`, `forecast`) and runs row checks | Bronze, Silver, Gold, `dq_results` |
| `nb_daily_aggregate` | Daily layer: one row per City and local day | `fact_weather_daily`, `dim_date` |
| `nb_migrate_legacy` | Migration: `delete` empties a range, `load` merges Legacy rows (`source = legacy`) | Silver, Gold |
| `nb_reconcile_legacy` | Compares Legacy aggregates with Gold | `dq_results` |
| `nb_scratch_bronze_tables` | Utility: creates `raw_weather`, `raw_air_quality` over Bronze | tables in `lh_bronze` |
| `nb_world_bank` | Empty; World Bank is planned | none |

Guards: `nb_backfill` and `nb_migrate_legacy` stop if a row is on the wrong side of the Cutover date (2024-01-01). `nb_reconcile_legacy` proves the access path and mapping only, because the Legacy source was filled from Gold.

## Pipelines

| Pipeline | Runs | Purpose |
|---|---|---|
| `pl_daily_refresh` | `nb_daily_refresh`, then `nb_daily_aggregate` | Daily load (schedule is set in Fabric, not verified) |
| `pl_legacy_seed` | Clear tables, copy cities, copy hours before 2024-01-01 | Fills the Legacy source once |
| `pl_legacy_smoke_test` | One Copy activity | Checks the gateway connection |
| `pl_legacy_delete_range` | A notebook with `mode`, `city_code`, `start_date`, `end_date` | Empties a range before a load (notebook not verified) |
| `pl_legacy_migrate` | Two Copy activities, `nb_migrate_legacy`, `nb_reconcile_legacy` | Migration with reconciliation |
