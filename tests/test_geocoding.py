import io
import json

import pytest

import geocoding

HANOI = {
    "name": "Hanoi", "feature_code": "PPLC", "country_code": "VN",
    "population": 8053663, "latitude": 21.0245, "longitude": 105.84117,
}
HANOI_WARD = {
    "name": "Hanoi", "feature_code": "PPLA2", "country_code": "VN",
    "latitude": 20.32773, "longitude": 106.01208,
}
AIRPORT = {
    "name": "Hanoi / Gialam", "feature_code": "AIRP", "country_code": "VN",
    "latitude": 21.04, "longitude": 105.88,
}
SMALL_TOWN = {
    "name": "Bach Mai", "feature_code": "PPL", "country_code": "VN",
    "population": 91308, "latitude": 20.98, "longitude": 105.83,
}
CITY_CONFIG = {"province_code": 1, "name": "Hanoi", "search_name": "Hanoi"}


def test_pick_city_chooses_highest_population():
    assert geocoding.pick_city([SMALL_TOWN, HANOI]) is HANOI


def test_pick_city_skips_places_without_population_and_airports():
    assert geocoding.pick_city([HANOI_WARD, AIRPORT]) is None


def test_pick_city_skips_other_countries():
    foreign = {**HANOI, "country_code": "TH"}
    assert geocoding.pick_city([foreign]) is None


def test_pick_city_empty_results():
    assert geocoding.pick_city([]) is None


def test_build_search_url_restricts_to_vietnam():
    url = geocoding.build_search_url("Ho Chi Minh City")
    assert url.startswith(geocoding.GEOCODING_URL)
    assert "countryCode=VN" in url
    assert "name=Ho+Chi+Minh+City" in url


def test_resolve_city_returns_coordinates():
    resolved = geocoding.resolve_city(CITY_CONFIG, fetch=lambda _name: [HANOI_WARD, HANOI])
    assert resolved["name"] == "Hanoi"
    assert resolved["province_code"] == 1
    assert resolved["latitude"] == 21.0245
    assert resolved["longitude"] == 105.84117


def test_resolve_city_rejects_wrong_place():
    with pytest.raises(geocoding.GeocodingError):
        geocoding.resolve_city(CITY_CONFIG, fetch=lambda _name: [HANOI_WARD, AIRPORT])


def test_resolve_city_wraps_network_error():
    def failing_fetch(_name):
        raise OSError("network down")

    with pytest.raises(geocoding.GeocodingError, match="network down"):
        geocoding.resolve_city(CITY_CONFIG, fetch=failing_fetch)


def test_resolve_all_resolves_each_city():
    cities = [CITY_CONFIG, {"province_code": 2, "name": "Other", "search_name": "Other"}]
    resolved = geocoding.resolve_all(cities, fetch=lambda _name: [HANOI])
    assert [city["name"] for city in resolved] == ["Hanoi", "Other"]


def test_load_cities_reads_config(tmp_path):
    path = tmp_path / "cities.json"
    path.write_text(json.dumps({"cities": [CITY_CONFIG]}), encoding="utf-8")
    assert geocoding.load_cities(path) == [CITY_CONFIG]


def test_default_config_lists_one_city_per_province():
    cities = geocoding.load_cities()
    codes = [city["province_code"] for city in cities]
    assert len(cities) == 34
    assert len(set(codes)) == 34
    assert len({city["name"] for city in cities}) == 34


def test_fetch_results_parses_response(monkeypatch):
    body = io.BytesIO(json.dumps({"results": [HANOI]}).encode("utf-8"))
    monkeypatch.setattr(geocoding, "urlopen", lambda url, timeout: body)
    assert geocoding.fetch_results("Hanoi") == [HANOI]


def test_fetch_results_handles_no_match(monkeypatch):
    body = io.BytesIO(json.dumps({"generationtime_ms": 0.2}).encode("utf-8"))
    monkeypatch.setattr(geocoding, "urlopen", lambda url, timeout: body)
    assert geocoding.fetch_results("Nowhere") == []


def test_format_table_lists_each_city():
    resolved = [
        {"province_code": 1, "name": "Hanoi", "latitude": 21.0245, "longitude": 105.84117,
         "population": 8053663, "feature_code": "PPLC"}
    ]
    table = geocoding.format_table(resolved)
    assert "Hanoi" in table
    assert "21.0245" in table


def test_main_reports_failure(monkeypatch, capsys):
    def failing_resolve_all(_cities):
        raise geocoding.GeocodingError("boom")

    monkeypatch.setattr(geocoding, "load_cities", lambda: [CITY_CONFIG])
    monkeypatch.setattr(geocoding, "resolve_all", failing_resolve_all)
    assert geocoding.main() == 1
    assert "[FAIL] boom" in capsys.readouterr().out


def test_main_prints_table_on_success(monkeypatch, capsys):
    resolved = [
        {"province_code": 1, "name": "Hanoi", "latitude": 21.0245, "longitude": 105.84117,
         "population": 8053663, "feature_code": "PPLC"}
    ]
    monkeypatch.setattr(geocoding, "load_cities", lambda: [CITY_CONFIG])
    monkeypatch.setattr(geocoding, "resolve_all", lambda _cities: resolved)
    assert geocoding.main() == 0
    assert "[OK] resolved 1 cities" in capsys.readouterr().out
