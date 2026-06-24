# app/ml/rul/weibull.py
"""
Weibull survival analysis for professional-tier RUL estimation.

Uses industry-baseline Weibull parameters (beta, eta) since labeled
failure history is not available at onboarding. The raw population-level
estimate is adjusted by the asset's current health score to produce
an asset-specific RUL.

Why Weibull over EWMA at the professional tier:
    EWMA extrapolates a health trend — it answers "if decline continues
    at this rate, when does health hit zero?" It has no model of the
    failure process itself.

    Weibull models the failure process directly — it answers "given
    this asset type's known wear-out behavior and how long it has been
    running, what is the probability it survives the next N days?"
    This is a fundamentally stronger claim, which is why confidence
    is higher (0.40–0.65 vs 0.20–0.40 for EWMA).

    Confidence is still capped because parameters are population-level
    baselines, not fitted to this specific asset's failure history.
    Enterprise tier (XGBoost RUL on NASA CMAPSS) closes that gap.

Weibull survival function:
    S(t) = exp(-(t/η)^β)

    β (beta)  — shape parameter
        β < 1 → infant mortality (early failures dominate)
        β = 1 → random failures (memoryless, like a Poisson process)
        β > 1 → wear-out failures (most industrial equipment)

    η (eta) — characteristic life in hours
        The time at which 63.2% of the population has failed.
        (Because S(η) = exp(-1) ≈ 0.368, so 1 - 0.368 = 63.2% failed.)

RUL derivation:
    End-of-life is defined as S(t*) = SURVIVAL_THRESHOLD (10%).
    Solving analytically: t* = η * (-ln(threshold))^(1/β)
    RUL = t* - elapsed_hours, health-adjusted, converted to days.

TUNING NOTE: WEIBULL_PARAMS are industry baselines sourced from
    published reliability engineering literature. Tune per asset_type
    using maximum likelihood estimation (MLE) on labeled failure history
    once sufficient failure events are collected per asset class.
    Target metric: Brier score on survival probability predictions.
    See ML.md § Validation Strategy.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeibullParams:
    """
    Weibull shape and scale parameters for a single asset type.

    Attributes:
        beta: Shape parameter. Controls the failure rate pattern.
            Industrial wear-out equipment typically falls in 1.5–3.0.
        eta:  Characteristic life in hours. The age at which 63.2%
            of the population has failed under normal operating conditions.
    """

    beta: float
    eta: float


# Industry-baseline Weibull parameters per asset type.
#
# Sources: reliability engineering literature and IEEE standards.
# These represent population-level behavior under normal operating
# conditions — individual assets will deviate based on load, environment,
# and maintenance history.
#
# beta > 1 for all three: wear-out failure mode dominates in each case,
# meaning failure rate increases with age (the expected regime for
# maintained rotating equipment).
WEIBULL_PARAMS: dict[str, WeibullParams] = {
    "compressor": WeibullParams(beta=2.2, eta=8760),   # ~1 year characteristic life
    "pump":       WeibullParams(beta=1.8, eta=6500),   # ~9 months
    "motor":      WeibullParams(beta=2.5, eta=12000),  # ~1.4 years
}

# Survival probability below which we declare end of useful life.
# 10% survival means 90% of the population has already failed —
# operating past this point is high-risk without explicit justification.
SURVIVAL_THRESHOLD = 0.10

# Health score at which no adjustment is applied.
# An asset at exactly this health level gets the raw population estimate.
# Chosen as 75/100 — "good" health, close to the population average
# for an asset that has been running and receiving maintenance.
HEALTH_NEUTRAL = 0.75

# Maximum fractional shift the health adjustment can apply.
# Health can shift the raw RUL by at most ±30%.
# Capped to prevent extreme health scores from dominating the estimate —
# the Weibull model should remain the primary signal.
HEALTH_ADJUSTMENT_RANGE = 0.30

# Assumed telemetry sample interval in hours.
# Used to convert record count → cumulative operating hours.
#
# TUNING NOTE: If telemetry is sampled at a different interval
# (e.g. every 5 minutes = 1/12 hour), update this constant or
# make it a per-asset-type config in Sprint 5 settings.
SAMPLE_INTERVAL_HOURS = 1.0

# Minimum records required before attempting an estimate.
# 24 records = 24 hours at the default sample interval —
# enough to confirm the asset is operational, not enough to trust
# the elapsed-time estimate for long-horizon RUL.
MIN_RECORDS = 24

# RUL ceiling in days.
MAX_RUL_DAYS = 365

# Confidence bounds for Weibull estimates.
# Higher floor than EWMA (0.40 vs 0.20) because Weibull models the
# failure process rather than extrapolating a health trend.
# Ceiling capped at 0.65 because parameters are population-level —
# enterprise tier (asset-specific fitted model) closes this gap.
CONFIDENCE_MIN = 0.40
CONFIDENCE_MAX = 0.65

# Record count at which confidence reaches CONFIDENCE_MAX.
# One year of hourly data — at this point the elapsed-time estimate
# is reliable enough that population parameters are the binding limit.
_CONFIDENCE_SCALE_MAX_RECORDS = 8760


def compute_weibull_rul(
    asset_type_name: str,
    telemetry_record_count: int,
    current_health_score: float,
) -> tuple[int | None, float]:
    """
    Estimate remaining useful life in days using Weibull survival analysis.

    Uses industry-baseline Weibull parameters for the asset type.
    Adjusts the raw population estimate by the asset's current health
    score relative to the neutral baseline (HEALTH_NEUTRAL = 0.75).

    Returns (None, 0.0) when:
        - asset_type_name is not in WEIBULL_PARAMS
        - telemetry_record_count < MIN_RECORDS
        - asset has already passed the survival threshold
        - adjusted remaining hours <= 0

    Args:
        asset_type_name:        Asset type string, case-insensitive.
                                Must match a key in WEIBULL_PARAMS.
        telemetry_record_count: Total telemetry records for this asset.
                                Multiplied by SAMPLE_INTERVAL_HOURS to
                                approximate cumulative operating hours.
        current_health_score:   Current health score from ml_asset_health,
                                0–100. Used to adjust the population-level
                                estimate toward this specific asset.

    Returns:
        tuple[int | None, float]: (rul_days, confidence) where rul_days
            is None when no meaningful estimate can be made, and
            confidence is 0.0 whenever rul_days is None.
    """
    # Unknown asset type — no parameters to work with
    params = WEIBULL_PARAMS.get(asset_type_name.lower())
    if params is None:
        logger.debug(
            "weibull_rul: no params for asset_type='%s', returning None. "
            "Add to WEIBULL_PARAMS to enable professional-tier RUL.",
            asset_type_name,
        )
        return None, 0.0

    # Insufficient data — elapsed-time estimate is not reliable
    if telemetry_record_count < MIN_RECORDS:
        logger.debug(
            "weibull_rul: insufficient records (%d < %d) for asset_type='%s'",
            telemetry_record_count,
            MIN_RECORDS,
            asset_type_name,
        )
        return None, 0.0

    # Step 1 — approximate cumulative operating hours
    elapsed_hours = telemetry_record_count * SAMPLE_INTERVAL_HOURS

    # Step 2 — check whether the asset has already passed end-of-life
    current_survival = _survival(elapsed_hours, params)
    if current_survival <= SURVIVAL_THRESHOLD:
        logger.info(
            "weibull_rul: asset_type='%s' at or past survival threshold "
            "(survival=%.3f, elapsed_hours=%.1f) — RUL is None",
            asset_type_name,
            current_survival,
            elapsed_hours,
        )
        return None, 0.0

    # Step 3 — solve for t* where S(t*) = SURVIVAL_THRESHOLD
    # Closed-form inversion: t* = η * (-ln(threshold))^(1/β)
    end_of_life_hours = _solve_end_of_life(params)

    # Step 4 — raw remaining life at population level
    raw_remaining_hours = end_of_life_hours - elapsed_hours
    if raw_remaining_hours <= 0:
        return None, 0.0

    # Step 5 — adjust for this asset's current health
    adjusted_hours = _apply_health_adjustment(raw_remaining_hours, current_health_score)

    # Step 6 — convert to days and apply ceiling
    rul_days = min(adjusted_hours / 24.0, MAX_RUL_DAYS)

    # Step 7 — confidence scales with record count
    confidence = _compute_confidence(telemetry_record_count)

    rul_int = max(1, int(round(rul_days)))

    logger.info(
        "weibull_rul: asset_type='%s' elapsed_hours=%.1f "
        "end_of_life_hours=%.1f raw_remaining=%.1f "
        "adjusted_hours=%.1f rul_days=%d confidence=%.2f",
        asset_type_name,
        elapsed_hours,
        end_of_life_hours,
        raw_remaining_hours,
        adjusted_hours,
        rul_int,
        confidence,
    )

    return rul_int, confidence


# ---------------------------------------------------------------------------
# Internal helpers — not part of the public API
# ---------------------------------------------------------------------------

def _survival(t: float, params: WeibullParams) -> float:
    """
    Weibull survival function: S(t) = exp(-(t/η)^β).

    Returns the probability that an asset of this type survives
    past age t hours under normal operating conditions.

    Args:
        t:      Age in hours.
        params: Weibull parameters for this asset type.

    Returns:
        float: Survival probability in [0.0, 1.0].
    """
    return math.exp(-((t / params.eta) ** params.beta))


def _solve_end_of_life(params: WeibullParams) -> float:
    """
    Solve for the age t* at which survival probability equals SURVIVAL_THRESHOLD.

    Closed-form inversion of S(t) = threshold:
        exp(-(t/η)^β) = threshold
        (t/η)^β       = -ln(threshold)
        t             = η * (-ln(threshold))^(1/β)

    No numerical root-finding required — the Weibull survival function
    inverts analytically. Zero dependencies, transparent math.

    Args:
        params: Weibull parameters for this asset type.

    Returns:
        float: Age in hours at which survival hits SURVIVAL_THRESHOLD.
    """
    return params.eta * ((-math.log(SURVIVAL_THRESHOLD)) ** (1.0 / params.beta))


def _apply_health_adjustment(
    raw_remaining_hours: float,
    current_health_score: float,
) -> float:
    """
    Scale raw remaining hours by the asset's current health relative to neutral.

    A healthy asset (above HEALTH_NEUTRAL) gets more remaining life than
    the population estimate. A degraded asset gets less.

    Adjustment factor at key health values:
        health=100  → factor ≈ 1.33  (+33% more life than population)
        health=75   → factor = 1.00  (population baseline, no change)
        health=50   → factor ≈ 0.90  (-10%)
        health=0    → factor = 0.70  (clamped floor — Weibull remains primary signal)

    The downside is intentionally conservative: health score, anomaly events,
    and failure probability already communicate risk through other channels.
    We don't want Weibull RUL to double-punish a degraded asset.

    Args:
        raw_remaining_hours: Population-level remaining hours from Weibull.
        current_health_score: Health score 0–100 from ml_asset_health.

    Returns:
        float: Adjusted remaining hours.
    """
    health_fraction = max(0.0, min(100.0, current_health_score)) / 100.0
    health_delta = health_fraction - HEALTH_NEUTRAL
    adjustment_factor = 1.0 + health_delta * (HEALTH_ADJUSTMENT_RANGE / HEALTH_NEUTRAL)

    # Clamp to ±50% — prevents extreme health scores from overwhelming
    # the Weibull estimate entirely
    adjustment_factor = max(0.50, min(1.50, adjustment_factor))

    logger.debug(
        "_apply_health_adjustment: health=%.1f fraction=%.3f "
        "delta=%.3f factor=%.3f",
        current_health_score,
        health_fraction,
        health_delta,
        adjustment_factor,
    )

    return raw_remaining_hours * adjustment_factor


def _compute_confidence(record_count: int) -> float:
    """
    Scale confidence linearly from CONFIDENCE_MIN to CONFIDENCE_MAX.

    Confidence grows as record count increases because a longer elapsed-time
    estimate is more reliable. Growth is linear from MIN_RECORDS to
    _CONFIDENCE_SCALE_MAX_RECORDS (one year of hourly data), then flat.

    Args:
        record_count: Total telemetry records available for this asset.

    Returns:
        float: Confidence in [CONFIDENCE_MIN, CONFIDENCE_MAX].
    """
    span = _CONFIDENCE_SCALE_MAX_RECORDS - MIN_RECORDS
    t = min(record_count - MIN_RECORDS, span) / span
    t = max(0.0, t)
    return round(CONFIDENCE_MIN + t * (CONFIDENCE_MAX - CONFIDENCE_MIN), 3)