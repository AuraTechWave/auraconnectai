from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class StaffBase(BaseModel, ConfigDict):
    name: str
    email: str
    phone: Optional[str] = None
    role_id: int


class StaffCreate(StaffBase):
    start_date: Optional[datetime]


class StaffOut(StaffBase):
    id: int
    status: str
    photo_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class RoleBase(BaseModel):
    name: str
    permissions: List[str]


class RoleOut(RoleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed
