"""
Test whether a SHORT rolling window (6h) rescues the rolling-std /
rate-of-change features that the 24h-only model is ignoring.

We don't touch data_loader.py or config.py — this is a standalone
copy of the feature-building logic, modified to add 6h features
alongside the existing 24h ones, so we can compare feature
importances side by side.

Run from backend/:
    poetry run python inspect_dual_window.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit

DATA_DIR = Path("scripts/training/data")
SENSORS = ["voltage", "rotation", "pressure", "vibration"]
COLMAP = {"volt": "voltage", "rotate": "rotation",
          "pressure": "pressure", "vibration": "vibration"}
FAILURE_HORIZON_HOURS = 48

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

print("Building features (24h only, then 24h+6h)...")
g = tel.groupby("machineID")

def build_features(windows: list[int]) -> list[str]:
    feats = []
    for s in SENSORS:
        feats.append(s)
        for w in windows:
            tel[f"{s}_roll_mean_{w}"] = g[s].transform(
                lambda x: x.rolling(w, min_periods=1).mean())
            tel[f"{s}_roll_std_{w}"] = g[s].transform(
                lambda x: x.rolling(w, min_periods=1).std())
            feats.append(f"{s}_roll_mean_{w}")
            feats.append(f"{s}_roll_std_{w}")
        tel[f"{s}_rate_change"] = g[s].transform(lambda x: x.diff())
        feats.append(f"{s}_rate_change")
    fill_cols = [c for c in tel.columns if ("roll_std" in c or "rate_change" in c)]
    for c in fill_cols:
        tel[c] = g[c].transform(lambda x: x.bfill()).fillna(0.0)
    return feats


def train_and_rank(feats: list[str], label: str) -> None:
    X = tel[feats].values.astype(float)
    y = tel["label"].values.astype(int)
    tscv = TimeSeriesSplit(n_splits=3, gap=FAILURE_HORIZON_HOURS, max_train_size=150_000)
    train_idx, val_idx = list(tscv.split(X))[-1]  # use last fold only, for speed

    pipe = Pipeline([("scaler", StandardScaler()),
                      ("model", RandomForestClassifier(
                          n_estimators=100, max_depth=6,
                          class_weight="balanced", random_state=42, n_jobs=1))])
    pipe.fit(X[train_idx], y[train_idx])

    importances = pipe.named_steps["model"].feature_importances_
    ranked = sorted(zip(feats, importances), key=lambda x: x[1], reverse=True)

    print(f"\n{'='*60}\n{label}\n{'='*60}")
    for name, imp in ranked:
        bar = "█" * int(imp * 100)
        print(f"  {name:<28} {imp:.4f}  {bar}")


feats_24_only = build_features([24])
train_and_rank(feats_24_only, "24h-ONLY features (baseline, matches real pipeline)")

feats_dual = build_features([6, 24])
train_and_rank(feats_dual, "6h + 24h DUAL-WINDOW features")