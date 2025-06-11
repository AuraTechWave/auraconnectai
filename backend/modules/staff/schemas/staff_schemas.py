from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class StaffBase(BaseModel):
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

    class Config:
        orm_mode = True

class RoleBase(BaseModel):
    name: str
    permissions: List[str]

class RoleOut(RoleBase):
    id: int

    class Config:
        orm_mode = True
