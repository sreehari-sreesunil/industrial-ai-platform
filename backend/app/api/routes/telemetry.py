from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.schemas.telemetry import (
    TelemetryIngest,
)
from app.services.telemetry import (
    get_asset_metric_stats_service,
    get_asset_telemetry_service,
    get_latest_telemetry_service,
    ingest_telemetry_service,
)
from app.schemas.telemetry import (
    TelemetryResponse,
    TelemetryStatsResponse,
)
from app.core.security import (
    get_current_username,
)

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)


@router.post("/ingest")
def ingest_telemetry_endpoint(
    telemetry_data: TelemetryIngest,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_username),
):
    return ingest_telemetry_service(
        db=db,
        telemetry_data=telemetry_data,
    )


@router.get(
    "/assets/{asset_id}",
    response_model=list[TelemetryResponse],
)
def get_asset_telemetry_endpoint(
    asset_id: int,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_asset_telemetry_service(
        db=db,
        asset_id=asset_id,
        start_time=start_time,
        end_time=end_time,
    )


@router.get(
    "/assets/{asset_id}/latest",
    response_model=TelemetryResponse,
)
def get_latest_telemetry_endpoint(
    asset_id: int,
    db: Session = Depends(get_db),
):
    return get_latest_telemetry_service(
        db=db,
        asset_id=asset_id,
    )


@router.get(
    "/assets/{asset_id}/stats",
    response_model=TelemetryStatsResponse,
)
def get_asset_metric_stats_endpoint(
    asset_id: int,
    metric: str,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_asset_metric_stats_service(
        db=db,
        asset_id=asset_id,
        metric=metric,
        start_time=start_time,
        end_time=end_time,
    )
