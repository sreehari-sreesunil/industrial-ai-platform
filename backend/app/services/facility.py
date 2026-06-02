from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.facility import (
    create_facility,
    get_facilities,
)
from app.crud.organization import (
    get_organization_by_id,
)
from app.models.facility import Facility
from app.schemas.facility import FacilityCreate


def create_facility_service(
    db: Session,
    facility_data: FacilityCreate,
) -> Facility:
    organization = get_organization_by_id(
        db=db,
        organization_id=facility_data.organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return create_facility(
        db=db,
        facility_data=facility_data,
    )


def get_facilities_service(
    db: Session,
) -> list[Facility]:
    return get_facilities(db=db)
