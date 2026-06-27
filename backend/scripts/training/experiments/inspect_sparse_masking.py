"""
Test whether training with randomly masked sensors (simulating missing
hardware) produces a model that's actually robust to missing sensors
at evaluation time, without meaningfully hurting performance when all
sensors ARE present.

Three things compared:
  A) baseline  - no masking at train or eval time (today's real model)
  B) masked    - masking applied at TRAIN time, evaluated normally (all sensors present)
  C) sparse    - model B, but evaluated with vibration ALWAYS missing
                 (simulating a real facility without a vibration sensor)

Run from backend/:
    poetry run python inspect_sparse_masking.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

DATA_DIR = Path("scripts/training/data")
SENSORS = ["voltage", "rotation", "pressure", "vibration"]
COLMAP = {"volt": "voltage", "rotate": "rotation",
          "pressure": "pressure", "vibration": "vibration"}
FAILURE_HORIZON_HOURS = 48
MASK_PROB = 0.15

print("Loading raw data...")
tel = pd.read_csv(DATA_DIR / "PdM_telemetry.csv", parse_dates=["datetime"])
tel = tel.sort_values(["machineID", "datetime"]).reset_index(drop=True)
tel = tel.rename(columns=COLMAP)
fail = pd.read_csv(DATA_DIR / "PdM_failures.csv", parse_dates=["datetime"])

print("Building labels...")
tel["label"] = 0
for mid, grp in fail.groupby("machineID"):
    sub = tel["machineID"] == mid
    idx = tel.index[sub]
    times = tel.loc[idx, "datetime"].values
    lab = np.zeros(len(idx), dtype=int)
    for ft in grp["datetime"].values:
        ws = ft - np.timedelta64(FAILURE_HORIZON_HOURS, "h")
        lab |= ((times > ws) & (times <= ft))
    tel.loc[idx, "label"] = lab

print("Building base features (raw + roll_mean_24 + roll_std_24 + rate_change)...")
g = tel.groupby("machineID")
base_feats = []
for s in SENSORS:
    base_feats.append(s)
    tel[f"{s}_roll_mean_24"] = g[s].transform(lambda x: x.rolling(24, min_periods=1).mean())
    tel[f"{s}_roll_std_24"] = g[s].transform(lambda x: x.rolling(24, min_periods=1).std())
    tel[f"{s}_rate_change"] = g[s].transform(lambda x: x.diff())
    base_feats += [f"{s}_roll_mean_24", f"{s}_roll_std_24", f"{s}_rate_change"]

fill_cols = [c for c in tel.columns if ("roll_std" in c or "rate_change" in c)]
for c in fill_cols:
    tel[c] = g[c].transform(lambda x: x.bfill()).fillna(0.0)

# Add _available flags, default 1.0 (present)
for s in SENSORS:
    tel[f"{s}_available"] = 1.0

all_feats = base_feats + [f"{s}_available" for s in SENSORS]

def sensor_cols(s: str) -> list[str]:
    return [s, f"{s}_roll_mean_24", f"{s}_roll_std_24", f"{s}_rate_change"]

# Split into a pool + holdout, same as the real pipeline
split_time = tel["datetime"].quantile(0.80)
train_pool = tel[tel["datetime"] <= split_time].copy()
holdout = tel[tel["datetime"] > split_time].copy()

tscv = TimeSeriesSplit(n_splits=3, gap=FAILURE_HORIZON_HOURS, max_train_size=150_000)
X_pool = train_pool[all_feats].values.astype(float)
y_pool = train_pool["label"].values.astype(int)
train_idx, val_idx = list(tscv.split(X_pool))[-1]


def apply_masking(X: np.ndarray, feats: list[str], rng: np.random.Generator) -> np.ndarray:
    """Randomly mask each sensor independently per row."""
    X = X.copy()
    n = X.shape[0]
    for s in SENSORS:
        mask = rng.random(n) < MASK_PROB
        cols = [feats.index(c) for c in sensor_cols(s)]
        avail_idx = feats.index(f"{s}_available")
        for c in cols:
            X[mask, c] = 0.0
        X[mask, avail_idx] = 0.0
    return X


def force_missing(X: np.ndarray, feats: list[str], sensor: str) -> np.ndarray:
    """Force one sensor to ALWAYS be missing (simulating no hardware)."""
    X = X.copy()
    cols = [feats.index(c) for c in sensor_cols(sensor)]
    avail_idx = feats.index(f"{sensor}_available")
    for c in cols:
        X[:, c] = 0.0
    X[:, avail_idx] = 0.0
    return X


def evaluate(model: Pipeline, X: np.ndarray, y: np.ndarray, label: str) -> None:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(y, proba) if len(np.unique(y)) > 1 else float("nan")
    p = precision_score(y, pred, zero_division=0)
    r = recall_score(y, pred, zero_division=0)
    f1 = f1_score(y, pred, zero_division=0)
    print(f"  {label:<40} auc={auc:.4f}  precision={p:.4f}  recall={r:.4f}  f1={f1:.4f}")


rng = np.random.default_rng(42)

X_train_raw, y_train = X_pool[train_idx], y_pool[train_idx]
X_val_raw, y_val = X_pool[val_idx], y_pool[val_idx]
X_holdout_raw = holdout[all_feats].values.astype(float)
y_holdout = holdout["label"].values.astype(int)

print("\nTraining model A (baseline, no masking)...")
model_a = Pipeline([("scaler", StandardScaler()),
                     ("model", RandomForestClassifier(n_estimators=100, max_depth=6,
                         class_weight="balanced", random_state=42, n_jobs=1))])
model_a.fit(X_train_raw, y_train)

print("Training model B (masking applied during training)...")
X_train_masked = apply_masking(X_train_raw, all_feats, rng)
model_b = Pipeline([("scaler", StandardScaler()),
                     ("model", RandomForestClassifier(n_estimators=100, max_depth=6,
                         class_weight="balanced", random_state=42, n_jobs=1))])
model_b.fit(X_train_masked, y_train)

print("\n" + "=" * 90)
print("RESULTS — holdout set")
print("=" * 90)
evaluate(model_a, X_holdout_raw, y_holdout, "A: baseline, full sensors at eval")
evaluate(model_b, X_holdout_raw, y_holdout, "B: masking-trained, full sensors at eval")

X_holdout_no_vibe = force_missing(X_holdout_raw, all_feats, "vibration")
evaluate(model_a, X_holdout_no_vibe, y_holdout, "A: baseline, vibration FORCED missing at eval")
evaluate(model_b, X_holdout_no_vibe, y_holdout, "B: masking-trained, vibration FORCED missing at eval")

X_holdout_no_rotation = force_missing(X_holdout_raw, all_feats, "rotation")
evaluate(model_a, X_holdout_no_rotation, y_holdout, "A: baseline, rotation FORCED missing at eval")
evaluate(model_b, X_holdout_no_rotation, y_holdout, "B: masking-trained, rotation FORCED missing at eval")