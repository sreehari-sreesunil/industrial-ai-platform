"""
Training pipeline CLI entry point.

Orchestrates the full training pipeline for a single
asset_type + task combination:

    1. Parse and validate CLI arguments 
    2. Load and prepare training data
    3. Train one Pipeline per CV fold
    4. Evaluate across folds + hold-out
    5. Chech pass/fail gate - abort if benchmarks not met 
    6. Register best pipeline in database
    7. Print summary report

Usage:
poetry run python -m scripts.training.run_training \\
        --asset-type compressor \\
        --task anomaly_detection \\
        --created-by 1

    poetry run python -m scripts.training.run_training \\
        --asset-type compressor \\
        --task failure_prediction \\
        --created-by 1

    # Force registration even if benchmarks fail (use with caution):
    poetry run python -m scripts.training.run_training \\
        --asset-type compressor \\
        --task anomaly_detection \\
        --created-by 1 \\
        --force

Exit codes:
    0 — success, model registered
    1 — benchmark gate failed, model not registered
    2 — pipeline error (data loading, training, or DB failure)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from app.db.session import SessionLocal
from scripts.training.config import TASK_MODEL_MAP
from scripts.training.data_loader import load_training_data
from scripts.training.evaluator import evaluate_model
from scripts.training.registrar import register_model
from scripts.training.trainer import train_model

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid argument values
# ---------------------------------------------------------------------------

VALID_ASSET_TYPES = ("compressor", "pump", "motor")
VALID_TASKS = ("anomaly_detection", "failure_prediction")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "NexusIQ training pipeline — trains and registers one ML model "
            "for a given asset_type + task combination."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--asset-type",
        required=True,
        choices=VALID_ASSET_TYPES,
        help="Asset type to train for (e.g. compressor).",
    )
    parser.add_argument(
        "--task",
        required=True,
        choices=VALID_TASKS,
        help="Inference task (anomaly_detection or failure_prediction).",
    )
    parser.add_argument(
        "--created-by",
        required=True,
        type=int,
        help="Superuser ID registering this model (must exist in DB).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help=(
            "Register model even if benchmarks are not met. "
            "Use only for debugging — never in production."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity (default: INFO).",
    )

    return parser


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline(
    asset_type: str,
    task: str,
    created_by_id: int,
    force: bool = False,
) -> int:
    """
    Execute the full training pipeline.

    Args:
        asset_type:    Asset type name.
        task:          Inference task.
        created_by_id: Superuser ID for model registration.
        force:         Register even if benchmarks fail.

    Returns:
        int: Exit code — 0 success, 1 benchmark failure, 2 pipeline error.
    """
    start_time = time.time()

    # Resolve model type for this task
    try:
        model_type = TASK_MODEL_MAP[task]
    except KeyError:
        logger.error(
            "No model type defined for task='%s'. "
            "Check TASK_MODEL_MAP in config.py.",
            task,
        )
        return 2

    _print_header(
        asset_type=asset_type,
        task=task,
        model_type=model_type,
    )

    # -----------------------------------------------------------------------
    # Stage 1 — Data loading
    # -----------------------------------------------------------------------
    logger.info("Stage 1/4 — Loading training data")
    try:
        dataset = load_training_data(task=task)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Data loading failed: %s", e)
        return 2
    except Exception:
        logger.exception("Unexpected error during data loading")
        return 2

    logger.info(
        "Data loaded: %d folds, %.2f%% positive rate, "
        "%d hold-out records",
        dataset.n_folds,
        dataset.positive_rate * 100,
        len(dataset.y_holdout),
    )

    # -----------------------------------------------------------------------
    # Stage 2 — Training (one pipeline per CV fold)
    # -----------------------------------------------------------------------
    logger.info("Stage 2/4 — Training %s across %d folds", model_type, dataset.n_folds)
    pipelines = []
    try:
        for fold in dataset.folds:
            pipeline = train_model(fold=fold, model_type=model_type)
            pipelines.append(pipeline)
    except (ValueError, ImportError) as e:
        logger.error("Training failed: %s", e)
        return 2
    except Exception:
        logger.exception("Unexpected error during training")
        return 2

    logger.info("Training complete: %d pipelines fitted", len(pipelines))

    # -----------------------------------------------------------------------
    # Stage 3 — Evaluation
    # -----------------------------------------------------------------------
    logger.info("Stage 3/4 — Evaluating across folds + hold-out")
    try:
        eval_result = evaluate_model(
            pipelines=pipelines,
            dataset=dataset,
            model_type=model_type,
        )
    except Exception:
        logger.exception("Unexpected error during evaluation")
        return 2

    # -----------------------------------------------------------------------
    # Benchmark gate
    # -----------------------------------------------------------------------
    if not eval_result.passed:
        logger.warning(
            "Benchmark gate FAILED. Failed metrics: %s",
            ", ".join(eval_result.failed_benchmarks),
        )
        if not force:
            _print_gate_failure(eval_result.failed_benchmarks)
            return 1
        else:
            logger.warning(
                "--force flag set — registering despite benchmark failure. "
                "This model should NOT be deployed to production."
            )

    # -----------------------------------------------------------------------
    # Stage 4 — Registration
    # -----------------------------------------------------------------------
    logger.info("Stage 4/4 — Registering model in database")

    # Best pipeline is the one from the best fold
    best_pipeline = pipelines[eval_result.best_fold_index]

    # Total training samples = sum across all folds
    total_training_samples = sum(fold.n_train for fold in dataset.folds)

    db = SessionLocal()
    try:
        ml_model = register_model(
            db=db,
            pipeline=best_pipeline,
            eval_result=eval_result,
            asset_type_name=asset_type,
            task=task,
            feature_names=dataset.feature_names,
            training_samples=total_training_samples,
            created_by_id=created_by_id,
        )
    except (ValueError, RuntimeError) as e:
        logger.error("Registration failed: %s", e)
        return 2
    except Exception:
        logger.exception("Unexpected error during registration")
        return 2
    finally:
        db.close()

    elapsed = time.time() - start_time
    _print_success_summary(
        ml_model_id=ml_model.id,
        ml_model_name=ml_model.name,
        asset_type=asset_type,
        task=task,
        model_type=model_type,
        eval_result=eval_result,
        elapsed_seconds=elapsed,
    )

    return 0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_header(
    asset_type: str,
    task: str,
    model_type: str,
) -> None:
    """Print pipeline run header."""
    print(f"\n{'='*70}")
    print(f"NexusIQ Training Pipeline")
    print(f"  Started:    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Asset type: {asset_type}")
    print(f"  Task:       {task}")
    print(f"  Model type: {model_type}")
    print(f"{'='*70}\n")


def _print_gate_failure(failed_benchmarks: list[str]) -> None:
    """Print benchmark gate failure message."""
    print(f"\n{'='*70}")
    print("BENCHMARK GATE FAILED — model not registered.")
    print("Failed metrics:")
    for metric in failed_benchmarks:
        print(f"  - {metric}")
    print(
        "\nOptions:\n"
        "  1. Review data quality and label construction\n"
        "  2. Tune hyperparameters in config.py\n"
        "  3. Increase FAILURE_HORIZON_HOURS for failure_prediction\n"
        "  4. Use --force to register anyway (debugging only)\n"
    )
    print(f"{'='*70}\n")


def _print_success_summary(
    ml_model_id: int,
    ml_model_name: str,
    asset_type: str,
    task: str,
    model_type: str,
    eval_result,
    elapsed_seconds: float,
) -> None:
    """Print success summary with next steps."""
    print(f"\n{'='*70}")
    print("TRAINING PIPELINE COMPLETE ✓")
    print(f"{'='*70}")
    print(f"  Model ID:   {ml_model_id}")
    print(f"  Name:       {ml_model_name}")
    print(f"  Asset type: {asset_type}")
    print(f"  Task:       {task}")
    print(f"  Algorithm:  {model_type}")
    print(f"  Status:     trained (not yet deployed)")
    print(f"  Elapsed:    {elapsed_seconds:.1f}s")
    print(f"\nHold-out metrics:")
    for metric, value in eval_result.metrics.items():
        print(f"  {metric:<25} {value:.4f}")
    print(f"\nNext steps:")
    print(f"  1. Review evaluation report above")
    print(f"  2. Deploy via API:")
    print(f"     POST /api/v1/ml-models/{ml_model_id}/deploy")
    print(f"  3. Trigger inference:")
    print(f"     POST /api/v1/inference/{{asset_id}}")
    print(f"{'='*70}\n")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse arguments and run the training pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    # Apply log level
    logging.getLogger().setLevel(args.log_level)

    exit_code = run_pipeline(
        asset_type=args.asset_type,
        task=args.task,
        created_by_id=args.created_by,
        force=args.force,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main() 