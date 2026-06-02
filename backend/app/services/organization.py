from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.organization import (
    create_organization,
    get_organization_by_name,
    get_organizations,
)
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


def create_organization_service(
    db: Session,
    organization_data: OrganizationCreate,
) -> Organization:
    existing_organization = get_organization_by_name(
        db=db,
        name=organization_data.name,
    )

    if existing_organization:
        raise HTTPException(
            status_code=400,
            detail="Organization already exists",
        )

    return create_organization(
        db=db,
        organization_data=organization_data,
    )


def get_organizations_service(
    db: Session,
) -> list[Organization]:
    return get_organizations(db=db)
