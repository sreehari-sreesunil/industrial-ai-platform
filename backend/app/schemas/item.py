from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ItemResponse(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }
