from pydantic import BaseModel
from datetime import datetime


class ShiftBase(BaseModel):
    staff_id: int
    start_time: datetime
    end_time: datetime
    date: datetime
    location_id: int


class ShiftOut(ShiftBase):
    id: int

    class Config:
        orm_mode = True
