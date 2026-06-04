import csv
from io import StringIO

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.schemas.telemetry import (
    TelemetryIngest,
)

from app.services.telemetry import (
    ingest_telemetry_service,
)

async def parse_csv_file(
    file: UploadFile,
):
    content = await file.read()

    decoded_content = content.decode(
        "utf-8"
    )

    csv_stream = StringIO(
        decoded_content
    )

    reader = csv.DictReader(
        csv_stream
    )

    rows = list(reader)

    return rows

async def ingest_csv_telemetry(
    db: Session,
    file,
):
    rows = await parse_csv_file(
        file=file,
    )

    inserted_rows = 0

    failed_rows = []

    for index, row in enumerate(rows):
        try:
            asset_id = int(
                row["asset_id"]
            )

            timestamp = row.get(
                "timestamp"
            )

            payload = {
                key: float(value)
                for key, value in row.items()
                if key
                not in [
                    "asset_id",
                    "timestamp",
                ]
            }

            telemetry_data = (
                TelemetryIngest(
                    asset_id=asset_id,
                    timestamp=timestamp,
                    payload=payload,
                )
            )

            ingest_telemetry_service(
                db=db,
                telemetry_data=telemetry_data,
            )

            inserted_rows += 1

        except Exception as e:
            failed_rows.append(
                {
                    "row": index + 1,
                    "error": str(e),
                }
            )

    return {
        "total_rows": len(rows),
        "inserted_rows": inserted_rows,
        "failed_rows": len(
            failed_rows
        ),
        "errors": failed_rows,
    }