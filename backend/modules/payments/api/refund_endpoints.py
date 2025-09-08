# backend/modules/payments/api/refund_endpoints.py

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator

from core.database import get_db
from core.auth import get_current_user, require_permission, User
from ..services.refund_service import refund_service
from ..models.refund_models import (
    RefundReason,
    RefundCategory,
    RefundApprovalStatus,
    RefundRequest,
    RefundPolicy,
)
from ..models.payment_models import Refund, RefundStatus

router = APIRouter(prefix="/refunds", tags=["Refunds"])


# Request/Response Models


class RefundItemRequest(BaseModel):
    item_id: int
    quantity: int
    amount: Decimal
    reason: Optional[str] = None


class CreateRefundRequest(BaseModel):
    order_id: int
    payment_id: int
    requested_amount: Decimal
    reason_code: RefundReason
    reason_details: Optional[str] = None
    refund_items: Optional[List[RefundItemRequest]] = None
    evidence_urls: Optional[List[str]] = None
    priority: str = Field("normal", pattern="^(urgent|high|normal|low)$")

    @field_validator("requested_amount", mode="after")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Requested amount must be positive")
        return v


class RefundApprovalRequest(BaseModel):
    notes: Optional[str] = None
    process_immediately: bool = True


class RefundRejectionRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


class RefundPolicyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    auto_approve_enabled: bool = False
    auto_approve_threshold: Decimal = Decimal("50.00")
    refund_window_hours: int = 168
    allow_partial_refunds: bool = True
    require_reason: bool = True
    notify_customer: bool = True
    notify_manager: bool = True


class RefundRequestResponse(BaseModel):
    id: int
    request_number: str
    order_id: int
    payment_id: int
    requested_amount: float
    reason_code: RefundReason
    category: RefundCategory
    reason_details: Optional[str]
    approval_status: RefundApprovalStatus
    customer_name: str
    customer_email: str
    created_at: datetime
    approved_at: Optional[datetime]
    processed_at: Optional[datetime]
    refund_id: Optional[int]

    class Config:
        orm_mode = True


class RefundResponse(BaseModel):
    id: int
    refund_id: str
    payment_id: int
    amount: float
    currency: str
    status: RefundStatus
    reason: Optional[str]
    processed_at: Optional[datetime]
    gateway_refund_id: Optional[str]

    class Config:
        orm_mode = True


class RefundStatisticsResponse(BaseModel):
    total_requests: int
    total_amount: float
    avg_amount: float
    by_category: Dict[str, Dict[str, Any]]
    by_status: Dict[str, Dict[str, Any]]
    by_reason: Dict[str, Dict[str, Any]]


class BulkRefundRequest(BaseModel):
    refund_requests: List[CreateRefundRequest]
    batch_notes: Optional[str] = None
    auto_approve: bool = False

    @field_validator("refund_requests", mode="after")
    def validate_batch_size(cls, v):
        if len(v) == 0:
            raise ValueError("At least one refund request is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 refund requests per batch")
        return v


class BulkRefundResponse(BaseModel):
    batch_id: str
    total_requests: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, str]] = []


class BulkApprovalRequest(BaseModel):
    request_ids: List[int]
    notes: Optional[str] = None
    process_immediately: bool = False

    @field_validator("request_ids", mode="after")
    def validate_request_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one request ID is required")
        if len(v) > 100:
            raise ValueError("Maximum 100 requests per batch approval")
        return list(set(v))  # Remove duplicates


class BulkProcessingRequest(BaseModel):
    request_ids: List[int]

    @field_validator("request_ids", mode="after")
    def validate_request_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one request ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 requests per batch processing")
        return list(set(v))  # Remove duplicates


# Endpoints


@router.post("/request", response_model=RefundRequestResponse)
@require_permission("refunds.create")
async def create_refund_request(
    request: CreateRefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new refund request"""

    try:
        # Create customer info from current user
        customer_info = {
            "user_id": current_user.id,
            "name": current_user.full_name,
            "email": current_user.email,
            "phone": getattr(current_user, "phone", None),
        }

        refund_request = await refund_service.create_refund_request(
            db=db,
            order_id=request.order_id,
            payment_id=request.payment_id,
            requested_amount=request.requested_amount,
            reason_code=request.reason_code,
            reason_details=request.reason_details,
            customer_info=customer_info,
            refund_items=(
                [item.dict() for item in request.refund_items]
                if request.refund_items
                else None
            ),
            evidence_urls=request.evidence_urls,
            priority=request.priority,
        )

        return RefundRequestResponse.from_orm(refund_request)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create refund request: {str(e)}"
        )


@router.get("/requests", response_model=Dict[str, Any])
@require_permission("refunds.view")
async def list_refund_requests(
    status: Optional[RefundApprovalStatus] = None,
    category: Optional[RefundCategory] = None,
    customer_id: Optional[int] = None,
    order_id: Optional[int] = None,
    priority: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List refund requests with filtering"""

    # Build filters
    filters = {}

    if status:
        filters["status"] = status
    if category:
        filters["category"] = category
    if priority:
        filters["priority"] = priority
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Apply user-based filtering
    if not current_user.is_staff:
        # Customers can only see their own requests
        if hasattr(current_user, "customer_id"):
            filters["customer_id"] = current_user.customer_id
        else:
            filters["customer_id"] = -1  # No results
    else:
        # Staff can filter by customer/order
        if customer_id:
            filters["customer_id"] = customer_id
        if order_id:
            filters["order_id"] = order_id

    requests, total = await refund_service.get_refund_requests(
        db, filters, offset, limit
    )

    return {
        "items": [RefundRequestResponse.from_orm(r) for r in requests],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/requests/{request_id}", response_model=RefundRequestResponse)
@require_permission("refunds.view")
async def get_refund_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific refund request"""

    request = await db.get(RefundRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Refund request not found")

    # Check permissions
    if not current_user.is_staff:
        if (
            hasattr(current_user, "customer_id")
            and request.customer_id != current_user.customer_id
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    return RefundRequestResponse.from_orm(request)


@router.post("/requests/{request_id}/approve")
@require_permission("refunds.approve")
async def approve_refund_request(
    request_id: int,
    approval: RefundApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a refund request (staff only)"""

    try:
        request = await refund_service.approve_refund_request(
            db=db,
            request_id=request_id,
            approver_id=current_user.id,
            notes=approval.notes,
            process_immediately=approval.process_immediately,
        )

        return {
            "success": True,
            "request_id": request.id,
            "approval_status": request.approval_status,
            "message": "Refund request approved successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to approve refund: {str(e)}"
        )


@router.post("/requests/{request_id}/reject")
@require_permission("refunds.approve")
async def reject_refund_request(
    request_id: int,
    rejection: RefundRejectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a refund request (staff only)"""

    try:
        request = await refund_service.reject_refund_request(
            db=db,
            request_id=request_id,
            rejector_id=current_user.id,
            reason=rejection.reason,
        )

        return {
            "success": True,
            "request_id": request.id,
            "approval_status": request.approval_status,
            "message": "Refund request rejected",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to reject refund: {str(e)}"
        )


@router.post("/requests/{request_id}/process")
@require_permission("refunds.process")
async def process_refund_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually process an approved refund request"""

    try:
        request, refund = await refund_service.process_refund_request(db, request_id)

        return {
            "success": True,
            "request_id": request.id,
            "refund": RefundResponse.from_orm(refund),
            "message": "Refund processed successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process refund: {str(e)}"
        )


@router.get("/statistics", response_model=RefundStatisticsResponse)
@require_permission("refunds.view_statistics")
async def get_refund_statistics(
    restaurant_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get refund statistics for reporting"""

    stats = await refund_service.get_refund_statistics(
        db, restaurant_id=restaurant_id, date_from=date_from, date_to=date_to
    )

    return RefundStatisticsResponse(
        total_requests=stats["total_requests"],
        total_amount=float(stats["total_amount"]),
        avg_amount=float(stats["avg_amount"]),
        by_category=stats["by_category"],
        by_status=stats["by_status"],
        by_reason=stats["by_reason"],
    )


@router.get("/reasons")
async def get_refund_reasons():
    """Get available refund reasons and their categories"""

    reasons = []
    for reason in RefundReason:
        from ..models.refund_models import get_refund_category

        reasons.append(
            {
                "code": reason.value,
                "display_name": reason.value.replace("_", " ").title(),
                "category": get_refund_category(reason).value,
            }
        )

    return {
        "reasons": reasons,
        "categories": [
            {"code": cat.value, "display_name": cat.value.replace("_", " ").title()}
            for cat in RefundCategory
        ],
    }


# Refund Policy Management


@router.post("/policies")
@require_permission("refunds.manage_policies")
async def create_refund_policy(
    policy: RefundPolicyRequest,
    restaurant_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new refund policy"""

    try:
        # Create policy
        new_policy = RefundPolicy(
            restaurant_id=restaurant_id,
            name=policy.name,
            description=policy.description,
            auto_approve_enabled=policy.auto_approve_enabled,
            auto_approve_threshold=policy.auto_approve_threshold,
            refund_window_hours=policy.refund_window_hours,
            allow_partial_refunds=policy.allow_partial_refunds,
            require_reason=policy.require_reason,
            notify_customer=policy.notify_customer,
            notify_manager=policy.notify_manager,
            created_by=current_user.id,
        )

        db.add(new_policy)
        await db.commit()

        return {
            "success": True,
            "policy_id": new_policy.id,
            "message": "Refund policy created successfully",
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create policy: {str(e)}"
        )


@router.get("/policies/{restaurant_id}")
@require_permission("refunds.view")
async def get_refund_policy(
    restaurant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get refund policy for a restaurant"""

    policy = await refund_service._get_refund_policy(db, restaurant_id)

    if not policy:
        return {"policy": None, "message": "No active refund policy found"}

    return {
        "policy": {
            "id": policy.id,
            "name": policy.name,
            "description": policy.description,
            "auto_approve_enabled": policy.auto_approve_enabled,
            "auto_approve_threshold": float(policy.auto_approve_threshold),
            "refund_window_hours": policy.refund_window_hours,
            "allow_partial_refunds": policy.allow_partial_refunds,
            "require_reason": policy.require_reason,
        }
    }


@router.post("/upload-evidence/{request_id}")
@require_permission("refunds.manage")
async def upload_refund_evidence(
    request_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload evidence files for a refund request"""

    request = await db.get(RefundRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Refund request not found")

    # Check permissions
    if not current_user.is_staff:
        if (
            hasattr(current_user, "customer_id")
            and request.customer_id != current_user.customer_id
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    # In a real implementation, you would:
    # 1. Validate file types and sizes
    # 2. Upload to cloud storage (S3, etc.)
    # 3. Store URLs in the request

    # For now, just simulate
    evidence_urls = request.evidence_urls or []
    for file in files:
        evidence_urls.append(
            f"https://storage.example.com/refunds/{request_id}/{file.filename}"
        )

    request.evidence_urls = evidence_urls
    await db.commit()

    return {
        "success": True,
        "evidence_count": len(evidence_urls),
        "message": "Evidence uploaded successfully",
    }


# Bulk Processing Endpoints


@router.post("/bulk/create", response_model=BulkRefundResponse)
@require_permission("refunds.create")
async def create_bulk_refund_requests(
    bulk_request: BulkRefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple refund requests in batch"""

    import uuid
    import asyncio
    from datetime import datetime

    batch_id = str(uuid.uuid4())[:8]
    results = []
    errors = []
    successful = 0

    # Customer info for all requests
    customer_info = {
        "user_id": current_user.id,
        "name": current_user.full_name,
        "email": current_user.email,
        "phone": getattr(current_user, "phone", None),
    }

    # Process each refund request
    for i, request in enumerate(bulk_request.refund_requests):
        try:
            refund_request = await refund_service.create_refund_request(
                db=db,
                order_id=request.order_id,
                payment_id=request.payment_id,
                requested_amount=request.requested_amount,
                reason_code=request.reason_code,
                reason_details=request.reason_details,
                customer_info=customer_info,
                refund_items=(
                    [item.dict() for item in request.refund_items]
                    if request.refund_items
                    else None
                ),
                evidence_urls=request.evidence_urls,
                priority=request.priority,
                batch_id=batch_id,
                batch_notes=bulk_request.batch_notes,
            )

            # Auto-approve if requested and allowed
            if bulk_request.auto_approve and hasattr(
                current_user, "can_approve_refunds"
            ):
                if current_user.can_approve_refunds:
                    await refund_service.approve_refund_request(
                        db=db,
                        request_id=refund_request.id,
                        approver_id=current_user.id,
                        notes=f"Auto-approved in batch {batch_id}",
                        process_immediately=False,
                    )

            results.append(
                {
                    "index": i,
                    "request_id": refund_request.id,
                    "request_number": refund_request.request_number,
                    "order_id": request.order_id,
                    "amount": float(request.requested_amount),
                    "status": "created",
                }
            )
            successful += 1

        except Exception as e:
            errors.append({"index": i, "order_id": request.order_id, "error": str(e)})

    return BulkRefundResponse(
        batch_id=batch_id,
        total_requests=len(bulk_request.refund_requests),
        successful=successful,
        failed=len(errors),
        results=results,
        errors=errors,
    )


@router.post("/bulk/approve", response_model=BulkRefundResponse)
@require_permission("refunds.approve")
async def bulk_approve_refund_requests(
    bulk_approval: BulkApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve multiple refund requests in batch"""

    import uuid

    batch_id = str(uuid.uuid4())[:8]
    results = []
    errors = []
    successful = 0

    for request_id in bulk_approval.request_ids:
        try:
            request = await refund_service.approve_refund_request(
                db=db,
                request_id=request_id,
                approver_id=current_user.id,
                notes=bulk_approval.notes or f"Bulk approved in batch {batch_id}",
                process_immediately=bulk_approval.process_immediately,
            )

            results.append(
                {
                    "request_id": request_id,
                    "status": "approved",
                    "approval_status": request.approval_status.value,
                    "processed": bulk_approval.process_immediately,
                }
            )
            successful += 1

        except Exception as e:
            errors.append({"request_id": request_id, "error": str(e)})

    return BulkRefundResponse(
        batch_id=batch_id,
        total_requests=len(bulk_approval.request_ids),
        successful=successful,
        failed=len(errors),
        results=results,
        errors=errors,
    )


@router.post("/bulk/process", response_model=BulkRefundResponse)
@require_permission("refunds.process")
async def bulk_process_refund_requests(
    bulk_processing: BulkProcessingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Process multiple approved refund requests in batch"""

    import uuid

    batch_id = str(uuid.uuid4())[:8]
    results = []
    errors = []
    successful = 0

    for request_id in bulk_processing.request_ids:
        try:
            request, refund = await refund_service.process_refund_request(
                db, request_id
            )

            results.append(
                {
                    "request_id": request_id,
                    "refund_id": refund.id,
                    "refund_reference": refund.refund_id,
                    "amount": float(refund.amount),
                    "status": "processed",
                }
            )
            successful += 1

        except Exception as e:
            errors.append({"request_id": request_id, "error": str(e)})

    return BulkRefundResponse(
        batch_id=batch_id,
        total_requests=len(bulk_processing.request_ids),
        successful=successful,
        failed=len(errors),
        results=results,
        errors=errors,
    )


@router.post("/bulk/reject")
@require_permission("refunds.approve")
async def bulk_reject_refund_requests(
    request_ids: List[int] = Body(..., embed=True),
    rejection_reason: str = Body(..., min_length=10, max_length=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject multiple refund requests in batch"""

    if len(request_ids) == 0:
        raise HTTPException(
            status_code=400, detail="At least one request ID is required"
        )
    if len(request_ids) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 requests per batch rejection"
        )

    import uuid

    batch_id = str(uuid.uuid4())[:8]
    results = []
    errors = []
    successful = 0

    # Remove duplicates
    request_ids = list(set(request_ids))

    for request_id in request_ids:
        try:
            request = await refund_service.reject_refund_request(
                db=db,
                request_id=request_id,
                rejector_id=current_user.id,
                reason=f"{rejection_reason} (Bulk rejected in batch {batch_id})",
            )

            results.append(
                {
                    "request_id": request_id,
                    "status": "rejected",
                    "approval_status": request.approval_status.value,
                }
            )
            successful += 1

        except Exception as e:
            errors.append({"request_id": request_id, "error": str(e)})

    return {
        "batch_id": batch_id,
        "total_requests": len(request_ids),
        "successful": successful,
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


@router.get("/bulk/status/{batch_id}")
@require_permission("refunds.view")
async def get_bulk_operation_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of a bulk operation"""

    # In a production system, you would store batch operation metadata
    # For now, return basic information based on batch_id

    return {
        "batch_id": batch_id,
        "status": "completed",
        "message": "Batch operation completed. Check individual request statuses for details.",
    }
