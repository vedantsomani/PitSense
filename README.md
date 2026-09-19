# PitSense

A Formula 1 strategy workbench built on the [F1 Race Strategy Engine](https://github.com/UsualSuspect09/F1-Race-Strategy-Engine). Explore tyre strategies, optimize simulated race time, inspect race telemetry, and train historical models with reproducible workflows.

## Start on this PC

**New: Race Time Optimizer.** Open it from the dashboard to search pit laps and
tyre sequences by total simulated race time. Edit pace, degradation, tyre-life,
warmup, fuel and pit-loss assumptions; compare time-gap charts, move a pit stop,
and export the complete scenario. Defaults are illustrative, not calibrated
race predictions. The original XGBoost stint explorer is still available.
See [the development roadmap](docs/DEVELOPMENT_ROADMAP.md) for model scope and
the path to data-backed validation.

CLI example: `.\.venv\Scripts\python.exe main.py optimize --laps 52 --stops 1 2 --pit-loss 22 --output reports/optimized.json`.

Use Python 3.12. Double-click **Start Dashboard.cmd** to set up and open the app on Windows. The dashboard is available at **http://127.0.0.1:8501** while its server is running. For manual setup or Linux/macOS, follow the instructions below.

1. Choose a Grand Prix and historical season in the sidebar.
2. Adjust race laps and temperatures if needed.
3. Select one, two or three pit stops and at least two different compounds.
4. Inspect the stint chart and pit windows, or open **Compare strategies**.
5. Download a strategy as JSON or comparisons as CSV.

No API key is needed for the included models and datasets. **Live Race Centre** now connects real OpenF1 historical/live feeds and Open-Meteo current weather. Live race access needs an OpenF1 subscription token; historical feeds and weather work without it. See [live-data setup and model inputs](docs/LIVE_DATA.md). The original strategy page continues to use manual/historical inputs.

## Set up again / another machine

Use Python **3.12**. In PowerShell, from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\run.ps1
```

Setup creates `.venv`, installs the tested dependency lock, checks dependencies, and runs tests. The policy flag applies only to that PowerShell process. Dependencies install inside the project environment.

For Linux/macOS (CI configuration included; local verification was on Windows):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py
```

If port 8501 is occupied by another app, use `--server.port=8502`. Stop a terminal-launched dashboard with Ctrl+C. To stop the background dashboard launched during setup, run `powershell -ExecutionPolicy Bypass -File .\stop-dashboard.ps1`.

## Command-line workflows

All examples below run in the project folder; no environment activation is required.

```powershell
# List the supported circuits and historical lap counts
.\.venv\Scripts\python.exe main.py races

# Simulate and save a strategy
.\.venv\Scripts\python.exe main.py simulate --gp "British Grand Prix" --compounds MEDIUM HARD --output reports/strategy.json

# Compare every supported one-stop and two-stop sequence (30 total)
.\.venv\Scripts\python.exe main.py compare --gp "Bahrain Grand Prix" --stops 1 2 --output reports/comparison.json

# Process included 2025 raw data without an internet download
.\.venv\Scripts\python.exe build_dataset.py --year 2025 --source bundled

# Explicitly download a season with FastF1 (can take a long time)
.\.venv\Scripts\python.exe build_dataset.py --year 2024 --source live

# Train on 2023 and evaluate on the separate 2024 season
.\.venv\Scripts\python.exe train_model.py

# Try the separately trained model
.\.venv\Scripts\python.exe main.py simulate --model reports/training/trained_stint_model.pkl

# Verify the installation
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

`simulate` and `compare` also accept `--laps`, `--air-temp`, and `--track-temp`. Supported simulation seasons are 2023 and 2024; a season choice is historical context, not an up-to-date calendar lookup. Run each script with `--help` for options.

## How the pipeline fits together

| Stage | Input | Output |
| --- | --- | --- |
| Lap/weather processing | Bundled 2025 raw CSVs, or explicitly downloaded FastF1 sessions | `datasets/generated/YEAR/`: raw, cleaned, sessioned, sorted and normalized CSVs |
| Baseline training | Included `notebooks/master_stint_2023_v3.csv` and `master_stint_2024_v3.csv` | `reports/training/trained_stint_model.pkl` and `metrics.json` |
| Simulation | Included original XGBoost model, circuit metadata, historical weather averages, selected compounds | Positive stint lengths adding up to the chosen race distance |
| Comparison | All valid compound sequences for selected stop counts | Results sorted by standard deviation of stint lengths |
| Race-time optimization | Explicit pace, degradation, tyre-life and pit-loss assumptions | Optimal pit laps per sequence, ranked by simulated race time |

**The lap/weather processing and model-training stages are separate.** New raw seasons are not automatically transformed into model-ready stint tables. The original notebook research covers that feature engineering, and has not been converted into an automated raw-to-model pipeline here. Normalized CSVs are exploratory outputs; their scalers are fitted to that dataset and must not be reused as leakage-free training evaluation features.

Live collection currently requests FP1, FP2, FP3, qualifying and race sessions; unavailable sessions are logged and skipped. Sprint-specific collection and complete-season coverage validation are future work. The live-download path was checked with mocks; a new full season was not downloaded during setup.

## What was fixed and added

- Removed author-specific paths from executable simulation and data-loading code.
- Pinned XGBoost 3.2.0 to match the included serialized model, and installed missing runtime dependencies.
- Fixed impossible negative final stints; reserved at least one lap per remaining stint.
- Added input checks, case-insensitive compounds and cumulative race-lap pit windows; final stint ends at the finish.
- Made data processing non-interactive, with generated outputs separate from original datasets.
- Fixed FastF1 round selection, per-session outlier filtering and weather filling across session boundaries.
- Added a browser dashboard, CLI, Windows launchers, training command, dependency lock, tests and a Windows/Linux CI workflow.

## Model limits and verification

This is a research tool. **Balanced stints do not mean the fastest race.** The original stint explorer does not optimize race time or account for pit-lane time losses, traffic, tyre inventory, fuel burn, evolving rain, or safety-car probabilities. The final stint is assigned the remaining laps; budget validity is not proof that the tyre can last that long. Pit windows use a fixed ±6-lap heuristic, not a calibrated confidence interval.

The separate Race Time Optimizer minimizes time under explicit assumptions,
including pit losses, tyre degradation and fuel pace effects. Its default values
are not fitted to historical data, and its outputs are not validated real-race
recommendations. Its maximum stint lengths are user constraints, not tyre-life
predictions. It does not use the XGBoost model. The expanded suite passed **47
tests**, including exhaustive optimizer checks and dashboard interactions.

The dashboard uses the original bundled XGBoost model. Historical default temperatures and lap counts are not live forecasts or current official rules. Some original model features use within-stint flag information; simulation assumes no such incidents. Future race performance is not validated.

The new baseline deliberately excludes within-stint flag counts and evaluates 2023 → 2024: **1,124 training rows, 1,117 test rows; training MAE 4.03 laps, held-out MAE 8.46 laps** with the pinned environment. Stint-average weather is still retrospective, and observed stint lengths include strategy decisions and censored observations. This evaluation is not directly comparable to the original random-split benchmark. The baseline is saved separately and does not replace either bundled model.

Verified locally: **33 automated tests passed**, dependency check passed, bundled 2025 data processing completed, training completed, CLI exports worked, and the dashboard chart/comparison were checked in the browser. Real OpenF1 historical snapshots, model estimates from session inputs, and Open-Meteo weather were verified. Paid live access still requires a token. CI has been configured but not run remotely. Original notebooks retain their historical research environment and may need path edits; they are not required for the supported workflows above.

The upstream README is preserved in `docs/UPSTREAM_README.md`; original benchmark notes remain in `benchmarks.md`. PitSense starts from a project snapshot; source attribution is preserved here and in the upstream README.
#   a i - m l  
 