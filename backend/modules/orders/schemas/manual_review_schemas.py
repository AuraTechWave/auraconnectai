# backend/modules/orders/schemas/manual_review_schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

from ..models.manual_review_models import ReviewReason, ReviewStatus


class ManualReviewResponse(BaseModel):
    """Response model for manual review details"""

    id: int
    order_id: int
    reason: ReviewReason
    status: ReviewStatus
    error_details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    assigned_to: Optional[int] = None
    reviewed_by: Optional[int] = None
    review_notes: Optional[str] = None
    resolution_action: Optional[str] = None

    created_at: datetime
    assigned_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    priority: int = Field(..., ge=0, le=10)
    escalated: bool = False
    escalation_reason: Optional[str] = None

    class Config:
        from_attributes = True


class ManualReviewListResponse(BaseModel):
    """Response model for list of manual reviews"""

    reviews: List[ManualReviewResponse]
    total: int
    has_more: bool
    high_priority_count: int


class AssignReviewRequest(BaseModel):
    """Request model for assigning a review"""

    assignee_id: int = Field(..., description="User ID to assign the review to")


class ResolveReviewRequest(BaseModel):
    """Request model for resolving a review"""

    resolution_action: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Action taken to resolve the issue",
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Additional notes about the resolution"
    )
    mark_order_completed: bool = Field(
        False, description="Whether to mark the associated order as completed"
    )


class EscalateReviewRequest(BaseModel):
    """Request model for escalating a review"""

    escalation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for escalating the review",
    )


class ReviewStatisticsResponse(BaseModel):
    """Response model for review statistics"""

    total_reviews: int
    status_breakdown: Dict[str, int]
    reason_breakdown: Dict[str, int]
    average_resolution_time_hours: Optional[float]
    escalation_rate: float


class InventoryDeductionErrorResponse(BaseModel):
    """Response model for inventory deduction errors"""

    error: str
    message: str
    error_code: str
    details: Dict[str, Any]
    requires_manual_review: bool = False
    review_id: Optional[int] = None


class InsufficientInventoryDetail(BaseModel):
    """Detail about insufficient inventory"""

    inventory_id: int
    item_name: str
    available: float
    required: float
    shortage: float
    unit: str
    menu_item_id: Optional[int] = None
    menu_item_name: Optional[str] = None


class MissingRecipeDetail(BaseModel):
    """Detail about missing recipe"""

    menu_item_id: int
    menu_item_name: str


class InventoryErrorDetail(BaseModel):
    """Detailed error information for inventory issues"""

    error_type: str
    items_affected: List[Dict[str, Any]]
    suggested_action: str
    can_retry: bool = False
    estimated_resolution_time: Optional[str] = None
