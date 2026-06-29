"""
ML asset baseline repository.

Provides database operations for managing per-asset learned behavior
baselines. One baseline row exists per asset per metric — enforced by
a unique constraint on (asset_id, metric_name).

Baselines are recomputed and updated in place as telemetry accumulates.
This is not append-only — upsert_baseline either creates a new row or
updates the existing one for that asset + metric combination.

Predictions are flagged low_confidence while is_mature = False.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_asset_baseline import MLAssetBaseline


@dataclass
class BaselineStats:
    """
    Statistical summary of an asset metric's normal operating behavior.

    Passed to upsert_baseline to avoid positional argument errors
    across nine statistical fields. All float fields are nullable —
    they are populated incrementally as telemetry accumulates.
    """

    # Central tendency of the metric during the learning period
    baseline_mean: float | None

    # Spread of the metric during the learning period
    baseline_std: float | None

    # Observed minimum during the learning period
    baseline_min: float | None

    # Observed maximum during the learning period
    baseline_max: float | None

    # 95th percentile — upper bound for anomaly thresholding
    percentile_95: float | None

    # Number of telemetry records that contributed to this baseline
    samples_count: int

    # Start of the window used to compute this baseline
    learning_period_start: datetime | None

    # End of the window used to compute this baseline
    learning_period_end: datetime | None

    # True once enough samples exist for reliable statistics
    is_mature: bool


def get_baseline(
    db: Session,
    asset_id: int,
    metric_name: str,
) -> MLAssetBaseline | None:
    """
    Retrieve the baseline for a specific asset and metric.

    Used by the inference pipeline to check baseline maturity before
    scoring and to retrieve the statistical envelope for z-score
    computation.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        metric_name: Metric name matching telemetry_records.values key.

    Returns:
        MLAssetBaseline | None: Matching baseline if found.
    """

    statement = select(MLAssetBaseline).where(
        MLAssetBaseline.asset_id == asset_id,
        MLAssetBaseline.metric_name == metric_name,
    )

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_baselines_by_asset(
    db: Session,
    asset_id: int,
) -> list[MLAssetBaseline]:
    """
    Retrieve all baselines for an asset.

    Used by the inference pipeline to load the full statistical
    envelope for an asset before feature engineering.

    Args:
        db: Database session.
        asset_id: Asset identifier.

    Returns:
        list[MLAssetBaseline]: All baselines for this asset.
    """

    statement = select(MLAssetBaseline).where(
        MLAssetBaseline.asset_id == asset_id,
    )

    result = db.execute(statement)

    return list(result.scalars().all())


def get_immature_baselines(
    db: Session,
) -> list[MLAssetBaseline]:
    """
    Retrieve all baselines that have not yet reached maturity.

    Used by the baseline learning pipeline to identify which asset
    and metric combinations still need more telemetry data before
    predictions can be made with full confidence.

    Args:
        db: Database session.

    Returns:
        list[MLAssetBaseline]: All immature baselines across all assets.
    """

    statement = select(MLAssetBaseline).where(
        MLAssetBaseline.is_mature.is_(False),
    )

    result = db.execute(statement)

    return list(result.scalars().all())


def upsert_baseline(
    db: Session,
    asset_id: int,
    metric_name: str,
    stats: BaselineStats,
) -> MLAssetBaseline:
    """
    Create or update the baseline for an asset and metric.

    The unique constraint on (asset_id, metric_name) means only one
    baseline row can exist per asset per metric. This function checks
    for an existing row and updates it in place, or creates a new one
    if none exists.

    Called by the baseline learning pipeline each time enough new
    telemetry has accumulated to recompute statistics.

    Args:
        db: Database session.
        asset_id: Asset identifier.
        metric_name: Metric name matching telemetry_records.values key.
        stats: Computed statistical summary for this asset and metric.

    Returns:
        MLAssetBaseline: Created or updated baseline record.
    """

    # Check whether a baseline row already exists for this asset + metric
    baseline = get_baseline(db, asset_id, metric_name)

    if baseline is None:
        # No existing row — create a new baseline record
        baseline = MLAssetBaseline(
            asset_id=asset_id,
            metric_name=metric_name,
            baseline_mean=stats.baseline_mean,
            baseline_std=stats.baseline_std,
            baseline_min=stats.baseline_min,
            baseline_max=stats.baseline_max,
            percentile_95=stats.percentile_95,
            samples_count=stats.samples_count,
            learning_period_start=stats.learning_period_start,
            learning_period_end=stats.learning_period_end,
            is_mature=stats.is_mature,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(baseline)

    else:
        # Existing row — update all statistical fields in place
        baseline.baseline_mean = stats.baseline_mean
        baseline.baseline_std = stats.baseline_std
        baseline.baseline_min = stats.baseline_min
        baseline.baseline_max = stats.baseline_max
        baseline.percentile_95 = stats.percentile_95
        baseline.samples_count = stats.samples_count
        baseline.learning_period_start = stats.learning_period_start
        baseline.learning_period_end = stats.learning_period_end
        baseline.is_mature = stats.is_mature
        # Stamp the recomputation time on every update
        baseline.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(baseline)

    return baseline