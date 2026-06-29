"""
ML anomaly event repository.

Provides database operations for managing anomaly events detected
by models or rule-based health scoring. Events have a resolution
lifecycle — they are created open and closed by an operator.

Open events are identified by WHERE resolved_at IS NULL.
Resolved events are permanent audit history — never deleted.

Serialization note: affected_metrics and payload_snapshot are stored
as JSON text in the database. This module serializes on write (json.dumps)
and leaves deserialization to the service layer (json.loads).
"""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_anomaly_event import MLAnomalyEvent


def create_anomaly_event(
    db: Session,
    asset_id: int,
    anomaly_score: float,
    severity: str,
    timestamp: datetime,
    model_id: int | None = None,
    affected_metrics: list | None = None,
    payload_snapshot: dict | None = None,
    notes: str | None = None,
) -> MLAnomalyEvent:
    """
    Record a newly detected anomaly event.

    Called by the inference pipeline when a model or rule engine
    determines an asset's telemetry exceeds the anomaly threshold.
    Events are created open — resolved_at and resolved_by_id are
    always NULL at creation time.

    affected_metrics and payload_snapshot are serialized to JSON
    text here — the ORM stores them as Text columns.

    Args:
        db: Database session.
        asset_id: Asset where the anomaly was detected.
        anomaly_score: Raw score produced by the model or rule engine.
        severity: Human-readable classification ("low", "medium", "high", "critical").
        timestamp: When the anomaly was detected.
        model_id: Model that detected this anomaly. None for rule-based detection.
        affected_metrics: List of metric names that triggered the anomaly.
        payload_snapshot: Raw telemetry values at detection time — forensic record.
        notes: Optional initial notes from the detection context.

    Returns:
        MLAnomalyEvent: Newly created open anomaly event.
    """

    # Build the ORM entity — serialize list/dict fields to JSON text
    event = MLAnomalyEvent(
        asset_id=asset_id,
        model_id=model_id,
        timestamp=timestamp,
        anomaly_score=anomaly_score,
        severity=severity,
        affected_metrics=json.dumps(affected_metrics) if affected_metrics is not None else None,
        payload_snapshot=json.dumps(payload_snapshot) if payload_snapshot is not None else None,
        notes=notes,
        # Resolution fields always start as NULL — event is open
        resolved_at=None,
        resolved_by_id=None,
    )

    # Persist and return the fully populated record
    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def get_anomaly_event(
    db: Session,
    event_id: int,
) -> MLAnomalyEvent | None:
    """
    Retrieve a single anomaly event by its ID.

    Used by the resolution endpoint to fetch the event before
    marking it resolved.

    Args:
        db: Database session.
        event_id: Anomaly event identifier.

    Returns:
        MLAnomalyEvent | None: Matching event if found.
    """

    statement = select(MLAnomalyEvent).where(MLAnomalyEvent.id == event_id)

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_open_anomaly_events(
    db: Session,
    asset_id: int,
) -> list[MLAnomalyEvent]:
    """
    Retrieve all unresolved anomaly events for an asset.

    Open events are identified by resolved_at IS NULL. Used by
    operational dashboards to surface active alerts that require
    operator attention.

    Results are ordered oldest first — operators should action
    the longest-standing anomalies first.

    Args:
        db: Database session.
        asset_id: Asset identifier.

    Returns:
        list[MLAnomalyEvent]: Open anomaly events oldest first.
    """

    statement = (
        select(MLAnomalyEvent)
        .where(
            MLAnomalyEvent.asset_id == asset_id,
            MLAnomalyEvent.resolved_at.is_(None),
        )
        .order_by(MLAnomalyEvent.timestamp.asc())
    )

    result = db.execute(statement)

    return list(result.scalars().all())


def get_anomaly_events_by_asset(
    db: Session,
    asset_id: int,
    severity: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 100,
) -> list[MLAnomalyEvent]:
    """
    Retrieve anomaly event history for an asset.

    Returns both open and resolved events. Used by asset history
    views and post-incident analysis. Results are ordered newest
    first so callers get the most recent events within the limit.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        severity: Optional filter by severity level.
        start_time: Optional lower bound on event timestamp.
        end_time: Optional upper bound on event timestamp.
        limit: Maximum number of records to return. Defaults to 100.

    Returns:
        list[MLAnomalyEvent]: Matching events newest first.
    """

    statement = select(MLAnomalyEvent).where(MLAnomalyEvent.asset_id == asset_id)

    # Narrow by severity level when provided
    if severity is not None:
        statement = statement.where(MLAnomalyEvent.severity == severity)

    # Apply lower time bound when provided
    if start_time is not None:
        statement = statement.where(MLAnomalyEvent.timestamp >= start_time)

    # Apply upper time bound when provided
    if end_time is not None:
        statement = statement.where(MLAnomalyEvent.timestamp <= end_time)

    # Newest events first, bounded by limit
    statement = statement.order_by(MLAnomalyEvent.timestamp.desc()).limit(limit)

    result = db.execute(statement)

    return list(result.scalars().all())


def resolve_anomaly_event(
    db: Session,
    event_id: int,
    resolved_by_id: int,
    notes: str | None = None,
) -> MLAnomalyEvent | None:
    """
    Mark an anomaly event as resolved by an operator.

    Only open events (resolved_at IS NULL) may be resolved. Attempting
    to resolve an already-resolved event is rejected — resolution is
    a one-way transition and must not be overwritten.

    Sets resolved_at to now() and records the resolving operator's ID.
    If notes are provided they overwrite any existing notes — operators
    document their findings at resolution time.

    Args:
        db: Database session.
        event_id: Anomaly event identifier.
        resolved_by_id: ID of the operator resolving this event.
        notes: Optional investigation findings from the operator.

    Returns:
        MLAnomalyEvent | None: Updated event, or None if not found or already resolved.
    """

    event = get_anomaly_event(db, event_id)

    # Return None if event does not exist
    if event is None:
        return None

    # Guard against resolving an already-resolved event
    if event.resolved_at is not None:
        return None

    # Stamp resolution time and record the resolving operator
    event.resolved_at = datetime.now(timezone.utc)
    event.resolved_by_id = resolved_by_id

    # Record operator findings when provided
    if notes is not None:
        event.notes = notes

    db.commit()
    db.refresh(event)

    return event