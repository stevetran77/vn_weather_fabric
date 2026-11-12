import pytest

import provinces
from http_json import HttpJsonError

API_PROVINCES = [
    {"code": 1, "name": "Thành phố Hà Nội", "division_type": "x"},
    {"code": 56, "name": "Tỉnh Khánh Hòa", "division_type": "x"},
]
HANOI = {"province_code": 1, "name": "Hanoi", "latitude": 21.0245, "longitude": 105.84117}
NHA_TRANG = {"province_code": 56, "name": "Nha Trang", "latitude": 12.2, "longitude": 109.2}


def test_fetch_provinces_returns_list_from_api():
    assert provinces.fetch_provinces(fetch=lambda _url: API_PROVINCES) == API_PROVINCES


def test_fetch_provinces_requests_the_v2_url():
    urls = []
    provinces.fetch_provinces(fetch=lambda url: urls.append(url) or API_PROVINCES)
    assert urls == [provinces.PROVINCES_URL]


def test_fetch_provinces_wraps_http_errors():
    def fail(_url):
        raise HttpJsonError("down")

    with pytest.raises(provinces.ProvinceError):
        provinces.fetch_provinces(fetch=fail)


def test_fetch_provinces_rejects_unexpected_payload():
    with pytest.raises(provinces.ProvinceError):
        provinces.fetch_provinces(fetch=lambda _url: {"error": "x"})
    with pytest.raises(provinces.ProvinceError):
        provinces.fetch_provinces(fetch=lambda _url: [])


def test_build_dim_city_maps_city_to_province():
    rows = provinces.build_dim_city([HANOI, NHA_TRANG], API_PROVINCES)
    assert rows[1] == {
        "city_id": 56,
        "city_name": "Nha Trang",
        "latitude": 12.2,
        "longitude": 109.2,
        "province_code": 56,
        "province_name": "Tỉnh Khánh Hòa",
    }


def test_build_dim_city_reports_unknown_province_codes():
    unknown = {**HANOI, "province_code": 999}
    with pytest.raises(provinces.ProvinceError, match="999"):
        provinces.build_dim_city([HANOI, unknown], API_PROVINCES)
