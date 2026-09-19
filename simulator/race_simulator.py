"""Sequential lap allocation; this is not a race-time optimization model."""
from simulator.stint_predictor import StintPredictor
from src.config import WINDOW_MARGIN
from src.validation import allocate_stint, validate_strategy


class RaceSimulator:
    def __init__(self, predictor=None):
        self.predictor = predictor if predictor is not None else StintPredictor()

    def simulate_strategy(self, strategy, race_context):
        race_laps = race_context["race_laps"]
        strategy = validate_strategy(strategy, race_laps)
        completed = 0
        lengths, progresses, windows = [], [], []
        for index, compound in enumerate(strategy):
            progress = completed / race_laps
            progresses.append(round(progress, 3))
            remaining_stints = len(strategy) - index - 1
            if remaining_stints:
                prediction = self.predictor.predict_stint_length(
                    compound=compound, GP=race_context["gp_name"],
                    air_temp=race_context["air_temp"], track_temp=race_context["track_temp"],
                    season=race_context["season"], race_progress=progress,
                    circuit_type=race_context["circuit_type"], track_length=race_context["track_length"],
                    track_abrasiveness=race_context["track_abrasiveness"],
                    average_corner_speed=race_context["average_corner_speed"],
                )
                length = allocate_stint(prediction, race_laps - completed, remaining_stints)
                pit_lap = completed + length
                windows.append((max(completed + 1, pit_lap - WINDOW_MARGIN),
                                min(race_laps - remaining_stints, pit_lap + WINDOW_MARGIN)))
            else:
                length = race_laps - completed
                windows.append(None)
            lengths.append(length)
            completed += length
        return {
            "strategy": strategy, "race_progresses": progresses,
            "predicted_stints": lengths, "pit_windows": windows,
            "total_laps": completed, "race_laps": race_laps,
            "coverage_margin": completed - race_laps,
            "pit_stops": len(strategy) - 1,
            "valid": completed == race_laps and all(n > 0 for n in lengths),
            "final_compound": strategy[-1], "circuit_type": race_context["circuit_type"],
        }
