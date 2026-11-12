import io
import json
from urllib.error import HTTPError

import pytest

import http_json

URL = "https://example.test/data"


def http_error(code):
    return HTTPError(URL, code, "error", {}, None)


def scripted_urlopen(outcomes):
    """Return a fake urlopen that yields each outcome in turn (an exception is raised)."""
    remaining = list(outcomes)

    def fake_urlopen(_url, timeout):
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(json.dumps(outcome).encode())

    return fake_urlopen


def test_get_json_returns_decoded_body(monkeypatch):
    monkeypatch.setattr(http_json, "urlopen", scripted_urlopen([{"ok": 1}]))
    assert http_json.get_json(URL) == {"ok": 1}


def test_get_json_retries_rate_limit_with_exponential_backoff(monkeypatch):
    monkeypatch.setattr(
        http_json, "urlopen", scripted_urlopen([http_error(429), http_error(503), {"ok": 1}])
    )
    waits = []
    result = http_json.get_json(URL, attempts=3, base_delay=2, sleep=waits.append)
    assert result == {"ok": 1}
    assert waits == [2, 4]


def test_get_json_retries_network_errors(monkeypatch):
    monkeypatch.setattr(http_json, "urlopen", scripted_urlopen([OSError("reset"), [1, 2]]))
    assert http_json.get_json(URL, sleep=lambda _seconds: None) == [1, 2]


def test_get_json_gives_up_after_all_attempts(monkeypatch):
    monkeypatch.setattr(http_json, "urlopen", scripted_urlopen([http_error(500)] * 3))
    with pytest.raises(http_json.HttpJsonError, match="3 attempt"):
        http_json.get_json(URL, attempts=3, sleep=lambda _seconds: None)


def test_get_json_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr(http_json, "urlopen", scripted_urlopen([http_error(404)]))
    waits = []
    with pytest.raises(http_json.HttpJsonError, match="HTTP 404"):
        http_json.get_json(URL, sleep=waits.append)
    assert waits == []


def test_get_json_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(http_json, "urlopen", lambda _url, timeout: io.BytesIO(b"not json"))
    with pytest.raises(http_json.HttpJsonError, match="not valid JSON"):
        http_json.get_json(URL)


def test_get_json_rejects_zero_attempts():
    with pytest.raises(ValueError):
        http_json.get_json(URL, attempts=0)
