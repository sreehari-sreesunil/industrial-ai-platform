from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
)
from app.services.organization import (
    create_organization_service,
    get_organizations_service,
)

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
)


@router.post(
    "/",
    response_model=OrganizationResponse,
)
def create_organization_endpoint(
    organization: OrganizationCreate,
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    return create_organization_service(
        db=db,
        organization_data=organization,
    )


@router.get(
    "/",
    response_model=list[OrganizationResponse],
)
def get_organizations_endpoint(
    db: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    return get_organizations_service(db=db)
