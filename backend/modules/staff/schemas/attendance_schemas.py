from pydantic import BaseModel
from datetime import datetime


class AttendanceLogBase(BaseModel):
    staff_id: int
    check_in: datetime
    check_out: datetime
    method: str
    status: str


class AttendanceLogOut(AttendanceLogBase):
    id: int

    class Config:
        from_attributes = True
