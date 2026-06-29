"""
Three-way RUL comparison on the SAME holdout machines/timeframe:

  1. RandomForest REGRESSOR — predicts hours-to-failure directly
  2. Naive classifier-derived RUL — (1 - failure_probability) * RUL_CAP_HOURS,
     no smoothing, straight from the failure_prediction classifier
  3. EWMA-smoothed classifier-derived RUL — same classifier output,
     run through the REAL compute_ewma_rul() (app/ml/rul/ewma.py),
     per machine, in time order

All three evaluated with: MAE, asymmetric score (penalizes late
predictions harder), and decision-zone MAE (true RUL <= 48h).

Run from backend/:
    poetry run python -m scripts.training.experiments.inspect_rul_comparison
"""
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error

from app.ml.rul.ewma import compute_ewma_rul

DATA_DIR = Path("scripts/training/data")
SENSORS = ["voltage", "rotation", "pressure", "vibration"]
COLMAP = {"volt": "voltage", "rotate": "rotation",
          "pressure": "pressure", "vibration": "vibration"}
RUL_CAP_HOURS = 300
DECISION_ZONE_HOURS = 48
FAILURE_HORIZON_HOURS = 48  # for the classifier's own label, matches data_loader.py

print("Loading raw data...")
tel = pd.read_csv(DATA_DIR / "PdM_telemetry.csv", parse_dates=["datetime"])
tel = tel.sort_values(["machineID", "datetime"]).reset_index(drop=True)
tel = tel.rename(columns=COLMAP)
fail = pd.read_csv(DATA_DIR / "PdM_failures.csv", parse_dates=["datetime"])

print("Computing capped hours-to-next-failure (regressor target)...")
tel["hours_to_next_failure"] = np.nan
for mid, grp in fail.groupby("machineID"):
    sub = tel["machineID"] == mid
    idx = tel.index[sub]
    times = tel.loc[idx, "datetime"].values
    failure_times = np.sort(grp["datetime"].values)
    hours_to_next = np.full(len(idx), np.nan)
    for i, t in enumerate(times):
        future_failures = failure_times[failure_times > t]
        if len(future_failures) > 0:
            hours_to_next[i] = (future_failures[0] - t) / np.timedelta64(1, "h")
    tel.loc[idx, "hours_to_next_failure"] = hours_to_next
tel = tel.dropna(subset=["hours_to_next_failure"]).reset_index(drop=True)
tel["rul_target"] = np.minimum(tel["hours_to_next_failure"], RUL_CAP_HOURS)

print("Computing failure_prediction binary label (classifier target)...")
tel["label"] = (tel["hours_to_next_failure"] <= FAILURE_HORIZON_HOURS).astype(int)

print("Building features...")
g = tel.groupby("machineID")
feats = []
for s in SENSORS:
    feats.append(s)
    tel[f"{s}_roll_mean_24"] = g[s].transform(lambda x: x.rolling(24, min_periods=1).mean())
    tel[f"{s}_roll_std_24"] = g[s].transform(lambda x: x.rolling(24, min_periods=1).std())
    tel[f"{s}_rate_change"] = g[s].transform(lambda x: x.diff())
    feats += [f"{s}_roll_mean_24", f"{s}_roll_std_24", f"{s}_rate_change"]
fill_cols = [c for c in tel.columns if ("roll_std" in c or "rate_change" in c)]
for c in fill_cols:
    tel[c] = g[c].transform(lambda x: x.bfill()).fillna(0.0)
for s in ["rotation", "vibration"]:
    tel[f"{s}_available"] = 1.0
feats += ["rotation_available", "vibration_available"]
print(f"  {len(tel)} records, {len(feats)} features")

split_time = tel["datetime"].quantile(0.80)
train_pool = tel[tel["datetime"] <= split_time].copy()
holdout = tel[tel["datetime"] > split_time].copy()

tscv = TimeSeriesSplit(n_splits=3, gap=DECISION_ZONE_HOURS, max_train_size=150_000)
X_pool = train_pool[feats].values.astype(float)
train_idx, val_idx = list(tscv.split(X_pool))[-1]

X_holdout = holdout[feats].values.astype(float)
y_rul_holdout = holdout["rul_target"].values.astype(float)

print("\n[1/3] Training RandomForest REGRESSOR (direct RUL prediction)...")
y_pool_rul = train_pool["rul_target"].values.astype(float)

regressor = Pipeline([("scaler", StandardScaler()),
                       ("model", RandomForestRegressor(n_estimators=100, max_depth=8,
                           random_state=42, n_jobs=1))])
regressor.fit(X_pool[train_idx], y_pool_rul[train_idx])

rul_pred_regressor = regressor.predict(X_holdout)

print("[2/3] Training RandomForest CLASSIFIER (failure_prediction)...")
y_pool_label = train_pool["label"].values.astype(int)

classifier = Pipeline([("scaler", StandardScaler()),
                        ("model", RandomForestClassifier(n_estimators=100, max_depth=6,
                            class_weight="balanced", random_state=42, n_jobs=1))])
classifier.fit(X_pool[train_idx], y_pool_label[train_idx])

failure_proba_holdout = classifier.predict_proba(X_holdout)[:, 1]
rul_pred_naive = (1.0 - failure_proba_holdout) * RUL_CAP_HOURS

print("[3/3] Running EWMA per-machine over holdout, in time order...")


holdout = holdout.copy()
holdout["failure_proba"] = failure_proba_holdout
holdout["health_score"] = (1.0 - holdout["failure_proba"]) * 100.0

# Quick timing probe on ONE machine before committing to the full loop
sample_mid = holdout["machineID"].iloc[0]
sample_grp = holdout[holdout["machineID"] == sample_mid].sort_values("datetime")
print(f"  Timing probe: machine {sample_mid}, {len(sample_grp)} records...")

t0 = time.time()
probe_history = []
for _, row in sample_grp.iterrows():
    _ = compute_ewma_rul(health_history=probe_history)
    probe_history.append((row["datetime"], row["health_score"]))
elapsed = time.time() - t0
print(f"  {len(sample_grp)} records took {elapsed:.2f}s "
      f"({elapsed/len(sample_grp)*1000:.2f}ms per record)")
print(f"  Estimated full holdout time (~{len(holdout)} records, ~100 machines): "
      f"{elapsed/len(sample_grp)*len(holdout):.1f}s")

rul_pred_ewma = np.full(len(holdout), np.nan)
holdout_reset = holdout.reset_index(drop=True)

for mid, grp in holdout_reset.groupby("machineID"):
    grp = grp.sort_values("datetime")
    history: list[tuple] = []
    for row_idx in grp.index:
        row = holdout_reset.loc[row_idx]
        rul_days, _confidence = compute_ewma_rul(health_history=history)
        if rul_days is not None:
            rul_pred_ewma[row_idx] = min(rul_days * 24.0, RUL_CAP_HOURS)
        history.append((row["datetime"], row["health_score"]))

print(f"\n{'='*70}")
print("THREE-WAY RUL COMPARISON — holdout set")
print(f"{'='*70}")


def asymmetric_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    error = y_pred - y_true
    penalty = np.where(error > 0, np.exp(error / 60) - 1, np.exp(-error / 80) - 1)
    return float(np.mean(penalty))

print("\nDEBUG: raw EWMA prediction distribution (hours, before any masking)")
valid_ewma = rul_pred_ewma[~np.isnan(rul_pred_ewma)]
print(f"  count: {len(valid_ewma)}")
print(f"  min: {valid_ewma.min():.1f}")
print(f"  max: {valid_ewma.max():.1f}")
print(f"  mean: {valid_ewma.mean():.1f}")
print(f"  median: {np.median(valid_ewma):.1f}")
print(f"  values > 10000: {(valid_ewma > 10000).sum()}")
print(f"  top 10 largest: {sorted(valid_ewma)[-10:]}")

def evaluate_rul(name: str, y_true: np.ndarray, y_pred: np.ndarray) -> None:
    valid = ~np.isnan(y_pred)
    n_valid = valid.sum()
    mae = mean_absolute_error(y_true[valid], y_pred[valid])
    asym = asymmetric_score(y_true[valid], y_pred[valid])

    zone_mask = valid & (y_true <= DECISION_ZONE_HOURS)
    zone_mae = (
        mean_absolute_error(y_true[zone_mask], y_pred[zone_mask])
        if zone_mask.sum() > 0 else float("nan")
    )

    print(f"\n{name}")
    print(f"  Valid predictions:    {n_valid} / {len(y_true)} ({n_valid/len(y_true)*100:.1f}%)")
    print(f"  Overall MAE:          {mae:.2f} hours")
    print(f"  Asymmetric score:     {asym:.4f}  (lower = better)")
    print(f"  Decision-zone records: {zone_mask.sum()}")
    print(f"  Decision-zone MAE:    {zone_mae:.2f} hours")


evaluate_rul("1. RandomForest REGRESSOR (direct)", y_rul_holdout, rul_pred_regressor)
evaluate_rul("2. Naive classifier-derived RUL (no smoothing)", y_rul_holdout, rul_pred_naive)
evaluate_rul("3. EWMA-smoothed classifier-derived RUL", y_rul_holdout, rul_pred_ewma)