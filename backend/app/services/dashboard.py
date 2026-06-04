from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.asset_type import (
    AssetType,
)
from app.models.facility import Facility
from app.models.metric_definition import (
    MetricDefinition,
)

from app.schemas.dashboard import (
    DashboardOverviewResponse,
)


def get_dashboard_overview_service(
    db: Session,
) -> DashboardOverviewResponse:
    asset_count = db.scalar(select(func.count(Asset.id)))

    facility_count = db.scalar(select(func.count(Facility.id)))

    asset_type_count = db.scalar(select(func.count(AssetType.id)))

    metric_definition_count = db.scalar(select(func.count(MetricDefinition.id)))

    recent_assets_statement = select(Asset).order_by(Asset.id.desc()).limit(5)

    recent_assets_result = db.execute(recent_assets_statement)

    recent_assets = list(recent_assets_result.scalars().all())

    return DashboardOverviewResponse(
        asset_count=asset_count or 0,
        facility_count=facility_count or 0,
        asset_type_count=asset_type_count or 0,
        metric_definition_count=metric_definition_count or 0,
        recent_assets=recent_assets,
    )
