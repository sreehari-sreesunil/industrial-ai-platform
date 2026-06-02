from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    facility_id: int
    asset_type_id: int


class AssetResponse(BaseModel):
    id: int
    name: str
    facility_id: int
    asset_type_id: int

    model_config = {
        "from_attributes": True,
    }
