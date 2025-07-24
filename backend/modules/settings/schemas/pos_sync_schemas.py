from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class POSSyncSettingBase(BaseModel):
    tenant_id: Optional[int] = None
    team_id: Optional[int] = None
    enabled: bool = True
    updated_by: int

class POSSyncSettingCreate(POSSyncSettingBase):
    pass

class POSSyncSettingUpdate(BaseModel):
    enabled: bool
    updated_by: int

class POSSyncSettingOut(POSSyncSettingBase):
    id: int
    updated_at: datetime
    
    class Config:
        from_attributes = True
