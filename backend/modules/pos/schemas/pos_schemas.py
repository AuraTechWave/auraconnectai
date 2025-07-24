from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from ..enums.pos_enums import POSVendor


class POSIntegrationCreate(BaseModel):
    vendor: POSVendor
    credentials: Dict[str, Any]


class POSIntegrationOut(BaseModel):
    id: int
    vendor: str
    connected_on: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class POSSyncLogOut(BaseModel):
    id: int
    integration_id: int
    type: str
    status: str
    message: Optional[str]
    order_id: Optional[int]
    attempt_count: int
    synced_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class SyncRequest(BaseModel):
    order_id: Optional[int] = None
    integration_id: Optional[int] = None


class SyncResponse(BaseModel):
    success: bool
    message: str
    sync_log_id: Optional[int] = None
