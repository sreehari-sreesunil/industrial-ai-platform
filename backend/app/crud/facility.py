from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.schemas.facility import FacilityCreate


def create_facility(
    db: Session,
    facility_data: FacilityCreate,
) -> Facility:
    facility = Facility(
        name=facility_data.name,
        organization_id=facility_data.organization_id,
    )

    db.add(facility)
    db.commit()
    db.refresh(facility)

    return facility


def get_facilities(
    db: Session,
) -> list[Facility]:
    statement = select(Facility)

    result = db.execute(statement)

    return list(result.scalars().all())


def get_facility_by_id(
    db: Session,
    facility_id: int,
) -> Facility | None:
    statement = select(Facility).where(Facility.id == facility_id)

    result = db.execute(statement)

    return result.scalar_one_or_none()
