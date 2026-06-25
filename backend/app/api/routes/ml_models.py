# app/api/routes/ml_models.py
"""
ML model lifecycle management routes.

Exposes endpoints for registering, listing, inspecting,
deploying, and retiring ML models.

NexusIQ owns all models — customers never train or deploy.
These endpoints are operator/admin facing, not customer facing.

Route summary:
    POST   /ml-models/                   → register a new trained model
    GET    /ml-models/                   → list models with optional filters
    GET    /ml-models/{model_id}         → get single model by ID
    POST   /ml-models/{model_id}/deploy  → deploy a trained model
    POST   /ml-models/{model_id}/retire  → retire a deployed model
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ml_model import MLModelCreate, MLModelResponse
from app.services.ml_model import (
    deploy_model_service,
    get_model_by_id,
    list_models_service,
    register_model,
    retire_model_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml-models", tags=["ML Models"])


@router.post(
    "/",
    response_model=MLModelResponse,
    status_code=201,
    summary="Register a trained model",
    description=(
        "Register a pre-trained model artifact with the platform. "
        "The artifact must already exist at artifact_path before calling this endpoint. "
        "Registered models start in 'trained' status and must be explicitly deployed."
    ),
)
def register_model_route(
    payload: MLModelCreate,
    db: Session = Depends(get_db),
) -> MLModelResponse:
    """
    Register a new trained model.

    Args:
        payload: Model registration data including artifact path and metadata.
        db:      Database session.

    Returns:
        MLModelResponse: Registered model with assigned ID and status.
    """
    return register_model(db=db, model_in=payload)


@router.get(
    "/",
    response_model=list[MLModelResponse],
    summary="List models",
    description=(
        "List all models with optional filters. "
        "Use status='deployed' to see active models, "
        "or filter by asset_type_id and task to inspect a specific inference slot."
    ),
)
def list_models_route(
    asset_type_id: int | None = Query(default=None, description="Filter by asset type"),
    task: str | None = Query(default=None, description="Filter by task name"),
    status: str | None = Query(default=None, description="Filter by model status"),
    db: Session = Depends(get_db),
) -> list[MLModelResponse]:
    """
    List models with optional filters.

    Args:
        asset_type_id: Optional asset type filter.
        task:          Optional task filter.
        status:        Optional status filter.
        db:            Database session.

    Returns:
        list[MLModelResponse]: Matching models.
    """
    return list_models_service(
        db=db,
        asset_type_id=asset_type_id,
        task=task,
        status=status,
    )


@router.get(
    "/{model_id}",
    response_model=MLModelResponse,
    summary="Get model by ID",
)
def get_model_route(
    model_id: int,
    db: Session = Depends(get_db),
) -> MLModelResponse:
    """
    Retrieve a single model by ID.

    Args:
        model_id: Model identifier.
        db:       Database session.

    Returns:
        MLModelResponse: Model details.

    Raises:
        HTTPException 404: If model not found.
    """
    return get_model_by_id(db=db, model_id=model_id)


@router.post(
    "/{model_id}/deploy",
    response_model=MLModelResponse,
    summary="Deploy a trained model",
    description=(
        "Deploy a model that is currently in 'trained' status. "
        "Only one model can be deployed per asset_type + task slot. "
        "Retire the current deployed model before deploying a new one."
    ),
)
def deploy_model_route(
    model_id: int,
    db: Session = Depends(get_db),
) -> MLModelResponse:
    """
    Deploy a trained model.

    Args:
        model_id: Model to deploy.
        db:       Database session.

    Returns:
        MLModelResponse: Deployed model.

    Raises:
        HTTPException 404: If model not found.
        HTTPException 409: If model is not in 'trained' status,
                           or if the inference slot is already occupied.
    """
    return deploy_model_service(db=db, model_id=model_id)


@router.post(
    "/{model_id}/retire",
    response_model=MLModelResponse,
    summary="Retire a deployed model",
    description=(
        "Retire a model that is currently in 'deployed' status. "
        "Retiring clears the inference slot so a new model can be deployed. "
        "Retired models are kept for audit — they are never deleted."
    ),
)
def retire_model_route(
    model_id: int,
    db: Session = Depends(get_db),
) -> MLModelResponse:
    """
    Retire a deployed model.

    Args:
        model_id: Model to retire.
        db:       Database session.

    Returns:
        MLModelResponse: Retired model.

    Raises:
        HTTPException 404: If model not found.
        HTTPException 409: If model is not in 'deployed' status.
    """
    return retire_model_service(db=db, model_id=model_id)