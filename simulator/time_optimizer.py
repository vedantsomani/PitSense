"""Deterministic dry-race optimization under explicit, user-supplied assumptions.

No parameters in this module are fitted to race data. Pit stops occur after the
reported lap; every stint uses a fresh set. Seconds are the unit of all costs.
"""
from dataclasses import asdict, dataclass, field
from itertools import accumulate, product
import math

from src.validation import COMPOUNDS, validate_strategy


@dataclass(frozen=True)
class TyreProfile:
    pace_offset: float
    degradation: float
    curvature: float = 0.0
    warmup: float = 0.0
    max_laps: int = 60


@dataclass(frozen=True)
class RaceAssumptions:
    race_laps: int = 52
    base_lap_seconds: float = 90.0
    pit_loss_seconds: float = 22.0
    fuel_effect_per_lap: float = 0.04
    tyres: dict = field(default_factory=lambda: {
        "SOFT": TyreProfile(-0.8, 0.12, 0.004, 0.3, 25),
        "MEDIUM": TyreProfile(0.0, 0.07, 0.002, 0.5, 35),
        "HARD": TyreProfile(0.6, 0.04, 0.001, 0.8, 45),
    })

    def validate(self):
        if type(self.race_laps) is not int or not 2 <= self.race_laps <= 200:
            raise ValueError("Race distance must be an integer from 2 to 200 laps.")
        for name in ("base_lap_seconds", "pit_loss_seconds", "fuel_effect_per_lap"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
        if set(self.tyres) != set(COMPOUNDS):
            raise ValueError("Provide SOFT, MEDIUM and HARD tyre profiles.")
        for compound, tyre in self.tyres.items():
            if type(tyre.max_laps) is not int or tyre.max_laps < 1:
                raise ValueError(f"{compound}: maximum tyre life must be a positive integer.")
            for name in ("pace_offset", "degradation", "curvature", "warmup"):
                value = getattr(tyre, name)
                if not math.isfinite(value) or (name != "pace_offset" and value < 0):
                    raise ValueError(f"{compound}: invalid {name}.")
            if self.base_lap_seconds + tyre.pace_offset <= 0:
                raise ValueError("Base pace plus compound offset must be positive.")


def _stint_cost(compound, start, length, assumptions):
    """Closed-form sum, with age zero on the first lap and a one-lap warmup."""
    tyre = assumptions.tyres[compound]
    age_sum = length * (length - 1) / 2
    age_square_sum = length * (length - 1) * (2 * length - 1) / 6
    fuel_sum = length * (assumptions.race_laps - start - 1) - age_sum
    return (length * (assumptions.base_lap_seconds + tyre.pace_offset)
            + tyre.degradation * age_sum + tyre.curvature * age_square_sum
            + tyre.warmup + assumptions.fuel_effect_per_lap * fuel_sum)


def simulate_plan(strategy, stint_laps, assumptions):
    assumptions.validate()
    strategy = validate_strategy(strategy, assumptions.race_laps)
    if (len(strategy) != len(stint_laps)
            or any(type(n) is not int or n < 1 for n in stint_laps)
            or sum(stint_laps) != assumptions.race_laps):
        raise ValueError("Positive integer stint lengths must sum to the race distance.")
    if any(n > assumptions.tyres[c].max_laps for c, n in zip(strategy, stint_laps)):
        raise ValueError("A stint exceeds the configured maximum tyre life.")
    rows, elapsed, lap = [], 0.0, 0
    for index, (compound, length) in enumerate(zip(strategy, stint_laps)):
        tyre = assumptions.tyres[compound]
        for age in range(length):
            lap += 1
            driving = (assumptions.base_lap_seconds + tyre.pace_offset
                       + tyre.degradation * age + tyre.curvature * age ** 2
                       + (tyre.warmup if age == 0 else 0)
                       + assumptions.fuel_effect_per_lap * (assumptions.race_laps - lap))
            pit = assumptions.pit_loss_seconds if age == length - 1 and index < len(strategy) - 1 else 0.0
            elapsed += driving + pit
            rows.append({"lap": lap, "compound": compound, "tyre_age": age,
                         "driving_seconds": driving, "pit_loss_seconds": pit,
                         "lap_seconds": driving + pit, "elapsed_seconds": elapsed})
    return {"strategy": strategy, "stint_laps": list(stint_laps),
            "pit_laps": list(accumulate(stint_laps))[:-1], "pit_stops": len(strategy) - 1,
            "total_seconds": elapsed, "laps": rows}


def _best_lengths(strategy, assumptions):
    # State = completed laps after a fixed number of stints. Each edge adds
    # a feasible stint. Retaining the cheapest predecessor gives the exact
    # minimum for this sequence under the additive time model.
    states = {0: (0.0, ())}
    for index, compound in enumerate(strategy):
        next_states = {}
        remaining = len(strategy) - index - 1
        for start, (cost, lengths) in states.items():
            limit = min(assumptions.tyres[compound].max_laps,
                        assumptions.race_laps - start - remaining)
            choices = range(1, limit + 1) if remaining else [assumptions.race_laps - start]
            for length in choices:
                if not 1 <= length <= limit:
                    continue
                end = start + length
                total = cost + _stint_cost(compound, start, length, assumptions)
                if index:
                    total += assumptions.pit_loss_seconds
                if end not in next_states or total < next_states[end][0]:
                    next_states[end] = (total, lengths + (length,))
        states = next_states
    return states.get(assumptions.race_laps)


def optimize(assumptions, stops=(1, 2), compounds=COMPOUNDS):
    """Return the best pit laps for every permitted sequence, ranked by time."""
    assumptions.validate()
    stops = tuple(stops)
    compounds = tuple(dict.fromkeys(str(c).strip().upper() for c in compounds))
    if not stops or any(type(n) is not int or not 1 <= n <= 3 for n in stops):
        raise ValueError("Select one to three pit stops.")
    if len(compounds) < 2 or any(c not in COMPOUNDS for c in compounds):
        raise ValueError("Select at least two supported dry compounds.")
    results = []
    for count in sorted(set(stops)):
        for strategy in product(compounds, repeat=count + 1):
            if len(set(strategy)) < 2:
                continue
            best = _best_lengths(strategy, assumptions)
            if best is not None:
                results.append(simulate_plan(strategy, best[1], assumptions))
    if not results:
        raise ValueError("No feasible strategy: increase tyre-life limits or allow more stops.")
    results.sort(key=lambda row: (row["total_seconds"], row["pit_stops"], row["strategy"], row["pit_laps"]))
    for result in results:
        result["delta_seconds"] = result["total_seconds"] - results[0]["total_seconds"]
    return {"model": "assumption-based-dry-race-v1", "calibrated": False,
            "assumptions": asdict(assumptions), "results": results}
