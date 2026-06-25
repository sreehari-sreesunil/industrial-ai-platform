# scripts/training/evaluator.py
"""
Model evaluator.

Evaluates fitted model pipelines across all CV folds and against
the final hold-out set. Computes metrics, optimizes decision threshold,
checks benchmarks, and produces calibration diagnostics.

Metrics computed:

    anomaly_detection:
        - Precision, Recall, F1 on anomaly class
        - False Positive Rate (alert fatigue indicator)
        - PR-AUC (more informative than ROC-AUC for imbalanced data)
        - Lead time (median records of warning before failure window)

    failure_prediction:
        - AUC-ROC (primary discrimination metric)
        - PR-AUC (imbalance-aware, mandatory alongside ROC-AUC)
        - F1, Precision, Recall at OPTIMIZED threshold (not fixed 0.5)
        - Brier Score (probability calibration quality)
        - Calibration diagnostics

Threshold optimization (failure_prediction only):
    With severe class imbalance (e.g. 2% positive rate), a fixed 0.5
    decision threshold is almost always wrong. The model's predict_proba
    output is a valid ranking signal even when miscalibrated at the 0.5
    cutoff — RandomForest AUC-ROC=0.96 in our case proves the ranking is
    excellent, but precision=0.17 at threshold=0.5 proves the cutoff is
    misplaced.

    The threshold is optimized using ONLY the concatenated CV fold
    validation sets — never the hold-out set. This prevents threshold
    selection from leaking hold-out information into a number that's
    supposed to be a final, unbiased test.

    Selection rule: among all thresholds where recall >= benchmark.recall,
    pick the one that maximizes precision. This directly targets "find
    the most precise threshold that still satisfies our minimum recall
    requirement" rather than optimizing F1 blindly, since recall has a
    higher safety cost than precision in this domain (missing a real
    failure is worse than a false alarm).

    The locked threshold is then applied ONCE to the hold-out set for
    the terminal, reported metrics.

CV evaluation strategy:
    Each fold produces a full set of metrics at the optimized threshold.
    Mean ± std across folds shown alongside hold-out for stability check.

Public API:
    evaluate_model(pipelines, dataset, model_type) → EvaluationResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from scripts.training.config import (
    ANOMALY_BENCHMARKS,
    FAILURE_BENCHMARKS,
    AnomalyDetectionBenchmarks,
    FailurePredictionBenchmarks,
)
from scripts.training.data_loader import TrainingDataset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result contracts
# ---------------------------------------------------------------------------

@dataclass
class FoldMetrics:
    """
    Metrics for a single CV fold.

    Attributes:
        fold_index: Zero-based fold index.
        metrics:    Dict of metric name → value for this fold.
    """
    fold_index: int
    metrics: dict[str, float]


@dataclass
class BenchmarkResult:
    """
    Result of a single metric benchmark check.

    Attributes:
        metric:           Metric name.
        cv_mean:          Mean value across CV folds.
        cv_std:           Std across CV folds — stability indicator.
        holdout_value:    Terminal value on hold-out set.
        threshold:        Benchmark from config.
        passed:           True if holdout_value meets threshold.
        higher_is_better: Direction of comparison.
    """
    metric: str
    cv_mean: float
    cv_std: float
    holdout_value: float
    threshold: float
    passed: bool
    higher_is_better: bool = True

    def __str__(self) -> str:
        direction = ">=" if self.higher_is_better else "<="
        status = "PASS" if self.passed else "FAIL"
        return (
            f"  [{status}] {self.metric:25s} "
            f"cv={self.cv_mean:.4f}±{self.cv_std:.4f}  "
            f"holdout={self.holdout_value:.4f}  "
            f"threshold{direction}{self.threshold:.4f}"
        )


@dataclass
class CalibrationDiagnostic:
    """
    Calibration curve data for failure prediction models.

    Attributes:
        fraction_of_positives: Actual positive rate per probability bin.
        mean_predicted_value:  Mean predicted probability per bin.
        n_bins:                Number of calibration bins used.
    """
    fraction_of_positives: list[float]
    mean_predicted_value: list[float]
    n_bins: int


@dataclass
class EvaluationResult:
    """
    Complete evaluation result across all CV folds and hold-out.

    Attributes:
        task:               Inference task.
        model_type:         Algorithm evaluated.
        passed:             True only if ALL benchmarks passed on hold-out.
        fold_metrics:       Per-fold metric breakdown.
        benchmarks:         Benchmark results with CV and hold-out values.
        metrics:            Final holdout metrics dict for registration.
        failed_benchmarks:  Names of failed benchmarks.
        calibration:        Calibration diagnostic (failure_prediction only).
        best_fold_index:    Index of the fold with best primary metric.
        decision_threshold: Optimized decision threshold (failure_prediction
                            only). None for anomaly_detection, which uses
                            decision_function's natural zero boundary.
    """
    task: str
    model_type: str
    passed: bool
    fold_metrics: list[FoldMetrics]
    benchmarks: list[BenchmarkResult]
    metrics: dict[str, float]
    failed_benchmarks: list[str] = field(default_factory=list)
    calibration: CalibrationDiagnostic | None = None
    best_fold_index: int = 0
    decision_threshold: float | None = None

    def print_report(self) -> None:
        """Print structured evaluation report to stdout."""
        status = "PASSED ✓" if self.passed else "FAILED ✗"
        print(f"\n{'='*70}")
        print(f"Evaluation Report — {self.model_type} ({self.task})")
        print(f"Overall: {status}")
        if self.decision_threshold is not None:
            print(f"Decision threshold (optimized): {self.decision_threshold:.4f}")
        print(f"{'='*70}")
        print(f"{'Metric':<25} {'CV Mean':>10} {'CV Std':>10} "
              f"{'Holdout':>10} {'Threshold':>10} {'':>6}")
        print(f"{'-'*70}")
        for b in self.benchmarks:
            print(b)
        if self.failed_benchmarks:
            print(f"\nFailed: {', '.join(self.failed_benchmarks)}")
        if self.calibration:
            self._print_calibration()
        print(f"{'='*70}\n")

    def _print_calibration(self) -> None:
        """Print calibration diagnostic summary."""
        if not self.calibration:
            return
        fop = self.calibration.fraction_of_positives
        mpv = self.calibration.mean_predicted_value
        max_gap = max(abs(f - m) for f, m in zip(fop, mpv))
        print(f"\nCalibration (max gap from perfect: {max_gap:.4f})")
        print(f"  Predicted → Actual")
        for m, f in zip(mpv, fop):
            bar = "█" * int(f * 20)
            print(f"  {m:.2f} → {f:.2f}  {bar}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_model(
    pipelines: list[Pipeline],
    dataset: TrainingDataset,
    model_type: str,
) -> EvaluationResult:
    """
    Evaluate fitted pipelines across CV folds and hold-out set.

    For failure_prediction, optimizes the decision threshold using
    ONLY CV fold validation data before computing any hold-out metrics.
    This prevents threshold selection from leaking hold-out information.

    Args:
        pipelines:  List of fitted Pipelines, one per CV fold.
                    Must have same length as dataset.folds.
        dataset:    TrainingDataset with folds and hold-out set.
        model_type: Algorithm name.

    Returns:
        EvaluationResult with CV metrics, holdout metrics, benchmarks.

    Raises:
        ValueError: If len(pipelines) != len(dataset.folds).
    """
    if len(pipelines) != len(dataset.folds):
        raise ValueError(
            f"Expected {len(dataset.folds)} pipelines, got {len(pipelines)}."
        )

    logger.info(
        "Evaluating %s across %d folds + hold-out (task=%s)",
        model_type,
        len(pipelines),
        dataset.task,
    )

    # Select best pipeline by primary metric (AUC-ROC for supervised,
    # PR-AUC for unsupervised) — done BEFORE threshold optimization
    # since threshold optimization needs one fixed pipeline to evaluate
    primary_metric = (
        "pr_auc" if dataset.task == "anomaly_detection" else "auc_roc"
    )

    # Quick pass to rank folds by primary metric using default threshold,
    # just to pick which pipeline becomes "the model" going forward
    quick_scores = []
    for pipeline, fold in zip(pipelines, dataset.folds):
        if dataset.task == "anomaly_detection":
            score = _quick_pr_auc_anomaly(pipeline, fold.X_val, fold.y_val)
        else:
            score = _quick_auc_roc(pipeline, fold.X_val, fold.y_val)
        quick_scores.append(score)

    best_fold_index = int(np.argmax(quick_scores))
    best_pipeline = pipelines[best_fold_index]

    logger.info(
        "Best fold: %d (primary metric %s=%.4f)",
        best_fold_index,
        primary_metric,
        quick_scores[best_fold_index],
    )

    # -----------------------------------------------------------------------
    # Threshold optimization (failure_prediction only)
    # -----------------------------------------------------------------------
    decision_threshold = 0.5  # default for anomaly_detection / fallback
    if dataset.task == "failure_prediction":
        decision_threshold = _optimize_threshold(
            pipeline=best_pipeline,
            folds=dataset.folds,
            benchmarks=FAILURE_BENCHMARKS,
        )
        logger.info(
            "Optimized decision threshold: %.4f (selected using CV folds only)",
            decision_threshold,
        )

    # -----------------------------------------------------------------------
    # Per-fold evaluation at the locked threshold
    # -----------------------------------------------------------------------
    evaluator_fn = (
        _evaluate_anomaly_detection
        if dataset.task == "anomaly_detection"
        else _evaluate_failure_prediction
    )

    fold_metrics: list[FoldMetrics] = []
    for pipeline, fold in zip(pipelines, dataset.folds):
        if dataset.task == "failure_prediction":
            metrics = evaluator_fn(
                pipeline=pipeline,
                X_val=fold.X_val,
                y_val=fold.y_val,
                threshold=decision_threshold,
            )
        else:
            metrics = evaluator_fn(
                pipeline=pipeline,
                X_val=fold.X_val,
                y_val=fold.y_val,
            )
        fold_metrics.append(FoldMetrics(
            fold_index=fold.fold_index,
            metrics=metrics,
        ))
        logger.info(
            "Fold %d metrics: %s",
            fold.fold_index,
            ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()),
        )

    # -----------------------------------------------------------------------
    # Terminal hold-out evaluation — happens ONCE, at the locked threshold
    # -----------------------------------------------------------------------
    if dataset.task == "failure_prediction":
        holdout_metrics = evaluator_fn(
            pipeline=best_pipeline,
            X_val=dataset.X_holdout,
            y_val=dataset.y_holdout,
            threshold=decision_threshold,
        )
    else:
        holdout_metrics = evaluator_fn(
            pipeline=best_pipeline,
            X_val=dataset.X_holdout,
            y_val=dataset.y_holdout,
        )

    logger.info(
        "Hold-out metrics: %s",
        ", ".join(f"{k}={v:.4f}" for k, v in holdout_metrics.items()),
    )

    # Build benchmark results
    benchmarks_config = (
        ANOMALY_BENCHMARKS
        if dataset.task == "anomaly_detection"
        else FAILURE_BENCHMARKS
    )

    benchmark_results = _build_benchmark_results(
        fold_metrics=fold_metrics,
        holdout_metrics=holdout_metrics,
        benchmarks=benchmarks_config,
        task=dataset.task,
    )

    # Calibration diagnostic for failure prediction
    calibration = None
    if dataset.task == "failure_prediction":
        calibration = _compute_calibration(
            pipeline=best_pipeline,
            X_val=dataset.X_holdout,
            y_val=dataset.y_holdout,
        )

    failed = [b.metric for b in benchmark_results if not b.passed]
    passed = len(failed) == 0

    result = EvaluationResult(
        task=dataset.task,
        model_type=model_type,
        passed=passed,
        fold_metrics=fold_metrics,
        benchmarks=benchmark_results,
        metrics=holdout_metrics,
        failed_benchmarks=failed,
        calibration=calibration,
        best_fold_index=best_fold_index,
        decision_threshold=(
            decision_threshold if dataset.task == "failure_prediction" else None
        ),
    )

    result.print_report()
    return result


# ---------------------------------------------------------------------------
# Threshold optimization
# ---------------------------------------------------------------------------

def _optimize_threshold(
    pipeline: Pipeline,
    folds: list[Any],
    benchmarks: FailurePredictionBenchmarks,
    recall_margin: float = 0.05,
) -> float:
    """
    Find the decision threshold that maximizes precision subject to
    a minimum recall constraint, using ONLY CV fold validation data.

    A safety margin is added to the recall floor during optimization.
    Without it, the selected threshold sits at the exact edge of the
    constraint on pooled CV data — and since hold-out is a different
    sample, natural variation can push the real recall below the
    benchmark even though the CV-pooled estimate cleared it. We saw
    this exact failure mode in practice: pooled recall=0.6511 against
    a 0.65 floor, with individual fold recalls ranging from 0.42 to
    0.64 (std=0.077) — far too unstable to trust a razor-thin margin.

    Args:
        pipeline:      The selected best pipeline.
        folds:         All CV folds — their validation sets are pooled.
        benchmarks:    FailurePredictionBenchmarks with minimum recall target.
        recall_margin: Extra recall cushion required during optimization,
                       above the actual benchmark floor. Default 0.05 —
                       targets recall>=0.70 internally to reliably clear
                       a 0.65 hold-out benchmark despite fold-to-fold variance.

    Returns:
        float: Optimized decision threshold in (0, 1).
    """
    all_y_val = []
    all_y_proba = []

    for fold in folds:
        y_proba = pipeline.predict_proba(fold.X_val)[:, 1]
        all_y_val.append(fold.y_val)
        all_y_proba.append(y_proba)

    y_val_pooled = np.concatenate(all_y_val)
    y_proba_pooled = np.concatenate(all_y_proba)

    if len(np.unique(y_val_pooled)) < 2:
        logger.warning(
            "Pooled CV validation set has only one class — "
            "cannot optimize threshold. Falling back to 0.5."
        )
        return 0.5

    precisions, recalls, thresholds = precision_recall_curve(
        y_val_pooled, y_proba_pooled
    )
    precisions = precisions[:-1]
    recalls = recalls[:-1]

    # Apply safety margin — require MORE recall than the bare minimum
    # during selection, to absorb fold-to-fold and CV-vs-holdout variance
    target_recall = benchmarks.recall + recall_margin
    meets_recall = recalls >= target_recall

    if meets_recall.any():
        candidate_precisions = np.where(meets_recall, precisions, -1.0)
        best_idx = int(np.argmax(candidate_precisions))
        selected_threshold = float(thresholds[best_idx])
        selected_precision = float(precisions[best_idx])
        selected_recall = float(recalls[best_idx])

        logger.info(
            "Threshold optimization: found %d candidates meeting "
            "recall>=%.2f (benchmark %.2f + margin %.2f). "
            "Selected threshold=%.4f (precision=%.4f, recall=%.4f)",
            meets_recall.sum(),
            target_recall,
            benchmarks.recall,
            recall_margin,
            selected_threshold,
            selected_precision,
            selected_recall,
        )
        return selected_threshold

    # Fallback: even with margin relaxed to zero, nothing qualifies —
    # try the bare benchmark floor before giving up to F1
    logger.warning(
        "No threshold achieves recall>=%.2f (with margin). "
        "Retrying with bare benchmark floor recall>=%.2f.",
        target_recall,
        benchmarks.recall,
    )
    meets_bare_recall = recalls >= benchmarks.recall
    if meets_bare_recall.any():
        candidate_precisions = np.where(meets_bare_recall, precisions, -1.0)
        best_idx = int(np.argmax(candidate_precisions))
        fallback_threshold = float(thresholds[best_idx])
        logger.info(
            "Fallback (bare floor) threshold=%.4f (precision=%.4f, recall=%.4f)",
            fallback_threshold,
            precisions[best_idx],
            recalls[best_idx],
        )
        return fallback_threshold

    # Final fallback: maximize F1
    logger.warning(
        "No threshold achieves even the bare recall floor. "
        "Falling back to F1-maximizing threshold."
    )
    f1_scores = np.where(
        (precisions + recalls) > 0,
        2 * precisions * recalls / (precisions + recalls + 1e-10),
        0.0,
    )
    best_idx = int(np.argmax(f1_scores))
    fallback_threshold = float(thresholds[best_idx])
    logger.info(
        "F1 fallback threshold=%.4f (precision=%.4f, recall=%.4f, f1=%.4f)",
        fallback_threshold,
        precisions[best_idx],
        recalls[best_idx],
        f1_scores[best_idx],
    )
    return fallback_threshold


def _quick_auc_roc(pipeline: Pipeline, X_val: np.ndarray, y_val: np.ndarray) -> float:
    """Quick AUC-ROC computation for fold ranking, no threshold needed."""
    if len(np.unique(y_val)) < 2:
        return 0.0
    y_proba = pipeline.predict_proba(X_val)[:, 1]
    return float(roc_auc_score(y_val, y_proba))


def _quick_pr_auc_anomaly(pipeline: Pipeline, X_val: np.ndarray, y_val: np.ndarray) -> float:
    """Quick PR-AUC computation for anomaly detection fold ranking."""
    if len(np.unique(y_val)) < 2:
        return 0.0
    raw_scores = pipeline.named_steps["model"].decision_function(
        pipeline.named_steps["scaler"].transform(X_val)
    )
    anomaly_scores = -raw_scores
    score_min, score_max = anomaly_scores.min(), anomaly_scores.max()
    score_range = score_max - score_min
    normalised = (
        (anomaly_scores - score_min) / score_range
        if score_range > 0 else np.zeros_like(anomaly_scores)
    )
    return float(average_precision_score(y_val, normalised))


# ---------------------------------------------------------------------------
# Task-specific metric computation
# ---------------------------------------------------------------------------

def _evaluate_anomaly_detection(
    pipeline: Pipeline,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> dict[str, float]:
    """
    Compute anomaly detection metrics for one evaluation set.

    Score extraction:
        decision_function() returns raw scores.
        For IsolationForest: negative = anomalous.
        Negated so higher score = more anomalous.
        Decision boundary is the model's natural zero point —
        no threshold optimization applies here (unsupervised).

    Args:
        pipeline: Fitted Pipeline (scaler + anomaly model).
        X_val:    Validation feature matrix.
        y_val:    True binary labels.

    Returns:
        dict[str, float]: All computed metrics.
    """
    raw_scores = pipeline.named_steps["model"].decision_function(
        pipeline.named_steps["scaler"].transform(X_val)
    )
    anomaly_scores = -raw_scores
    y_pred = (anomaly_scores > 0).astype(int)

    precision = float(precision_score(y_val, y_pred, zero_division=0))
    recall = float(recall_score(y_val, y_pred, zero_division=0))
    f1 = float(f1_score(y_val, y_pred, zero_division=0))

    tn, fp, fn, tp = confusion_matrix(y_val, y_pred, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    score_min, score_max = anomaly_scores.min(), anomaly_scores.max()
    score_range = score_max - score_min
    normalised = (
        (anomaly_scores - score_min) / score_range
        if score_range > 0 else np.zeros_like(anomaly_scores)
    )
    pr_auc = float(average_precision_score(y_val, normalised)) \
        if len(np.unique(y_val)) > 1 else 0.0

    lead_time = _compute_lead_time(y_val, y_pred)

    return {
        "precision":           precision,
        "recall":              recall,
        "f1":                  f1,
        "false_positive_rate": fpr,
        "pr_auc":              pr_auc,
        "lead_time_records":   float(lead_time),
    }


def _evaluate_failure_prediction(
    pipeline: Pipeline,
    X_val: np.ndarray,
    y_val: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """
    Compute failure prediction metrics for one evaluation set.

    Uses the provided decision threshold instead of a fixed 0.5 —
    see _optimize_threshold() for how this is selected. AUC-ROC,
    PR-AUC, and Brier score are threshold-independent and computed
    from raw probabilities regardless of the threshold parameter.

    Args:
        pipeline:  Fitted Pipeline (scaler + classifier).
        X_val:     Validation feature matrix.
        y_val:     True binary labels.
        threshold: Decision threshold for binary classification metrics
                  (F1, precision, recall). Default 0.5 only used when
                  no optimization has run (e.g. direct unit testing).

    Returns:
        dict[str, float]: All computed metrics.
    """
    if len(np.unique(y_val)) < 2:
        logger.warning(
            "Single class in validation set — "
            "AUC metrics cannot be computed. Returning zeros."
        )
        return {
            "auc_roc":     0.0,
            "pr_auc":      0.0,
            "f1":          0.0,
            "precision":   0.0,
            "recall":      0.0,
            "brier_score": 1.0,
        }

    y_proba = pipeline.predict_proba(X_val)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    auc = float(roc_auc_score(y_val, y_proba))
    pr_auc = float(average_precision_score(y_val, y_proba))
    f1 = float(f1_score(y_val, y_pred, zero_division=0))
    precision = float(precision_score(y_val, y_pred, zero_division=0))
    recall = float(recall_score(y_val, y_pred, zero_division=0))
    brier = float(brier_score_loss(y_val, y_proba))

    return {
        "auc_roc":     auc,
        "pr_auc":      pr_auc,
        "f1":          f1,
        "precision":   precision,
        "recall":      recall,
        "brier_score": brier,
    }


# ---------------------------------------------------------------------------
# Benchmark construction
# ---------------------------------------------------------------------------

def _build_benchmark_results(
    fold_metrics: list[FoldMetrics],
    holdout_metrics: dict[str, float],
    benchmarks: AnomalyDetectionBenchmarks | FailurePredictionBenchmarks,
    task: str,
) -> list[BenchmarkResult]:
    """
    Build BenchmarkResult list from CV fold metrics and holdout metrics.

    Args:
        fold_metrics:    Per-fold metric dicts.
        holdout_metrics: Terminal metrics from hold-out evaluation.
        benchmarks:      Threshold config for this task.
        task:            Task name for threshold direction lookup.

    Returns:
        list[BenchmarkResult]: One per metric in holdout_metrics.
    """
    all_metric_names = list(holdout_metrics.keys())
    cv_values: dict[str, list[float]] = {m: [] for m in all_metric_names}
    for fm in fold_metrics:
        for metric in all_metric_names:
            cv_values[metric].append(fm.metrics.get(metric, 0.0))

    lower_is_better = {"false_positive_rate", "brier_score"}

    results = []
    for metric in all_metric_names:
        values = cv_values[metric]
        cv_mean = float(np.mean(values))
        cv_std = float(np.std(values))
        holdout_value = holdout_metrics[metric]
        higher_is_better = metric not in lower_is_better

        threshold = getattr(benchmarks, metric, None)
        if threshold is None:
            continue

        if higher_is_better:
            passed = holdout_value >= threshold
        else:
            passed = holdout_value <= threshold

        results.append(BenchmarkResult(
            metric=metric,
            cv_mean=cv_mean,
            cv_std=cv_std,
            holdout_value=holdout_value,
            threshold=threshold,
            passed=passed,
            higher_is_better=higher_is_better,
        ))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_calibration(
    pipeline: Pipeline,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_bins: int = 10,
) -> CalibrationDiagnostic | None:
    """
    Compute calibration curve for probability output models.

    Args:
        pipeline: Fitted Pipeline with predict_proba support.
        X_val:    Validation feature matrix.
        y_val:    True binary labels.
        n_bins:   Number of calibration bins.

    Returns:
        CalibrationDiagnostic | None: None if single class in y_val.
    """
    if len(np.unique(y_val)) < 2:
        return None

    try:
        y_proba = pipeline.predict_proba(X_val)[:, 1]
        fop, mpv = calibration_curve(y_val, y_proba, n_bins=n_bins)
        return CalibrationDiagnostic(
            fraction_of_positives=fop.tolist(),
            mean_predicted_value=mpv.tolist(),
            n_bins=n_bins,
        )
    except Exception:
        logger.warning("Calibration curve computation failed", exc_info=True)
        return None


def _compute_lead_time(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> int:
    """
    Compute median lead time in records across all failure windows.

    Args:
        y_true: True binary labels.
        y_pred: Predicted binary labels.

    Returns:
        int: Median lead time across all failure windows. 0 if none found.
    """
    lead_times = []
    in_window = False

    for i in range(len(y_true)):
        if y_true[i] == 1 and not in_window:
            in_window = True
            lead = 0
            j = i - 1
            while j >= 0 and y_pred[j] == 1 and y_true[j] == 0:
                lead += 1
                j -= 1
            lead_times.append(lead)
        elif y_true[i] == 0:
            in_window = False

    if not lead_times:
        logger.warning("No failure windows in validation set — lead_time=0")
        return 0

    return int(np.median(lead_times))