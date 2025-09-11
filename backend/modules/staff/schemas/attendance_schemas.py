from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AttendanceLogBase(BaseModel):
    staff_id: int
    check_in: datetime
    check_out: datetime
    method: str
    status: str


class AttendanceLogOut(AttendanceLogBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed
