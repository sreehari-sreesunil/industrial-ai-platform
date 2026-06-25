"""
ML model repository.

Provides database operations for managing the ML model lifecycle:
registration (trained), deployment, and retirement. Each row is one
trained model artifact for a given asset_type + task combination.

Model lifecycle states:
    trained   — registered, evaluated, not yet serving inference
    deployed  — actively serving inference for its asset_type + task slot
    retired   — no longer serving inference, kept for audit history

Exactly one model may be "deployed" per asset_type + task combination
at a time — enforced by the service layer (app/services/ml_model.py),
not by a database constraint.

Serialization note: feature_names, hyperparameters, and metrics are
stored as JSON text in the database. This module serializes on write
(json.dumps) and leaves deserialization to the service/schema layer
(json.loads), matching the convention in ml_anomaly_event.py.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_model import MLModel

def create_model(
    db: Session,
    name: str,
    model_type: str,
    task: str,
    asset_type_id: int,
    tier: str,
    version: int,
    artifact_path: str,
    feature_names: list[str],
    supports_sparse_features: bool,
    training_samples: int,
    hyperparameters: dict,
    metrics: dict,
    trained_at: datetime,
    created_by_id: int,
) -> MLModel:
    """
    Register a newly trained model artifact.

    Called by the training pipeline (scripts/training/registrar.py)
    after a model passes its benchmark gate. Models are created in
    "trained" status — deployment is a separate, deliberate action
    via deploy_model(), never automatic.

    feature_names, hyperparameters, and metrics are serialized to
    JSON text here — the ORM stores them as Text columns.

    Args:
        db: Database session.
        name: Human-readable model name.
        model_type: Algorithm name (e.g. "RandomForest").
        task: Inference task (e.g. "failure_prediction").
        asset_type_id: Asset type this model was trained for.
        tier: Subscription tier — always "standard" in the current
            single-tier system. Column kept for forward compatibility.
        version: Version number for this asset_type + task slot.
        artifact_path: URI-style path to the serialized pipeline.
        feature_names: Ordered list of raw sensor names used in training.
        supports_sparse_features: Whether the model handles missing
            sensor values natively.
        training_samples: Total training records across all CV folds.
        hyperparameters: Model hyperparameters extracted at training time.
        metrics: Hold-out evaluation metrics.
        trained_at: Timestamp when training completed.
        created_by_id: Superuser ID who registered this model.

    Returns:
        MLModel: Newly created model in "trained" status.
    """
    model = MLModel(
        name=name,
        model_type=model_type,
        task=task,
        asset_type_id=asset_type_id,
        tier=tier,
        version=version,
        status="trained",
        artifact_path=artifact_path,
        feature_names=json.dumps(feature_names),
        supports_sparse_features=supports_sparse_features,
        training_samples=training_samples,
        hyperparameters=json.dumps(hyperparameters),
        metrics=json.dumps(metrics),
        trained_at=trained_at,
        deployed_at=None,
        created_by_id=created_by_id,
    )

    db.add(model)
    db.commit()
    db.refresh(model)

    return model
    
def get_model(
    db: Session,
    model_id: int,
) -> MLModel | None:
    """
    Retrieve a single model by its ID.

    Used by deploy_model_service and retire_model_service to fetch
    the model before validating and applying a lifecycle transition.

    Args:
        db: Database session.
        model_id: Model identifier.

    Returns:
        MLModel | None: Matching model if found.
    """
    statement = select(MLModel).where(MLModel.id == model_id)
    result = db.execute(statement)
    return result.scalar_one_or_none()

def list_models(
    db: Session,
    asset_type_id: int | None = None,
    task: str | None = None,
    tier: str | None = None,
    status: str | None = None,
) -> list[MLModel]:
    """
    Retrieve models matching the given optional filters.

    All filters are optional and compose with AND — omitting a filter
    means "don't restrict on this field," not "match models where
    this field is NULL." Called both by the training pipeline
    (registrar._resolve_next_version, which omits tier/status to see
    every version ever trained for a slot) and by the API service
    layer (list_models_service, which typically supplies all four).

    Results are ordered newest first by creation time.

    Args:
        db: Database session.
        asset_type_id: Optional filter by asset type.
        task: Optional filter by inference task.
        tier: Optional filter by subscription tier.
        status: Optional filter by lifecycle status
            ("trained", "deployed", "retired").

    Returns:
        list[MLModel]: Matching models ordered by creation time descending.
    """

    statement = select(MLModel)

    if asset_type_id is not None:
        statement = statement.where(MLModel.asset_type_id == asset_type_id)

    if task is not None:
        statement = statement.where(MLModel.task == task)

    if tier is not None:
        statement = statement.where(MLModel.tier == tier)

    if status is not None:
        statement = statement.where(MLModel.status == status)

    statement = statement.order_by(MLModel.created_at.desc())

    result = db.execute(statement)
    return list(result.scalars().all())

def deploy_model(
    db: Session,
    model_id: int,
) -> MLModel:
    """
    Transition a model from "trained" to "deployed" status.

    Called by deploy_model_service after it has already validated
    the lifecycle transition and checked the one-deployed-model-
    per-slot constraint — this function performs the write only,
    with no validation of its own.

    Sets deployed_at to the current time.

    Args:
        db: Database session.
        model_id: Model identifier. Assumed to exist and be in
            "trained" status — callers are responsible for that
            validation.

    Returns:
        MLModel: The now-deployed model.
    """
    model = get_model(db=db, model_id=model_id)

    model.status = "deployed"
    model.deployed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(model)

    return model


def retire_model(
    db: Session,
    model_id: int,
) -> MLModel:
    """
    Transition a model from "deployed" to "retired" status.

    Called by retire_model_service after it has already validated
    the lifecycle transition — this function performs the write
    only, with no validation of its own. Retired models remain in
    the registry as permanent audit history; they are never deleted.

    Args:
        db: Database session.
        model_id: Model identifier. Assumed to exist and be in
            "deployed" status — callers are responsible for that
            validation.

    Returns:
        MLModel: The now-retired model.
    """
    model = get_model(db=db, model_id=model_id)

    model.status = "retired"

    db.commit()
    db.refresh(model)

    return model 

def get_model_for_inference(
    db: Session,
    asset_type_id: int,
    task: str,
    tier: str,
) -> MLModel | None:
    """
    Retrieve the currently deployed model for an inference slot.

    A slot is the combination of asset_type_id + task + tier. At
    most one model should ever be "deployed" for a given slot — that
    invariant is enforced by deploy_model_service's conflict check,
    not by a database constraint, so this function trusts the
    invariant rather than re-validating it.

    Used both by the inference pipeline (to find the model to run)
    and by deploy_model_service (to detect a slot conflict before
    allowing a new deployment).

    Args:
        db: Database session.
        asset_type_id: Asset type to find a model for.
        task: Inference task.
        tier: Subscription tier — always "standard" in the current
            single-tier system.

    Returns:
        MLModel | None: The deployed model for this slot, or None
            if no model is currently deployed for it.
    """
    statement = select(MLModel).where(
        MLModel.asset_type_id == asset_type_id,
        MLModel.task == task,
        MLModel.tier == tier,
        MLModel.status == "deployed",
    )
    result = db.execute(statement)
    return result.scalar_one_or_none()