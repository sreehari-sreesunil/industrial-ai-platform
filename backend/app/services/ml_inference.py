# app/services/ml_inference.py
"""
ML inference pipeline.

Orchestrates the full inference cycle for a single asset:
fetches the deployed model, builds the feature vector, scores,
persists the prediction, and conditionally creates an anomaly event.

Two public entry points:

    run_inference_all_tasks(db, asset_id)
        Runs anomaly_detection and failure_prediction in sequence.
        Called by the telemetry ingest pipeline after each record write.
        Failures in one task do not block the other.

    run_inference(db, asset_id, task)
        Runs inference for a single task.
        Called directly by the inference API endpoint.

Failure isolation strategy:
    Each task is wrapped in a broad except block. A model artifact
    missing from disk, a feature engineering error, or a DB write
    failure must not crash the telemetry ingest path. The failure
    is logged with full context and None is returned — the caller
    decides whether to surface the error or continue silently.

Health scoring is intentionally excluded from this pipeline.
Health score is a composite computed from prediction outputs,
not a direct model inference. It lives in services/ml_health.py (Sprint 3).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.crud import (
    ml_anomaly_event as crud_anomaly_event,
    ml_asset_baseline as crud_baseline,
    ml_asset_health as crud_health,
    ml_model as crud_model,
    ml_prediction as crud_prediction,
    telemetry as crud_telemetry,
)
from app.crud import asset as crud_asset
from app.ml import feature_engineering, model_loader, scoring
from app.ml.rul import ewma
from app.models.ml_prediction import MLPrediction

logger = logging.getLogger(__name__)

# Tasks this pipeline handles.
# health_scoring is excluded — it is a composite, not a direct inference.
_INFERENCE_TASKS = ("anomaly_detection", "failure_prediction")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_inference_all_tasks(
    db: Session,
    asset_id: int,
) -> dict[str, MLPrediction | None]:
    """
    Run inference for all tasks on a single asset.

    Executes anomaly_detection and failure_prediction in sequence.
    A failure in one task does not block the other — each is
    independently failure-isolated.

    Called by the telemetry ingest pipeline after each record write.

    Args:
        db:       Database session.
        asset_id: Asset to run inference on.

    Returns:
        dict[str, MLPrediction | None]: Task name → prediction result.
            Value is None if inference failed or no deployed model exists
            for that task combination.
    """
    results: dict[str, MLPrediction | None] = {}

    for task in _INFERENCE_TASKS:
        results[task] = run_inference(db=db, asset_id=asset_id, task=task)

    return results


def run_inference(
    db: Session,
    asset_id: int,
    task: str,
) -> MLPrediction | None:
    """
    Run inference for a single task on a single asset.

    Resolves the deployed model for this asset's type,
    builds the feature vector from the latest telemetry record,
    scores, persists the prediction, and conditionally creates
    an anomaly event.

    Args:
        db:       Database session.
        asset_id: Asset to run inference on.
        task:     Inference task — "anomaly_detection" or
                  "failure_prediction".

    Returns:
        MLPrediction | None: Persisted prediction record, or None
            if inference could not be completed.
    """
    try:
        return _run_inference_for_task(db=db, asset_id=asset_id, task=task)
    except Exception:
        logger.exception(
            "Inference failed for asset_id=%d task=%s — returning None",
            asset_id,
            task,
        )
        return None


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def _run_inference_for_task(
    db: Session,
    asset_id: int,
    task: str,
) -> MLPrediction | None:
    """
    Execute the full 13-step inference pipeline for one asset and task.

    Steps:
        1.  Load asset → resolve asset_type_id
        2.  (tier resolution removed — single tier, always "standard")
        3.  Fetch deployed model for asset_type + task
        4.  Load model artifact from disk (cached after first load)
        5.  Fetch latest telemetry record for the asset
        6.  Fetch baselines for the asset
        7.  Build feature vector
        8.  Score with model
        9.  Normalize score to 0-1
        10. Classify risk level
        11. Compute confidence
        12. Persist MLPrediction record
        13. Conditionally create MLAnomalyEvent

    Args:
        db:       Database session.
        asset_id: Asset to run inference on.
        task:     Inference task name.

    Returns:
        MLPrediction | None: Persisted prediction, or None if any
            required input is missing (no deployed model, no telemetry).
    """

    # Step 1 — load asset, get asset_type_id
    asset = crud_asset.get_asset_by_id(db=db, asset_id=asset_id)
    if asset is None:
        logger.warning("Inference skipped: asset_id=%d not found", asset_id)
        return None

    asset_type_id = asset.asset_type_id

    # Step 3 — fetch the deployed model for this slot
    ml_model = crud_model.get_model_for_inference(
        db=db,
        asset_type_id=asset_type_id,
        task=task,
        tier="standard",
    )
    if ml_model is None:
        logger.debug(
            "No deployed model for asset_type_id=%d task=%s — skipping",
            asset_type_id,
            task,
        )
        return None

    # Step 4 — load artifact from disk (cached after first load)
    model_obj = model_loader.load_model(
        model_id=ml_model.id,
        artifact_path=ml_model.artifact_path,
    )

    # Step 5 — fetch latest telemetry record
    latest_telemetry = crud_telemetry.get_latest_telemetry_by_asset(
        db=db,
        asset_id=asset_id,
    )
    if latest_telemetry is None:
        logger.debug(
            "No telemetry for asset_id=%d — skipping inference",
            asset_id,
        )
        return None

    telemetry_values: dict[str, Any] = latest_telemetry.payload or {}

    # Step 6 — fetch baselines for z-score computation
    baselines = crud_baseline.get_baselines_by_asset(db=db, asset_id=asset_id)

    # Step 7 — build feature vector
    feature_names: list[str] = json.loads(ml_model.feature_names)
    feature_vector = feature_engineering.build_feature_vector(
        telemetry_values=telemetry_values,
        baselines=baselines,
        feature_names=feature_names,
    )

    # Step 8 — score with model
    raw_score = _score_with_model(
        model=model_obj,
        model_type=ml_model.model_type,
        feature_vector=feature_vector,
    )

    # Step 9 — normalize to 0-1
    normalized_score = scoring.normalize_score(
        raw_score=raw_score,
        model_type=ml_model.model_type,
    )

    # Step 10 — classify risk level
    risk_level = scoring.classify_risk(
        score=normalized_score,
        task=task,
    )

    # Health scoring is a side effect of failure_prediction specifically —
    # not a standalone task (see _INFERENCE_TASKS comment). anomaly_detection's
    # normalized_score means "deviation from normal," not "probability of
    # failure," so deriving health from it wouldn't be meaningful.
    if task == "failure_prediction":
        _maybe_update_health(
            db=db,
            asset_id=asset_id,
            failure_probability=normalized_score,
            risk_level=risk_level,
        )
        
    # Step 11 — compute confidence
    confidence = _compute_confidence(normalized_score)

    # Step 12 — persist prediction
    feature_values_for_storage = dict(zip(feature_names, feature_vector))
    prediction = crud_prediction.create_prediction(
        db=db,
        model_id=ml_model.id,
        asset_id=asset_id,
        timestamp=latest_telemetry.timestamp,
        prediction_type=task,
        score=normalized_score,
        confidence=confidence,
        risk_level=risk_level,
        feature_values=feature_values_for_storage,
        explanation=None,
    )

    # Step 13 — conditionally create anomaly event
    _maybe_create_anomaly_event(
        db=db,
        asset_id=asset_id,
        model_id=ml_model.id,
        prediction=prediction,
        task=task,
        telemetry_values=telemetry_values,
        baselines=baselines,
        feature_names=feature_names,
        feature_vector=feature_vector,
    )

    logger.info(
        "Inference complete: asset_id=%d task=%s score=%.4f "
        "risk=%s confidence=%.3f model_id=%d",
        asset_id,
        task,
        normalized_score,
        risk_level,
        confidence,
        ml_model.id,
    )

    return prediction

def _maybe_update_health(
    db: Session,
    asset_id: int,
    failure_probability: float,
    risk_level: str,
) -> None:
    """
    Derive and persist a health record from a failure_prediction result.

    Called only when task == "failure_prediction" — health score is
    defined as the inverse of failure probability, which only makes
    sense for that task (anomaly_detection's score means something
    different: deviation from normal, not probability of failure).

    Fetches this asset's health history, computes an EWMA-based RUL
    estimate from it, then persists the new health record (with this
    reading included, for the NEXT call's history).

    Args:
        db:                   Database session.
        asset_id:             Asset this health record belongs to.
        failure_probability:  The failure_prediction task's normalized
                              score (0-1, higher = more likely to fail).
        risk_level:           Already-computed risk level for this score
                              (from scoring.classify_risk), reused here
                              via risk_level_to_health_category rather
                              than recomputed.
    """
    health_score = (1.0 - failure_probability) * 100.0
    health_category = scoring.risk_level_to_health_category(risk_level)

    # Fetch history BEFORE this new reading — EWMA needs prior readings
    # to compute a trend; this reading becomes part of history for the
    # NEXT call, not this one.
    history_records = crud_health.get_health_history_by_asset(
        db=db,
        asset_id=asset_id,
    )
    health_history = [
        (record.timestamp, record.health_score) for record in history_records
    ]

    rul_days, rul_confidence = ewma.compute_ewma_rul(
        health_history=health_history,
    )

    crud_health.create_asset_health(
        db=db,
        asset_id=asset_id,
        timestamp=datetime.now(timezone.utc),
        health_score=health_score,
        health_category=health_category,
        failure_probability=failure_probability,
        rul_days=rul_days,
        contributing_factors=None,
    )

    logger.info(
        "Health updated: asset_id=%d health_score=%.1f category=%s "
        "rul_days=%s rul_confidence=%.2f",
        asset_id,
        health_score,
        health_category,
        rul_days,
        rul_confidence,
    )


def _score_with_model(
    model: Any,
    model_type: str,
    feature_vector: list[float],
) -> float:
    """
    Call the correct scoring method based on model type.

    IsolationForest expose decision_function() —
    returns a scalar where negative = anomalous.

    RandomForest expose predict_proba() —
    returns class probabilities; we take the positive class (index 1).

    Args:
        model:          Deserialized sklearn-compatible model object.
        model_type:     Model type string from MLModel.model_type.
        feature_vector: Ordered feature list ready for inference.

    Returns:
        float: Raw model output score (not yet normalized).

    Raises:
        ValueError: If model_type is not recognized.
    """
    import numpy as np

    X = np.array(feature_vector).reshape(1, -1)

    if model_type == "IsolationForest":
        return float(model.decision_function(X)[0])

    if model_type == "RandomForest":
        return float(model.predict_proba(X)[0][1])

    raise ValueError(
        f"Unknown model_type '{model_type}' in _score_with_model. "
        f"Expected one of: IsolationForest, RandomForest."
    )


def _compute_confidence(normalized_score: float) -> float:
    """
    Compute prediction confidence from the normalized score.

    Confidence measures how far the score is from the decision boundary
    (0.5). A score near 0.5 is ambiguous — the model is uncertain.
    A score near 0.0 or 1.0 is unambiguous — high confidence.

    Formula: |score - 0.5| * 2
        score=0.5  → confidence=0.00 (maximum uncertainty)
        score=0.75 → confidence=0.50
        score=1.0  → confidence=1.00 (maximum certainty)

    Args:
        normalized_score: Score in [0.0, 1.0] from normalize_score.

    Returns:
        float: Confidence in [0.0, 1.0].
    """
    return round(abs(normalized_score - 0.5) * 2, 3)


def _extract_affected_metrics(
    feature_names: list[str],
    feature_vector: list[float],
    baselines: list[Any],
    zscore_threshold: float = 1.5,
) -> list[str]:
    """
    Identify metrics with z-scores above the anomaly threshold.

    Used to populate the affected_metrics field on MLAnomalyEvent,
    giving operators a fast signal of which sensors drove the alert
    without needing to inspect the full feature vector.

    Only raw metric features are checked (not _available or _zscore
    derived features — those are model inputs, not operator-facing).

    Args:
        feature_names:    Ordered feature names from the model.
        feature_vector:   Corresponding feature values.
        baselines:        Asset baselines for z-score lookup.
        zscore_threshold: Minimum absolute z-score to flag a metric.
                          Default 1.5 — elevated but not extreme.

    Returns:
        list[str]: Metric names whose z-scores exceed the threshold.
    """
    baseline_map = {b.metric_name: b for b in baselines}
    affected: list[str] = []

    for name, value in zip(feature_names, feature_vector):
        # Only check raw metric features, skip derived suffixes
        if name.endswith("_available") or name.endswith("_zscore"):
            continue

        baseline = baseline_map.get(name)
        if baseline is None or not baseline.is_mature:
            continue

        if baseline.baseline_std and baseline.baseline_std > 0:
            zscore = abs(value - baseline.baseline_mean) / baseline.baseline_std
            if zscore >= zscore_threshold:
                affected.append(name)

    return affected


def _maybe_create_anomaly_event(
    db: Session,
    asset_id: int,
    model_id: int,
    prediction: MLPrediction,
    task: str,
    telemetry_values: dict[str, Any],
    baselines: list[Any],
    feature_names: list[str],
    feature_vector: list[float],
) -> None:
    """
    Create an MLAnomalyEvent if the prediction score crosses the event threshold.

    Failure-isolated — an error here must not roll back the prediction
    that was already persisted in step 12.

    Args:
        db:              Database session.
        asset_id:        Asset the prediction was made for.
        model_id:        Model that produced the prediction.
        prediction:      Persisted MLPrediction from step 12.
        task:            Inference task name.
        telemetry_values: Raw telemetry dict for payload snapshot.
        baselines:       Asset baselines for affected metric extraction.
        feature_names:   Ordered feature names.
        feature_vector:  Corresponding feature values.
    """
    try:
        if not scoring.should_create_anomaly_event(
            score=prediction.score,
            task=task,
        ):
            return

        affected_metrics = _extract_affected_metrics(
            feature_names=feature_names,
            feature_vector=feature_vector,
            baselines=baselines,
        )

        severity = prediction.risk_level

        crud_anomaly_event.create_anomaly_event(
            db=db,
            asset_id=asset_id,
            model_id=model_id,
            timestamp=prediction.timestamp,
            anomaly_score=prediction.score,
            severity=severity,
            affected_metrics=affected_metrics,
            payload_snapshot=telemetry_values,
        )

        logger.info(
            "Anomaly event created: asset_id=%d task=%s score=%.4f "
            "severity=%s affected=%s",
            asset_id,
            task,
            prediction.score,
            severity,
            affected_metrics,
        )

    except Exception:
        logger.exception(
            "Failed to create anomaly event for asset_id=%d task=%s "
            "— prediction already persisted, continuing",
            asset_id,
            task,
        )