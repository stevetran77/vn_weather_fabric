# vn_weather_fabric

Hourly weather and air quality (PM2.5) for one representative city in each of Vietnam's 34 provinces, loaded into Microsoft Fabric with a Bronze / Silver / Gold lakehouse design.

This is a Data Engineer portfolio project, also used to prepare for the DP-700 exam. It runs on a Fabric Trial capacity.

## Status

- Done: city config and geocoding, Bronze to Gold load for one city and one week (tracer), idempotent merge, CI
- Written: the 34-city Backfill notebook (`nb_backfill`, which builds `dim_city`), the daily refresh (`nb_daily_refresh`, `pl_daily_refresh`) and the data quality checks (`src/quality.py`)
- Daily aggregate: `nb_daily_aggregate` builds `fact_weather_daily` (one row per City and local day) and `dim_date` (with a dry/wet `season` column); `fact_weather_daily` has data in Fabric
- Power BI: the Direct Lake on OneLake semantic model `sm_vn_weather` (relationships, season, DAX measures) and a two-page report are written; the report has not been checked in the Fabric UI yet, and its "Insights and recommendations" text is not written
- Planned: World Bank yearly indicators, near-real-time branch and dashboard

The agreed design is in [`docs/design.md`](docs/design.md); domain terms are in [`GLOSSARY.md`](GLOSSARY.md).

## Architecture

```
Open-Meteo (weather, PM2.5) ──┐
provinces.open-api.vn ────────┼──> notebooks ──> lh_bronze (raw Parquet, by ingest date)
World Bank (planned) ─────────┘                       │
                                                      v
                                          lh_silver (Delta, cleaned, UTC)
                                                      │
                                                      v
                              lh_gold (Delta: fact_weather_hourly, dim_city)
                                                      │  nb_daily_aggregate
                                                      v
                              lh_gold (Delta: fact_weather_daily, dim_date)
                                                      │
                                                      v
                              sm_vn_weather (Direct Lake on OneLake) ──> Power BI report
```

- The plain Python logic lives in `src/` and is tested outside Fabric; notebooks only import it and call it
- Writes use a Delta `MERGE` on `(city_id, ts)`, so rerunning a load adds no duplicates
- Timestamps are UTC in Bronze and Silver; Gold adds a local-time column (`Asia/Ho_Chi_Minh`)
- Days in `fact_weather_daily` are cut on local time and leave out forecast hours; a day is above the PM2.5 threshold when its mean Model PM2.5 is above the `pm2_5_threshold` notebook parameter (default 15 ug/m3, the WHO 24-hour guideline)
- `dim_date` has a single writer, `nb_daily_aggregate`, which rebuilds it to cover the days in `fact_weather_daily`
- The report splits the year into a dry season (November to April) and a wet season (May to October); this is a coarse national split, and the real seasons differ by region

## Data sources and attribution

- Weather and air quality: [Open-Meteo](https://open-meteo.com/), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The free tier is for non-commercial use only
- Province names: [provinces.open-api.vn](https://provinces.open-api.vn/) (community-run; its terms are not verified)
- Planned: World Bank API

## Limitations

- PM2.5 is **model data** (CAMS Global, about 45 km grid), not station measurements
- Each Province is represented by one chosen city, so the data is a coarse view of the Province
- The planned near-real-time branch is a micro-batch (a notebook polling every 2 hours), not a true stream
- Open-Meteo's free tier has rate limits (600 calls per minute, 10,000 per day)

## Repository layout

- `fabric/`: Fabric items (the Git folder of the workspace `de_vn_prod`)
- `src/`: plain Python modules (API calls, transforms, schemas, request planning)
- `tests/`: pytest tests for `src/`, with mocked HTTP
- `scripts/`: helper scripts (offline validation of Fabric item folders)
- `config/cities.json`: the 34 cities, one per Province
- `docs/`: design and data source notes

## How changes reach Fabric

- Every push to `main` runs CI (ruff, pytest, gitleaks, and the Fabric item validator)
- Deployment is manual: after CI is green, run "Update all" in the Fabric Source control panel
- Notebooks install the code in `src/` from the repository with `%pip install`, so a push to `main` is picked up the next time a notebook runs

## Common questions

### What is the difference between `src/backfill.py` and `nb_backfill`?

- `src/backfill.py` is a module of small functions: split a date range into chunks, plan the requests, estimate the Open-Meteo call cost, and build the `dim_date` rows. It calls no API and writes nothing, so `pytest` can test it on any machine
- `nb_backfill` is the Fabric notebook that runs the Backfill. It uses those functions to fetch data, write Bronze Parquet, and merge Silver and Gold Delta tables with Spark
- The same split applies to the other modules and notebooks: logic in `src/`, orchestration in the notebook

### Why do the pipelines need notebooks?

- The lakehouses live in Fabric (OneLake), and Spark and Delta `MERGE` are only available there
- A Data Pipeline needs something to run on a schedule, and that is a notebook
- Notebooks stay thin so that the logic remains testable locally

### Why do notebooks install the code from GitHub, and why is the repository public?

- Fabric does not import `src/` from the Git folder, which only syncs the `fabric/` items. Notebooks therefore run `%pip install` on `https://github.com/<owner>/vn_weather_fabric/archive/refs/heads/main.zip`
- A private repository returns 404 for that link, so the repository is public. It contains no secrets, and CI scans the history with gitleaks
- The trade-off: a push to `main` changes what notebooks run, even if CI is red. Pinning the commit SHA in the link gives a reproducible run

### Why is deployment to Fabric not automated?

- An automated deployment with a service principal was tested: the login worked, but the Fabric Git API returned `GitCredentialsNotConfigured`. A service principal needs its own GitHub credential, which means a long-lived token
- For a one-person project that was judged not worth it, so "Update all" is a manual step. Details are in [`docs/design.md`](docs/design.md)
