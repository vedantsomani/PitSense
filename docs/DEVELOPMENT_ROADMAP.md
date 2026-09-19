# Building a credible race strategy engine

The objective is measurable strategy quality: reproducible inputs, justified
models, out-of-sample evaluation and useful decision support.

## Implemented: race-time scenario optimizer

`simulator/time_optimizer.py` adds a deterministic lap-time model, per-compound
linear/quadratic degradation, first-lap warmup, fuel pace effects, maximum stint
lengths and a fixed pit-loss cost. Dynamic programming selects the best pit laps
for each allowed compound sequence; rankings minimize total simulated seconds.
The new dashboard page includes cumulative time-gap charts, a pit-lap adjustment
control and JSON/CSV exports. Defaults are illustrative and are **not calibrated**.
The historical XGBoost stint explorer remains available as a separate workflow.

The optimizer is exact for its additive model, not for a real race. Every set is
fresh, tyre supply is unlimited, and there is no traffic, evolving weather,
safety car, red flag, start penalty, or driver-specific pace. Fuel penalty is
common to all plans and cannot change strategy rankings. All pit losses are
charged after the specified lap. Integer tyre age begins at zero. Dry plans
use at least two compounds; this is a scenario constraint, not a complete
sporting-regulation validator. Exports retain assumptions and unrounded results.

Validation includes independent exhaustive enumeration of small races, a
hand-calculated time example, pit-loss sensitivity, fuel invariance, tyre-life
constraints, invalid inputs, CLI exports and dashboard interaction.

## Next: data-backed calibration

Build a versioned lap/stint dataset from the included raw seasons. Preserve source
session IDs and collection times. Exclude pit in/out laps and flag-affected laps
from clean-pace fitting; document handling of missing data and outliers. Separate
tyre aging from fuel, driver, track evolution and traffic effects. Report where
these effects cannot be identified reliably. Compare simple baselines before
adding model complexity. Do not treat observed stint length as tyre failure age.

Acceptance: train and evaluate on different events/seasons, publish lap-time and
degradation errors by compound/circuit with sample counts, and reproduce results
from a single command. Training data must never include the evaluation race.

## Then: historical replay and uncertainty

Replay races using only observations available at each decision time. Compare
recommendations with fixed strategies and simple rules. Actual race results are
not ground truth for an unobserved counterfactual strategy; report that distinction.
Add seeded simulations of pace, degradation and pit-stop variability, then show
expected time, downside outcomes and sensitivity to uncertain assumptions.

Acceptance: reproducible replay reports, checks against future-data leakage, and
empirical interval coverage on held-out data. Probabilities require calibrated
uncertainty, not arbitrary noise.

## Then: race interactions and operational quality

Introduce pit-exit traffic, driver/team pace, undercut/overcut comparisons, safety
car scenarios, available tyre sets and wet-weather transitions. Validate each
addition against a simpler baseline. Extend live ingestion with persistent
snapshots, clear stale-data handling and recovery from provider failures.

Keep the UI centered on the decision, expected benefit, assumptions and
uncertainty. Add replayable bug reports, performance measurements, CI regression
checks and model/data version provenance before production deployment.
