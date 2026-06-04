from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metric_definition import (
    MetricDefinition,
)
from app.schemas.metric_definition import (
    MetricDefinitionCreate,
)


def create_metric_definition(
    db: Session,
    metric_data: MetricDefinitionCreate,
) -> MetricDefinition:
    metric = MetricDefinition(
        name=metric_data.name,
        unit=metric_data.unit,
        data_type=metric_data.data_type,
        min_value=metric_data.min_value,
        max_value=metric_data.max_value,
        asset_type_id=metric_data.asset_type_id,
    )

    db.add(metric)
    db.commit()
    db.refresh(metric)

    return metric


def get_metric_definitions(
    db: Session,
    asset_type_id: int | None = None,
) -> list[MetricDefinition]:

    statement = select(
        MetricDefinition
    )

    if asset_type_id is not None:
        statement = statement.where(
            MetricDefinition.asset_type_id
            == asset_type_id
        )

    result = db.execute(statement)

    return list(result.scalars().all())


def get_metric_definitions_by_asset_type(
    db: Session,
    asset_type_id: int,
) -> list[MetricDefinition]:
    statement = select(MetricDefinition).where(
        MetricDefinition.asset_type_id == asset_type_id
    )

    result = db.execute(statement)

    return list(result.scalars().all())
