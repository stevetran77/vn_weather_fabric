# vn_weather_fabric design

Agreed on: 2026-11-12. Status: agreed after a design interview; not implemented yet.

## Goals and scope
- Data Engineer portfolio project, also used to prepare for the DP-700 exam
- Fabric Trial (64 CU, Southeast Asia), activated 2026-11-12, expires after 60 days
- Time budget: 2 weeks
- Data comes from APIs (no CSV files), stored as Parquet/Delta

## Data
- Main source: Open-Meteo (weather and air quality) for 6 cities: Hanoi, Ho Chi Minh City, Da Nang, Hai Phong, Can Tho, Hue
- Dimension: provinces.open-api.vn; yearly enrichment: World Bank API (VNM)
- Source details and risks: see `docs/data_sources.md`
- Open-Meteo license: CC BY 4.0, free tier is non-commercial only, attribution required
- PM2.5 is CAMS model data (~45 km), not station measurements

## Data architecture
- Bronze: plain Parquet under `Files/`, partitioned by ingest date
- Silver, Gold: Delta tables
- Three separate lakehouses: `lh_bronze`, `lh_silver`, `lh_gold`
- Gold (small star schema):
  - `dim_city`: 6 cities, coordinates, province code
  - `dim_date`
  - `fact_weather_hourly`: grain (city, hour), weather and PM2.5 combined
  - `fact_vn_indicator_yearly`: World Bank indicators per year
  - `agg_city_daily`: daily aggregate for reporting
- One-time backfill from 2022-09-01 (first date with air quality data)
- Daily run re-fetches the last 3 days and writes with Delta `MERGE` on (`city_id`, `ts`)

## Near-real-time branch
- A notebook calls the Open-Meteo `current` endpoint for 6 cities every 2 hours and sends events to an Eventstream (custom endpoint), stored in an Eventhouse (KQL)
- This is micro-batch, not a true stream; the README must say so
- Separate pipeline from the daily batch pipeline
- Data from this branch does not go into Gold

## Processing and visualization
- Thin PySpark notebooks; logic lives in plain Python modules under `src/` (testable outside Fabric)
- Data Pipeline handles orchestration and schedules
- Power BI Direct Lake (1-2 pages) for batch; Real-Time Dashboard for the near-real-time branch

## Git and CI/CD
- GitHub, single `main` branch, commit directly
- A single workspace: `de_vn_prod`, not connected to Git; the repo is the source of truth
- Every push to `main`: CI job (ruff, pytest, gitleaks, validate), then deploy job (`needs: ci`) using `fabric-cicd`
- No manual approval step; rollback is `git revert` followed by a redeploy
- Authentication: service principal with OIDC federated credential (no stored secret)
  - App registration: `vn_weather_fabric_cicd`
  - Security group: `vn_fabric_cicd`
  - Federated credential for repo `vn_weather_fabric`, branch `main`
- Environment-specific values (workspace ID, etc.) are not hardcoded; use the `fabric-cicd` parameter file and GitHub variables

## Repo layout
- `fabric/`: workspace items
- `src/`: plain Python modules (API calls, transforms)
- `tests/`: pytest tests for `src/`
- `.github/workflows/`: `ci.yml`, `deploy.yml`
- `docs/`: documentation and architecture diagram
- `README.md`

## Naming conventions
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- Fabric items: `lh_`, `nb_`, `pl_`, `es_`, `eh_` (lakehouse, notebook, pipeline, eventstream, eventhouse)
- Workspace: `de_vn_prod`
- Language: all markdown and code in the repo are in English

## Definition of done
- 6 cities backfilled; daily pipeline and 2-hour pipeline run on schedule
- Gold tables populated; basic data quality checks (nulls, duplicates, schema) run in notebooks
- Power BI Direct Lake report and Real-Time Dashboard are viewable
- CI is green; a push to `main` deploys to `de_vn_prod` automatically
- README has an architecture diagram and states the limitations (PM2.5 is model data, the 2-hour branch is micro-batch, CC BY 4.0 attribution)
- Every function in `src/` has a test

## Out of scope (deferred)
- Dev/test environments, Deployment Pipelines, advanced Purview/lineage, Data Activator, ML

## Unverified (check during implementation)
- Exact display name of the service principal tenant setting in the portal
- How `azure/login` OIDC works together with `fabric-cicd`
- How to store the Eventstream custom endpoint connection key without hardcoding it
- Licenses of World Bank data and provinces.open-api.vn
- Schema support in lakehouses (if the three lakehouses are ever merged into one)

## Open items
- Assign the Fabric Administrator role to the account and enable the service principal tenant setting
- Create group `vn_fabric_cicd`, app `vn_weather_fabric_cicd`, and the federated credential (needs the repo)
- Create workspace `de_vn_prod` on the Trial capacity and grant the app access
- Create the GitHub repo `vn_weather_fabric` (public)
