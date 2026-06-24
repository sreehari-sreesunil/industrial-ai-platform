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
from typing import Any 

from app.models.ml_asset_baseline import MLAssetBaseline 

logger = logging.getLogger(__name__)

# Suffix tokens that identify derived feature types
_AVAILABLE_SUFFIX = "_available"
_ZSCORE_SUFFIX = "_zscore"


def build_feature_vector(
    telemetry_values: dict[str, Any],
    baselines: list[MLAssetBaseline],
    feature_names: list[str],
) -> list[float]:
    """
    Build a numeical feature vector from raw telemetry values.

    Produces features in the exact order specified by feature_names -
    the order the model was trained on. Raises if a feature name cannot
    be resolved, since silent defaults on unknown features produce 
    wrong predictions without any warning. 

    Missing sensors are handled via the sparse-safe pattern:
        raw value -> 0.0 
        availability flag -> 0.0 
        z_score -> 0.0

    Args:
        telemetry_values: Raw telemetry dict from telemtry_records. values.
            keys are  metric names, values are sensor readings.
        baselines: All MLAssetBaseline records for this asset. Used to 
            compute z-scores for each metric. 
        feature_names: Ordered list of feature names from MLModel. feature_names.
            The output vector matches this order exactly.

    Returns:
        list[float]: Feature vector in feature_names order, ready for inference. 

    Raises:
        ValueError: If a feature name does not match any known pattern.
    """

    