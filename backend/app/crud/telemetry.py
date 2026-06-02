from sqlalchemy.orm import Session

from app.models.telemetry_record import (
    TelemetryRecord,
)
from app.schemas.telemetry import (
    TelemetryIngest,
)


def create_telemetry_record(
    db: Session,
    telemetry_data: TelemetryIngest,
) -> TelemetryRecord:
    record = TelemetryRecord(
        asset_id=telemetry_data.asset_id,
        timestamp=telemetry_data.timestamp,
        payload=telemetry_data.payload,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
