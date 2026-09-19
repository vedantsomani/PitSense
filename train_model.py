"""Reproducible baseline: train on 2023, evaluate on 2024; preserve shipped models."""
import argparse
import json
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor
from src.paths import ROOT

CATEGORICAL = ["GP", "Compound", "CircuitType", "TrackAbrasiveness"]
NUMERIC = ["TrackLength", "AverageCornerSpeed", "AirTemp", "TrackTemp", "FreshTyre", "RaceProgress"]


def load_season(year):
    frame = pd.read_csv(ROOT / "notebooks" / f"master_stint_{year}_v3.csv")
    frame = frame[frame.Compound.isin(["SOFT", "MEDIUM", "HARD"])].copy()
    frame = frame.dropna(subset=["StintLength"])
    return frame[frame.StintLength > 0]


def train(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    training, testing = load_season(2023), load_season(2024)
    preprocess = ColumnTransformer([
        ("category", Pipeline([("missing", SimpleImputer(strategy="most_frequent")),
                               ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
        ("numeric", SimpleImputer(strategy="median"), NUMERIC),
    ])
    model = Pipeline([("preprocess", preprocess),
                      ("model", XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                                             random_state=42, n_jobs=2, objective="reg:squarederror"))])
    features = CATEGORICAL + NUMERIC
    model.fit(training[features], training.StintLength)
    metrics = {
        "train_season": 2023, "test_season": 2024,
        "train_rows": len(training), "test_rows": len(testing),
        "train_mae_laps": float(mean_absolute_error(training.StintLength, model.predict(training[features]))),
        "test_mae_laps": float(mean_absolute_error(testing.StintLength, model.predict(testing[features]))),
        "features": features,
        "limitations": "Historical observed stint lengths include strategy decisions and censored stints. Air/track temperatures are observed stint averages. Retrospective error is not a live-race accuracy guarantee. No within-stint flag counts are used as predictors.",
    }
    joblib.dump(model, output_dir / "trained_stint_model.pkl")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=__import__("pathlib").Path, default=ROOT / "reports" / "training")
    train(parser.parse_args().output_dir)
