from sqlalchemy.orm import Session

from app.crud.metric_definition import (
    create_metric_definition,
    get_metric_definitions,
)
from app.models.metric_definition import (
    MetricDefinition,
)
from app.schemas.metric_definition import (
    MetricDefinitionCreate,
)


def create_metric_definition_service(
    db: Session,
    metric_data: MetricDefinitionCreate,
) -> MetricDefinition:
    return create_metric_definition(
        db=db,
        metric_data=metric_data,
    )


def get_metric_definitions_service(
    db: Session,
    asset_type_id: int | None = None,
) -> list[MetricDefinition]:
    return get_metric_definitions(
        db=db,
        asset_type_id=asset_type_id,
    )
