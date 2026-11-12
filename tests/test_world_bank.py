import json
from pathlib import Path

import pytest

import schemas
import transforms
import world_bank
from http_json import HttpJsonError

POP = {"id": "SP.POP.TOTL", "value": "Population, total"}


def raw(year, value, indicator=POP):
    return {"indicator": indicator, "countryiso3code": "VNM", "date": str(year), "value": value}


def page_body(rows, page, pages, total):
    return [{"page": page, "pages": pages, "per_page": 2, "total": total}, rows]


def paged_fetch(bodies):
    urls = []

    def fetch(url):
        urls.append(url)
        return bodies[len(urls) - 1]

    return fetch, urls


def test_parse_indicator_config_returns_country_and_names():
    config = {"country": "VNM", "indicators": [{"code": "A.B", "name": "a_b"}]}
    assert world_bank.parse_indicator_config(config) == ("VNM", {"A.B": "a_b"})


@pytest.mark.parametrize(
    "config",
    [{}, {"country": "VNM"}, {"country": "VNM", "indicators": []},
     {"country": "VNM", "indicators": [{"code": "A"}]}, None],
)
def test_parse_indicator_config_rejects_bad_config(config):
    with pytest.raises(world_bank.WorldBankError):
        world_bank.parse_indicator_config(config)


def test_the_repo_config_file_is_valid():
    path = Path(__file__).parent.parent / "config" / "indicators.json"
    country, names = world_bank.parse_indicator_config(json.loads(path.read_text()))
    assert country == "VNM"
    assert len(names) == len(set(names.values())) >= 1


def test_build_indicator_url():
    assert world_bank.build_indicator_url("VNM", "SP.POP.TOTL", 2, 50) == (
        "https://api.worldbank.org/v2/country/VNM/indicator/SP.POP.TOTL"
        "?format=json&per_page=50&page=2"
    )


def test_fetch_indicator_reads_all_pages_in_order():
    fetch, urls = paged_fetch([
        page_body([raw(2024, 3.0), raw(2023, 2.0)], 1, 2, 3),
        page_body([raw(2022, 1.0)], 2, 2, 3),
    ])
    rows = world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=fetch, per_page=2)
    assert [row["date"] for row in rows] == ["2024", "2023", "2022"]
    assert len(urls) == 2
    assert "page=1" in urls[0] and "page=2" in urls[1]


def test_fetch_indicator_with_one_page_makes_one_request():
    fetch, urls = paged_fetch([page_body([raw(2024, 1.0)], 1, 1, 1)])
    assert len(world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=fetch)) == 1
    assert len(urls) == 1


def test_fetch_indicator_handles_a_response_without_rows():
    fetch, _ = paged_fetch([page_body(None, 1, 0, 0)])
    assert world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=fetch) == []


def test_fetch_indicator_fails_when_rows_differ_from_total():
    fetch, _ = paged_fetch([page_body([raw(2024, 1.0)], 1, 1, 5)])
    with pytest.raises(world_bank.WorldBankError, match="reports 5"):
        world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=fetch)


def test_fetch_indicator_wraps_http_errors_and_names_the_page():
    fetch, _ = paged_fetch([page_body([raw(2024, 1.0)], 1, 2, 2)])

    def flaky(url):
        if "page=2" in url:
            raise HttpJsonError("HTTP 502")
        return fetch(url)

    with pytest.raises(world_bank.WorldBankError, match="page 2"):
        world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=flaky, per_page=1)


def test_fetch_indicator_reports_the_api_error_body():
    body = [{"message": [{"id": "120", "key": "Invalid value"}]}]
    with pytest.raises(world_bank.WorldBankError, match="Invalid value"):
        world_bank.fetch_indicator("VNM", "BAD", fetch=lambda _url: body)


@pytest.mark.parametrize("body", [{}, [], [{"pages": 1}], [{"pages": "x", "total": 1}, []]])
def test_fetch_indicator_rejects_unexpected_shapes(body):
    with pytest.raises(world_bank.WorldBankError):
        world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=lambda _url: body)


def test_to_bronze_rows_keeps_raw_values_and_adds_ingest_date():
    rows = world_bank.to_bronze_rows([raw(2024, 100), raw(2025, None)], "2026-11-12")
    assert rows[0] == {
        "country_code": "VNM", "indicator_code": "SP.POP.TOTL",
        "indicator_name": "Population, total", "date": "2024", "value": 100.0,
        "ingest_date": "2026-11-12",
    }
    assert rows[1]["value"] is None


def test_bronze_rows_match_the_bronze_ddl():
    row = world_bank.to_bronze_rows([raw(2024, 1)], "2026-11-12")[0]
    assert set(row) == set(schemas.column_names(schemas.BRONZE_INDICATOR_DDL))


def test_build_silver_rows_drops_null_years_and_sorts():
    bronze = world_bank.to_bronze_rows([raw(2024, 3), raw(2025, None), raw(2023, 2)], "d")
    rows = world_bank.build_silver_rows(bronze)
    assert [(row["year"], row["value"]) for row in rows] == [(2023, 2.0), (2024, 3.0)]


def test_build_silver_rows_collapses_duplicate_keys_last_wins():
    bronze = world_bank.to_bronze_rows([raw(2024, 1), raw(2024, 9)], "d")
    rows = world_bank.build_silver_rows(bronze)
    assert [(row["year"], row["value"]) for row in rows] == [(2024, 9.0)]


def test_silver_and_gold_rows_match_their_ddl():
    silver = world_bank.build_silver_rows(world_bank.to_bronze_rows([raw(2024, 1)], "d"))
    gold = world_bank.build_gold_rows(silver, {"SP.POP.TOTL": "population"})
    assert set(silver[0]) == set(schemas.column_names(schemas.INDICATOR_SILVER_DDL))
    assert set(gold[0]) == set(schemas.column_names(schemas.INDICATOR_GOLD_DDL))
    assert gold[0]["indicator_name"] == "population"


def test_build_gold_rows_rejects_an_indicator_missing_from_the_config():
    silver = world_bank.build_silver_rows(world_bank.to_bronze_rows([raw(2024, 1)], "d"))
    with pytest.raises(world_bank.WorldBankError, match="SP.POP.TOTL"):
        world_bank.build_gold_rows(silver, {"OTHER": "other"})


def test_merge_condition_for_the_indicator_key():
    assert transforms.build_merge_condition(world_bank.KEY_COLUMNS) == (
        "t.country_code = s.country_code AND t.indicator_code = s.indicator_code"
        " AND t.year = s.year"
    )


def test_fetch_indicator_stops_at_the_page_limit():
    def endless(_url):
        return page_body([raw(2024, 1.0)], 1, 10_000, 10_000)

    with pytest.raises(world_bank.WorldBankError, match="more than"):
        world_bank.fetch_indicator("VNM", "SP.POP.TOTL", fetch=endless)


@pytest.mark.parametrize("bad_row", [{"date": "2024"}, {**raw(2024, 1), "value": "n/a"}])
def test_to_bronze_rows_wraps_malformed_rows(bad_row):
    with pytest.raises(world_bank.WorldBankError, match="Malformed"):
        world_bank.to_bronze_rows([bad_row], "d")


def test_build_silver_rows_rejects_a_date_that_is_not_a_year():
    bronze = world_bank.to_bronze_rows([raw("2020Q1", 1.0)], "d")
    with pytest.raises(world_bank.WorldBankError, match="not a year"):
        world_bank.build_silver_rows(bronze)
