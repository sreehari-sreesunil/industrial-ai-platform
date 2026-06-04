from pydantic import BaseModel, Field


class MetricDefinitionCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    unit: str
    data_type: str

    min_value: float | None = None
    max_value: float | None = None

    asset_type_id: int


class AssetTypeNested(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class MetricDefinitionResponse(BaseModel):
    id: int
    name: str
    unit: str
    data_type: str

    min_value: float | None
    max_value: float | None

    asset_type: AssetTypeNested

    model_config = {
        "from_attributes": True,
    }
