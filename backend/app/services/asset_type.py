from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.asset_type import (
    create_asset_type,
    get_asset_type_by_name,
    get_asset_types,
)
from app.models.asset_type import AssetType
from app.schemas.asset_type import AssetTypeCreate


def create_asset_type_service(
    db: Session,
    asset_type_data: AssetTypeCreate,
) -> AssetType:
    existing_asset_type = get_asset_type_by_name(
        db=db,
        name=asset_type_data.name,
    )

    if existing_asset_type:
        raise HTTPException(
            status_code=400,
            detail="Asset type already exists",
        )

    return create_asset_type(
        db=db,
        asset_type_data=asset_type_data,
    )


def get_asset_types_service(
    db: Session,
) -> list[AssetType]:
    return get_asset_types(db=db)
