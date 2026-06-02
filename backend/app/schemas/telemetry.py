from datetime import datetime

from pydantic import BaseModel


class TelemetryIngest(BaseModel):
    asset_id: int

    timestamp: datetime

    payload: dict[str, float | int | bool]
