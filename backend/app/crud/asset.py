from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.schemas.asset import AssetCreate


def create_asset(
    db: Session,
    asset_data: AssetCreate,
) -> Asset:
    asset = Asset(
        name=asset_data.name,
        facility_id=asset_data.facility_id,
        asset_type_id=asset_data.asset_type_id,
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset


def get_assets(
    db: Session,
) -> list[Asset]:
    statement = select(Asset)

    result = db.execute(statement)

    return list(result.scalars().all())


def get_asset_by_id(
    db: Session,
    asset_id: int,
) -> Asset | None:
    statement = select(Asset).where(Asset.id == asset_id)

    result = db.execute(statement)

    return result.scalar_one_or_none()
