from pydantic import BaseModel, Field


class FacilityCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    organization_id: int

class OrganizationNested(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }

class FacilityResponse(BaseModel):
    id: int
    name: str

    organization: OrganizationNested

    model_config = {
        "from_attributes": True,
    }
