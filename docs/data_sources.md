# Vietnam-related API data sources

Checked on: 2026-11-12 (the research agent called each endpoint with curl). [UNVERIFIED] means it could not be checked and nothing was guessed.

## Chosen sources

### Open-Meteo (batch + near-real-time)
- Docs: open-meteo.com/en/docs, /en/docs/air-quality-api, /en/docs/historical-weather-api
- No API key required
- Free tier limits: < 10,000 calls/day, 5,000/hour, 600/minute; no uptime guarantee
- License: free API is non-commercial only, data is CC BY 4.0 (attribution required)
- Historical weather (`archive-api.open-meteo.com/v1/archive`): hourly, available since 1940
- Air quality (`air-quality-api.open-meteo.com`): hourly PM2.5, available since 2022-09 (CAMS Global ~45 km; model data, not station measurements)
- Current (`api.open-meteo.com/v1/forecast`): updated every 900 s; plan is to poll every 2 hours and send to an Eventstream (micro-batch, not a true stream)
- Response is columnar (a `time` array plus value arrays); coordinates are snapped to a grid; default timezone is GMT (`Asia/Ho_Chi_Minh` not tested)
- Planned cities: one representative City per Province (34), see `config/cities.json`

### Dimension / enrichment
- provinces.open-api.vn: use `/api/v1/` (63 old provinces) or v2 (34 provinces after the 2025 merger). Community-run; SLA and license [UNVERIFIED]
- World Bank API (`api.worldbank.org/v2/country/VNM/indicator/...`): no key, JSON, paginated, yearly data. License CC BY 4.0 [UNVERIFIED]

## Alternatives considered

| Source | Result | Notes |
|---|---|---|
| Wikimedia vi.wikipedia Pageviews + EventStreams | OK | No key. viwiki has ~3 events/minute. Fabric Eventstream has no built-in SSE connector. Pageviews license [UNVERIFIED] |
| OpenSky (Vietnam airspace bbox) | OK (anonymous) | True real-time via polling, no history. Terms [UNVERIFIED] |
| USGS Earthquake (Vietnam bbox) | OK | Very few events, not suitable as a main source |
| VNDirect finfo, SSI iboard | OK, no key | Unofficial, may be blocked or changed. ToS [UNVERIFIED] |
| SSI FastConnect Data | Needs an account | Official API with streaming. Details [UNVERIFIED] |
| OpenAQ v3 | Needs an API key | v2 is retired. Vietnam coverage [UNVERIFIED] |
| OSM Overpass | OK | ODbL, usable as a dimension, can be slow |
| VnExpress / Tuoi Tre RSS | OK | Store metadata only. Content copyright [UNVERIFIED] |
| GDELT DOC API | OK | At most 1 request per 5 seconds. License [UNVERIFIED] |

## Avoid
- WAQI/AQICN: terms forbid storing or archiving its data
- SJC, TCBS: blocked by Cloudflare
- data.gov.vn, GSO/NSO, SBV: unreachable or no API found
- Vietcombank XML: limited to 1 request per 5 minutes, no history, unofficial

## To verify before publishing
- License of Wikimedia pageviews data (if used)
- ToS of Vietcombank / VNDirect / SSI (if used)
- OpenSky and Overpass limits; exact Wikimedia and OpenAQ rate limits
