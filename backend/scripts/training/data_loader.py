# scripts/training/data_loader.py
"""
Training data loader.

Loads and prepares the Azure Predictive Maintenance dataset for
model training. Handles column alignment, data validation, failure
label construction, and temporal splitting.

Dataset: Microsoft Azure Predictive Maintenance
Source:  https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance
Files required (place in scripts/training/data/):
    PdM_telemetry.csv   — hourly sensor readings
    PdM_failures.csv    — component failure records

Dataset schema:
    PdM_telemetry.csv:
        datetime    — hourly timestamp
        machineID   — integer machine identifier (1-100)
        volt        — voltage reading
        rotate      — rotation speed
        pressure    — pressure reading
        vibration   — vibration reading

    PdM_failures.csv:
        datetime    — failure timestamp (rounded to nearest hour)
        machineID   — machine that failed
        failure     — component that failed (comp1-comp4)

Column mapping (dataset → NexusIQ feature schema):
    volt      → voltage
    rotate    → rotation
    pressure  → pressure   (direct)
    vibration → vibration  (direct)

Why sklearn Pipeline replaces manual z-score computation:
    Previous version computed z-scores manually using training set
    mean/std, then stored them separately from the model artifact.
    This creates training-serving skew — inference must replicate
    the exact same computation independently.

    Pipeline([StandardScaler(), model]) serializes the scaler WITH
    the model artifact. Inference calls pipeline.predict() and gets
    identical scaling automatically. Zero divergence risk.

    feature_engineering.py still handles availability flags —
    those are not statistical transformations and belong in the
    inference layer, not the training pipeline.

Temporal split strategy:
    TimeSeriesSplit with n_splits folds (default 5).
    Each fold's training set is strictly earlier than its validation set.
    A gap of FAILURE_HORIZON_HOURS records between train and val prevents
    failure windows from straddling the split boundary and leaking labels.

Label construction strategy (failure_prediction):
    A record is labeled 1 if a failure occurs within the next
    FAILURE_HORIZON_HOURS for that machine. Otherwise labeled 0.

Label construction strategy (anomaly_detection):
    IsolationForest is unsupervised — training uses normal records only.
    Anomaly labels used only during evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from scripts.training.config import CV_CONFIG, FEATURE_CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
TELEMETRY_FILE = DATA_DIR / "PdM_telemetry.csv"
FAILURES_FILE = DATA_DIR / "PdM_failures.csv"

COLUMN_MAP: dict[str, str] = {
    "volt":      "voltage",
    "rotate":    "rotation",
    "pressure":  "pressure",
    "vibration": "vibration",
}

# Hours before failure within which records are labeled positive.
# 48h is the chosen labeling horizon: a wider window than a bare 24h
# gives the failure-prediction model more positive lead-time signal to
# learn from (each failure contributes twice as many labeled records),
# at the cost of labeling earlier, less-degraded records as positive.
# This is a design default — tune against held-out precision/recall if a
# labeled horizon sweep is run later. Keep in sync with
# CrossValidationConfig.gap in config.py (the CV gap matches this horizon
# so no failure window straddles a train/val split boundary).
FAILURE_HORIZON_HOURS = 48

# Fraction of full dataset used for final hold-out test set
# CV folds are created from the remaining training portion only
HOLDOUT_FRACTION = 0.20


# ---------------------------------------------------------------------------
# Public contracts
# ---------------------------------------------------------------------------

@dataclass
class CVFold:
    """
    Single cross-validation fold.

    Attributes:
        fold_index: Zero-based fold number.
        X_train:    Training feature matrix.
        X_val:      Validation feature matrix.
        y_train:    Training labels (None for anomaly_detection).
        y_val:      Validation labels.
        n_train:    Training record count.
        n_val:      Validation record count.
        positive_rate: Fraction of positives in training labels.
        hours_to_failure: Per-training-record hours until the next failure
                    for positive records, np.nan for negatives. None for
                    anomaly_detection (unsupervised — no labels or weights).
                    Consumed by the trainer's proximity_weights() to weight
                    records nearer to failure more heavily.
    """
    fold_index: int
    X_train: np.ndarray
    X_val: np.ndarray
    y_train: np.ndarray | None
    y_val: np.ndarray
    n_train: int
    n_val: int
    positive_rate: float
    hours_to_failure: np.ndarray | None = None


@dataclass
class TrainingDataset:
    """
    Output contract of the data loader.

    Contains CV folds for model selection and a final hold-out
    set for unbiased terminal evaluation.

    Attributes:
        folds:          CV folds for training and model selection.
        X_holdout:      Final hold-out feature matrix — used ONCE
                        for terminal evaluation after model selection.
                        Never used during CV or hyperparameter tuning.
        y_holdout:      Hold-out labels.
        feature_names:  Full engineered feature list — raw sensors plus
                        rolling mean, rolling std, and rate-of-change
                        per sensor. Built by FEATURE_CONFIG.feature_names.
                        Scaler in the model Pipeline operates on these
                        directly; availability flags are added separately
                        by the inference engineering layer.
        task:           Inference task this dataset was prepared for.
        n_folds:        Number of CV folds.
        positive_rate:  Overall positive label rate across all folds.
    """
    folds: list[CVFold]
    X_holdout: np.ndarray
    y_holdout: np.ndarray
    feature_names: list[str]
    task: str
    n_folds: int
    positive_rate: float

    def __post_init__(self) -> None:
        if not self.folds:
            raise ValueError("TrainingDataset must contain at least one CV fold.")
        expected_features = len(self.feature_names)
        for fold in self.folds:
            assert fold.X_train.shape[1] == expected_features, (
                f"Fold {fold.fold_index}: X_train has {fold.X_train.shape[1]} "
                f"columns but feature_names has {expected_features} entries."
            )


def load_training_data(task: str) -> TrainingDataset:
    """
    Load and prepare the Azure PM dataset for a given inference task.

    Full pipeline:
        1.  Validate task and file existence
        2.  Load raw CSVs
        3.  Validate data quality
        4.  Align column names to feature schema
        5.  Construct binary failure labels
        6.  Hold out final test set (last HOLDOUT_FRACTION by time)
        7.  Create TimeSeriesSplit CV folds from training portion
        8.  Build raw feature matrices per fold (no scaling —
            scaler is part of the model Pipeline)
        9.  Return TrainingDataset

    Args:
        task: "anomaly_detection" or "failure_prediction".

    Returns:
        TrainingDataset with CV folds and hold-out set.

    Raises:
        FileNotFoundError: If dataset CSVs are not in DATA_DIR.
        ValueError:        If task is not recognized or data is invalid.
    """
    _validate_task(task)
    _validate_files_exist()

    # Steps 2-3: load and validate
    telemetry, failures = _load_raw_data()
    _validate_data_quality(telemetry)

    # Step 4: align columns
    telemetry = _align_columns(telemetry)

    telemetry = _build_rolling_features(
        telemetry=telemetry,
        sensor_names=FEATURE_CONFIG.sensors,
        window=FEATURE_CONFIG.rolling_window,
    )

    # Step 5: construct labels
    telemetry = _attach_failure_labels(
        telemetry=telemetry,
        failures=failures,
        horizon_hours=FAILURE_HORIZON_HOURS,
    )

    # Step 6: global temporal hold-out split
    # Hold-out is the last HOLDOUT_FRACTION of the full timeline
    # This is done BEFORE CV fold creation — hold-out is never
    # seen during cross-validation
    split_time = telemetry["datetime"].quantile(1.0 - HOLDOUT_FRACTION)
    train_pool = telemetry[telemetry["datetime"] <= split_time].copy()
    holdout_df = telemetry[telemetry["datetime"] > split_time].copy()

    logger.info(
        "Hold-out split: %d training pool / %d hold-out records",
        len(train_pool),
        len(holdout_df),
    )

    # Step 7-8: build CV folds from training pool
    feature_cols = FEATURE_CONFIG.feature_names
    X_pool = train_pool[feature_cols].values.astype(float)
    y_pool = train_pool["label"].values
    hours_pool = train_pool["hours_to_failure"].values.astype(float)

    tscv = TimeSeriesSplit(
        n_splits=CV_CONFIG.n_splits,
        gap=CV_CONFIG.gap,
        max_train_size=CV_CONFIG.max_train_size,
        test_size=CV_CONFIG.test_size,
    )

    folds: list[CVFold] = []
    for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X_pool)):
        X_train_raw = X_pool[train_idx]
        X_val_raw = X_pool[val_idx]
        y_train_raw = y_pool[train_idx]
        y_val = y_pool[val_idx]
        hours_train_raw = hours_pool[train_idx]

        positive_rate = float(y_train_raw.mean())

        if task == "anomaly_detection":
            # Train on normal records only — unsupervised, no labels or weights
            normal_mask = y_train_raw == 0
            X_train = X_train_raw[normal_mask]
            y_train = None
            hours_to_failure = None
        else:
            X_train = X_train_raw
            y_train = y_train_raw
            hours_to_failure = hours_train_raw

        folds.append(CVFold(
            fold_index=fold_idx,
            X_train=X_train,
            X_val=X_val_raw,
            y_train=y_train,
            y_val=y_val,
            n_train=len(X_train),
            n_val=len(X_val_raw),
            positive_rate=positive_rate,
            hours_to_failure=hours_to_failure,
        ))

        logger.info(
            "Fold %d: n_train=%d n_val=%d positive_rate=%.3f",
            fold_idx,
            len(X_train),
            len(X_val_raw),
            positive_rate,
        )

    # Build hold-out matrices
    X_holdout = holdout_df[feature_cols].values.astype(float)
    y_holdout = holdout_df["label"].values

    overall_positive_rate = float(y_pool.mean())

    logger.info(
        "Dataset ready: task=%s folds=%d overall_positive_rate=%.3f "
        "holdout_records=%d features=%d",
        task,
        len(folds),
        overall_positive_rate,
        len(X_holdout),
        len(feature_cols),
    )

    return TrainingDataset(
        folds=folds,
        X_holdout=X_holdout,
        y_holdout=y_holdout,
        feature_names=feature_cols,   # full 16-feature list, not just sensor_names
        task=task,
        n_folds=len(folds),
        positive_rate=overall_positive_rate,
    )


# ---------------------------------------------------------------------------
# Internal pipeline steps
# ---------------------------------------------------------------------------

def _validate_task(task: str) -> None:
    valid = ("anomaly_detection", "failure_prediction")
    if task not in valid:
        raise ValueError(
            f"Unknown task '{task}'. Must be one of: {', '.join(valid)}."
        )


def _validate_files_exist() -> None:
    missing = [f for f in (TELEMETRY_FILE, FAILURES_FILE) if not f.exists()]
    if missing:
        missing_names = ", ".join(f.name for f in missing)
        raise FileNotFoundError(
            f"Dataset files not found: {missing_names}\n"
            f"Download from: https://www.kaggle.com/datasets/arnabbiswas1/"
            f"microsoft-azure-predictive-maintenance\n"
            f"Place CSV files in: {DATA_DIR}"
        )


def _load_raw_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    logger.info("Reading %s", TELEMETRY_FILE.name)
    telemetry = pd.read_csv(TELEMETRY_FILE, parse_dates=["datetime"])
    telemetry = telemetry.sort_values(
        ["machineID", "datetime"]
    ).reset_index(drop=True)

    logger.info("Reading %s", FAILURES_FILE.name)
    failures = pd.read_csv(FAILURES_FILE, parse_dates=["datetime"])

    logger.info(
        "Loaded %d telemetry records, %d machines, %d failure events",
        len(telemetry),
        telemetry["machineID"].nunique(),
        len(failures),
    )
    return telemetry, failures


def _validate_data_quality(telemetry: pd.DataFrame) -> None:
    """
    Validate data quality before any processing.

    Checks:
        - Required columns present
        - No NaN values in sensor columns
        - No infinite values
        - No zero-variance sensors (would make z-scores meaningless)
        - Minimum record count

    Raises:
        ValueError: With specific diagnostic on first failure found.
    """
    required_cols = {"datetime", "machineID", "volt", "rotate", "pressure", "vibration"}
    missing_cols = required_cols - set(telemetry.columns)
    if missing_cols:
        raise ValueError(
            f"Telemetry CSV missing required columns: {missing_cols}. "
            f"Check dataset download — expected Azure PM format."
        )

    sensor_cols = ["volt", "rotate", "pressure", "vibration"]

    # NaN check
    nan_counts = telemetry[sensor_cols].isna().sum()
    nan_sensors = nan_counts[nan_counts > 0]
    if not nan_sensors.empty:
        raise ValueError(
            f"NaN values found in sensors: {nan_sensors.to_dict()}. "
            f"Handle missing values before training."
        )

    # Infinite value check
    inf_mask = np.isinf(telemetry[sensor_cols].values)
    if inf_mask.any():
        inf_cols = [sensor_cols[i] for i in range(len(sensor_cols))
                    if inf_mask[:, i].any()]
        raise ValueError(
            f"Infinite values found in sensors: {inf_cols}."
        )

    # Zero variance check — StandardScaler produces NaN for zero-variance features
    variances = telemetry[sensor_cols].var()
    zero_var = variances[variances == 0]
    if not zero_var.empty:
        raise ValueError(
            f"Zero-variance sensors found: {list(zero_var.index)}. "
            f"These sensors carry no information and will break scaling."
        )

    # Minimum record count
    min_records = 10_000
    if len(telemetry) < min_records:
        raise ValueError(
            f"Only {len(telemetry)} records found — expected at least "
            f"{min_records}. Dataset may be incomplete."
        )

    logger.info(
        "Data quality validation passed: %d records, no NaN/Inf/zero-variance",
        len(telemetry),
    )


def _align_columns(telemetry: pd.DataFrame) -> pd.DataFrame:
    telemetry = telemetry.rename(columns=COLUMN_MAP)
    missing = [s for s in FEATURE_CONFIG.sensors if s not in telemetry.columns]
    if missing:
        raise ValueError(
            f"After column alignment, missing sensors: {missing}. "
            f"Check COLUMN_MAP in data_loader.py."
        )
    return telemetry


def _attach_failure_labels(
    telemetry: pd.DataFrame,
    failures: pd.DataFrame,
    horizon_hours: int,
) -> pd.DataFrame:
    """
    Construct binary failure labels using a trailing horizon window.

    A record is labeled 1 if a failure occurs within the next
    horizon_hours for the same machine. Otherwise 0.

    Alongside the binary label, a continuous 'hours_to_failure' column is
    built: for a positive record it holds the hours until the failure that
    labeled it (the minimum when overlapping failure windows cover the same
    record), and np.nan for negatives. The trainer turns this into per-sample
    weights so records nearer to a failure carry more influence.

    Args:
        telemetry:     Aligned telemetry DataFrame.
        failures:      Failure records with datetime + machineID.
        horizon_hours: Hours before failure to label as positive.

    Returns:
        pd.DataFrame: Telemetry with 'label' and 'hours_to_failure' columns.
    """
    telemetry = telemetry.copy()
    telemetry["label"] = 0
    telemetry["hours_to_failure"] = np.nan
    horizon = pd.Timedelta(hours=horizon_hours)

    for _, failure in failures.iterrows():
        machine_id = failure["machineID"]
        failure_time = failure["datetime"]
        window_start = failure_time - horizon

        mask = (
            (telemetry["machineID"] == machine_id)
            & (telemetry["datetime"] > window_start)
            & (telemetry["datetime"] <= failure_time)
        )
        telemetry.loc[mask, "label"] = 1

        # Hours from each in-window record to this failure. np.fmin keeps the
        # smaller of any existing value and this one while ignoring NaN, so a
        # record covered by multiple failure windows takes the nearest failure.
        hours_until = (
            (failure_time - telemetry.loc[mask, "datetime"]).dt.total_seconds()
            / 3600.0
        )
        telemetry.loc[mask, "hours_to_failure"] = np.fmin(
            telemetry.loc[mask, "hours_to_failure"],
            hours_until,
        )

    positive_rate = telemetry["label"].mean()
    logger.info(
        "Label construction complete: %.2f%% positive rate (%d / %d records)",
        positive_rate * 100,
        telemetry["label"].sum(),
        len(telemetry),
    )
    return telemetry

def _build_rolling_features(
    telemetry: pd.DataFrame,
    sensor_names: list[str],
    window: int,
) -> pd.DataFrame:
    """
    Compute rolling features per machine, in time order.

    Must run BEFORE any splitting — rolling statistics require a
    continuous time series. Computing them after splitting would
    corrupt the window at fold boundaries (mixing un-related time
    ranges) and leak information across the train/val boundary.

    Adds three derived columns per sensor:
        {sensor}_roll_mean_{window}  — rolling mean over `window` records
        {sensor}_roll_std_{window}   — rolling std over `window` records
        {sensor}_rate_change         — first difference from previous record

    NaN values from the warm-up period (first `window` records per
    machine) are backfilled with the first valid value — these are
    the earliest records for each machine where insufficient history
    exists to compute a full window.

    Args:
        telemetry:    Telemetry DataFrame, already sorted by
                      machineID + datetime.
        sensor_names: Raw sensor column names.
        window:       Rolling window size in records.

    Returns:
        pd.DataFrame: Telemetry with rolling feature columns added.
    """
    telemetry = telemetry.copy()

    for sensor in sensor_names:
        grouped = telemetry.groupby("machineID")[sensor]

        telemetry[f"{sensor}_roll_mean_{window}"] = (
            grouped.transform(lambda s: s.rolling(window, min_periods=1).mean())
        )
        telemetry[f"{sensor}_roll_std_{window}"] = (
            grouped.transform(lambda s: s.rolling(window, min_periods=1).std())
        )
        telemetry[f"{sensor}_rate_change"] = (
            grouped.transform(lambda s: s.diff())
        )

    # Backfill NaN from rolling std (first record per machine has no std)
    # and rate_change (first record per machine has no prior value)
    roll_std_cols = [f"{s}_roll_std_{window}" for s in sensor_names]
    rate_change_cols = [f"{s}_rate_change" for s in sensor_names]

    for col in roll_std_cols + rate_change_cols:
        telemetry[col] = telemetry.groupby("machineID")[col].transform(
            lambda s: s.bfill().fillna(0.0)
        )

    logger.info(
        "Rolling features built: window=%d, added %d derived columns",
        window,
        len(sensor_names) * 3,
    )

    return telemetry