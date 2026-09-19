# Live feeds and ML inputs

Open **Live Race Centre** from the sidebar or http://127.0.0.1:8501/Live_Race_Centre.

## What works without credentials

- **Historical API snapshot:** choose a year, Load sessions, select session/driver/minute and Fetch. These are real OpenF1 records at that timestamp, not live data or fabricated examples.
- **Current circuit weather:** choose a circuit and Fetch current weather. Open-Meteo supplies current model estimates and a 24-hour forecast; track temperature is not invented. Today's forecast stays separate from old-race weather.

## Connect live car data

OpenF1 requires a subscribed account for live telemetry. Get an OAuth access token using the provider's [authentication guide](https://openf1.org/auth.html). This app does not purchase a subscription or accept credentials through chat.

Either paste the access token into the password field under **Connect live access**, or copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and enter it locally. Environment variable `OPENF1_ACCESS_TOKEN` is also supported. The secrets file is ignored by Git. Tokens are sent only in the Authorization header to api.openf1.org, never in exports. Replace expired tokens manually; the app does not store your OpenF1 password or automatically renew tokens.

Choose **Live session**, the current year, Load sessions, and the current session/driver. Enable **Auto-refresh every 30 seconds**. This is REST polling, not MQTT/subsecond streaming. The app displays an explicit historical, scheduled, access-required, or stale state unless the selected session is within its published time range and car telemetry is less than a minute old. Published session end times may precede an overrun; such a session is conservatively shown as ended.

## Available feeds

| Feed | Display |
| --- | --- |
| car_data | Selected car's speed, RPM, throttle, brake, gear and DRS code; last 45 seconds |
| location | Selected car's x/y position trace in provider coordinates; not GPS or a surveyed track map |
| position + intervals | Updates for all received drivers, gap to leader and interval; last 3 minutes; per-field timestamps |
| laps | Selected driver's completed lap/sector times; future lap completion is excluded |
| stints | Compounds, stint number, starting lap and provider tyre age; future stint ends are excluded |
| weather | Track air/track temperatures, rain and other available weather sensor fields; last 10 minutes |
| pit + race_control | Pit events and control/flag messages; last 10 minutes |
| Open-Meteo | Current weather estimates plus next 24 forecast hours at an independently selected circuit |

Some endpoints are absent outside races or between updates. The timing tower lists recent updates, not a guaranteed complete official classification. Empty or failed feeds are explicit; old values are not silently substituted. Requests have timeouts and pacing; authentication/rate/provider failures stop subsequent requests for that snapshot. Session/driver metadata is cached five minutes and weather ten minutes.

## How AI uses it

`models/xgb_stint_model.pkl` is a saved scikit-learn preprocessing pipeline plus an **XGBoost regression model**. It is local machine learning, not ChatGPT or an LLM. Its features are Compound, GP, CircuitType, TrackAbrasiveness, AirTemp, TrackTemp, TrackLength, Season, RaceProgress, FreshTyre, YellowLaps, SCLaps, VSCLaps, RedFlagLaps and AverageCornerSpeed.

For a supported race with completed laps and dry track-weather observations, the Race Centre feeds actual session temperatures and driver lap progress into this model. It shows a hypothetical new fresh-tyre stint estimate for each dry compound, separately from the remaining race-lap budget. These are not the remaining life of the currently fitted tyre or an optimized pit recommendation. Historical circuit metadata and the manually verified race distance are used. Future incident counts remain zero. Estimates stop when rain is reported, the race distance has been completed, or live car telemetry is stale.

Speed, RPM, brake, DRS, gaps and car position are displayed but do **not** influence the saved model: retraining and race-time modelling would be required. Model accuracy outside its 2023–2024 training period is unvalidated. No LLM API key is needed or used.

## Verification and sources

Real API smoke check: British GP 2024, session 9558, driver 44, cutoff 14:45 UTC returned 162 car samples, 165 position-trace samples, 10 track-weather samples, 17 position updates, 726 interval updates, 26 completed laps, 1 visible stint, 6 pit events and 44 race-control messages, without feed errors. Open-Meteo also returned actual current circuit conditions. Snapshot JSONs are in `reports/api-smoke.json` and `reports/weather-smoke.json` locally. These counts are a verification example, not fixed expected outputs.

Paid live access has not been verified because no access token was provided. Automated tests cover authentication failures, rate limits, date-filter encoding, stale/live labels, replay future-data exclusion, and offline UI startup.

Sources: [OpenF1 API](https://openf1.org/docs/), [OpenF1 authentication](https://openf1.org/auth.html), [Open-Meteo](https://open-meteo.com/en/docs), [Jolpica circuit coordinates](https://api.jolpi.ca/ergast/f1/2024/circuits.json).
