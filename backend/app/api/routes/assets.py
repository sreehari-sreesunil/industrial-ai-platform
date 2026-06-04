from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.asset import (
    AssetCreate,
    AssetResponse,
)
from app.services.asset import (
    create_asset_service,
    get_assets_service,
)
from app.core.security import (
    get_current_username,
)

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
)


@router.post(
    "/",
    response_model=AssetResponse,
)
def create_asset_endpoint(
    asset: AssetCreate,
    db: Session = Depends(get_db),
    username: str = Depends(
        get_current_username,
    ),
) -> AssetResponse:
    return create_asset_service(
        db=db,
        asset_data=asset,
    )


@router.get(
    "/",
    response_model=list[AssetResponse],
)
def get_assets_endpoint(
    db: Session = Depends(get_db),
) -> list[AssetResponse]:
    return get_assets_service(db=db)
