"""
MLAssetHealth ORM model.
Defines the asset health score time-series entity and its relationships.
"""
from datetime import datetime
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.db.base_class import Base


class MLAssetHealth(Base):
    """
    Asset health score time-series entity.
    Append-only — a new row is inserted each time health is computed.
    Never updated after insert. Complete history enables trend charts
    and deterioration analysis.
    """

    __tablename__ = "ml_asset_health"

    # Primary key
    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    # Asset this health record belongs to
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )

    # When this health score was computed
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Composite health score — 0 = failed, 100 = perfect health
    health_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Human-readable category derived from health_score
    # Values: 'excellent' | 'good' | 'fair' | 'poor' | 'critical'
    health_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Rule-based failure probability proxy — range 0-1
    # NULL when insufficient data to compute a meaningful probability
    failure_probability: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Estimated days until failure
    # NULL when asset trend is stable or improving — no meaningful RUL
    rul_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # JSON list of human-readable factor descriptions
    # Example: '["Temperature at 91% of max", "Vibration trending up 15%"]'
    # Deserialized via json.loads() in the service layer — never queried by DB
    contributing_factors: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Set by database at insert time — never set by application code
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
    )

    # --- Relationships ---------------------------------------------------

    # Asset this health record belongs to (unidirectional — Option B)
    asset = relationship(
        "Asset",
    )