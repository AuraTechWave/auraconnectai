from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ShiftBase(BaseModel):
    staff_id: int
    start_time: datetime
    end_time: datetime
    date: datetime
    location_id: int


class ShiftOut(ShiftBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed
