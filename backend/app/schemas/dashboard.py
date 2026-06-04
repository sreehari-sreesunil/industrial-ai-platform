from pydantic import BaseModel

from app.schemas.asset import (
    AssetResponse,
)


class DashboardOverviewResponse(BaseModel):
    asset_count: int

    facility_count: int

    asset_type_count: int

    metric_definition_count: int

    recent_assets: list[AssetResponse]

    model_config = {
        "from_attributes": True,
    }
