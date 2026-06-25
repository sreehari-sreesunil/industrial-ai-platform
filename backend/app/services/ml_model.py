"""
ML model service.

Provides business logic for ML model registration, deployment,
and retirement. All operations are restricted to superusers —
customers never interact with this service directly.

This service enforces the model lifecycle state machine and the
one-deployed-model-per-slot constraint:
    asset_type + task → exactly one deployed model at a time.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.asset_type import get_asset_type_by_id
from app.crud.ml_model import (
    create_model,
    deploy_model,
    get_model,
    get_model_for_inference,
    list_models,
    retire_model,
)
from app.models.ml_model import MLModel
from app.schemas.ml_model import MLModelCreate


def register_model(
    db: Session,
    model_data: MLModelCreate,
    created_by_id: int,
) -> MLModel:
    """
    Register a new ML model in the registry.

    Validates that the target asset type exists before persisting
    the model record. Status is always set to 'trained' by CRUD —
    the model is ready for deployment review but not yet serving
    inference.

    Args:
        db: Database session.
        model_data: Validated model registration payload.
        created_by_id: ID of the superuser registering this model.

    Returns:
        MLModel: Newly registered model record.

    Raises:
        HTTPException: 404 if the asset type does not exist.
    """

    # Validate the target asset type exists before inserting
    # Catches the error early with a clean 404 rather than a FK violation
    asset_type = get_asset_type_by_id(
        db=db,
        asset_type_id=model_data.asset_type_id,
    )

    if asset_type is None:
        raise HTTPException(
            status_code=404,
            detail="Asset type not found",
        )

    # Delegate registration to the repository layer
    return create_model(
        db=db,
        model_data=model_data,
        created_by_id=created_by_id,
    )


def get_model_by_id(
    db: Session,
    model_id: int,
) -> MLModel:
    """
    Retrieve a single ML model by ID.

    Args:
        db: Database session.
        model_id: ML model identifier.

    Returns:
        MLModel: Matching model.

    Raises:
        HTTPException: 404 if the model does not exist.
    """

    model = get_model(db=db, model_id=model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    return model


def list_models_service(
    db: Session,
    asset_type_id: int | None = None,
    task: str | None = None,
    tier: str = "standard",
    status: str | None = None,
) -> list[MLModel]:
    """
    Retrieve ML models with optional filters.

    All filters are optional — omitting all returns the full registry.

    Args:
        db: Database session.
        asset_type_id: Optional filter by asset type.
        task: Optional filter by inference task.
        tier: Always "standard" — single-tier system, parameter kept
            for forward compatibility.
        status: Optional filter by lifecycle status.

    Returns:
        list[MLModel]: Matching models ordered by creation time descending.
    """

    return list_models(
        db=db,
        asset_type_id=asset_type_id,
        task=task,
        tier=tier,
        status=status,
    )


def deploy_model_service(
    db: Session,
    model_id: int,
) -> MLModel:
    """
    Promote a trained model to deployed status.

    Enforces the one-deployed-model-per-slot constraint — only one
    model may be deployed per asset_type + task  combination
    at a time. If a deployed model already occupies the slot, the
    admin must manually retire it before deploying a new one.

    This is intentional — automatic retirement removes accountability
    and creates risk of silent inference disruption for customers.

    Args:
        db: Database session.
        model_id: ML model identifier.

    Returns:
        MLModel: Deployed model.

    Raises:
        HTTPException: 404 if the model does not exist.
        HTTPException: 409 if the model is not in 'trained' status.
        HTTPException: 409 if another model is already deployed for
            this asset_type + task slot.
    """

    # Fetch the model — raise 404 if not found
    model = get_model(db=db, model_id=model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # Guard against illegal lifecycle transition
    if model.status != "trained":
        raise HTTPException(
            status_code=409,
            detail=f"Model cannot be deployed from '{model.status}' status. "
                   f"Only 'trained' models may be deployed.",
        )

    # Enforce one-deployed-model-per-slot constraint
    existing = get_model_for_inference(
        db=db,
        asset_type_id=model.asset_type_id,
        task=model.task,
        tier=model.tier,
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Model {existing.id} is already deployed for this "
                   f"asset_type + task slot. "
                   f"Retire it before deploying a new model.",
        )

    # Delegate deployment to the repository layer
    return deploy_model(db=db, model_id=model_id)


def retire_model_service(
    db: Session,
    model_id: int,
) -> MLModel:
    """
    Retire a deployed model from active inference.

    Only deployed models may be retired. A retired model remains
    in the registry as audit history but is no longer resolved
    by inference.

    Args:
        db: Database session.
        model_id: ML model identifier.

    Returns:
        MLModel: Retired model.

    Raises:
        HTTPException: 404 if the model does not exist.
        HTTPException: 409 if the model is not in 'deployed' status.
    """

    # Fetch the model — raise 404 if not found
    model = get_model(db=db, model_id=model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # Guard against retiring a model that was never deployed
    if model.status != "deployed":
        raise HTTPException(
            status_code=409,
            detail=f"Model cannot be retired from '{model.status}' status. "
                   f"Only 'deployed' models may be retired.",
        )

    # Delegate retirement to the repository layer
    return retire_model(db=db, model_id=model_id)