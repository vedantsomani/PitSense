"""Command-line interface. Run python main.py --help."""
import argparse
import json
from pathlib import Path
from simulator.race_context import get_race_context
from simulator.race_simulator import RaceSimulator
from simulator.stint_predictor import StintPredictor
from src.config import RACE_LAPS
from src.simulate import get_valid_strategies
import numpy as np


def compare(context, stops=(1, 2), model_path=None):
    simulator = RaceSimulator(StintPredictor(model_path))
    results = []
    for count in stops:
        for strategy in get_valid_strategies(count):
            result = simulator.simulate_strategy(strategy, context)
            result["balance_score"] = round(float(np.std(result["predicted_stints"])), 2)
            results.append(result)
    return sorted(results, key=lambda row: row["balance_score"])


def main():
    parser = argparse.ArgumentParser(description="F1 dry-race stint simulator (historical model)")
    parser.add_argument("command", choices=["simulate", "compare", "races", "optimize"], nargs="?", default="simulate")
    parser.add_argument("--gp", default="British Grand Prix")
    parser.add_argument("--season", type=int, choices=[2023, 2024], default=2024)
    parser.add_argument("--compounds", nargs="+", default=["MEDIUM", "HARD"])
    parser.add_argument("--laps", type=int, help="Override historical lap count")
    parser.add_argument("--air-temp", type=float)
    parser.add_argument("--track-temp", type=float)
    parser.add_argument("--stops", type=int, nargs="+", choices=[1, 2, 3], default=[1, 2])
    parser.add_argument("--output", type=Path, help="Save JSON results")
    parser.add_argument("--model", type=Path, help="Optional locally trained model")
    parser.add_argument("--base-lap", type=float, default=90.0, help="Optimizer reference lap time in seconds (illustrative default)")
    parser.add_argument("--pit-loss", type=float, default=22.0, help="Optimizer time lost per stop in seconds")
    args = parser.parse_args()
    try:
        if args.command == "races":
            result = RACE_LAPS
        elif args.command == "optimize":
            from simulator.time_optimizer import RaceAssumptions, optimize
            result = optimize(RaceAssumptions(
                race_laps=args.laps if args.laps is not None else get_race_context(args.season, args.gp)["race_laps"],
                base_lap_seconds=args.base_lap, pit_loss_seconds=args.pit_loss), args.stops)
        else:
            context = get_race_context(args.season, args.gp)
            for name in ["laps", "air_temp", "track_temp"]:
                value = getattr(args, name)
                if value is not None:
                    context["race_laps" if name == "laps" else name] = value
            result = compare(context, args.stops, args.model) if args.command == "compare" else RaceSimulator(StintPredictor(args.model)).simulate_strategy(args.compounds, context)
        payload = json.dumps(result, indent=2, ensure_ascii=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        print(payload)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
