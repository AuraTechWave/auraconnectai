# backend/modules/orders/routers/pos_sync/schemas.py

"""
Pydantic schemas for POS sync endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class POSSyncRequest(BaseModel):
    """Request model for POS sync endpoint"""

    terminal_id: Optional[str] = Field(None, description="POS terminal identifier")
    order_ids: Optional[List[int]] = Field(
        None, description="Specific order IDs to sync"
    )
    sync_all_pending: bool = Field(
        True, description="Sync all pending orders if order_ids not provided"
    )
    include_recent: bool = Field(
        False, description="Include recently synced orders (last 24 hours)"
    )


class POSSyncResponse(BaseModel):
    """Response model for POS sync endpoint"""

    status: str  # initiated, completed, failed
    terminal_id: Optional[str]
    sync_batch_id: Optional[str]
    orders_queued: int
    orders_synced: int = 0
    orders_failed: int = 0
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None
