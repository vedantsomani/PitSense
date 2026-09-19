"""Interactive scenario workbench for the deterministic race-time engine."""
import json

import altair as alt
import pandas as pd
import streamlit as st

from simulator.time_optimizer import RaceAssumptions, TyreProfile, optimize, simulate_plan

st.set_page_config(page_title="Race Time Optimizer", page_icon="🏁", layout="wide")
st.caption("PITSENSE / RACE TIME")
st.title("Find the fastest plan for your scenario")
st.write("Compare tyre sequences and pit laps using a lap-by-lap time model.")
st.info("Experimental scenario model. Defaults are illustrative, not fitted circuit data. "
        "Results are optimal only for your inputs; traffic, weather changes, safety cars and tyre inventory are not modelled.")

defaults = RaceAssumptions()
with st.form("race_assumptions"):
    st.subheader("Race assumptions")
    cols = st.columns(4)
    laps = cols[0].number_input("Race laps", 4, 100, 52)
    base = cols[1].number_input("Base lap time (s)", 20.0, 300.0, 90.0, step=0.5)
    pit = cols[2].number_input("Time lost per pit stop (s)", 0.0, 120.0, 22.0, step=0.5)
    fuel = cols[3].number_input("Fuel pace penalty per remaining lap (s)", 0.0, 0.2, 0.04, step=0.01)
    stops = st.multiselect("Allowed pit-stop counts", [1, 2, 3], default=[1, 2])
    st.caption("Base lap time is the reference pace at the end of the race on a fresh medium tyre, before warmup. "
               "Fuel adds the same total time to every plan and does not change their ranking.")
    st.subheader("Tyre assumptions")
    profiles = {}
    for col, (compound, tyre) in zip(st.columns(3), defaults.tyres.items()):
        with col:
            st.markdown(f"**{compound}**")
            offset = st.number_input("Pace offset (s)", -5.0, 5.0, tyre.pace_offset, step=0.1, key=f"{compound}_offset")
            degradation = st.number_input("Linear degradation (s / lap of age)", 0.0, 1.0, tyre.degradation, step=0.01, key=f"{compound}_deg")
            curve = st.number_input("Quadratic degradation (s / age²)", 0.0, 0.1, tyre.curvature, step=0.001, format="%.3f", key=f"{compound}_curve")
            warmup = st.number_input("First-lap warmup penalty (s)", 0.0, 10.0, tyre.warmup, step=0.1, key=f"{compound}_warmup")
            life = st.number_input("Maximum stint length (laps)", 1, 100, tyre.max_laps, key=f"{compound}_life")
            profiles[compound] = TyreProfile(offset, degradation, curve, warmup, life)
    submitted = st.form_submit_button("Optimize race strategy", type="primary")

if submitted:
    st.session_state.pop("time_optimization", None)
    try:
        assumptions = RaceAssumptions(laps, base, pit, fuel, profiles)
        with st.spinner("Finding optimal pit laps for every tyre sequence…"):
            st.session_state["time_optimization"] = optimize(assumptions, stops)
    except ValueError as exc:
        st.error(str(exc))

payload = st.session_state.get("time_optimization")
if payload:
    results = payload["results"]
    best = results[0]
    saved = payload["assumptions"]
    st.caption(f"Showing the last completed run: {saved['race_laps']} laps, "
               f"{saved['base_lap_seconds']:.1f}s base pace, {saved['pit_loss_seconds']:.1f}s pit loss. "
               "Submit the form again to apply changes.")
    a, b, c = st.columns(3)
    minutes, seconds = divmod(best["total_seconds"], 60)
    a.metric("Best simulated time", f"{int(minutes)}m {seconds:04.1f}s")
    b.metric("Pit after laps", ", ".join(map(str, best["pit_laps"])))
    c.metric("Feasible tyre sequences", len(results))
    st.success(" → ".join(best["strategy"]) + " · stint lengths: " + " / ".join(map(str, best["stint_laps"])))

    table = pd.DataFrame([{"Strategy": " → ".join(r["strategy"]), "Stops": r["pit_stops"],
                           "Pit after laps": ", ".join(map(str, r["pit_laps"])),
                           "Stint lengths": " / ".join(map(str, r["stint_laps"])),
                           "Race time (s)": round(r["total_seconds"], 2),
                           "Gap to best (s)": round(r["delta_seconds"], 2)} for r in results])
    st.subheader("Strategy leaderboard")
    st.dataframe(table, hide_index=True, width="stretch")
    labels = [f"{i + 1}. {' → '.join(r['strategy'])}" for i, r in enumerate(results)]
    chosen = st.multiselect("Compare cumulative race time", labels, default=labels[:3])
    chart_rows = []
    for label in chosen:
        result = results[labels.index(label)]
        for row, reference in zip(result["laps"], best["laps"]):
            chart_rows.append({"Lap": row["lap"], "Strategy": label,
                               "Gap to best plan (s)": row["elapsed_seconds"] - reference["elapsed_seconds"]})
    if chart_rows:
        st.altair_chart(alt.Chart(pd.DataFrame(chart_rows)).mark_line().encode(
            x="Lap:Q", y="Gap to best plan (s):Q", color="Strategy:N",
            tooltip=["Lap", "Strategy", alt.Tooltip("Gap to best plan (s):Q", format=".2f")]
        ).properties(height=300), width="stretch")
        st.caption("Negative means ahead at that lap. Pit stops cause jumps; the finish determines the winner.")

    st.subheader("What if you move a pit stop?")
    selected = st.selectbox("Plan to inspect", labels)
    plan = results[labels.index(selected)]
    pit_index = st.selectbox("Pit stop", list(range(len(plan["pit_laps"]))), format_func=lambda n: f"Stop {n + 1}")
    boundaries = [0] + plan["pit_laps"] + [saved["race_laps"]]
    moved = st.slider("Pit after lap", boundaries[pit_index] + 1, boundaries[pit_index + 2] - 1,
                      plan["pit_laps"][pit_index]) if boundaries[pit_index + 2] - boundaries[pit_index] > 2 else plan["pit_laps"][pit_index]
    boundaries[pit_index + 1] = moved
    edited_lengths = [end - start for start, end in zip(boundaries, boundaries[1:])]
    assumptions = RaceAssumptions(**{**saved, "tyres": {key: TyreProfile(**value) for key, value in saved["tyres"].items()}})
    try:
        edited = simulate_plan(plan["strategy"], edited_lengths, assumptions)
        st.metric("Time change versus this plan's optimum (s)", f"{edited['total_seconds'] - plan['total_seconds']:+.2f}")
        st.dataframe(pd.DataFrame(edited["laps"]), hide_index=True, width="stretch")
    except ValueError as exc:
        st.warning(str(exc))
    st.download_button("Download reproducible scenario JSON", json.dumps(payload, indent=2), "race_time_scenario.json", "application/json")
    st.download_button("Download rankings CSV", table.to_csv(index=False), "race_time_rankings.csv", "text/csv")
else:
    st.write("Set your assumptions and run the optimizer to see rankings, time gaps and pit-lap sensitivity.")

with st.expander("Model equation and scope"):
    st.code("lap time = base pace + compound offset + degradation × age\n"
            "         + curvature × age² + first-lap warmup\n"
            "         + fuel penalty × remaining race laps\n"
            "race time = sum(lap times) + pit stops × pit loss")
    st.write("Tyre age starts at zero on each fresh set. Dynamic programming finds the lowest-time pit laps "
             "for every allowed sequence. Every stint respects the configured maximum tyre life and every "
             "plan uses at least two compounds. These limits are assumptions, not measured tyre endurance. "
             "No uncertainty interval or real-race accuracy claim is attached to these results.")
