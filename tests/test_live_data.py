from datetime import timedelta
import json

import pytest
import requests

from src.live_data import OpenF1, FeedError, current_weather, feed_status, timestamp
from src.paths import ROOT

NOW = timestamp("2024-07-07T14:45:00Z")
SESSION = {"session_key": 9558, "date_start": "2024-07-07T14:00:00Z", "date_end": "2024-07-07T16:00:00Z"}


class Response:
    def __init__(self, data, code=200):
        self.data, self.status_code = data, code
    def json(self):
        return self.data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("secret must not leak")


class HTTP:
    def __init__(self, data=None, code=200):
        self.data, self.code, self.calls = data, code, []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        data = self.data.get(url.rsplit('/', 1)[-1], []) if isinstance(self.data, dict) else self.data
        return Response(data, self.code)


@pytest.fixture(autouse=True)
def no_pacing(monkeypatch):
    monkeypatch.setattr("src.live_data.time.sleep", lambda seconds: None)


def test_live_label_needs_fresh_sample_and_auth():
    assert feed_status(SESSION, NOW.isoformat(), True, NOW).startswith("LIVE ·")
    assert "AUTHENTICATION" in feed_status(SESSION, NOW.isoformat(), False, NOW)
    assert "STALE" in feed_status(SESSION, (NOW - timedelta(minutes=2)).isoformat(), True, NOW)
    assert "HISTORICAL" in feed_status(SESSION, NOW.isoformat(), True, NOW + timedelta(days=1))
    assert "SCHEDULED" in feed_status(SESSION, None, True, NOW - timedelta(days=1))


@pytest.mark.parametrize("status,expected", [(401, "access denied"), (403, "access denied"), (429, "rate limit"), (500, "unavailable")])
def test_api_errors_do_not_expose_credentials(status, expected):
    with pytest.raises(FeedError, match=expected) as error:
        OpenF1("super-secret", HTTP([], status)).get("car_data")
    assert "super-secret" not in str(error.value)


def test_headers_and_filters():
    http = HTTP([])
    OpenF1("test-token", http).get("car_data", **{"date<=": NOW.isoformat()})
    _, kwargs = http.calls[0]
    assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
    assert "date<" in kwargs["params"] and "date<=" not in kwargs["params"]
    assert kwargs["timeout"] == (3, 10)


def test_replay_excludes_future_lap_and_stint_information():
    http = HTTP({
        "laps": [{"lap_number": 1, "date_start": "2024-07-07T14:01:00Z", "lap_duration": 90},
                 {"lap_number": 30, "date_start": "2024-07-07T14:44:50Z", "lap_duration": 90}],
        "stints": [{"stint_number": 1, "lap_start": 1, "lap_end": 20},
                   {"stint_number": 2, "lap_start": 21, "lap_end": 52}],
    })
    result = OpenF1(http=http).snapshot(SESSION, 44, NOW)
    assert [lap["lap_number"] for lap in result["laps"]] == [1]
    assert len(result["stints"]) == 1
    assert "lap_end" not in result["stints"][0]
    car_params = http.calls[0][1]["params"]
    assert timestamp(car_params["date<"]) - timestamp(car_params["date>"]) == timedelta(seconds=45)


def test_rate_limit_stops_followup_requests():
    http = HTTP([], 429)
    result = OpenF1(http=http).snapshot(SESSION, 44, NOW)
    assert len(http.calls) == 1
    assert len(result["errors"]) == 9


def test_weather_failure_is_explicit():
    with pytest.raises(FeedError):
        current_weather(52, -1, HTTP({}, 500))


def test_live_page_has_no_automatic_network_calls(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: pytest.fail("Unexpected network request"))
    app = AppTest.from_file(str(ROOT / 'pages/1_Live_Race_Centre.py')).run(timeout=30)
    assert not app.exception
    app.radio[0].set_value("Live session").run()
    assert not app.exception
    assert any("not connected" in warning.value for warning in app.warning)
