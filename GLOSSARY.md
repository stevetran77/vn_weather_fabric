# vn_weather_fabric

Weather and air quality data for one representative city per Vietnamese province, loaded into Microsoft Fabric as a batch history plus a near-real-time snapshot feed.

## Language

**City**:
The representative city of one Province (34 in total), from the configured list, whose weather and air quality are tracked. It is a major city in the Province, not the geometric centre of the Province or its official seat.
_Avoid_: Location, station, site

**Observation**:
An hourly record of weather and PM2.5 for one City at one hour, taken from the Legacy source (before the Cutover date) or from the Open-Meteo APIs (from the Cutover date).
_Avoid_: Measurement, record

**Reading**:
A snapshot of the current conditions of one City, fetched every 2 hours from the `current` endpoint.
_Avoid_: Observation, event, sample

**Backfill**:
The one-time load of all historical Observations from the Cutover date up to the start of the Refresh window, taken from the historical API.
_Avoid_: Initial import, history load

**Legacy source**:
The simulated on-premises database (SQL Server) that holds the Observations from 2022-09-01 up to the day before the Cutover date. It is read-only and decommissioned once the Migration is verified.
_Avoid_: Old system, on-prem DB

**Cutover date**:
The first day (2024-01-01) whose Observations come from the APIs instead of the Legacy source. Observations before it are never written by the Backfill; Observations from it are never written by the Migration.
_Avoid_: Split date, switch date

**Migration**:
The one-time, repeatable transfer of all Observations from the Legacy source to Fabric, verified by reconciliation. Migrated rows carry `source = legacy`.
_Avoid_: Backfill, import

**Refresh window**:
The 7 days before today plus today itself, which every refresh run fetches again from the Forecast API, because the historical API lags about 5 days. Each hour carries a source: `forecast` (not over yet), `provisional` (over, not final), or `archive` (final, from the historical API).
_Avoid_: Incremental window, lookback

**Model PM2.5**:
A PM2.5 value produced by the CAMS model on a roughly 45 km grid, not measured at a station.
_Avoid_: Measured air quality, sensor reading

**Province**:
A province-level administrative unit in the 34-province structure that applies after the 2025 merger.
_Avoid_: The old 63-province units
