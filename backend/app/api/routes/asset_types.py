from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
)
def create_asset_type_endpoint(
    asset_type: AssetTypeCreate,
    db: Session = Depends(get_db),
) -> AssetTypeResponse:
    return create_asset_type_service(
        db=db,
        asset_type_data=asset_type,
    )


@router.get(
    "/",
    response_model=list[AssetTypeResponse],
)
def get_asset_types_endpoint(
    db: Session = Depends(get_db),
) -> list[AssetTypeResponse]:
    return get_asset_types_service(db=db)
