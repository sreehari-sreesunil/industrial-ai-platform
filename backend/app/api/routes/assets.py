from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_username
from app.db.session import get_db
from app.schemas.asset import (
    AssetCreate,
    AssetResponse,
)
from app.services.asset import (
    create_asset_service,
    get_assets_service,
)

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
)


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    asset: AssetCreate,
    db: Session = Depends(get_db),
    _username: str = Depends(get_current_username),
) -> AssetResponse:
    return create_asset_service(
        db=db,
        asset_data=asset,
    )


@router.get(
    "/",
    response_model=list[AssetResponse],
)
def get_assets(
    db: Session = Depends(get_db),
) -> list[AssetResponse]:
    return get_assets_service(
        db=db,
    )