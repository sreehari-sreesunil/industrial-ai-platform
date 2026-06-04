from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.services.csv_ingest import (
    ingest_csv_telemetry,
)
from app.core.security import (
    get_current_username,
)

router = APIRouter(
    prefix="/csv",
    tags=["CSV"],
)


@router.post(
    "/telemetry-upload",
)
async def upload_telemetry_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(
        get_current_username,
    ),
):
    result = (
        await ingest_csv_telemetry(
            db=db,
            file=file,
        )
    )

    return result