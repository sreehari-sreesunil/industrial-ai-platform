from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.metric_definition import (
    MetricDefinitionCreate,
    MetricDefinitionResponse,
)
from app.services.metric_definition import (
    create_metric_definition_service,
    get_metric_definitions_service,
)
from app.core.security import (
    get_current_username,
)

router = APIRouter(
    prefix="/metric-definitions",
    tags=["metric-definitions"],
)


@router.post(
    "/",
    response_model=MetricDefinitionResponse,
)
def create_metric_definition_endpoint(
    metric: MetricDefinitionCreate,
    db: Session = Depends(get_db),
    username: str = Depends(
        get_current_username,
    ),
) -> MetricDefinitionResponse:
    return create_metric_definition_service(
        db=db,
        metric_data=metric,
    )


@router.get(
    "/",
    response_model=list[MetricDefinitionResponse],
)
def get_metric_definitions_endpoint(
    asset_type_id: int | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> list[MetricDefinitionResponse]:
    return get_metric_definitions_service(
        db=db,
        asset_type_id=asset_type_id,
    )
