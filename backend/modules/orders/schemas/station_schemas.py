from pydantic import BaseModel
from typing import Optional


class StationBase(BaseModel, ConfigDict):
    name: str
    staff_id: Optional[int] = None


class StationCreate(StationBase):
    pass


class StationOut(StationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed
