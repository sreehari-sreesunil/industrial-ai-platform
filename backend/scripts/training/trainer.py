"""
Model trainer.

Wraps every model in an sklearn Pipeline with StandardScaler.
This is the single most important production pattern in this pipeline:

    Pipeline([
        ("scaler", StandardScaler()),
        ("model",  IsolationForest(...)),
    ])

Why Pipeline matters:
    Without Pipeline: scaler is fit separately, stored separately,
    must be reconstructed identically at inference time.
    Training-serving skew is silent and catastrophic.

    With Pipeline: scaler is fit and serialized WITH the model.
    Inference calls pipeline.predict() — identical scaling guaranteed.
    One artifact file. One call. Zero divergence.

Model selection (single-tier scope):
    anomaly_detection  -> IsolationForest
    failure_prediction -> RandomForest

Sample weighting (failure_prediction):
    RandomForest does NOT use class_weight="balanced". Records are
    weighted by proximity to the eventual failure — a reading at the
    moment of failure gets full positive weight; a reading near the
    far edge of FAILURE_HORIZON_HOURS gets 20% of that weight. This
    was validated offline against the real dataset: it improved
    precision (0.20 -> 0.25) and F1 (0.31 -> 0.37) versus flat
    class_weight="balanced", with no recall cost. See
    proximity_weights() below for the exact formula.

Public API:
    train_model(fold, model_type) -> fitted Pipeline
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.training.config import (
    MODEL_CONFIGS,
    IsolationForestConfig,
    RandomForestConfig,
)
from scripts.training.data_loader import CVFold, FAILURE_HORIZON_HOURS

logger = logging.getLogger(__name__)


def train_model(
    fold: CVFold,
    model_type: str,
) -> Pipeline:
    """
    Train a model on a single CV fold, wrapped in an sklearn Pipeline.

    The Pipeline includes StandardScaler followed by the model.
    Scaler is fit on training data only — never on validation data.

    Args:
        fold:       Single CV fold with X_train, y_train.
        model_type: Algorithm name — must match a key in MODEL_CONFIGS.

    Returns:
        Pipeline: Fitted sklearn Pipeline (scaler + model).

    Raises:
        ValueError: If model_type is not recognized.
    """
    trainers = {
        "IsolationForest": _train_isolation_forest,
        "RandomForest":    _train_random_forest,
    }

    if model_type not in trainers:
        raise ValueError(
            f"Unknown model_type '{model_type}'. "
            f"Must be one of: {', '.join(trainers.keys())}."
        )

    logger.info(
        "Training %s on fold %d: %d records, %d features",
        model_type,
        fold.fold_index,
        fold.n_train,
        fold.X_train.shape[1],
    )

    pipeline = trainers[model_type](fold)
    logger.info(
        "%s fold %d training complete",
        model_type,
        fold.fold_index,
    )
    return pipeline


# ---------------------------------------------------------------------------
# Algorithm-specific trainers
# ---------------------------------------------------------------------------

def _build_pipeline(model: Any) -> Pipeline:
    """
    Wrap a model in a StandardScaler Pipeline.

    StandardScaler standardizes features to zero mean and unit variance.
    Required for IsolationForest's distance-based scoring; less critical
    for RandomForest (tree splits are scale-invariant) but included for
    pipeline uniformity — every artifact has the same interface.

    Args:
        model: Unfitted sklearn-compatible model.

    Returns:
        Pipeline: Unfitted pipeline with scaler and model.
    """
    return Pipeline([
        ("scaler", StandardScaler()),
        ("model",  model),
    ])


def _train_isolation_forest(fold: CVFold) -> Pipeline:
    """
    Train IsolationForest wrapped in StandardScaler Pipeline.

    Unsupervised — uses X_train only. fold.y_train is None
    for anomaly_detection tasks and is never accessed here.

    Args:
        fold: CV fold with normal records only in X_train.

    Returns:
        Fitted Pipeline.
    """
    from sklearn.ensemble import IsolationForest

    cfg: IsolationForestConfig = MODEL_CONFIGS["IsolationForest"]

    model = IsolationForest(
        n_estimators=cfg.n_estimators,
        contamination=cfg.contamination,
        max_samples=cfg.max_samples,
        random_state=cfg.random_state,
        n_jobs=-1,
    )

    pipeline = _build_pipeline(model)
    pipeline.fit(fold.X_train)

    logger.debug(
        "IsolationForest fold %d: n_estimators=%d contamination=%.3f",
        fold.fold_index,
        cfg.n_estimators,
        cfg.contamination,
    )
    return pipeline


def proximity_weights(
        y_train: np.ndarray,
        hours_to_failure: np.ndarray,
        horizon_hours: int,
        min_weight_fraction: float = 0.2
) -> np.ndarray:
    """
    Sample weights for failure_prediction that decay with distance
    from the eventual failure event.

    Why this exists:
        A flat class_weight="balanced" treats every positive record as
        equally informative — a reading 1 hour before failure and a
        reading near the far edge of FAILURE_HORIZON_HOURS get the same
        weight, even though the far-edge reading often looks statistically
        identical to a healthy one. This function keeps every positive
        record in training (nothing is discarded) but scales its weight
        down the further it sits from the actual failure.

    Formula:
        negatives -> weight 1.0
        positives -> pos_weight_base * proximity_fraction, where:
            pos_weight_base = n_neg / n_pos (mirrors class_weight="balanced")
            proximity_fraction = clip(
            1- (hours_to_failure / horizon_hours) * (1 - min_weight_fraction),
            min_weight_fraction,
            1.0,
            )
    A positive at hours_to_failure=0 (the failure moment) gets full
        pos_weight_base. A positive at hours_to_failure=horizon_hours (the
        far edge of the label window) gets pos_weight_base * min_weight_fraction.
        NaN hours_to_failure on a positive record falls back to
        proximity_fraction = 1.0 — treated as if at the failure moment,
        a conservative choice that never silently zeroes out a record's weight.

    Validated offline against the real Azure PM dataset with
    min_weight_fraction=0.2: improved precision 0.20 -> 0.25 and
    F1 0.31 -> 0.37 versus flat class_weight="balanced", with no
    recall cost.

    Args:
        y_train:             Binary labels for the training fold.
        hours_to_failure:    Hours between each record and the failure
                              event that produced its positive label.
                              Ignored for negative records.
        horizon_hours:        FAILURE_HORIZON_HOURS — the labeling window.
        min_weight_fraction:  Weight fraction applied at the far edge of
                              the horizon. Default 0.2.

    Returns:
        np.ndarray: Per-record sample weights, same length as y_train.
    """
    n_pos = int(y_train.sum())
    n_neg = int((y_train == 0).sum())

    if n_pos == 0:
        return np.ones_like(y_train, dtype=float)

    pos_weight_base = n_neg / n_pos

    pos_mask = y_train == 1
    proximity_fraction = np.where(
        np.isnan(hours_to_failure),
        1.0,
        np.clip(
            1.0 - (hours_to_failure / horizon_hours) * (1.0 - min_weight_fraction),
            min_weight_fraction,
            1.0,
        ),
    )

    weights = np.where(
        pos_mask,
        pos_weight_base * proximity_fraction,
        1.0,
    )
    return weights


def _train_random_forest(fold: CVFold) -> Pipeline:
    """
    Train RandomForestClassifier wrapped in Pipeline.

    RandomForest is scale-invariant (tree splits don't depend on scale)
    but is wrapped in Pipeline for architectural uniformity — all
    artifacts have the same interface regardless of algorithm.

    Uses proximity_weights() instead of class_weight="balanced" — see
    module docstring and proximity_weights() for rationale.

    Args:
        fold: CV fold with X_train, y_train labels, and
              hours_to_failure for weighting.

    Returns:
        Fitted Pipeline.

    Raises:
        ValueError: If fold.y_train is None.
    """
    from sklearn.ensemble import RandomForestClassifier

    if fold.y_train is None:
        raise ValueError(
            f"RandomForest requires labels. "
            f"fold {fold.fold_index} y_train is None — "
            f"check task type in data_loader."
        )

    cfg: RandomForestConfig = MODEL_CONFIGS["RandomForest"]

    model = RandomForestClassifier(
        n_estimators=cfg.n_estimators,
        max_depth=cfg.max_depth,
        class_weight=None,  # replaced by explicit proximity sample_weight
        random_state=cfg.random_state,
        n_jobs=-1,
    )

    pipeline = _build_pipeline(model)

    sample_weight = proximity_weights(
        y_train=fold.y_train,
        hours_to_failure=fold.hours_to_failure,
        horizon_hours=FAILURE_HORIZON_HOURS,
    )
    pipeline.fit(
        fold.X_train,
        fold.y_train,
        model__sample_weight=sample_weight,
    )

    # Log feature importances from the model step
    importances = dict(zip(
        [f"feature_{i}" for i in range(fold.X_train.shape[1])],
        pipeline.named_steps["model"].feature_importances_,
    ))
    top = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]
    logger.info(
        "RandomForest fold %d top features: %s",
        fold.fold_index,
        ", ".join(f"{k}={v:.3f}" for k, v in top),
    )

    return pipeline