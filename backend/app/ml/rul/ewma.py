"""
EWMA (Exponentially Weighted Moving Average) RUL estimator.

Smooths noisy health score history by weighting recent readings
more heavily than older ones, then extrapolates the smoothed trend
to estimate remaining useful life.

Confidence is always low (0.2-0.4) — EWMA is a rough estimate
based on linear trend extrapolation. The frontend displays this
with a clear "rough estimate" warning and low confidence indicator.

Frontend displays:
    ~127 days  (⚠ Rough estimate — low confidence)
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Smoothing factor — controls reactivity vs smoothness
# 0.3 is the production standard for industrial sensor data
# Higher α → more reactive to recent changes
# Lower α → smoother, slower to respond
DEFAULT_ALPHA = 0.3

# Minimum health records needed for a meaningful trend
# Less than 7 days of history → return (None, 0.0)
MIN_HISTORY_RECORDS = 7

# Minimum daily decline rate to consider health truly degrading
# Below this threshold → treat as stable, return None for RUL
MIN_DECLINE_RATE = 0.01

# EWMA confidence range — always low for linear extrapolation
# Scaled by data quality: more history → higher confidence within range
CONFIDENCE_MIN = 0.20
CONFIDENCE_MAX = 0.40

# Maximum reasonable RUL estimate — beyond this, return None
# Linear extrapolation is unreliable over very long horizons
MAX_RUL_DAYS = 365


def compute_ewma_rul(
    health_history: list[tuple[datetime, float]],
    alpha: float = DEFAULT_ALPHA,
) -> tuple[int | None, float]:
    """
    Estimate remaining useful life from smoothed health score trend.

    Applies EWMA smoothing to health history, computes the daily
    decline rate from the smoothed series, then extrapolates to
    estimate how many days until health reaches zero.

    Returns (None, 0.0) when:
        - Fewer than MIN_HISTORY_RECORDS records exist
        - Health is stable or improving (no meaningful decline)
        - Extrapolated RUL exceeds MAX_RUL_DAYS

    Args:
        health_history: List of (timestamp, health_score) pairs
            ordered oldest first. Health scores are 0-100.
        alpha: EWMA smoothing factor. Defaults to 0.3.

    Returns:
        tuple[int | None, float]: (rul_days, confidence) where
            rul_days is None when no meaningful estimate exists,
            confidence is always in [CONFIDENCE_MIN, CONFIDENCE_MAX]
            for EWMA estimates.
    """

    # Insufficient history — no meaningful trend to extrapolate
    if len(health_history) < MIN_HISTORY_RECORDS:
        logger.debug(
            "Insufficient history for EWMA RUL: %d records (min %d)",
            len(health_history), MIN_HISTORY_RECORDS,
        )
        return None, 0.0

    # Unpack timestamps and scores
    timestamps = [entry[0] for entry in health_history]
    scores = [entry[1] for entry in health_history]

    # Compute smoothed series
    ewma_series = compute_ewma_series(
        health_history=health_history,
        alpha=alpha,
    )

    # Estimate daily decline rate from smoothed series
    decline_rate = _estimate_daily_decline(
        ewma_series=ewma_series,
        timestamps=timestamps,
    )

    # No meaningful decline — asset is stable or improving
    if decline_rate is None or decline_rate < MIN_DECLINE_RATE:
        logger.debug(
            "Health stable or improving — no RUL estimate. "
            "decline_rate=%s",
            decline_rate,
        )
        return None, 0.0

    # Extrapolate days until health reaches zero
    current_ewma = ewma_series[-1]
    rul_days = current_ewma / decline_rate

    # Extrapolation unreliable beyond one year
    if rul_days > MAX_RUL_DAYS:
        logger.debug(
            "EWMA RUL extrapolation exceeds max horizon: %.1f days",
            rul_days,
        )
        return None, 0.0

    # Scale confidence by data quantity within EWMA confidence range
    confidence = _compute_confidence(len(health_history))

    rul_int = max(1, int(round(rul_days)))

    logger.info(
        "EWMA RUL estimate: %d days (confidence=%.2f, "
        "decline_rate=%.4f/day, current_ewma=%.1f)",
        rul_int, confidence, decline_rate, current_ewma,
    )

    return rul_int, confidence


def compute_ewma_series(
    health_history: list[tuple[datetime, float]],
    alpha: float = DEFAULT_ALPHA,
) -> list[float]:
    """
    Compute EWMA smoothed health scores from raw history.

    Each smoothed value is a weighted combination of the current
    raw score and the previous smoothed value:
        ewma_t = α * score_t + (1 - α) * ewma_t-1

    The first value seeds the series with the raw score.

    Used by the frontend trend chart to show both raw health
    scores and the smoothed EWMA line on the same chart.

    Args:
        health_history: List of (timestamp, health_score) pairs
            ordered oldest first.
        alpha: Smoothing factor between 0.0 and 1.0.

    Returns:
        list[float]: Smoothed health scores, same length as input.
    """

    if not health_history:
        return []

    scores = [entry[1] for entry in health_history]
    ewma_series = [scores[0]]  # Seed with first raw value

    for score in scores[1:]:
        smoothed = alpha * score + (1 - alpha) * ewma_series[-1]
        ewma_series.append(smoothed)

    return ewma_series


def _estimate_daily_decline(
    ewma_series: list[float],
    timestamps: list[datetime],
) -> float | None:
    """
    Estimate the average daily health decline rate from smoothed series.

    Uses the last 7 days of smoothed health to compute the average
    daily decline. Returns None if the window has fewer than 2 points
    or if the time span is zero.

    Args:
        ewma_series: Smoothed health scores ordered oldest first.
        timestamps: Corresponding timestamps ordered oldest first.

    Returns:
        float | None: Average daily decline rate, or None if
            insufficient data to compute.
    """

    if len(ewma_series) < 2 or len(timestamps) < 2:
        return None

    # Find records within the last 7 days
    cutoff = timestamps[-1] - timedelta(days=7)
    window_indices = [
        i for i, ts in enumerate(timestamps)
        if ts >= cutoff
    ]

    # Need at least 2 points for a rate
    if len(window_indices) < 2:
        return None

    start_idx = window_indices[0]
    end_idx = window_indices[-1]

    health_start = ewma_series[start_idx]
    health_end = ewma_series[end_idx]

    time_delta = timestamps[end_idx] - timestamps[start_idx]
    days_elapsed = time_delta.total_seconds() / 86400.0

    # Avoid division by zero
    if days_elapsed == 0:
        return None

    # Positive decline rate means health is decreasing
    decline = (health_start - health_end) / days_elapsed

    return decline if decline > 0 else None


def _compute_confidence(record_count: int) -> float:
    """
    Scale EWMA confidence by data quantity.

    More history gives a more reliable trend estimate, but EWMA
    confidence is always capped within the low confidence range
    [CONFIDENCE_MIN, CONFIDENCE_MAX] — it is never a high confidence
    estimate regardless of data quantity.

    Confidence scales linearly from CONFIDENCE_MIN at MIN_HISTORY_RECORDS
    to CONFIDENCE_MAX at 90 days of history.

    Args:
        record_count: Number of health records available.

    Returns:
        float: Confidence score in [CONFIDENCE_MIN, CONFIDENCE_MAX].
    """

    # Scale from min to max confidence over 7 to 90 records
    scale = min(1.0, (record_count - MIN_HISTORY_RECORDS) / (90 - MIN_HISTORY_RECORDS))
    confidence = CONFIDENCE_MIN + scale * (CONFIDENCE_MAX - CONFIDENCE_MIN)

    return round(confidence, 3)