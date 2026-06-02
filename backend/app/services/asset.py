from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.asset import (
    create_asset,
    get_assets,
)
from app.crud.asset_type import (
    get_asset_type_by_id,
)
from app.crud.facility import (
    get_facility_by_id,
)
from app.models.asset import Asset
from app.schemas.asset import AssetCreate


def create_asset_service(
    db: Session,
    asset_data: AssetCreate,
) -> Asset:
    facility = get_facility_by_id(
        db=db,
        facility_id=asset_data.facility_id,
    )

    if facility is None:
        raise HTTPException(
            status_code=404,
            detail="Facility not found",
        )

    asset_type = get_asset_type_by_id(
        db=db,
        asset_type_id=asset_data.asset_type_id,
    )

    if asset_type is None:
        raise HTTPException(
            status_code=404,
            detail="Asset type not found",
        )

    return create_asset(
        db=db,
        asset_data=asset_data,
    )


def get_assets_service(
    db: Session,
) -> list[Asset]:
    return get_assets(db=db)
