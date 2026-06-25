"""
ML scoring and risk classification. 

Maps raw model output scores to human-readable risk levels and 
determines whether a score crosses the anomaly event threshold. 

Task-aware thresholds are used because the cosequences of a given
score differ by task:

    anomaly_detection - scores represent deviation from normal behavior
                        (IsolationForest output)
    
    failure_prediction -scores represent probability of failure
                        (RandomForest output)

A 0.7 anomaly score means high deviation from normal.
A 0.7 failure probability means 70% chance of imminent failure.
The same numeric value carries different operational weight — so
the thresholds and classifications are defined per task.

Risk levels (ascending severity):
    low       → normal operating range, no action needed
    medium    → elevated, increased monitoring recommended
    high      → significant deviation, investigation warranted
    critical  → immediate operator attention required
"""



import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskThresholds:
    """
    Score thresholds that define risk level boundaries for a task.

    All thresholds are inclusive lower bounds:
        score >= critical_threshold  → critical
        score >= high_threshold      → high
        score >= medium_threshold    → medium
        score <  medium_threshold    → low

    anomaly_event_threshold defines the minimum score at which
    an MLAnomalyEvent record is created. Set higher than high_threshold
    to avoid event noise from elevated-but-not-alarming scores.
    """

    # Lower bound for medium risk classification
    medium_threshold: float

    # Lower bound for high risk classification
    high_threshold: float

    # Lower bound for critical risk classification
    critical_threshold: float

    # Minimum score to trigger anomaly event creation
    anomaly_event_threshold: float


# Anomaly detection thresholds
# Isolation Forest output deviation scores.
# Industrial equipment can show elevated readings without being
# truly anomalous — thresholds are set conservatively to reduce
# false alarms that erode operator trust.
_ANOMALY_DETECTION_THRESHOLDS = TaskThresholds(
    medium_threshold=0.40,
    high_threshold=0.65,
    critical_threshold=0.85,
    anomaly_event_threshold=0.65,
)

# Failure prediction thresholds
# Random Forest output failure probabilities.
# A 50% failure probability is operationally significant — lower
# thresholds than anomaly detection because the consequence of
# missing an impending failure is higher than a false anomaly alert.
_FAILURE_PREDICTION_THRESHOLDS = TaskThresholds(
    medium_threshold=0.30,
    high_threshold=0.55,
    critical_threshold=0.75,
    anomaly_event_threshold=0.55,
)

# Health scoring thresholds
# Health scores run 0 (failed) to 100 (perfect) — inverted scale.
# A health score of 40 means 40% health remaining, which is critical.
_HEALTH_SCORING_THRESHOLDS = TaskThresholds(
    medium_threshold=0.40,
    high_threshold=0.25,
    critical_threshold=0.15,
    anomaly_event_threshold=0.25,
)

# Task name → thresholds lookup
_TASK_THRESHOLDS: dict[str, TaskThresholds] = {
    "anomaly_detection": _ANOMALY_DETECTION_THRESHOLDS,
    "failure_prediction": _FAILURE_PREDICTION_THRESHOLDS,
    "health_scoring": _HEALTH_SCORING_THRESHOLDS,
}

# Valid risk level labels in ascending severity order
RISK_LEVELS = ("low", "medium", "high", "critical")

# Model types that output decision_function() scores (negative = anomalous)
# These require inversion and normalization to 0-1 before classification
_DECISION_FUNCTION_MODELS = frozenset({
    "IsolationForest",
})

# Model types that output predict_proba() scores (already 0-1)
# These require no normalization — passed through directly
_PROBA_MODELS = frozenset({
    "RandomForest",
})


def classify_risk(
    score: float,
    task: str,
) -> str:
    """
    Map a raw model score to a human-readable risk level.

    Thresholds are task-aware — anomaly detection and failure
    prediction use different boundaries because the same numeric
    score carries different operational weight per task.

    Args:
        score: Raw model output score between 0.0 and 1.0.
            For health_scoring, pass the normalized score (health/100).
        task: Inference task that produced this score.
            One of: "anomaly_detection", "failure_prediction",
            "health_scoring".

    Returns:
        str: Risk level — "low", "medium", "high", or "critical".

    Raises:
        ValueError: If task is not recognized.
        ValueError: If score is outside the 0.0 to 1.0 range.
    """

    _validate_score(score)
    thresholds = _get_thresholds(task)

    # Evaluate from highest severity downward
    if score >= thresholds.critical_threshold:
        level = "critical"
    elif score >= thresholds.high_threshold:
        level = "high"
    elif score >= thresholds.medium_threshold:
        level = "medium"
    else:
        level = "low"

    logger.debug(
        "Score %.4f classified as '%s' for task '%s'",
        score, level, task,
    )

    return level


def should_create_anomaly_event(
    score: float,
    task: str,
) -> bool:
    """
    Determine whether a score warrants creating an anomaly event.

    Anomaly events represent operational alerts that require operator
    attention. The event threshold is set above the high_threshold
    for anomaly detection to avoid alert fatigue from elevated-but-
    stable readings.

    Args:
        score: Raw model output score between 0.0 and 1.0.
        task: Inference task that produced this score.

    Returns:
        bool: True if an MLAnomalyEvent should be created.

    Raises:
        ValueError: If task is not recognized.
        ValueError: If score is outside the 0.0 to 1.0 range.
    """

    _validate_score(score)
    thresholds = _get_thresholds(task)

    return score >= thresholds.anomaly_event_threshold


def get_thresholds_for_task(task: str) -> TaskThresholds:
    """
    Return the threshold configuration for a task.

    Used by the inference pipeline and drift monitoring to inspect
    threshold boundaries without re-implementing threshold logic.

    Args:
        task: Inference task name.

    Returns:
        TaskThresholds: Threshold configuration for this task.

    Raises:
        ValueError: If task is not recognized.
    """

    return _get_thresholds(task)


def normalize_health_score(health_score: float) -> float:
    """
    Normalize a 0-100 health score to a 0-1 inverted scale.

    Health scores run 0 (failed) to 100 (perfect). Risk classification
    uses 0-1 where higher means worse. This function inverts and
    normalizes so health scores can be passed to classify_risk.

    Examples:
        100 (perfect health) → 0.0 (no risk)
        75  (good health)    → 0.25 (low risk)
        40  (degraded)       → 0.60 (high risk)
        15  (critical)       → 0.85 (critical risk)

    Args:
        health_score: Health score from 0.0 to 100.0.

    Returns:
        float: Normalized inverted score from 0.0 to 1.0.

    Raises:
        ValueError: If health_score is outside the 0.0 to 100.0 range.
    """

    if not 0.0 <= health_score <= 100.0:
        raise ValueError(
            f"Health score must be between 0.0 and 100.0. Got: {health_score}"
        )

    return 1.0 - (health_score / 100.0)


def normalize_score(
    raw_score: float,
    model_type: str,
) -> float:
    """
    Normalize a raw model output to a 0-1 risk score.

    Different model types produce different output ranges:

    Isolation Forest — decision_function() output:
        Negative values = anomalous, positive = normal.
        More negative = more anomalous.
        Normalized by clipping to [-1, 1] then inverting to [0, 1].

    RandomForest — predict_proba() output:
        Already in 0-1 range. Passed through directly.

    Args:
        raw_score: Raw score directly from model.predict() or
            model.decision_function().
        model_type: Model type string from MLModel.model_type.
            One of: "IsolationForest", "RandomForest".

    Returns:
        float: Normalized score between 0.0 and 1.0 where
            higher always means higher risk.

    Raises:
        ValueError: If model_type is not recognized.
    """

    if model_type in _DECISION_FUNCTION_MODELS:
        # decision_function outputs: negative = anomalous, positive = normal
        # Clip to [-1, 1] to handle outlier scores beyond expected range
        # Invert and shift to [0, 1]: score of -1 → 1.0 (max risk)
        clipped = max(-1.0, min(1.0, raw_score))
        normalized = (1.0 - clipped) / 2.0
        logger.debug(
            "Normalized %s score %.4f → %.4f (decision_function inversion)",
            model_type, raw_score, normalized,
        )
        return normalized

    if model_type in _PROBA_MODELS:
        # predict_proba outputs: already in 0-1 range
        # Clip defensively to handle floating point edge cases
        normalized = max(0.0, min(1.0, raw_score))
        logger.debug(
            "Normalized %s score %.4f → %.4f (proba passthrough)",
            model_type, raw_score, normalized,
        )
        return normalized

    # Unknown model type — raise with clear message
    known = ", ".join(
        f"'{m}'" for m in sorted(_DECISION_FUNCTION_MODELS | _PROBA_MODELS)
    )
    raise ValueError(
        f"Unknown model type '{model_type}'. Known types are: {known}. "
        f"Verify that MLModel.model_type is set correctly at registration."
    )


def _get_thresholds(task: str) -> TaskThresholds:
    """
    Look up thresholds for a task, raising clearly on unknown tasks.

    Args:
        task: Inference task name.

    Returns:
        TaskThresholds: Threshold configuration.

    Raises:
        ValueError: If task is not in the known task registry.
    """

    thresholds = _TASK_THRESHOLDS.get(task)

    if thresholds is None:
        known = ", ".join(f"'{t}'" for t in _TASK_THRESHOLDS)
        raise ValueError(
            f"Unknown task '{task}'. Known tasks are: {known}. "
            f"Verify that MLModel.task matches one of the registered tasks."
        )

    return thresholds


def _validate_score(score: float) -> None:
    """
    Validate that a score is within the expected 0.0 to 1.0 range.

    Args:
        score: Score value to validate.

    Raises:
        ValueError: If score is outside 0.0 to 1.0.
    """

    if not 0.0 <= score <= 1.0:
        raise ValueError(
            f"Score must be between 0.0 and 1.0. Got: {score}. "
            f"Ensure model output is normalized before classification."
        )