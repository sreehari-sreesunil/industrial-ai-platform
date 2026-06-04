from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_username
from app.db.session import get_db
from app.schemas.asset_type import (
    AssetTypeCreate,
    AssetTypeResponse,
)
from app.services.asset_type import (
    create_asset_type_service,
    get_asset_types_service,
)

router = APIRouter(
    prefix="/asset-types",
    tags=["asset-types"],
)


@router.post(
    "/",
    response_model=AssetTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_type(
    asset_type: AssetTypeCreate,
    db: Session = Depends(get_db),
    _username: str = Depends(get_current_username),
) -> AssetTypeResponse:
    return create_asset_type_service(
        db=db,
        asset_type_data=asset_type,
    )


@router.get(
    "/",
    response_model=list[AssetTypeResponse],
)
def get_asset_types(
    db: Session = Depends(get_db),
) -> list[AssetTypeResponse]:
    return get_asset_types_service(
        db=db,
    )