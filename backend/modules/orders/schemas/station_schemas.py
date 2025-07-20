from pydantic import BaseModel
from typing import Optional


class StationBase(BaseModel):
    name: str
    staff_id: Optional[int] = None


class StationCreate(StationBase):
    pass


class StationOut(StationBase):
    id: int

    class Config:
        orm_mode = True
