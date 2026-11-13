# vn_weather_fabric design

Agreed on: 2026-11-12. Status: agreed after a design interview; not implemented yet.

## Goals and scope
- Data Engineer portfolio project, also used to prepare for the DP-700 exam
- Fabric Trial (64 CU, Southeast Asia), activated 2026-11-12, expires after 60 days
- Time budget: 2 weeks
- Data comes from APIs (no CSV files), stored as Parquet/Delta

## Business questions
- How do PM2.5 levels change by city (one representative City per Province) and by season over the years?
- Which cities have the most days above the recommended PM2.5 threshold each month?
- Do temperature, rainfall, and PM2.5 correlate (per city, per hour)?
- The real-time dashboard only shows the latest Reading and the trend of the day; it does not answer the questions above

## Data
- Main source: Open-Meteo (weather and air quality) for 34 cities, one representative City per Province of the 34-province structure (scope widened from 6 cities on 2026-11-12)
- Dimension: provinces.open-api.vn; yearly enrichment: World Bank API (VNM)
- Source details and risks: see `docs/data_sources.md`
- Open-Meteo license: CC BY 4.0, free tier is non-commercial only, attribution required
- PM2.5 is CAMS model data (~45 km), not station measurements
- The list of 34 cities lives in `config/cities.json` (approved hardcoding: it is configuration, not data). Each entry has the Province code (provinces.open-api.vn v2), the City `name`, and a `search_name` for geocoding. Names are English without diacritics because the Geocoding API returned a wrong place for `Ha Noi` with diacritics
- A City is a major city of its Province chosen by hand (for example Nha Trang for Khanh Hoa), not the geometric centre or the official seat. Searching by Province name failed or returned a wrong place for 14 of 34 Provinces, so the config uses city names; `search_name` differs from `name` where the API needs another spelling (`Haiphong`, `Qui Nhon`)
- Data for one point per Province is a coarse view of a Province; the README must say so
- Coordinates are resolved at ingest with the Open-Meteo Geocoding API (filter `countryCode=VN`, pick the populated place (feature code starting with PPL) with the highest population; places without a population are skipped) and stored in `dim_city`; they are not hardcoded
- Domain vocabulary is defined in `GLOSSARY.md`

## Data architecture
- Bronze: plain Parquet under `Files/`, partitioned by ingest date
- Silver, Gold: Delta tables
- Three separate lakehouses: `lh_bronze`, `lh_silver`, `lh_gold`
- Gold (small star schema):
  - `dim_city`: 34 cities, coordinates, Province
  - `dim_date`
  - `fact_weather_hourly`: grain (city, hour), weather and PM2.5 combined, with a `source` column
  - `fact_vn_indicator_yearly`: World Bank indicators per year
  - `agg_city_daily`: daily aggregate for reporting
- One-time backfill from the Cutover date (2024-01-01) using the historical (ERA5) API; Observations from 2022-09-01 (first date with air quality data) to 2023-12-31 come from the Legacy source (see "On-premises migration")
- Refresh run, every 2 hours (the historical API lags about 5 days, so recent days come from the Forecast API):
  - Fetch the 7 days before today and all of today from the Forecast and Air Quality APIs. Hours already over are tagged `source = provisional`, hours still to come `source = forecast`
  - Re-fetch the days 8 to 14 days ago from the historical API, tag rows `source = archive` (final values, replacing provisional ones)
  - Write with Delta `MERGE` on (`city_id`, `ts`): a `forecast` hour becomes `provisional` and then `archive` on later runs
  - Gold holds all sources (`forecast`, `provisional`, `archive`, and `legacy` for migrated rows); Silver holds finished hours only (no predictions)
  - About 136 Open-Meteo calls per run (about 1,632 per day), measured from `X-RateLimit-Cost`
- Timestamps are stored in UTC in Bronze and Silver; Gold adds a local-time column (`Asia/Ho_Chi_Minh`)
- `dim_city` maps each City to its Province by the Province code in the config (provinces.open-api.vn v2); a City name and its Province name may differ after the 2025 merger

## On-premises migration
Status: agreed on 2026-11-13; in progress (the access path was proven on 2026-11-13, see ticket `onprem-migration/01`). Time-boxed to about 3-4 working days; it is an extension and is cut first if time runs out (it must not block the definition of done).

- Purpose: a portfolio story (legacy system moved to the cloud, verified) and practice for DP-700 (on-premises ingest, gateway, pipeline copy)
- Legacy source: a simulated on-premises SQL Server 2022 (Developer edition) in a Docker container on the user's Mac (`legacy_source/`: `docker-compose.yml`, `init_legacy_db.sql`; passwords in a gitignored `.env`). The image is x64 only and runs under emulation on Apple Silicon; stability under a large load is not verified. The port is bound to the Mac address of the Fusion NAT network only, not to the home network. Believed free of charge (Fusion Pro personal-use terms and SQL Server Developer terms not verified in this session)
- Why Docker and not the VM: SQL Server has no ARM64 build and its installer failed to run on Windows 11 ARM according to Microsoft Q&A threads (community answers, no official documentation); the install was not tried in the VM
- Content: Observations from 2022-09-01 to 2023-12-31, loaded once from the ERA5 API into the database. The README states that the source is simulated and filled from the same ERA5 data
- Access: an on-premises data gateway (`gw_legacy_onprem`) installed in a Windows 11 ARM VM (VMware Fusion Pro) on the same Mac; the gateway is Windows only, no container support, per Microsoft docs. It ran on Windows ARM and reached SQL Server through the Fusion NAT address of the Mac (the Fabric connection `cn_legacy_sqlserver` uses a read-only login `fabric_reader`). That address depends on the Fusion network and can change after a restart. Fallback if the setup breaks: export files from the database and upload them to OneLake, with no gateway
- Path: Copy activity in a pipeline writes Parquet to `lh_bronze` `Files/` (partitioned by ingest date), then the same Silver notebook, then Gold with `source = legacy`
- Idempotent: Delta `MERGE` on (`city_id`, `ts`), so the Migration can be re-run safely
- Cutover date `2024-01-01` lives in `config/` (business boundary, not an environment value; hardcoding approved on 2026-11-13)
  - The Migration writes only `ts` before the Cutover date; the Backfill writes only from it
  - A row outside its range stops the pipeline with an error
  - Continuity check around the boundary: 2023-12-31 23:00 and 2024-01-01 00:00 exist for all 34 Cities
- Reconciliation (results go to the data quality table in `lh_gold`):
  - Row counts equal per City and month
  - Sum, min and max of key columns (temperature, PM2.5) equal
  - No duplicate keys and no missing hours from 2022-09-01 to 2023-12-31
- Current state: the first Backfill (ticket `vn-weather-pipeline/04`, 2026-11-12) loaded the API data from 2022-09-01. The Migration ticket replaces the rows of 2022-09-01 to 2023-12-31 in Silver and Gold by the Legacy rows, then the boundary guards apply
- Cutover: the data is historical, so no parallel run and no incremental load (a deliberate choice, stated in the README). After the Migration is verified the database is set read-only and marked decommissioned. Rollback is re-running the Migration, not restoring the database

## Near-real-time branch
- A notebook calls the Open-Meteo `current` endpoint for 34 cities every 2 hours and sends events to an Eventstream (custom endpoint), stored in an Eventhouse (KQL)
- This is micro-batch, not a true stream; the README must say so
- Separate pipeline from the daily batch pipeline
- Data from this branch does not go into Gold

## Processing and visualization
- Thin PySpark notebooks; logic lives in plain Python modules under `src/` (testable outside Fabric)
- Data Pipeline handles orchestration and schedules
- Power BI Direct Lake (1-2 pages) for batch; Real-Time Dashboard for the near-real-time branch

## Git and CI/CD
- GitHub, single `main` branch, commit directly
- A single workspace `de_vn_prod`, connected to GitHub (branch `main`, Git folder `fabric/`); there is no dev or test environment
- Authoring: items created or changed in the Fabric UI are committed to `main` from Source control; code edited in an IDE is pushed to `main`
- Every push to `main` runs the CI job: ruff, pytest, gitleaks, and a no-deploy validation (every JSON file and `.platform` parses, `py_compile` on notebook sources, every item folder has a valid `.platform` with a known item type)
- CD is manual: after CI is green, run "Update all" in the Fabric Source control panel
  - Automation with a service principal was tested on 2026-11-12: OIDC login worked, but the Fabric Git API returned `GitCredentialsNotConfigured`. A service principal needs its own GitHub credential, which means a long-lived token stored in a Fabric connection and renewed regularly. This was judged not worth it for a one-person project; the README documents the decision
- Rollback: `git revert` on `main`, then "Update all" in Fabric
- Working rules (UI and IDE write to the same branch):
  - Before editing in the Fabric UI, run "Update all" in Source control
  - Before pushing from an IDE, run `git pull --rebase`
  - Never edit the same item on both sides at the same time
- `fabric-cicd` is not used: it publishes items into a workspace that is not Git-connected and mainly pays off with several environments, which this project does not have. Its parameterization is also not needed (one environment). Workspace-specific IDs, when needed, go in GitHub variables, never hardcoded

## Identity and access (set up on 2026-11-12)
- `de_vn_prod` is connected to GitHub (`stevetran77/vn_weather_fabric`, branch `main`, folder `/fabric`) with the user's own token
- Tenant setting "Users can sync workspace items with GitHub repositories" is enabled for group `vn_fabric_cicd`, which now contains the signed-in user
- The service principal created for the CD experiment (Entra app, service principal, federated credentials, workspace role) was deleted, and the tenant setting "Service principals can call Fabric public APIs" was turned off again
- GitHub Actions uses no cloud credentials, so the repository has no secrets and no variables
- GitHub's OIDC subject claim includes numeric owner and repo IDs (`repo:<owner>@<id>/<repo>@<id>:ref:...`); a federated credential must use that exact form

## Repo layout
- `fabric/`: workspace items (the Git folder of `de_vn_prod`)
- `src/`: plain Python modules (API calls, transforms)
- `tests/`: pytest tests for `src/`
- `scripts/`: helper scripts (`validate_fabric_items.py` checks the Fabric item folders without calling any API)
- `.github/workflows/`: `ci.yml`
- `pyproject.toml`, `requirements-dev.txt`: ruff and pytest configuration, dev dependencies
- `docs/`: documentation and architecture diagram
- `README.md`

## Naming conventions
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- Fabric items: `lh_`, `nb_`, `pl_`, `es_`, `eh_` (lakehouse, notebook, pipeline, eventstream, eventhouse)
- Workspace: `de_vn_prod`
- Language: all markdown and code in the repo are in English

## Data quality
- Schema violations or duplicate keys (`city_id`, `ts`): the pipeline stops and reports an error
- Null PM2.5: warning only (expected before 2022-09 and in model gaps)
- Check results are written to a small table in `lh_gold` so the dashboard can show them

## Testing
- pytest on the functions in `src/` with mocked HTTP; no live API calls in CI
- A separate live-API test can be run manually and is not part of CI

## After the trial
- The Trial expires about 2027-01-11. After that, non-Power-BI items (notebooks, pipelines) become inaccessible and their content stays in OneLake for about 7 days
- Before then, capture screenshots and a short video of the report and dashboard, store them in `docs/`, and embed them in the README

## Definition of done
- 34 cities backfilled; daily pipeline and 2-hour pipeline run on schedule
- Gold tables populated; basic data quality checks run in notebooks
- Power BI Direct Lake report and Real-Time Dashboard are viewable
- CI is green on every push to `main`, and `de_vn_prod` is synced with "Update all" afterwards
- README has an architecture diagram and states the limitations (PM2.5 is model data, the 2-hour branch is micro-batch, CC BY 4.0 attribution)
- Every function in `src/` has a test
- Demo screenshots and video are stored in `docs/` before the Trial expires

## Out of scope (deferred)
- Dev/test environments, `fabric-cicd`, automated CD, Deployment Pipelines, advanced Purview/lineage, Data Activator, ML

## Unverified (check during implementation)
- How Open-Meteo counts a request with several comma-separated locations against the free-tier limits (10,000 calls/day); the pricing page only says long time ranges count as several calls (about 3 calls for 4 weeks). Rough estimate, not measured: a 4-year Backfill for 34 cities and 2 APIs may use about 10,000 calls, so it may need to be split across days. Measure in ticket 03
- Volume of 34 cities x 4 years of hourly data against the Trial capacity
- How to store the Eventstream custom endpoint connection key without hardcoding it
- Licenses of World Bank data and provinces.open-api.vn
- Whether the Trial keeps scheduled pipelines running for the full 60 days
- Schema support in lakehouses (if the three lakehouses are ever merged into one)

- Whether SQL Server 2022 in Docker under x64 emulation stays stable while loading about 1.2 million rows (Apple Silicon); personal-use terms of Fusion Pro and costs of SQL Server Developer (believed free, not checked)

## Open items
- On-premises migration: split into tickets (VM and database setup, seed from ERA5, gateway and pipeline, reconciliation checks, boundary checks, README section)
- Build the pipeline: `src/` modules and tests, Fabric items under `fabric/` (`src/geocoding.py` and `config/cities.json` done)
- Write the README (architecture diagram, limitations, manual sync step)
