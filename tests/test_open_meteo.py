import io
import json

import pytest

import open_meteo

HOURLY = {
    "latitude": 21.0,
    "longitude": 105.8,
    "hourly": {
        "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
        "temperature_2m": [17.5, 17.1],
        "precipitation": [0.0, 0.2],
    },
}


def test_build_weather_url_single_location():
    url = open_meteo.build_weather_url([21.0245], [105.8412], "2024-01-01", "2024-01-07")
    assert url.startswith(open_meteo.ARCHIVE_URL)
    assert "latitude=21.0245" in url
    assert "longitude=105.8412" in url
    assert "start_date=2024-01-01" in url
    assert "end_date=2024-01-07" in url
    assert "timezone=GMT" in url
    assert "hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m" in url


def test_build_weather_url_several_locations_uses_commas():
    url = open_meteo.build_weather_url([21.0, 10.8], [105.8, 106.7], "2024-01-01", "2024-01-07")
    assert "latitude=21.0,10.8" in url
    assert "longitude=105.8,106.7" in url


def test_build_air_quality_url_requests_pm25():
    url = open_meteo.build_air_quality_url([21.0], [105.8], "2024-01-01", "2024-01-07")
    assert url.startswith(open_meteo.AIR_QUALITY_URL)
    assert "hourly=pm2_5" in url


def test_build_url_rejects_mismatched_coordinates():
    with pytest.raises(ValueError):
        open_meteo.build_weather_url([21.0, 10.8], [105.8], "2024-01-01", "2024-01-07")


def test_hourly_to_rows_transposes_columns():
    rows = open_meteo.hourly_to_rows(HOURLY)
    assert rows == [
        {"time": "2024-01-01T00:00", "temperature_2m": 17.5, "precipitation": 0.0},
        {"time": "2024-01-01T01:00", "temperature_2m": 17.1, "precipitation": 0.2},
    ]


def test_hourly_to_rows_rejects_missing_block():
    with pytest.raises(open_meteo.OpenMeteoError):
        open_meteo.hourly_to_rows({"error": True})


def test_hourly_to_rows_rejects_length_mismatch():
    broken = {"hourly": {"time": ["2024-01-01T00:00"], "pm2_5": [1.0, 2.0]}}
    with pytest.raises(open_meteo.OpenMeteoError):
        open_meteo.hourly_to_rows(broken)


def test_split_locations_wraps_single_object():
    assert open_meteo.split_locations(HOURLY) == [HOURLY]


def test_split_locations_keeps_list():
    assert open_meteo.split_locations([HOURLY, HOURLY]) == [HOURLY, HOURLY]


def test_fetch_hourly_returns_rows_per_location():
    locations = open_meteo.fetch_hourly("https://example.test", fetch=lambda _url: [HOURLY, HOURLY])
    assert len(locations) == 2
    assert locations[0][0]["temperature_2m"] == 17.5


def test_fetch_json_decodes_body(monkeypatch):
    body = io.BytesIO(json.dumps(HOURLY).encode())
    monkeypatch.setattr(open_meteo, "urlopen", lambda _url, timeout: body)
    assert open_meteo.fetch_json("https://example.test") == HOURLY


def test_fetch_json_wraps_network_errors(monkeypatch):
    def fail(_url, timeout):
        raise OSError("boom")

    monkeypatch.setattr(open_meteo, "urlopen", fail)
    with pytest.raises(open_meteo.OpenMeteoError):
        open_meteo.fetch_json("https://example.test")
