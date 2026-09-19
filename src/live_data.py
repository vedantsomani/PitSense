"""Bounded API snapshots. No synthetic or historical data is labelled live."""
from datetime import datetime, timedelta, timezone
import math
import threading
import time

import requests

UTC = timezone.utc
_request_lock = threading.Lock()
_last_request = 0.0


class FeedError(RuntimeError):
    pass


def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def utc_now():
    return datetime.now(UTC)


def latest(rows, field="date"):
    return max(rows, key=lambda row: timestamp(row.get(field)) or datetime.min.replace(tzinfo=UTC), default={})


def latest_by_driver(rows):
    grouped = {}
    for row in sorted(rows, key=lambda r: timestamp(r.get("date")) or datetime.min.replace(tzinfo=UTC)):
        grouped[row.get("driver_number")] = row
    return grouped


def feed_status(session, sample_date, authenticated, now=None):
    now = now or utc_now()
    start, end, sample = timestamp(session.get("date_start")), timestamp(session.get("date_end")), timestamp(sample_date)
    if not start or not end:
        return "UNKNOWN SESSION TIME"
    if now < start:
        return "SCHEDULED · not started"
    if now > end:
        return "HISTORICAL · session ended"
    if not authenticated:
        return "LIVE ACCESS REQUIRES AUTHENTICATION"
    if not sample or not -5 <= (now - sample).total_seconds() <= 60:
        return "STALE / NO RECENT TELEMETRY"
    return "LIVE · recent telemetry"


class OpenF1:
    def __init__(self, token="", http=None):
        self.token = token
        self.http = http or requests.Session()

    def get(self, endpoint, **params):
        global _last_request
        # requests supplies '=' between key/value: date< becomes date<=value.
        params = {key.rstrip("="): value for key, value in params.items()}
        # Share pacing across sessions; avoid bursts against the public API.
        with _request_lock:
            delay = max(0, 0.4 - (time.monotonic() - _last_request))
            if delay:
                time.sleep(delay)
            _last_request = time.monotonic()
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = self.http.get(f"https://api.openf1.org/v1/{endpoint}", params=params,
                                     headers=headers, timeout=(3, 10))
            if response.status_code in (401, 403):
                raise FeedError("OpenF1 access denied. Live data needs a subscribed account and a valid access token.")
            if response.status_code == 429:
                raise FeedError("OpenF1 rate limit reached. Wait before refreshing.")
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise FeedError("OpenF1 returned an unexpected response.")
            return result
        except (requests.RequestException, ValueError) as exc:
            # Do not include request objects, headers, tokens or provider response bodies.
            raise FeedError(f"OpenF1 {endpoint} is unavailable. Try again later.") from None

    def snapshot(self, session, driver, cursor):
        key = int(session["session_key"])
        end = cursor.isoformat()
        start = timestamp(session["date_start"])
        queries = {
            "car_data": {"driver_number": driver, "date>": (cursor - timedelta(seconds=45)).isoformat(), "date<=": end},
            "location": {"driver_number": driver, "date>": (cursor - timedelta(seconds=45)).isoformat(), "date<=": end},
            "weather": {"date>": (cursor - timedelta(minutes=10)).isoformat(), "date<=": end},
            "position": {"date>": (cursor - timedelta(minutes=3)).isoformat(), "date<=": end},
            "intervals": {"date>": (cursor - timedelta(minutes=3)).isoformat(), "date<=": end},
            "laps": {"driver_number": driver, "date_start>=": start.isoformat(), "date_start<=": end},
            "stints": {"driver_number": driver},
            "pit": {"date>": (cursor - timedelta(minutes=10)).isoformat(), "date<=": end},
            "race_control": {"date>": (cursor - timedelta(minutes=10)).isoformat(), "date<=": end},
        }
        result = {"session": session, "cursor": end, "fetched_at": utc_now().isoformat(), "errors": {}}
        for endpoint, params in queries.items():
            try:
                result[endpoint] = self.get(endpoint, session_key=key, **params)
            except FeedError as exc:
                result[endpoint] = []
                result["errors"][endpoint] = str(exc)
                # Do not issue more requests after authentication/rate/network failures.
                for remaining in queries.keys() - result.keys():
                    result[remaining] = []
                    result["errors"][remaining] = "Not fetched after a feed error."
                break
        # Completed laps only: historical records may describe a lap which ends after the cursor.
        result["laps"] = [lap for lap in result["laps"]
                          if timestamp(lap.get("date_start")) and lap.get("lap_duration") is not None
                          and timestamp(lap["date_start"]) + timedelta(seconds=float(lap["lap_duration"])) <= cursor]
        completed = max((int(lap["lap_number"]) for lap in result["laps"]), default=0)
        # Avoid future stint ends leaking into historical snapshots.
        result["stints"] = [{k: v for k, v in row.items() if k != "lap_end"}
                            for row in result["stints"] if row.get("lap_start", math.inf) <= completed + 1]
        return result


def current_weather(latitude, longitude, http=None):
    try:
        response = (http or requests).get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude, "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,weather_code",
            "hourly": "temperature_2m,precipitation_probability,precipitation",
            "forecast_days": 2, "timezone": "UTC", "wind_speed_unit": "ms",
        }, timeout=(3, 10))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data.get("current"), dict) or not data["current"].get("time"):
            raise FeedError("Open-Meteo returned no current conditions.")
        data["fetched_at"] = utc_now().isoformat()
        return data
    except (requests.RequestException, ValueError):
        raise FeedError("Open-Meteo is unavailable. No replacement weather has been invented.") from None
