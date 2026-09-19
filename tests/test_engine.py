import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from simulator.race_context import get_race_context
from simulator.race_simulator import RaceSimulator
from src.config import RACE_LAPS
from src.paths import ROOT
from src.simulate import get_valid_strategies, simulate_strategy
from src.validation import allocate_stint


class FixedPredictor:
    def __init__(self, value):
        self.value = value

    def predict_stint_length(self, **kwargs):
        return self.value


@pytest.mark.parametrize('prediction', [-100, 0, 1, 20, 1000])
@pytest.mark.parametrize('laps', [4, 52])
def test_lap_budget_and_windows(prediction, laps):
    context = get_race_context(2024, 'British Grand Prix')
    context['race_laps'] = laps
    result = RaceSimulator(FixedPredictor(prediction)).simulate_strategy(['soft', 'medium', 'hard', 'hard'], context)
    assert sum(result['predicted_stints']) == laps
    assert min(result['predicted_stints']) >= 1
    assert result['valid']
    assert result['pit_windows'][-1] is None
    for window in result['pit_windows'][:-1]:
        assert 1 <= window[0] <= window[1] < laps
    assert result['race_progresses'] == sorted(result['race_progresses'])


@pytest.mark.parametrize('strategy,laps', [([], 52), (['HARD'], 52), (['HARD', 'HARD'], 52),
                                        (['WET', 'HARD'], 52), (['SOFT', 'HARD'], 0),
                                        (['SOFT', 'MEDIUM', 'HARD'], 2)])
def test_invalid_strategy(strategy, laps):
    context = get_race_context(2024, 'British Grand Prix')
    context['race_laps'] = laps
    with pytest.raises(ValueError):
        RaceSimulator(FixedPredictor(20)).simulate_strategy(strategy, context)


def test_non_finite_prediction():
    with pytest.raises(ValueError):
        allocate_stint(float('nan'), 52, 1)


def test_sequence_counts():
    assert len(get_valid_strategies(1)) == 6
    assert len(get_valid_strategies(2)) == 24
    assert len(get_valid_strategies(3)) == 78
    with pytest.raises(ValueError):
        get_valid_strategies(100)


def test_included_models_all_circuits():
    simulator = RaceSimulator()
    for gp in RACE_LAPS:
        result = simulator.simulate_strategy(['MEDIUM', 'HARD'], get_race_context(2024, gp))
        assert result['valid']
        assert all(np.isfinite(result['predicted_stints']))
    legacy = simulate_strategy('British Grand Prix', ['Medium', 'Hard'], 52)
    assert legacy['BudgetValid']
    assert legacy['Stints'][-1]['PitWindow'] is None


def test_cli_from_different_directory(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), 'simulate'], cwd=tmp_path,
                            text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)['total_laps'] == 52


def test_weather_fill_stays_within_session():
    from build_dataset import clean_weather_data
    data = pd.DataFrame({'RoundNumber': [1, 1, 2], 'Session': ['R'] * 3, 'Time': [1, 2, 1],
                         **{name: [20.0, None, None] for name in
                            ['AirTemp', 'Humidity', 'Pressure', 'TrackTemp', 'WindDirection', 'WindSpeed']}})
    result = clean_weather_data(data)
    assert result.iloc[1].AirTemp == 20
    assert pd.isna(result.iloc[2].AirTemp)


def test_live_collection_uses_round_number(monkeypatch):
    import build_dataset as dataset
    monkeypatch.setattr(dataset.fastf1, 'get_event_schedule', lambda *args, **kwargs:
                        pd.DataFrame({'RoundNumber': [7]}, index=[42]))
    rounds = []

    class Session:
        laps = pd.DataFrame({'LapNumber': [1]})
        def load(self):
            pass

    class Event:
        EventName = 'Test GP'
        EventDate = '2025-01-01'
        def get_session(self, name):
            return Session()

    def get_event(year, round_number):
        rounds.append(round_number)
        return Event()

    monkeypatch.setattr(dataset.fastf1, 'get_event', get_event)
    result = dataset.collect_driver_data(2025)
    assert rounds == [7]
    assert result.RoundNumber.unique().tolist() == [7]


def test_dashboard():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=60)
    assert not app.exception
    assert len(app.dataframe) == 2
    assert app.dataframe[0].value.Laps.sum() == 52
    app.select_slider[0].set_value(2).run(timeout=60)
    assert not app.exception
    assert len(app.dataframe[0].value) == 3
    app.selectbox(key='compound_0').set_value('HARD').run(timeout=60)
    assert not app.exception
    assert any('two compounds' in warning.value for warning in app.warning)
