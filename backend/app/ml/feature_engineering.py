"""
ML feature engineering.
 
Transforms raw telemetry values into the numerical feature vectors
that ML models consume. This module is the contract between training
and inference — both pipelines use the same functions to guarantee
the model receives identical feature representations at both stages.
 
Sparse-safe design: missing sensors are represented as zero values
with a corresponding availability flag set to 0.0, rather than
raising errors or imputing values. Models are trained on all
configurations of sensor availability so they handle missingness
correctly at inference time.
 
Feature naming convention:
    {metric}              -> raw sensor value
    {metric}_available    -> 1.0 if sensor present, 0.0 if missing
    {metric}_zscore       -> deviation from learned baseline mean
                            (0.0 when no mature baseline exists)
"""

import logging
import numpy as np
from typing import Any 

from app.models.ml_asset_baseline import MLAssetBaseline 

logger = logging.getLogger(__name__)

# Suffix tokens that identify derived feature types
_AVAILABLE_SUFFIX = "_available"
_ZSCORE_SUFFIX = "_zscore"


def build_feature_vector(
    telemetry_history: list[dict[str, Any]],
    baselines: list[MLAssetBaseline],
    feature_names: list[str],
    rolling_window: int = 24,
) -> list[float]:
    """
    Build a numerical feature vector from a window of telemetry history.

    Produces features in the exact order specified by feature_names —
    the order the model was trained on. Raises if a feature name cannot
    be resolved, since silent defaults on unknown features produce
    wrong predictions without any warning.

    telemetry_history must be ORDERED OLDEST-FIRST, with the LAST entry
    being the current reading to score. Rolling features (mean, std)
    are computed across the full window; rate_change is the difference
    between the last two entries. This mirrors
    scripts/training/data_loader.py's _build_rolling_features() logic,
    just computed over a small live window instead of the full
    historical dataset.

    Missing sensors are handled via the sparse-safe pattern (only for
    sensors in the feature_names list that have an _available
    counterpart — see scripts/training/config.py's MASKABLE_SENSORS
    for which sensors this currently applies to):
        raw value          -> 0.0
        rolling mean/std    -> 0.0
        rate_change          -> 0.0
        availability flag    -> 0.0
        z_score              -> 0.0

    Args:
        telemetry_history: Ordered (oldest-first) list of telemetry
            payload dicts, e.g. [{"voltage": 175.2, "rotation": 490.1,
            ...}, ...]. The last entry is the current reading.
        baselines: All MLAssetBaseline records for this asset. Used to
            compute z-scores for each metric.
        feature_names: Ordered list of feature names from MLModel.
            feature_names. The output vector matches this order exactly.
        rolling_window: Expected window size — used only for the
            roll_mean_{N}/roll_std_{N} feature-name suffix matching;
            does not truncate telemetry_history (callers are
            responsible for fetching an appropriately-sized window).

    Returns:
        list[float]: Feature vector in feature_names order, ready for
            inference.

    Raises:
        ValueError: If telemetry_history is empty, or if a feature
            name does not match any known pattern.
    """
    if not telemetry_history:
        raise ValueError(
            "telemetry_history is empty — cannot build a feature "
            "vector with no telemetry data. Callers must verify at "
            "least one record exists before calling this function."
        )
    current = telemetry_history[-1]
    previous = telemetry_history[-2] if len(telemetry_history) >= 2 else None

    baseline_map = {b.metric_name: b for b in baselines}

    # Pre-extract per-sensor history arrays once, reused across multiple
    # feature_names referencing the same sensor (e.g. both roll_mean
    # and roll_std for "rotation" reuse the same underlying values).
    sensor_names_in_history: set[str] = set()
    for record in telemetry_history:
        sensor_names_in_history.update(record.keys())

    sensor_value_arrays: dict[str, list[float]] = {}
    for sensor in sensor_names_in_history:
        sensor_value_arrays[sensor] = [
            float(record[sensor]) for record in telemetry_history if sensor in record
        ]

    vector: list[float] = []

    for name in feature_names:
        if name.endswith("_available"):
            sensor = name.removesuffix("_available")
            value = 1.0 if sensor in current else 0.0

        elif name.endswith("_zscore"):
            sensor = name.removesuffix("_zscore")
            baseline = baseline_map.get(sensor)
            if (
                baseline is not None
                and baseline.is_mature
                and sensor in current
                and baseline.baseline_std
                and baseline.baseline_std > 0
            ):
                value = (float(current[sensor]) - baseline.baseline_mean) / baseline.baseline_std
            else:
                value = 0.0

        elif name.endswith("_rate_change"):
            sensor = name.removesuffix("_rate_change")
            if previous is not None and sensor in current and sensor in previous:
                value = float(current[sensor]) - float(previous[sensor])
            else:
                value = 0.0

        elif name.endswith(f"_roll_mean_{rolling_window}"):
            sensor = name.removesuffix(f"_roll_mean_{rolling_window}")
            values = sensor_value_arrays.get(sensor, [])
            value = float(np.mean(values)) if values else 0.0

        elif name.endswith(f"_roll_std_{rolling_window}"):
            sensor = name.removesuffix(f"_roll_std_{rolling_window}")
            values = sensor_value_arrays.get(sensor, [])
            value = float(np.std(values)) if len(values) >= 2 else 0.0

        elif name in current:
            value = float(current[name])

        else:
            raise ValueError(
                f"Feature name '{name}' does not match any known "
                f"pattern (_available, _zscore, _rate_change, "
                f"_roll_mean_{rolling_window}, _roll_std_{rolling_window}, "
                f"or a bare sensor name) and is not present in the "
                f"current telemetry reading."
            )

        vector.append(value)

    return vector