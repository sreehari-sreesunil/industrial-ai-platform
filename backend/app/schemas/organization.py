from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class OrganizationResponse(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }
