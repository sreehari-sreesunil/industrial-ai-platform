"""
Validates PSI-based drift detection (app/ml/drift.py) using the real
Azure Predictive Maintenance dataset, two ways:

  1. NEGATIVE CONTROL: real train_pool (80%, reference) vs. real
     holdout (20%, current) — both genuine, unperturbed data from the
     same underlying process. Expect LOW PSI (no real drift, just
     normal time-based variation).

  2. POSITIVE CONTROL: holdout vs. a copy of holdout with rotation's
     mean shifted +10% (simulating realistic sensor calibration
     drift). Expect PSI to rise sharply and be correctly flagged.

Run from backend/:
    poetry run python -m scripts.training.experiments.inspect_drift_detection
"""
import numpy as np
import pandas as pd
from pathlib import Path

from app.ml.drift import calculate_psi, classify_drift_severity

DATA_DIR = Path("scripts/training/data")
SENSORS = ["voltage", "rotation", "pressure", "vibration"]
COLMAP = {"volt": "voltage", "rotate": "rotation",
          "pressure": "pressure", "vibration": "vibration"}

print("Loading raw data...")
tel = pd.read_csv(DATA_DIR / "PdM_telemetry.csv", parse_dates=["datetime"])
tel = tel.sort_values(["machineID", "datetime"]).reset_index(drop=True)
tel = tel.rename(columns=COLMAP)

split_time = tel["datetime"].quantile(0.80)
train_pool = tel[tel["datetime"] <= split_time]
holdout = tel[tel["datetime"] > split_time]
print(f"  train_pool: {len(train_pool)} records, holdout: {len(holdout)} records")

print("\n" + "=" * 70)
print("PART 1 — NEGATIVE CONTROL: real train_pool vs. real holdout")
print("=" * 70)
for sensor in SENSORS:
    psi = calculate_psi(
        reference=train_pool[sensor].values,
        current=holdout[sensor].values,
    )
    severity = classify_drift_severity(psi)
    print(f"  {sensor:<12} PSI={psi:.4f}  severity={severity}")

print("\n" + "=" * 70)
print("PART 2 — POSITIVE CONTROL: holdout vs. holdout with rotation +10%")
print("=" * 70)
holdout_drifted = holdout.copy()
holdout_drifted["rotation"] = holdout_drifted["rotation"] * 1.10

for sensor in SENSORS:
    drifted_values = (
        holdout_drifted[sensor].values if sensor == "rotation"
        else holdout[sensor].values  # other sensors unchanged, should stay low PSI
    )
    psi = calculate_psi(
        reference=holdout[sensor].values,
        current=drifted_values,
    )
    severity = classify_drift_severity(psi)
    marker = "  <-- injected drift" if sensor == "rotation" else ""
    print(f"  {sensor:<12} PSI={psi:.4f}  severity={severity}{marker}")