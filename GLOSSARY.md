# vn_weather_fabric

Weather and air quality data for Vietnamese cities, loaded into Microsoft Fabric as a batch history plus a near-real-time snapshot feed.

## Language

**City**:
A Vietnamese city from the configured list whose weather and air quality are tracked.
_Avoid_: Location, station, site

**Observation**:
An hourly record of weather and PM2.5 for one City at one hour, taken from the historical API.
_Avoid_: Measurement, record

**Reading**:
A snapshot of the current conditions of one City, fetched every 2 hours from the `current` endpoint.
_Avoid_: Observation, event, sample

**Backfill**:
The one-time load of all historical Observations from 2022-09-01.
_Avoid_: Initial import, history load

**Refresh window**:
The most recent 7 days that every daily run fetches again from the Forecast API, because the historical API lags about 5 days.
_Avoid_: Incremental window, lookback

**Model PM2.5**:
A PM2.5 value produced by the CAMS model on a roughly 45 km grid, not measured at a station.
_Avoid_: Measured air quality, sensor reading

**Province**:
A province-level administrative unit in the 34-province structure that applies after the 2025 merger.
_Avoid_: The old 63-province units
