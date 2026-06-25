# app/api/routes/ml_inference.py
"""
ML inference routes.

Exposes endpoints to trigger inference on assets and
retrieve recent prediction results.

Route summary:
    POST  /inference/{asset_id}              → run all tasks
    POST  /inference/{asset_id}/{task}       → run single task
    GET   /inference/{asset_id}/latest       → latest prediction per task
    GET   /inference/{asset_id}/anomalies    → open anomaly events for asset
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.crud import ml_anomaly_event as crud_anomaly_event
from app.crud import ml_prediction as crud_prediction
from app.db.session import get_db
from app.schemas.ml_model import MLAnomalyEventResponse, MLPredictionResponse
from app.services.ml_inference import run_inference, run_inference_all_tasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["ML Inference"])

# Valid task names — used for path parameter validation
_VALID_TASKS = ("anomaly_detection", "failure_prediction")


@router.post(
    "/{asset_id}",
    response_model=dict[str, MLPredictionResponse | None],
    summary="Run inference for all tasks",
    description=(
        "Trigger anomaly_detection and failure_prediction inference "
        "for an asset using its latest telemetry record. "
        "Returns results for both tasks. A null value for a task means "
        "no deployed model exists for that asset type and task."
    ),
)
def run_all_tasks_route(
    asset_id: int = Path(description="Asset to run inference on"),
    db: Session = Depends(get_db),
) -> dict[str, MLPredictionResponse | None]:
    """
    Run inference for all tasks on a single asset.

    Args:
        asset_id: Asset identifier.
        db:       Database session.

    Returns:
        dict: Task name → MLPredictionResponse, or null if inference
              could not run for that task.
    """
    results = run_inference_all_tasks(db=db, asset_id=asset_id)

    return {
        task: (
            MLPredictionResponse.model_validate(prediction)
            if prediction is not None else None
        )
        for task, prediction in results.items()
    }


@router.post(
    "/{asset_id}/{task}",
    response_model=MLPredictionResponse | None,
    summary="Run inference for a single task",
    description=(
        "Trigger inference for a specific task on an asset. "
        "task must be one of: anomaly_detection, failure_prediction."
    ),
)
def run_single_task_route(
    asset_id: int = Path(description="Asset to run inference on"),
    task: str = Path(description="Inference task name"),
    db: Session = Depends(get_db),
) -> MLPredictionResponse | None:
    """
    Run inference for a single task.

    Args:
        asset_id: Asset identifier.
        task:     Task name — anomaly_detection or failure_prediction.
        db:       Database session.

    Returns:
        MLPredictionResponse | None: Prediction result, or null if
            inference could not run.

    Raises:
        HTTPException 422: If task name is not valid.
    """
    if task not in _VALID_TASKS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid task '{task}'. "
                f"Must be one of: {', '.join(_VALID_TASKS)}."
            ),
        )

    prediction = run_inference(db=db, asset_id=asset_id, task=task)
    return (
        MLPredictionResponse.model_validate(prediction)
        if prediction is not None else None
    )


@router.get(
    "/{asset_id}/latest",
    response_model=dict[str, MLPredictionResponse | None],
    summary="Get latest prediction per task",
    description=(
        "Returns the most recent prediction for each task for this asset. "
        "Useful for the asset dashboard to show current risk state "
        "without triggering new inference."
    ),
)
def get_latest_predictions_route(
    asset_id: int = Path(description="Asset identifier"),
    db: Session = Depends(get_db),
) -> dict[str, MLPredictionResponse | None]:
    """
    Retrieve the latest stored prediction for each task.

    Args:
        asset_id: Asset identifier.
        db:       Database session.

    Returns:
        dict: Task name → MLPredictionResponse, or null if none exists.
    """
    result = {}
    for task in _VALID_TASKS:
        prediction = crud_prediction.get_latest_prediction_by_asset(
            db=db,
            asset_id=asset_id,
            prediction_type=task,
        )
        result[task] = (
            MLPredictionResponse.model_validate(prediction)
            if prediction is not None else None
        )
    return result

@router.get(
    "/{asset_id}/anomalies",
    response_model=list[MLAnomalyEventResponse],
    summary="Get open anomaly events for asset",
    description=(
        "Returns all unresolved anomaly events for this asset, "
        "ordered oldest first. Use this to surface active alerts "
        "on the asset detail page."
    ),
)
def get_open_anomalies_route(
    asset_id: int = Path(description="Asset identifier"),
    db: Session = Depends(get_db),
) -> list[MLAnomalyEventResponse]:
    """
    Retrieve open anomaly events for an asset.

    Args:
        asset_id: Asset identifier.
        db:       Database session.

    Returns:
        list[MLAnomalyEventResponse]: Open anomaly events ordered oldest first.
    """
    events = crud_anomaly_event.get_open_anomaly_events(
        db=db,
        asset_id=asset_id,
    )
    return [MLAnomalyEventResponse.model_validate(e) for e in events] 

