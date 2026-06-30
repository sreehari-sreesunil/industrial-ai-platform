"""
Model registrar.

Serializes the best fitted Pipeline to disk and registers it
in the NexusIQ database via the CRUD layer.

Responsibilities:
    1. Resolve the next version number for this asset_type + task slot
    2. Serialize the Pipeline artifact with joblib
    3. Register model metadata in the database
    4. Return the registered MLModel ORM object

Design decisions:
    - Registrar talks directly to the CRUD layer, never to the HTTP API.
      Scripts are internal tools — they share the data layer with the
      application, not the HTTP interface.
    - Version number is resolved from the database, not from config.
      The DB is the source of truth for what version exists — hardcoding
      version numbers causes conflicts when multiple asset types are trained.
    - Artifact is written to disk BEFORE the DB record is created.
      If the DB write fails, the artifact exists and can be re-registered
      without retraining. If the artifact write fails, no DB record is
      created. Artifact-first ordering prevents orphaned DB records.
    - Registrar does NOT deploy the model — deployment is a deliberate
      human action via the API. Training → registration is automatic.
      Registration → deployment is intentional.

PRODUCTION NOTE:
    artifact_path uses local:// URI scheme.
    Replace _write_artifact() S3 upload logic when moving to
    multi-worker deployment. DB record format stays identical.
    See app/ml/model_loader.py for the corresponding resolution logic.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline
from sqlalchemy.orm import Session

from app.crud import asset_type as crud_asset_type
from app.crud import ml_model as crud_model
from app.models.ml_model import MLModel
from scripts.training.config import ARTIFACT_CONFIG, TASK_MODEL_MAP
from scripts.training.evaluator import EvaluationResult

logger = logging.getLogger(__name__)


def register_model(
    db: Session,
    pipeline: Pipeline,
    eval_result: EvaluationResult,
    asset_type_name: str,
    task: str,
    feature_names: list[str],
    training_samples: int,
    created_by_id: int,
) -> MLModel:
    """
    Serialize the pipeline artifact and register in the database.

    Full sequence:
        1. Validate inputs — asset_type exists, task known
        2. Resolve next version number from DB
        3. Build artifact path
        4. Write artifact to disk
        5. Create DB record via CRUD
        6. Return registered model

    Args:
        db:               Database session.
        pipeline:         Best fitted Pipeline from evaluator.
        eval_result:      EvaluationResult containing metrics.
        asset_type_name:  Asset type name (e.g. "compressor").
        task:             Inference task (e.g. "anomaly_detection").
        feature_names:    Raw sensor names the pipeline was trained on.
        training_samples: Total training records across all CV folds.
        created_by_id:    Superuser ID registering this model.

    Returns:
        MLModel: Registered ORM object with assigned ID and status="trained".

    Raises:
        ValueError: If asset_type not found, or task unknown.
        RuntimeError: If artifact write fails.
    """
    # Step 1 — validate inputs
    asset_type = crud_asset_type.get_asset_type_by_name(
        db=db,
        name=asset_type_name,
    )
    if asset_type is None:
        raise ValueError(
            f"Asset type '{asset_type_name}' not found in database. "
            f"Create it via the API before registering a model."
        )

    try:
        expected_model_type = TASK_MODEL_MAP[task]
    except KeyError:
        raise ValueError(
            f"No model type defined for task='{task}'. "
            f"Check TASK_MODEL_MAP in config.py."
        )

    # Infer the sklearn class name from the pipeline's final step, but
    # ALWAYS use TASK_MODEL_MAP's canonical name for storage — the raw
    # sklearn class name (e.g. "RandomForestClassifier") is an
    # implementation detail that doesn't match this system's naming
    # convention used everywhere else (TASK_MODEL_MAP, trainer.py,
    # scoring.py's _DECISION_FUNCTION_MODELS/_PROBA_MODELS). Storing
    # the raw class name instead of the canonical one previously broke
    # inference: _score_with_model() and normalize_score() do exact
    # string matches against "RandomForest"/"IsolationForest" with no
    # fuzzy matching, so a stored "RandomForestClassifier" would raise
    # ValueError("Unknown model_type") on every real inference call.
    sklearn_class_name = type(pipeline.named_steps["model"]).__name__
    if sklearn_class_name != expected_model_type:
        logger.warning(
            "Pipeline sklearn class '%s' does not match TASK_MODEL_MAP "
            "canonical name '%s' for task=%s. Storing canonical name "
            "'%s', not the raw sklearn class name.",
            sklearn_class_name,
            expected_model_type,
            task,
            expected_model_type,
        )
    model_type = expected_model_type

    # Step 2 — resolve next version number
    version = _resolve_next_version(
        db=db,
        asset_type_id=asset_type.id,
        task=task,
    )

    # Step 3 — build artifact path
    artifact_path = ARTIFACT_CONFIG.build_artifact_path(
        asset_type=asset_type_name,
        model_type=model_type,
        task=task,
        version=version,
    )

    # Step 4 — write artifact (before DB record — see module docstring)
    _write_artifact(
        pipeline=pipeline,
        artifact_path=artifact_path,
    )

    # Step 5 — create DB record
    hyperparameters = _extract_hyperparameters(pipeline)

    ml_model = crud_model.create_model(
        db=db,
        name=_build_model_name(
            asset_type_name=asset_type_name,
            model_type=model_type,
            task=task,
            version=version,
        ),
        model_type=model_type,
        task=task,
        asset_type_id=asset_type.id,
        tier="standard",
        version=version,
        artifact_path=artifact_path,
        feature_names=feature_names,
        supports_sparse_features=False,  # Pipeline uses raw sensors only
        training_samples=training_samples,
        hyperparameters=hyperparameters,
        metrics=eval_result.metrics,
        trained_at=datetime.now(timezone.utc),
        created_by_id=created_by_id,
    )

    logger.info(
        "Model registered: id=%d name='%s' version=%d "
        "asset_type='%s' task=%s status=%s",
        ml_model.id,
        ml_model.name,
        ml_model.version,
        asset_type_name,
        task,
        ml_model.status,
    )

    return ml_model


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_next_version(
    db: Session,
    asset_type_id: int,
    task: str,
) -> int:
    """
    Resolve the next version number for this inference slot.

    Queries all models (any status) for this asset_type + task
    and returns max_version + 1. Returns 1 if no models exist yet.

    Version numbers are global per slot — they never reset even after
    retirement. This preserves a complete audit trail of all versions
    ever trained for this slot.

    Args:
        db:            Database session.
        asset_type_id: Asset type ID.
        task:          Inference task.

    Returns:
        int: Next version number (1-based).
    """
    existing_models = crud_model.list_models(
        db=db,
        asset_type_id=asset_type_id,
        task=task,
    )

    if not existing_models:
        return 1

    max_version = max(m.version for m in existing_models)
    next_version = max_version + 1

    logger.debug(
        "Version resolution: asset_type_id=%d task=%s "
        "existing_versions=%s → next=%d",
        asset_type_id,
        task,
        [m.version for m in existing_models],
        next_version,
    )

    return next_version


def _write_artifact(
    pipeline: Pipeline,
    artifact_path: str,
) -> None:
    """
    Serialize the Pipeline to disk using joblib.

    Resolves the local filesystem path from the URI-style artifact_path.
    Creates the output directory if it does not exist.

    PRODUCTION NOTE: Replace this function body with S3 upload logic
    when moving to multi-worker deployment:
        import boto3
        s3 = boto3.client("s3")
        with tempfile.NamedTemporaryFile() as tmp:
            joblib.dump(pipeline, tmp.name, compress=ARTIFACT_CONFIG.compress_level)
            s3.upload_file(tmp.name, bucket, key)
    The artifact_path URI scheme changes from local:// to s3://.
    model_loader.py resolves the URI — update there too.

    Args:
        pipeline:      Fitted sklearn Pipeline to serialize.
        artifact_path: URI-style path (e.g. local://artifacts/model_v1.joblib).

    Raises:
        RuntimeError: If artifact write fails.
    """
    # Strip URI scheme to get filesystem path
    local_path = _resolve_local_path(artifact_path)

    # Create directory if needed
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        joblib.dump(
            pipeline,
            local_path,
            compress=ARTIFACT_CONFIG.compress_level,
        )
        file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
        logger.info(
            "Artifact written: %s (%.2f MB)",
            local_path,
            file_size_mb,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to write artifact to {local_path}: {e}"
        ) from e


def _resolve_local_path(artifact_path: str) -> Path:
    """
    Resolve a URI-style artifact path to a filesystem Path.

    Strips the local:// scheme prefix and resolves relative to
    the backend root directory.

    Args:
        artifact_path: URI-style path (e.g. local://artifacts/model.joblib).

    Returns:
        Path: Resolved filesystem path.

    Raises:
        ValueError: If URI scheme is not local://.
    """
    if not artifact_path.startswith("local://"):
        raise ValueError(
            f"Unsupported URI scheme in artifact_path: '{artifact_path}'. "
            f"Only local:// is supported. "
            f"Add S3 support in _write_artifact() for production."
        )

    relative_path = artifact_path.removeprefix("local://")

    # Resolve relative to backend root (two levels up from scripts/training/)
    backend_root = Path(__file__).parent.parent.parent
    return backend_root / relative_path


def _extract_hyperparameters(pipeline: Pipeline) -> dict[str, Any]:
    """
    Extract hyperparameters from the pipeline's model step.

    Reads from model.get_params() and filters out non-serializable
    values. Stored in the DB as training provenance metadata —
    allows exact reproduction of any registered model.

    Args:
        pipeline: Fitted Pipeline with named step "model".

    Returns:
        dict[str, Any]: JSON-serializable hyperparameter dict.
    """
    model = pipeline.named_steps["model"]
    raw_params = model.get_params()

    # Filter to JSON-serializable types only
    serializable = {}
    for key, value in raw_params.items():
        if isinstance(value, (int, float, str, bool, type(None))):
            serializable[key] = value
        else:
            # Convert non-serializable (e.g. numpy types) to string
            serializable[key] = str(value)

    return serializable


def _build_model_name(
    asset_type_name: str,
    model_type: str,
    task: str,
    version: int,
) -> str:
    """
    Build a human-readable model name for the DB record.

    Format: {AssetType} {ModelType} {Task} v{version}
    Example: Compressor IsolationForest anomaly_detection v3

    Args:
        asset_type_name: Asset type (e.g. "compressor").
        model_type:      Algorithm (e.g. "IsolationForest").
        task:            Task (e.g. "anomaly_detection").
        version:         Version integer.

    Returns:
        str: Human-readable model name.
    """
    return (
        f"{asset_type_name.capitalize()} "
        f"{model_type} "
        f"{task} "
        f"v{version}"
    )