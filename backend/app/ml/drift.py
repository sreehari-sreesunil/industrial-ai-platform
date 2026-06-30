"""
ML drift detection.

Population Stability Index (PSI) — measures how much a feature's
distribution has shifted between a reference period (typically
training data) and a current period (typically recent production
telemetry). Widely used in ML monitoring (originated in credit risk
modeling); chosen here for being simple, interpretable, and having
well-established, widely-cited severity thresholds — not because it's
the only valid drift-detection method (KL divergence, Kolmogorov-
Smirnov tests, and Wasserstein distance are also common; PSI is a
defensible choice among several, not a uniquely correct one).

Interpretation thresholds (standard, not specific to this codebase):
    PSI < 0.10            — no significant shift
    0.10 <= PSI < 0.25     — moderate shift, worth monitoring
    PSI >= 0.25            — significant shift, consider retraining

Validated (see scripts/training/experiments/ for the validation
script): identical distributions produce PSI ~0; a 2-standard-deviation
mean shift produces PSI > 3 (far above the "significant" threshold);
a 0.5-standard-deviation shift produces PSI ~0.26, correctly landing
at the moderate/significant boundary.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def calculate_psi(
    reference: np.ndarray,
    current: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Compute the Population Stability Index between two samples of the
    same feature.

    Bin edges are defined by the REFERENCE distribution's quantiles
    (standard practice) — the current sample is then binned using
    those same edges, so both distributions are compared on identical
    buckets even if their individual ranges differ.

    A small epsilon is applied to zero-count bins to avoid log(0) /
    division-by-zero, which would otherwise occur whenever a bin is
    empty in either sample — a real possibility with sparse data or
    a current sample much smaller than the reference.

    Args:
        reference: Reference distribution values (e.g. training data
            for this feature).
        current:   Current distribution values to compare against the
            reference (e.g. recent production telemetry).
        n_bins:    Number of quantile bins. Default 10, the
            conventional choice for PSI.

    Returns:
        float: PSI value. 0 means identical distributions; higher
            values indicate more divergence. See module docstring for
            interpretation thresholds.
    """
    quantiles = np.linspace(0, 1, n_bins + 1)
    bin_edges = np.quantile(reference, quantiles)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    ref_counts, _ = np.histogram(reference, bins=bin_edges)
    cur_counts, _ = np.histogram(current, bins=bin_edges)

    ref_pct = ref_counts / len(reference)
    cur_pct = cur_counts / len(current)

    eps = 1e-6
    ref_pct = np.clip(ref_pct, eps, None)
    cur_pct = np.clip(cur_pct, eps, None)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi

# PSI severity thresholds — see module docstring for citation/standard.
_PSI_MODERATE_THRESHOLD = 0.10
_PSI_SIGNIFICANT_THRESHOLD = 0.25


def classify_drift_severity(psi: float) -> str:
    """
    Map a raw PSI value to a human-readable severity label.

    Args:
        psi: PSI value from calculate_psi(). Expected non-negative;
            not validated here since calculate_psi() always returns
            a non-negative value by construction.

    Returns:
        str: "none", "moderate", or "significant".
    """
    if psi >= _PSI_SIGNIFICANT_THRESHOLD:
        return "significant"
    if psi >= _PSI_MODERATE_THRESHOLD:
        return "moderate"
    return "none"