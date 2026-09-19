"""Independent exhaustive checks of optimization and accounting invariants."""
from dataclasses import replace
from itertools import combinations, product
import json
import subprocess
import sys

import pytest

from simulator.time_optimizer import RaceAssumptions, TyreProfile, optimize, simulate_plan
from src.paths import ROOT


@pytest.mark.parametrize("stops", [1, 2, 3])
def test_optimizer_matches_exhaustive_search(stops):
    config = RaceAssumptions(race_laps=8)
    expected = {}
    for strategy in product(config.tyres, repeat=stops + 1):
        if len(set(strategy)) < 2:
            continue
        times = []
        for pits in combinations(range(1, config.race_laps), stops):
            boundaries = (0,) + pits + (config.race_laps,)
            lengths = [b - a for a, b in zip(boundaries, boundaries[1:])]
            times.append(simulate_plan(strategy, lengths, config)["total_seconds"])
        expected[strategy] = min(times)
    results = optimize(config, [stops])["results"]
    assert len(results) == len(expected)
    for result in results:
        assert result["total_seconds"] == pytest.approx(expected[tuple(result["strategy"])])
        assert sum(result["stint_laps"]) == 8


def test_hand_calculated_lap_costs():
    config = RaceAssumptions(race_laps=4, base_lap_seconds=80, pit_loss_seconds=20,
                            fuel_effect_per_lap=0.1,
                            tyres={c: TyreProfile(0, 1, 0, 2, 4) for c in ("SOFT", "MEDIUM", "HARD")})
    result = simulate_plan(["SOFT", "HARD"], [2, 2], config)
    assert [r["lap_seconds"] for r in result["laps"]] == pytest.approx([82.3, 101.2, 82.1, 81])
    assert result["total_seconds"] == pytest.approx(346.6)
    assert result["pit_laps"] == [2]


def test_pit_loss_can_change_optimal_stop_count():
    tyres = {c: TyreProfile(0, 1, max_laps=20) for c in ("SOFT", "MEDIUM", "HARD")}
    config = RaceAssumptions(race_laps=12, tyres=tyres, pit_loss_seconds=0)
    assert optimize(config)["results"][0]["pit_stops"] == 2
    assert optimize(replace(config, pit_loss_seconds=100))["results"][0]["pit_stops"] == 1


def test_fuel_changes_time_but_not_optimal_plan():
    config = RaceAssumptions(race_laps=10, fuel_effect_per_lap=0)
    before = optimize(config)["results"][0]
    after = optimize(replace(config, fuel_effect_per_lap=0.1))["results"][0]
    assert before["strategy"] == after["strategy"]
    assert before["pit_laps"] == after["pit_laps"]
    assert after["total_seconds"] - before["total_seconds"] == pytest.approx(4.5)


def test_life_limits_and_infeasible_plans():
    config = RaceAssumptions(race_laps=10, tyres={c: TyreProfile(0, 0, max_laps=4) for c in ("SOFT", "MEDIUM", "HARD")})
    with pytest.raises(ValueError, match="No feasible"):
        optimize(config, [1])
    assert all(max(r["stint_laps"]) <= 4 for r in optimize(config, [2])["results"])
    with pytest.raises(ValueError, match="maximum tyre life"):
        simulate_plan(["SOFT", "HARD"], [5, 5], config)


@pytest.mark.parametrize("kwargs", [{"pit_loss_seconds": -1}, {"base_lap_seconds": float("nan")},
                                   {"fuel_effect_per_lap": float("inf")}, {"race_laps": True},
                                   {"base_lap_seconds": 0}])
def test_invalid_assumptions(kwargs):
    with pytest.raises(ValueError):
        optimize(replace(RaceAssumptions(), **kwargs))


def test_optimizer_cli():
    run = subprocess.run([sys.executable, str(ROOT / "main.py"), "optimize", "--laps", "8", "--stops", "1"],
                         capture_output=True, text=True, check=True)
    payload = json.loads(run.stdout)
    assert payload["calibrated"] is False
    assert len(payload["results"]) == 6


def test_optimizer_ui():
    from streamlit.testing.v1 import AppTest
    page = AppTest.from_file(str(ROOT / "pages" / "2_Race_Time_Optimizer.py")).run(timeout=60)
    assert not page.exception
    page.button[0].click().run(timeout=60)
    assert not page.exception
    assert len(page.dataframe[0].value) == 30
    assert page.dataframe[0].value.iloc[0]["Gap to best (s)"] == 0
    page.slider[0].set_value(page.slider[0].value + 1).run(timeout=60)
    assert not page.exception
    page.multiselect[0].set_value([])
    page.button[0].click().run(timeout=60)
    assert not page.exception
    assert page.error
    assert not page.dataframe
