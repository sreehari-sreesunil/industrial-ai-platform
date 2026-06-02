from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.telemetry import (
    TelemetryIngest,
)
from app.services.telemetry import (
    ingest_telemetry_service,
)

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)


@router.post("/ingest")
def ingest_telemetry_endpoint(
    telemetry: TelemetryIngest,
    db: Session = Depends(get_db),
):
    return ingest_telemetry_service(
        db=db,
        telemetry_data=telemetry,
    )
