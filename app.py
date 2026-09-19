import json
import altair as alt
import pandas as pd
import streamlit as st
from main import compare
from simulator.race_context import get_race_context
from simulator.race_simulator import RaceSimulator
from src.config import RACE_LAPS

st.set_page_config(page_title="PitSense", page_icon="🏁", layout="wide")
st.caption("RACE ENGINEERING / STRATEGY EXPLORER")
st.title("PitSense")
st.page_link("pages/2_Race_Time_Optimizer.py", label="Race Time Optimizer — optimize pit laps and compare simulated race times", icon="⏱️")
st.write("Explore tyre sequences, stint lengths and pit windows using the included historical model.")
st.page_link("pages/1_Live_Race_Centre.py", label="Open Live Race Centre — API telemetry, timing & weather", icon="🏎️")
with st.expander("How the AI model works"):
    st.write("The app loads models/xgb_stint_model.pkl: an XGBoost regression model trained on historical stint data. It encodes the circuit and tyre compound, then predicts a numeric stint length from temperatures, race progress and circuit features. No chatbot or language model is used.")
    st.write("This page uses manual/historical inputs. The Live Race Centre connects OpenF1 observations to the model's weather and race-progress inputs. Car speed, RPM and gaps are visible there, but the saved model was not trained to use them. The final stint here fills the remaining race distance rather than being an independent prediction.")
with st.sidebar:
    st.header("Race setup")
    gp = st.selectbox("Grand Prix", sorted(RACE_LAPS), index=sorted(RACE_LAPS).index("British Grand Prix"))
    season = st.selectbox("Historical season", [2024, 2023])
    context = get_race_context(season, gp)
    context["race_laps"] = int(st.number_input("Race laps", min_value=4, max_value=100, value=context["race_laps"]))
    context["air_temp"] = st.slider("Air temperature (°C)", 0.0, 50.0, float(context["air_temp"]))
    context["track_temp"] = st.slider("Track temperature (°C)", 0.0, 70.0, float(context["track_temp"]))
    st.caption("Temperatures default to historical averages, not a live forecast. Lap counts use the repository's historical configuration; override when needed.")

left, right = st.columns(2)
left.metric("Race distance · laps", context["race_laps"])
right.metric("Track length · km", f'{context["track_length"]:.3f}')
st.caption(f'Circuit type: {context["circuit_type"]}')
st.info("A research simulator, not a fastest-strategy optimizer. Rankings measure stint balance only. The final stint fills the remaining laps; tyre life, traffic and pit-time losses are not verified.")
simulate_tab, compare_tab = st.tabs(["Build a strategy", "Compare strategies"])
with simulate_tab:
    stops = st.select_slider("Pit stops", options=[1, 2, 3], value=1)
    cols = st.columns(stops + 1)
    strategy = [col.selectbox(f"Stint {i + 1}", ["SOFT", "MEDIUM", "HARD"], index=1 if i == 0 else 2, key=f"compound_{i}") for i, col in enumerate(cols)]
    try:
        result = RaceSimulator().simulate_strategy(strategy, context)
        start = 0
        rows = []
        for i, (compound, length, window) in enumerate(zip(strategy, result["predicted_stints"], result["pit_windows"])):
            rows.append({"Stint": i + 1, "Compound": compound, "Start": start, "End": start + length, "Laps": length,
                         "Pit window": f"Lap {window[0]}–{window[1]}" if window else "Finish"})
            start += length
        frame = pd.DataFrame(rows)
        chart = alt.Chart(frame).mark_bar(size=55).encode(
            x=alt.X("Start:Q", title="Race lap", scale=alt.Scale(domain=[0, context["race_laps"]])),
            x2="End:Q", color=alt.Color("Compound:N", scale=alt.Scale(domain=["SOFT", "MEDIUM", "HARD"], range=["#ef4444", "#facc15", "#cbd5e1"])),
            tooltip=["Stint", "Compound", "Laps", "Pit window"],
        ).properties(height=130)
        st.altair_chart(chart, width="stretch")
        st.dataframe(frame[["Stint", "Compound", "Laps", "Pit window"]], hide_index=True, width="stretch")
        st.caption("Pit windows are approximate race-lap ranges (±6 laps), not calibrated confidence intervals. Final stint has no pit window.")
        st.download_button("Download strategy JSON", json.dumps({"context": context, "result": result}, indent=2), "strategy.json", "application/json")
    except ValueError as exc:
        st.warning(str(exc))
with compare_tab:
    stop_counts = st.multiselect("Compare pit-stop counts", [1, 2, 3], default=[1, 2])
    if stop_counts:
        results = compare(context, stop_counts)
        comparison = pd.DataFrame([{
            "Strategy": " → ".join(row["strategy"]), "Stops": row["pit_stops"],
            "Stint laps": " / ".join(map(str, row["predicted_stints"])),
            "Balance score": row["balance_score"], "Total laps": row["total_laps"],
        } for row in results])
        st.caption("Lower balance score means more evenly split stints. It does not imply a quicker race.")
        st.dataframe(comparison, hide_index=True, width="stretch")
        st.download_button("Download comparison CSV", comparison.to_csv(index=False), "strategy_comparison.csv", "text/csv")
    else:
        st.write("Choose at least one pit-stop count.")
