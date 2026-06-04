from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    facility_id: int
    asset_type_id: int

class FacilityNested(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class AssetTypeNested(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }
class AssetResponse(BaseModel):
    id: int
    name: str

    facility: FacilityNested

    asset_type: AssetTypeNested

    model_config = {
        "from_attributes": True,
    }
