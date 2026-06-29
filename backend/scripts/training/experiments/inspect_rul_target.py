"""
Inspect the real distribution of hours-to-next-failure before deciding
whether to cap it for RUL regression training.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("scripts/training/data")
COLMAP = {"volt": "voltage", "rotate": "rotation",
          "pressure": "pressure", "vibration": "vibration"}

print("Loading raw data...")
tel = pd.read_csv(DATA_DIR / "PdM_telemetry.csv", parse_dates=["datetime"])
tel = tel.sort_values(["machineID", "datetime"]).reset_index(drop=True)
tel = tel.rename(columns=COLMAP)
fail = pd.read_csv(DATA_DIR / "PdM_failures.csv", parse_dates=["datetime"])

print("Computing hours-to-NEXT-failure (unbounded) per machine...")
tel["hours_to_next_failure"] = np.nan

for mid, grp in fail.groupby("machineID"):
    sub = tel["machineID"] == mid
    idx = tel.index[sub]
    times = tel.loc[idx, "datetime"].values
    failure_times = np.sort(grp["datetime"].values)

    # for each record, find the smallest failure time STRICTLY AFTER it
    hours_to_next = np.full(len(idx), np.nan)
    for i, t in enumerate(times):
        future_failures = failure_times[failure_times > t]
        if len(future_failures) > 0:
            next_failure = future_failures[0]
            hours_to_next[i] = (next_failure - t) / np.timedelta64(1, "h")
    tel.loc[idx, "hours_to_next_failure"] = hours_to_next

valid = tel["hours_to_next_failure"].dropna()
print(f"\nRecords with a known next failure: {len(valid)} / {len(tel)} ({len(valid)/len(tel)*100:.1f}%)")
print(f"Records with NO future failure (machine's last failure already happened, "
      f"or never fails again in the dataset): {tel['hours_to_next_failure'].isna().sum()}")

print(f"\nDistribution of hours_to_next_failure (for records that DO have one):")
print(valid.describe())
print(f"\nPercentiles:")
for p in [50, 75, 90, 95, 99]:
    print(f"  p{p}: {valid.quantile(p/100):.1f} hours")