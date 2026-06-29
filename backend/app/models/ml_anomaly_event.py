"""
MLAnomalyEvent ORM model.
Defines the anomaly event entity and its relationships.
"""
from datetime import datetime
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.db.base_class import Base


class MLAnomalyEvent(Base):
    """
    Anomaly event entity.
    Records every detected anomaly for an asset with full resolution lifecycle.
    Unresolved events are queried via WHERE resolved_at IS NULL.
    Source of truth for alert generation and operational dashboards.
    """

    __tablename__ = "ml_anomaly_events"

    # Primary key
    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    # Asset where the anomaly was detected
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )

    # NULL if anomaly was detected by rule-based health scoring, not a model
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_models.id"),
        nullable=True,
    )

    # When the anomaly was detected
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Raw anomaly score produced by the model or rule engine
    anomaly_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Human-readable severity classification derived from anomaly_score
    # Values: 'low' | 'medium' | 'high' | 'critical'
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # JSON list of metric names that triggered this anomaly
    # Example: '["temperature", "vibration"]'
    # Deserialized via json.loads() in the service layer — never queried by DB
    affected_metrics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Raw telemetry values at detection time — forensic record
    # Deserialized via json.loads() in the service layer — never queried by DB
    payload_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Free-text operator investigation notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Resolution tracking — NULL means this event is still open
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Operator who resolved this event — NULL while event is still open
    resolved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # Set by database at insert time — never set by application code
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
    )

    # --- Relationships ---------------------------------------------------

    # Asset where the anomaly was detected (unidirectional — Option B)
    asset = relationship(
        "Asset",
    )

    # Model that detected this anomaly (bidirectional)
    # foreign_keys required — MLAnomalyEvent has two FKs to ml_models
    # would be ambiguous without it
    model = relationship(
        "MLModel",
        foreign_keys=[model_id],
        back_populates="anomaly_events",
    )

    # Operator who resolved this event (unidirectional — Option B)
    # foreign_keys required — MLAnomalyEvent has two FKs to users
    # resolved_by_id and the inherited ambiguity must be explicit
    resolved_by = relationship(
        "User",
        foreign_keys=[resolved_by_id],
    )