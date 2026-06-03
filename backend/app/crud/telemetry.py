from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import select, cast, func, Float

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

def get_telemetry_by_asset(
    db: Session,
    asset_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[TelemetryRecord]:
    statement = select(TelemetryRecord).where(
        TelemetryRecord.asset_id == asset_id
    )

    if start_time is not None:
        statement = statement.where(
            TelemetryRecord.timestamp >= start_time
        )

    if end_time is not None:
        statement = statement.where(
            TelemetryRecord.timestamp <= end_time
        )

    statement = statement.order_by(
        TelemetryRecord.timestamp.asc()
    )

    result = db.execute(statement)

    return list(result.scalars().all())

def get_latest_telemetry_by_asset(
    db: Session,
    asset_id: int,
) -> TelemetryRecord | None:
    statement = (
        select(TelemetryRecord)
        .where(
            TelemetryRecord.asset_id == asset_id
        )
        .order_by(
            TelemetryRecord.timestamp.desc()
        )
        .limit(1)
    )

    result = db.execute(statement)

    return result.scalar_one_or_none()

def get_telemetry_metric_stats(
    db: Session,
    asset_id: int,
    metric: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    metric_value = cast(
        TelemetryRecord.payload[metric].astext,
        Float,
    )

    statement = select(
        func.avg(metric_value),
        func.min(metric_value),
        func.max(metric_value),
        func.count(),
    ).where(
        TelemetryRecord.asset_id == asset_id
    )

    if start_time is not None:
        statement = statement.where(
            TelemetryRecord.timestamp >= start_time
        )

    if end_time is not None:
        statement = statement.where(
            TelemetryRecord.timestamp <= end_time
        )

    result = db.execute(statement)

    return result.one()