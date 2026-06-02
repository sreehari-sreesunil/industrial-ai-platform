from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_type import AssetType
from app.schemas.asset_type import AssetTypeCreate


def create_asset_type(
    db: Session,
    asset_type_data: AssetTypeCreate,
) -> AssetType:
    asset_type = AssetType(
        name=asset_type_data.name,
        description=asset_type_data.description,
    )

    db.add(asset_type)
    db.commit()
    db.refresh(asset_type)

    return asset_type


def get_asset_type_by_name(
    db: Session,
    name: str,
) -> AssetType | None:
    statement = select(AssetType).where(AssetType.name == name)

    result = db.execute(statement)

    return result.scalar_one_or_none()


def get_asset_types(
    db: Session,
) -> list[AssetType]:
    statement = select(AssetType)

    result = db.execute(statement)

    return list(result.scalars().all())
