# backend/modules/kds/schemas/kds_bulk_schemas.py

"""
Bulk operation schemas for KDS module.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.kds_models import StationStatus


class BulkStationStatusUpdateRequest(BaseModel):
    """Request schema for bulk station status update"""

    station_ids: List[int] = Field(
        ..., min_items=1, max_items=50, description="List of station IDs to update"
    )
    status: StationStatus = Field(..., description="New status to apply")

    class Config:
        schema_extra = {"example": {"station_ids": [1, 2, 3], "status": "ACTIVE"}}


class BulkStationStatusUpdateResponse(BaseModel):
    """Response schema for bulk station status update"""

    message: str = Field(..., description="Summary message")
    updated_count: int = Field(..., description="Number of stations updated")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Errors if any")
    updated_stations: List[int] = Field(..., description="IDs of updated stations")

    class Config:
        schema_extra = {
            "example": {
                "message": "Updated 3 stations",
                "updated_count": 3,
                "errors": None,
                "updated_stations": [1, 2, 3],
            }
        }


class OrderRoutingResponse(BaseModel):
    """Response schema for order routing"""

    message: str = Field(..., description="Routing summary")
    items_routed: int = Field(..., description="Number of items routed")
    stations_affected: int = Field(..., description="Number of stations affected")
    routing_summary: Dict[str, int] = Field(
        ..., description="Summary of items routed to each station"
    )

    class Config:
        schema_extra = {
            "example": {
                "message": "Order routed successfully",
                "items_routed": 5,
                "stations_affected": 2,
                "routing_summary": {"1": 3, "2": 2},
            }
        }
