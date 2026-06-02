from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


def create_organization(
    db: Session,
    organization_data: OrganizationCreate,
) -> Organization:
    organization = Organization(
        name=organization_data.name,
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    return organization


def get_organization_by_name(
    db: Session,
    name: str,
) -> Organization | None:
    statement = select(Organization).where(Organization.name == name)

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_organizations(
    db: Session,
) -> list[Organization]:
    statement = select(Organization)

    result = db.execute(statement)

    return list(result.scalars().all())


def get_organization_by_id(
    db: Session,
    organization_id: int,
) -> Organization | None:
    statement = select(Organization).where(Organization.id == organization_id)

    result = db.execute(statement)

    return result.scalar_one_or_none()
