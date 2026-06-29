"""
ML asset health repository.

Provides database operations for storing and retrieving asset health
score time-series records. Health scores are computed by the scoring
pipeline and written here after each evaluation cycle.

Append-only — no update or delete operations exist by design.
Complete history is required for trend charts and deterioration analysis.

Serialization note: contributing_factors is stored as JSON text in the
database. This module serializes on write (json.dumps) and leaves
deserialization to the service layer (json.loads).
"""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_asset_health import MLAssetHealth


def create_asset_health(
    db: Session,
    asset_id: int,
    timestamp: datetime,
    health_score: float,
    health_category: str,
    failure_probability: float | None = None,
    rul_days: int | None = None,
    contributing_factors: list | None = None,
) -> MLAssetHealth:
    """
    Record a new asset health score.

    Called by the health scoring pipeline after each evaluation cycle.
    contributing_factors is serialized to JSON text here — the ORM
    stores it as a Text column.

    Args:
        db: Database session.
        asset_id: Asset this health record belongs to.
        timestamp: When this health score was computed.
        health_score: Composite score from 0 (failed) to 100 (perfect).
        health_category: Human-readable category derived from score.
        failure_probability: Rule-based failure probability proxy (0-1).
            None when insufficient data exists to compute a meaningful value.
        rul_days: Estimated days until failure. None when asset trend
            is stable or improving.
        contributing_factors: List of human-readable factor descriptions
            explaining what drove this health score.

    Returns:
        MLAssetHealth: Newly created health record.
    """

    # Build the ORM entity — serialize list field to JSON text
    health = MLAssetHealth(
        asset_id=asset_id,
        timestamp=timestamp,
        health_score=health_score,
        health_category=health_category,
        failure_probability=failure_probability,
        rul_days=rul_days,
        contributing_factors=json.dumps(contributing_factors) if contributing_factors is not None else None,
    )

    # Persist and return the fully populated record
    db.add(health)
    db.commit()
    db.refresh(health)

    return health


def get_latest_health_by_asset(
    db: Session,
    asset_id: int,
) -> MLAssetHealth | None:
    """
    Retrieve the most recent health record for an asset.

    Used by asset dashboards to display the current health score
    and category without loading the full history.

    Args:
        db: Database session.
        asset_id: Asset identifier.

    Returns:
        MLAssetHealth | None: Most recent health record if found.
    """

    statement = (
        select(MLAssetHealth)
        .where(MLAssetHealth.asset_id == asset_id)
        .order_by(MLAssetHealth.timestamp.desc())
        .limit(1)
    )

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_health_history_by_asset(
    db: Session,
    asset_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 200,
) -> list[MLAssetHealth]:
    """
    Retrieve health score history for an asset.

    Used by trend charts and deterioration analysis. Results are
    ordered oldest first so callers can plot a time series directly
    without reversing the list.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        start_time: Optional lower bound on health record timestamp.
        end_time: Optional upper bound on health record timestamp.
        limit: Maximum number of records to return. Defaults to 200.

    Returns:
        list[MLAssetHealth]: Health records oldest first.
    """

    statement = select(MLAssetHealth).where(MLAssetHealth.asset_id == asset_id)

    # Apply lower time bound when provided
    if start_time is not None:
        statement = statement.where(MLAssetHealth.timestamp >= start_time)

    # Apply upper time bound when provided
    if end_time is not None:
        statement = statement.where(MLAssetHealth.timestamp <= end_time)

    # Oldest records first — callers plot directly without reversing
    statement = statement.order_by(MLAssetHealth.timestamp.asc()).limit(limit)

    result = db.execute(statement)

    return list(result.scalars().all())