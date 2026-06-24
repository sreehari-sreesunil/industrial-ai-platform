# Training Data

Dataset: Microsoft Azure Predictive Maintenance
Source: https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance

## Setup

1. Download the dataset from the Kaggle link above (requires free Kaggle account)
2. Place the following files in this directory:
    - PdM_telemetry.csv
    - PdM_failures.csv

## Why these files are not committed

The telemetry CSV is ~150MB. Large data files are never committed to Git.
This directory is tracked via .gitkeep — the data files are gitignored.

## Dataset schema

PdM_telemetry.csv  — 876,099 hourly sensor readings from 100 machines
    datetime, machineID, volt, rotate, pressure, vibration

PdM_failures.csv   — component failure records
    datetime, machineID, failure (comp1–comp4)