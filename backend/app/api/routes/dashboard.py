from fastapi import (
    APIRouter,
    Depends,
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.dashboard import (
    DashboardOverviewResponse,
)

from app.services.dashboard import (
    get_dashboard_overview_service,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
)
def get_dashboard_overview_endpoint(
    db: Session = Depends(get_db),
) -> DashboardOverviewResponse:
    return get_dashboard_overview_service(
        db=db,
    )
