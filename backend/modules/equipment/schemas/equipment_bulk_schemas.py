# backend/modules/equipment/schemas/equipment_bulk_schemas.py

"""
Bulk operation schemas for equipment module.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from .equipment_schemas_improved import MaintenanceRecord


class BulkScheduleMaintenanceRequest(BaseModel):
    """Request schema for bulk scheduling maintenance"""

    equipment_ids: List[int] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of equipment IDs to schedule maintenance for",
    )

    class Config:
        schema_extra = {"example": {"equipment_ids": [1, 2, 3, 4, 5]}}


class BulkScheduleMaintenanceResponse(BaseModel):
    """Response schema for bulk scheduling maintenance"""

    message: str = Field(..., description="Success message")
    records: List[MaintenanceRecord] = Field(
        ..., description="Created maintenance records"
    )
    scheduled_count: int = Field(..., description="Number of items scheduled")
    failed_count: int = Field(0, description="Number of failed items")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Errors if any")

    class Config:
        schema_extra = {
            "example": {
                "message": "Successfully scheduled maintenance for 5 equipment items",
                "scheduled_count": 5,
                "failed_count": 0,
                "records": [],
            }
        }


class BulkOperationError(BaseModel):
    """Schema for individual bulk operation error"""

    item_id: int = Field(..., description="ID of the item that failed")
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class BulkOperationResponse(BaseModel):
    """Generic response for bulk operations"""

    message: str = Field(..., description="Summary message")
    success_count: int = Field(..., description="Number of successful operations")
    failed_count: int = Field(..., description="Number of failed operations")
    errors: Optional[List[BulkOperationError]] = Field(
        None, description="List of errors"
    )
    processed_ids: List[int] = Field(
        ..., description="IDs that were successfully processed"
    )

    class Config:
        schema_extra = {
            "example": {
                "message": "Bulk operation completed",
                "success_count": 8,
                "failed_count": 2,
                "errors": [{"item_id": 3, "error": "Equipment not found"}],
                "processed_ids": [1, 2, 4, 5, 6, 7, 8, 9],
            }
        }
