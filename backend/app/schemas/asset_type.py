from pydantic import BaseModel, Field


class AssetTypeCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None


class AssetTypeResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {
        "from_attributes": True,
    }
