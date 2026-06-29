"""
ML prediction repository.

Provides database operations for storing and retrieving inference
history. Predictions are written by the inference pipeline and read
by asset dashboards and drift monitoring.

Append-only — no update or delete operations exist by design.
Every prediction is permanent audit and forensic history.

Serialization note: feature_values and explanation are stored as
JSON text in the database. This module serializes on write (json.dumps)
and leaves deserialization to the service layer (json.loads).
"""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_prediction import MLPrediction


def create_prediction(
    db: Session,
    asset_id: int,
    prediction_type: str,
    score: float,
    timestamp: datetime,
    model_id: int | None = None,
    confidence: float | None = None,
    risk_level: str | None = None,
    feature_values: dict | None = None,
    explanation: dict | None = None,
) -> MLPrediction:
    """
    Record a new inference result.

    Called internally by the inference pipeline after a model scores
    an asset's telemetry. There is no API schema for this — the service
    layer constructs all values programmatically.

    feature_values and explanation are serialized to JSON text here —
    the ORM stores them as Text columns.

    Args:
        db: Database session.
        asset_id: Asset this prediction was made against.
        prediction_type: Kind of prediction (e.g. "anomaly_score").
        score: Primary output value — 0-1 for probabilities, 0-100 for health.
        timestamp: When this prediction was generated.
        model_id: Model that produced this prediction. None for rule-based logic.
        confidence: Model confidence in this prediction. None if not produced.
        risk_level: Human-readable risk classification (e.g. "high").
        feature_values: Feature vector snapshot used at inference time.
        explanation: Feature importance dict at inference time.

    Returns:
        MLPrediction: Newly created prediction record.
    """

    # Build the ORM entity — serialize dict fields to JSON text
    prediction = MLPrediction(
        model_id=model_id,
        asset_id=asset_id,
        timestamp=timestamp,
        prediction_type=prediction_type,
        score=score,
        confidence=confidence,
        risk_level=risk_level,
        feature_values=json.dumps(feature_values) if feature_values is not None else None,
        explanation=json.dumps(explanation) if explanation is not None else None,
    )

    # Persist and return the fully populated record
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return prediction


def get_predictions_by_asset(
    db: Session,
    asset_id: int,
    prediction_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 100,
) -> list[MLPrediction]:
    """
    Retrieve prediction history for an asset.

    Used by asset dashboards to display risk trends and scoring history.
    Results are ordered newest first so callers get the most relevant
    data within the limit without offset pagination.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        prediction_type: Optional filter by prediction kind.
        start_time: Optional lower bound on prediction timestamp.
        end_time: Optional upper bound on prediction timestamp.
        limit: Maximum number of records to return. Defaults to 100.

    Returns:
        list[MLPrediction]: Matching predictions newest first.
    """

    statement = select(MLPrediction).where(MLPrediction.asset_id == asset_id)

    # Narrow by prediction type when provided
    if prediction_type is not None:
        statement = statement.where(MLPrediction.prediction_type == prediction_type)

    # Apply lower time bound when provided
    if start_time is not None:
        statement = statement.where(MLPrediction.timestamp >= start_time)

    # Apply upper time bound when provided
    if end_time is not None:
        statement = statement.where(MLPrediction.timestamp <= end_time)

    # Newest predictions first, bounded by limit
    statement = statement.order_by(MLPrediction.timestamp.desc()).limit(limit)

    result = db.execute(statement)

    return list(result.scalars().all())


def get_latest_prediction_by_asset(
    db: Session,
    asset_id: int,
    prediction_type: str,
) -> MLPrediction | None:
    """
    Retrieve the most recent prediction for an asset and prediction type.

    Used by dashboards to display the current risk level without
    loading the full prediction history.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        prediction_type: Kind of prediction to retrieve.

    Returns:
        MLPrediction | None: Most recent matching prediction if found.
    """

    statement = (
        select(MLPrediction)
        .where(
            MLPrediction.asset_id == asset_id,
            MLPrediction.prediction_type == prediction_type,
        )
        .order_by(MLPrediction.timestamp.desc())
        .limit(1)
    )

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_predictions_by_model(
    db: Session,
    model_id: int,
    limit: int = 500,
) -> list[MLPrediction]:
    """
    Retrieve predictions produced by a specific model.

    Used by drift monitoring to evaluate whether a model's output
    distribution is shifting over time. A higher default limit than
    asset history — drift analysis needs more data points to be
    statistically meaningful.

    Args:
        db: Database session.
        model_id: ML model identifier.
        limit: Maximum number of records to return. Defaults to 500.

    Returns:
        list[MLPrediction]: Predictions from this model, newest first.
    """

    statement = (
        select(MLPrediction)
        .where(MLPrediction.model_id == model_id)
        .order_by(MLPrediction.timestamp.desc())
        .limit(limit)
    )

    result = db.execute(statement)

    return list(result.scalars().all())