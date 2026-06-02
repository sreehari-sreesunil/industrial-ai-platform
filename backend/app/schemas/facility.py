from pydantic import BaseModel, Field


class FacilityCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    organization_id: int


class FacilityResponse(BaseModel):
    id: int
    name: str
    organization_id: int

    model_config = {
        "from_attributes": True,
    }
