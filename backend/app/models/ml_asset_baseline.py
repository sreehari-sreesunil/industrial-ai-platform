"""
MLAssetBaseline ORM model.
Defines the per-asset learned behavior baseline entity and its relationships.
"""
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.db.base_class import Base


class MLAssetBaseline(Base):
    """
    Per-asset learned behavior baseline entity.
    Stores the statistical normal envelope for one metric on one asset.
    One row per asset per metric — enforced by unique constraint.
    Enables local calibration of global models to per-asset operating conditions.
    Predictions are flagged low_confidence until is_mature = TRUE.
    """

    __tablename__ = "ml_asset_baselines"

    # Unique constraint mirrors the migration index
    # One baseline row per asset per metric — no duplicates allowed
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "metric_name",
            name="ix_ml_asset_baselines_asset_metric",
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    # Asset this baseline belongs to
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )

    # Matches the metric name key in telemetry_records.values JSONB
    # Example: 'temperature' | 'vibration' | 'rpm'
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Statistical summary of normal operating behavior
    # All nullable — populated incrementally as telemetry accumulates
    baseline_mean: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    baseline_std: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    baseline_min: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    baseline_max: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    percentile_95: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # How many telemetry records contributed to this baseline
    samples_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Time window used to build this baseline
    learning_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    learning_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # FALSE until enough samples collected for reliable statistics
    # Predictions flagged low_confidence while FALSE
    is_mature: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )

    # Updated each time baseline statistics are recomputed
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
    )

    # --- Relationships ---------------------------------------------------

    # Asset this baseline belongs to (unidirectional — Option B)
    asset = relationship(
        "Asset",
    )