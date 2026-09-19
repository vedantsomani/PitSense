import math

COMPOUNDS = ("SOFT", "MEDIUM", "HARD")


def validate_strategy(strategy, race_laps):
    if isinstance(strategy, str):
        raise ValueError("Pass a list of compounds, not a single string.")
    compounds = [str(c).strip().upper() for c in strategy]
    if not 2 <= len(compounds) <= 4:
        raise ValueError("Choose two to four stints (one to three pit stops).")
    if any(c not in COMPOUNDS for c in compounds):
        raise ValueError("Supported compounds: SOFT, MEDIUM, HARD.")
    if len(set(compounds)) < 2:
        raise ValueError("Dry-race strategies must use at least two compounds.")
    if isinstance(race_laps, bool) or not isinstance(race_laps, int) or race_laps < len(compounds):
        raise ValueError("Race laps must be an integer with at least one lap per stint.")
    return compounds


def allocate_stint(prediction, remaining_laps, remaining_stints):
    if not math.isfinite(float(prediction)):
        raise ValueError("The model returned a non-finite stint prediction.")
    return max(1, min(round(float(prediction)), remaining_laps - remaining_stints))
