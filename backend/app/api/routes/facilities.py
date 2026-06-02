from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.facility import (
    FacilityCreate,
    FacilityResponse,
)
from app.services.facility import (
    create_facility_service,
    get_facilities_service,
)

router = APIRouter(
    prefix="/facilities",
    tags=["facilities"],
)


@router.post(
    "/",
    response_model=FacilityResponse,
)
def create_facility_endpoint(
    facility: FacilityCreate,
    db: Session = Depends(get_db),
) -> FacilityResponse:
    return create_facility_service(
        db=db,
        facility_data=facility,
    )


@router.get(
    "/",
    response_model=list[FacilityResponse],
)
def get_facilities_endpoint(
    db: Session = Depends(get_db),
) -> list[FacilityResponse]:
    return get_facilities_service(db=db)
