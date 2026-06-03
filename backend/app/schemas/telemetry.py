from datetime import datetime

from pydantic import BaseModel


class TelemetryIngest(BaseModel):
    asset_id: int

    timestamp: datetime

    payload: dict[str, float | int | bool]

class TelemetryResponse(BaseModel):
    id: int

    asset_id: int

    timestamp: datetime

    payload: dict

    model_config = {
        "from_attributes": True,
    }

class TelemetryStatsResponse(BaseModel):
    metric: str

    avg: float | None
    min: float | None
    max: float | None

    count: int