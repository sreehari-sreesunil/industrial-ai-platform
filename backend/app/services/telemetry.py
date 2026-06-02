from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.asset import get_asset_by_id
from app.crud.metric_definition import (
    get_metric_definitions_by_asset_type,
)
from app.crud.telemetry import (
    create_telemetry_record,
)
from app.schemas.telemetry import (
    TelemetryIngest,
)


def validate_payload(
    payload: dict,
    metric_definitions: dict,
) -> None:
    for metric_name, value in payload.items():

        if metric_name not in metric_definitions:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown metric: {metric_name}",
            )

        metric = metric_definitions[metric_name]

        expected_type = metric.data_type

        if expected_type == "float" and not isinstance(
            value,
            (float, int),
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{metric_name} must be float",
            )

        if metric.min_value is not None and value < metric.min_value:
            raise HTTPException(
                status_code=400,
                detail=f"{metric_name} below minimum threshold",
            )

        if metric.max_value is not None and value > metric.max_value:
            raise HTTPException(
                status_code=400,
                detail=f"{metric_name} above maximum threshold",
            )


def ingest_telemetry_service(
    db: Session,
    telemetry_data: TelemetryIngest,
):
    asset = get_asset_by_id(
        db=db,
        asset_id=telemetry_data.asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found",
        )

    metric_definitions = get_metric_definitions_by_asset_type(
        db=db,
        asset_type_id=asset.asset_type_id,
    )

    metric_map = {metric.name: metric for metric in metric_definitions}

    validate_payload(
        payload=telemetry_data.payload,
        metric_definitions=metric_map,
    )

    return create_telemetry_record(
        db=db,
        telemetry_data=telemetry_data,
    )
