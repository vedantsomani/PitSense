"""UI for real API snapshots, independent of the offline simulator."""
from datetime import timedelta
import json
import math
import os

import pandas as pd
import streamlit as st

from src.live_data import OpenF1, FeedError, current_weather, feed_status, latest, latest_by_driver, timestamp, utc_now
from src.paths import ROOT
from simulator.race_context import get_race_context
from simulator.stint_predictor import StintPredictor

CIRCUIT_GP = {
    "Silverstone": "British Grand Prix", "Sakhir": "Bahrain Grand Prix",
    "Jeddah": "Saudi Arabian Grand Prix", "Melbourne": "Australian Grand Prix",
    "Baku": "Azerbaijan Grand Prix", "Miami": "Miami Grand Prix", "Monte Carlo": "Monaco Grand Prix",
    "Catalunya": "Spanish Grand Prix", "Montreal": "Canadian Grand Prix", "Spielberg": "Austrian Grand Prix",
    "Hungaroring": "Hungarian Grand Prix", "Spa-Francorchamps": "Belgian Grand Prix",
    "Zandvoort": "Dutch Grand Prix", "Monza": "Italian Grand Prix", "Marina Bay": "Singapore Grand Prix",
    "Suzuka": "Japanese Grand Prix", "Lusail": "Qatar Grand Prix", "Austin": "United States Grand Prix",
    "Mexico City": "Mexico City Grand Prix", "Interlagos": "São Paulo Grand Prix",
    "Las Vegas": "Las Vegas Grand Prix", "Yas Marina Circuit": "Abu Dhabi Grand Prix",
}


def configured_token():
    value = os.getenv("OPENF1_ACCESS_TOKEN", "")
    if value:
        return value.strip()
    try:
        return str(st.secrets.get("OPENF1_ACCESS_TOKEN", "")).strip()
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


@st.cache_data(ttl=300, show_spinner=False)
def sessions(year, token):
    return OpenF1(token).get("sessions", year=year)


@st.cache_data(ttl=300, show_spinner=False)
def drivers(session_key, token):
    return OpenF1(token).get("drivers", session_key=session_key)


@st.cache_data(ttl=30, show_spinner=False)
def snapshot(session_json, driver, cursor_iso, token):
    return OpenF1(token).snapshot(json.loads(session_json), driver, timestamp(cursor_iso))


@st.cache_data(ttl=600, show_spinner=False)
def weather(lat, lon):
    return current_weather(lat, lon)


def render_weather():
    st.subheader("Current circuit weather & forecast")
    circuits = json.loads((ROOT / "datasets/circuit_coordinates.json").read_text(encoding="utf-8"))
    ids = [row["circuitId"] for row in circuits]
    chosen = st.selectbox("Weather circuit (independent of session selection)", ids, index=ids.index("silverstone"),
                          format_func=lambda value: next(row["circuitName"] for row in circuits if row["circuitId"] == value))
    row = next(row for row in circuits if row["circuitId"] == chosen)
    if st.button("Fetch current weather"):
        try:
            st.session_state["circuit_weather"] = {"circuit": row, "data": weather(float(row["Location"]["lat"]), float(row["Location"]["long"]))}
        except FeedError as exc:
            st.error(str(exc))
    saved = st.session_state.get("circuit_weather")
    if saved and saved["circuit"]["circuitId"] == chosen:
        data, current = saved["data"], saved["data"]["current"]
        st.caption(f'Open-Meteo model estimate · valid {current["time"]} UTC · fetched {data["fetched_at"]} · cache 10 min')
        a, b, c = st.columns(3)
        a.metric("Air · °C", current.get("temperature_2m", "—"))
        b.metric("Wind · m/s", current.get("wind_speed_10m", "—"))
        c.metric("Precipitation · mm", current.get("precipitation", "—"))
        forecast = pd.DataFrame(data.get("hourly", {}))
        if not forecast.empty:
            forecast["time"] = pd.to_datetime(forecast["time"], utc=True)
            forecast = forecast[forecast.time >= utc_now()].head(24)
            st.dataframe(forecast, hide_index=True, width="stretch")
        st.caption("This forecast is for today, even when viewing an old race. It is not track temperature and is not silently substituted into historical simulation.")
    st.markdown("Sources: [Open-Meteo weather](https://open-meteo.com/) · [Jolpica circuit coordinates](https://api.jolpi.ca/ergast/f1/2024/circuits.json)")


def display_snapshot(data, driver, authenticated, live_mode, race_laps):
    session = data["session"]
    car = latest(data["car_data"])
    label = feed_status(session, car.get("date"), authenticated) if live_mode else "HISTORICAL SNAPSHOT · not live"
    st.subheader(label)
    st.caption(f'Session {session["session_key"]} · snapshot cutoff {data["cursor"]} · fetched {data["fetched_at"]}')
    for endpoint, message in data["errors"].items():
        st.warning(f"{endpoint}: {message}")
    if car:
        st.caption(f'Selected car #{driver} · sensor timestamp {car["date"]}')
        cols = st.columns(2)
        for i, (name, unit) in enumerate(zip(["speed", "rpm", "throttle", "n_gear"], ["Speed · km/h", "RPM", "Throttle · %", "Gear"])):
            cols[i % 2].metric(unit, car.get(name, "—"))
        chart = pd.DataFrame(data["car_data"])
        chart["date"] = pd.to_datetime(chart.date, utc=True)
        st.line_chart(chart.set_index("date")[["speed"]], width="stretch")
        st.caption(f'Brake: {car.get("brake", "—")} · DRS code: {car.get("drs", "—")} · 45-second telemetry window')
    else:
        st.info("No car telemetry in this snapshot window. No previous car sample has been substituted.")

    positions, gaps = latest_by_driver(data["position"]), latest_by_driver(data["intervals"])
    table = [{"Driver": number, "Position": row.get("position"), "Gap to leader": str(gaps.get(number, {}).get("gap_to_leader", "—")),
              "Interval": str(gaps.get(number, {}).get("interval", "—")), "Position timestamp": row.get("date"),
              "Gap timestamp": gaps.get(number, {}).get("date")} for number, row in positions.items()]
    st.subheader("Timing tower · last 3 minutes of updates")
    if table:
        st.dataframe(pd.DataFrame(table).sort_values("Position"), hide_index=True, width="stretch")
    else:
        st.caption("No timing updates. Gaps are only available for races.")
    track_weather = latest(data["weather"])
    st.subheader("Track weather sensors")
    if track_weather:
        st.dataframe(pd.DataFrame([track_weather]), hide_index=True, width="stretch")
    else:
        st.caption("No track-weather observation in the last 10 minutes.")

    st.subheader("Tyres & completed laps · selected driver")
    if data["stints"]:
        st.dataframe(pd.DataFrame(data["stints"]), hide_index=True, width="stretch")
    if data["laps"]:
        columns = ["lap_number", "lap_duration", "duration_sector_1", "duration_sector_2", "duration_sector_3", "is_pit_out_lap"]
        frame = pd.DataFrame(data["laps"]).sort_values("lap_number").tail(10)
        st.dataframe(frame[[c for c in columns if c in frame]], hide_index=True, width="stretch")
    for endpoint, title in [("pit", "Pit stops"), ("race_control", "Race control / flags")]:
        with st.expander(f"{title} · last 10 minutes"):
            if data[endpoint]:
                st.dataframe(pd.DataFrame(data[endpoint]), hide_index=True, width="stretch")
            else:
                st.write("No events received in this window.")
    with st.expander("Car location trace · provider coordinates, not GPS"):
        if data["location"]:
            frame = pd.DataFrame(data["location"])
            st.scatter_chart(frame, x="x", y="y", width="stretch")
        else:
            st.write("No location samples in this window.")
    model_from_snapshot(data, race_laps, live_mode, label)
    st.download_button("Download API snapshot", json.dumps(data, indent=2), "race_snapshot.json", "application/json")


def model_from_snapshot(data, race_laps, live_mode, label):
    st.subheader("ML estimate using this session's inputs")
    session, observed = data["session"], latest(data["weather"])
    gp = CIRCUIT_GP.get(session.get("circuit_short_name"))
    if not gp or not observed or not data["laps"]:
        st.info("ML estimate needs a supported circuit, track-weather observation and completed driver lap.")
        return
    try:
        valid_temperatures = all(math.isfinite(float(observed[field])) for field in ["air_temperature", "track_temperature"])
    except (KeyError, TypeError, ValueError):
        valid_temperatures = False
    if not valid_temperatures:
        st.info("ML estimate paused: the weather feed has missing or invalid temperatures.")
        return
    if live_mode and not label.startswith("LIVE ·"):
        st.info("Live ML estimate paused because telemetry is not current.")
        return
    if session.get("session_type") != "Race":
        st.info("This model estimates race stints; practice and qualifying telemetry are view-only.")
        return
    if observed.get("rainfall"):
        st.warning("Rain is reported. Dry-compound estimates are disabled.")
        return
    lap = max(int(row["lap_number"]) for row in data["laps"])
    if lap >= race_laps:
        st.info("No remaining laps under the configured race distance.")
        return
    context = get_race_context(int(session["year"]), gp)
    predictor = StintPredictor()
    rows = []
    for compound in ["SOFT", "MEDIUM", "HARD"]:
        prediction = predictor.predict_stint_length(
            GP=gp, compound=compound, air_temp=observed["air_temperature"], track_temp=observed["track_temperature"],
            season=int(session["year"]), race_progress=lap / race_laps, circuit_type=context["circuit_type"],
            track_length=context["track_length"], track_abrasiveness=context["track_abrasiveness"],
            average_corner_speed=context["average_corner_speed"], fresh_tyre=1,
        )
        rows.append({"New fresh compound": compound, "Model stint estimate · laps": prediction,
                     "Within remaining lap budget": max(1, min(round(prediction), race_laps - lap))})
    st.caption(f'{gp} · completed lap {lap}/{race_laps} · air {observed["air_temperature"]} °C · track {observed["track_temperature"]} °C · weather timestamp {observed["date"]}')
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("XGBoost now receives observed session weather and race progress. These are prospective fresh-tyre stint estimates, not remaining life of the fitted tyre or a pit-now recommendation. Speed/RPM/gaps are displayed but are not features of this trained model. Future flag counts remain zero; incident and wet-race strategy is not modelled.")
    if int(session["year"]) not in (2023, 2024):
        st.warning("This season is outside the model's 2023–2024 training period; accuracy has not been validated.")


def render_live_page():
    st.title("Live Race Centre")
    st.write("Actual API data for cars, timing, tyres and weather. Every snapshot has a source time.")
    token = configured_token()
    with st.expander("Connect live access"):
        st.write("OpenF1 historical data is public. Live telemetry requires an OpenF1 subscription and OAuth access token.")
        typed = st.text_input("OpenF1 access token (kept in this session only)", type="password", key="openf1_token")
        token = typed.strip() or token
        st.caption("Or set OPENF1_ACCESS_TOKEN in .streamlit/secrets.toml / the environment. No token is written into exports or logs. Replace expired tokens here.")
        st.markdown("[OpenF1 authentication guide](https://openf1.org/auth.html)")
    mode = st.radio("Feed mode", ["Historical API snapshot", "Live session"], horizontal=True)
    live_mode = mode == "Live session"
    year = st.number_input("Session year", min_value=2023, max_value=utc_now().year, value=2024 if not live_mode else utc_now().year)
    if live_mode and not token:
        st.warning("Live telemetry is not connected: add an OpenF1 access token above. Free circuit weather is available below.")
    elif st.button("Load sessions"):
        try:
            st.session_state["feed_sessions"] = {"year": year, "mode": mode, "rows": sessions(year, token)}
        except FeedError as exc:
            st.error(str(exc))
    available = st.session_state.get("feed_sessions", {})
    rows = available.get("rows", []) if available.get("year") == year and available.get("mode") == mode else []
    if rows and (not live_mode or token):
        rows = sorted(rows, key=lambda row: row["date_start"], reverse=True)
        default_session = next((i for i, row in enumerate(rows) if timestamp(row["date_start"]) <= utc_now()), 0) if live_mode else 0
        selected = st.selectbox("Session", range(len(rows)), index=default_session, format_func=lambda i:
                                f'{rows[i]["date_start"][:10]} · {rows[i]["circuit_short_name"]} · {rows[i]["session_name"]}')
        session = rows[selected]
        try:
            roster = drivers(session["session_key"], token)
        except FeedError as exc:
            st.error(str(exc))
            roster = []
        if roster:
            driver = st.selectbox("Driver", [row["driver_number"] for row in roster],
                                  format_func=lambda number: next(f'{row["full_name"]} · #{number} · {row["team_name"]}' for row in roster if row["driver_number"] == number))
            start, end = timestamp(session["date_start"]), timestamp(session["date_end"])
            if not live_mode:
                duration = max(1, int((end - start).total_seconds() / 60))
                minute = st.slider("Snapshot minute after scheduled session start", 0, duration, min(45, duration))
                cursor = start + timedelta(minutes=minute)
            else:
                cursor = utc_now()
            gp = CIRCUIT_GP.get(session.get("circuit_short_name"))
            laps = get_race_context(int(year), gp)["race_laps"] if gp else 52
            race_laps = int(st.number_input("Race distance for ML estimate (verify for selected event)", 1, 100, laps))
            auto = st.toggle("Auto-refresh every 30 seconds", value=False, disabled=not live_mode)

            @st.fragment(run_every="30s" if auto and live_mode else None)
            def live_panel():
                if st.button("Fetch / refresh race snapshot") or auto:
                    cutoff = utc_now() if live_mode else cursor
                    with st.spinner("Fetching bounded API windows…"):
                        data = snapshot(json.dumps(session, sort_keys=True), driver, cutoff.isoformat(), token)
                    st.session_state["feed_snapshot"] = {"selection": (session["session_key"], driver, mode, None if live_mode else cursor.isoformat()), "data": data}
                saved = st.session_state.get("feed_snapshot")
                selection = (session["session_key"], driver, mode, None if live_mode else cursor.isoformat())
                if saved and saved["selection"] == selection:
                    display_snapshot(saved["data"], driver, bool(token), live_mode, race_laps)
            live_panel()
            st.caption("Live mode polls REST every 30 seconds when enabled; it is not a subsecond stream. No session running means no live car data. A failed feed is shown explicitly.")
    st.divider()
    render_weather()
