"""
Test whether a TIME-RESPECTING per-machine baseline z-score feature
improves failure_prediction precision, beyond what the existing
18-feature model (with sparse-sensor masking) already achieves.

Critical design constraint: each machine's baseline at time T must be
computed ONLY from that machine's data strictly before T (an expanding
window). Using future data to compute a "historical" baseline would be
information leakage — the model would effectively be told something
about its own evaluation period.

Compared:
  A) baseline  - today's real 18-feature model (no per-machine z-score)
  B) zscore    - same 18 features + 4 new {sensor}_zscore features,
                 each computed from that machine's own expanding-window
                 mean/std up to (not including) the current record

Run from backend/:
    poetry run python -m scripts.training.experiments.inspect_per_machine_baseline
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
MIN_HISTORY_FOR_BASELINE = 24  # records needed before a machine gets a real baseline

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

# availability flags (matching real pipeline, always 1.0 here)
for s in ["rotation", "vibration"]:
    tel[f"{s}_available"] = 1.0

feats_a = base_feats + ["rotation_available", "vibration_available"]

print("Building TIME-RESPECTING per-machine z-score features...")
print(f"  (expanding window, shifted by 1 to exclude current record,")
print(f"   minimum {MIN_HISTORY_FOR_BASELINE} prior records required)")
for s in SENSORS:
    # expanding mean/std computed on data STRICTLY BEFORE the current row
    # .shift(1) excludes the current value from its own baseline
    expanding_mean = g[s].transform(lambda x: x.shift(1).expanding().mean())
    expanding_std = g[s].transform(lambda x: x.shift(1).expanding().std())
    expanding_count = g[s].transform(lambda x: x.shift(1).expanding().count())

    is_mature = expanding_count >= MIN_HISTORY_FOR_BASELINE
    zscore = np.where(
        is_mature & (expanding_std > 0),
        (tel[s] - expanding_mean) / expanding_std,
        0.0,  # immature baseline -> 0.0, matching feature_engineering.py's real convention
    )
    tel[f"{s}_zscore"] = zscore

feats_b = feats_a + [f"{s}_zscore" for s in SENSORS]

# Split into pool + holdout, same as the real pipeline
split_time = tel["datetime"].quantile(0.80)
train_pool = tel[tel["datetime"] <= split_time].copy()
holdout = tel[tel["datetime"] > split_time].copy()

tscv = TimeSeriesSplit(n_splits=3, gap=FAILURE_HORIZON_HOURS, max_train_size=150_000)


def evaluate(model, X, y, label: str) -> None:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(y, proba) if len(np.unique(y)) > 1 else float("nan")
    p = precision_score(y, pred, zero_division=0)
    r = recall_score(y, pred, zero_division=0)
    f1 = f1_score(y, pred, zero_division=0)
    print(f"  {label:<40} auc={auc:.4f}  precision={p:.4f}  recall={r:.4f}  f1={f1:.4f}")


def train_and_eval(feats: list[str], label: str) -> None:
    X_pool = train_pool[feats].values.astype(float)
    y_pool = train_pool["label"].values.astype(int)
    train_idx, val_idx = list(tscv.split(X_pool))[-1]

    model = Pipeline([("scaler", StandardScaler()),
                       ("model", RandomForestClassifier(n_estimators=100, max_depth=6,
                           class_weight="balanced", random_state=42, n_jobs=1))])
    model.fit(X_pool[train_idx], y_pool[train_idx])

    X_holdout = holdout[feats].values.astype(float)
    y_holdout = holdout["label"].values.astype(int)
    evaluate(model, X_holdout, y_holdout, label)

    if "rotation_zscore" in feats:
        importances = model.named_steps["model"].feature_importances_
        ranked = sorted(zip(feats, importances), key=lambda x: x[1], reverse=True)
        print(f"\n  Top 5 features for {label}:")
        for name, imp in ranked[:5]:
            print(f"    {name:<28} {imp:.4f}")


print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
train_and_eval(feats_a, "A: baseline (18 features, no per-machine zscore)")
train_and_eval(feats_b, "B: with per-machine zscore (22 features)")