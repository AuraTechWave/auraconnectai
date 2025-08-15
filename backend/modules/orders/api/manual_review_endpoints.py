# backend/modules/orders/api/manual_review_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user, require_roles, User
from ..services.manual_review_service import ManualReviewService
from ..models.manual_review_models import ReviewReason, ReviewStatus
from ..schemas.manual_review_schemas import (
    ManualReviewResponse,
    ManualReviewListResponse,
    AssignReviewRequest,
    ResolveReviewRequest,
    EscalateReviewRequest,
    ReviewStatisticsResponse,
)


router = APIRouter(prefix="/manual-reviews", tags=["manual_reviews"])


@router.get("/pending", response_model=ManualReviewListResponse)
async def get_pending_reviews(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    priority_threshold: Optional[int] = Query(None, ge=0, le=10),
    current_user: User = Depends(require_roles(["manager", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Get pending manual reviews

    - **limit**: Maximum number of reviews to return
    - **offset**: Offset for pagination
    - **priority_threshold**: Only return reviews with priority >= threshold
    """
    service = ManualReviewService(db)
    result = await service.get_pending_reviews(
        limit=limit, offset=offset, priority_threshold=priority_threshold
    )

    return {
        "reviews": result["reviews"],
        "total": result["total"],
        "has_more": result["has_more"],
        "high_priority_count": result["high_priority_count"],
    }


@router.get("/statistics", response_model=ReviewStatisticsResponse)
async def get_review_statistics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_roles(["manager", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Get statistics about manual reviews

    - **start_date**: Filter reviews created after this date
    - **end_date**: Filter reviews created before this date
    """
    service = ManualReviewService(db)
    stats = await service.get_review_statistics(
        start_date=start_date, end_date=end_date
    )

    return stats


@router.get("/{review_id}", response_model=ManualReviewResponse)
async def get_review_details(
    review_id: int,
    current_user: User = Depends(require_roles(["staff", "manager", "admin"])),
    db: Session = Depends(get_db),
):
    """Get details of a specific review"""
    from ..models.manual_review_models import ManualReviewQueue

    review = (
        db.query(ManualReviewQueue).filter(ManualReviewQueue.id == review_id).first()
    )

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return review


@router.post("/{review_id}/assign")
async def assign_review(
    review_id: int,
    request: AssignReviewRequest,
    current_user: User = Depends(require_roles(["manager", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Assign a review to a user

    - **review_id**: ID of the review to assign
    - **assignee_id**: User ID to assign the review to
    """
    service = ManualReviewService(db)

    try:
        review = await service.assign_review(
            review_id=review_id, assignee_id=request.assignee_id
        )
        return {
            "message": "Review assigned successfully",
            "review_id": review.id,
            "assigned_to": review.assigned_to,
            "status": review.status.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error assigning review: {str(e)}")


@router.post("/{review_id}/resolve")
async def resolve_review(
    review_id: int,
    request: ResolveReviewRequest,
    current_user: User = Depends(require_roles(["manager", "admin"])),
    db: Session = Depends(get_db),
):
    """
    Resolve a manual review

    - **review_id**: ID of the review to resolve
    - **resolution_action**: Action taken to resolve the issue
    - **notes**: Additional notes about the resolution
    - **mark_order_completed**: Whether to mark the associated order as completed
    """
    service = ManualReviewService(db)

    try:
        review = await service.resolve_review(
            review_id=review_id,
            reviewer_id=current_user.id,
            resolution_action=request.resolution_action,
            notes=request.notes,
            mark_order_completed=request.mark_order_completed,
        )
        return {
            "message": "Review resolved successfully",
            "review_id": review.id,
            "status": review.status.value,
            "resolved_at": review.resolved_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving review: {str(e)}")


@router.post("/{review_id}/escalate")
async def escalate_review(
    review_id: int,
    request: EscalateReviewRequest,
    current_user: User = Depends(require_roles(["staff", "manager"])),
    db: Session = Depends(get_db),
):
    """
    Escalate a review to higher management

    - **review_id**: ID of the review to escalate
    - **escalation_reason**: Reason for escalation
    """
    service = ManualReviewService(db)

    try:
        review = await service.escalate_review(
            review_id=review_id,
            escalation_reason=request.escalation_reason,
            escalated_by=current_user.id,
        )
        return {
            "message": "Review escalated successfully",
            "review_id": review.id,
            "status": review.status.value,
            "priority": review.priority,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error escalating review: {str(e)}"
        )


@router.get("/order/{order_id}/reviews")
async def get_order_reviews(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all reviews associated with an order"""
    from ..models.manual_review_models import ManualReviewQueue

    reviews = (
        db.query(ManualReviewQueue)
        .filter(ManualReviewQueue.order_id == order_id)
        .order_by(ManualReviewQueue.created_at.desc())
        .all()
    )

    return {
        "order_id": order_id,
        "reviews": [
            {
                "id": review.id,
                "reason": review.reason.value,
                "status": review.status.value,
                "priority": review.priority,
                "created_at": review.created_at,
                "resolved_at": review.resolved_at,
                "resolution_action": review.resolution_action,
                "escalated": review.escalated,
            }
            for review in reviews
        ],
        "total": len(reviews),
    }


@router.get("/my-assigned")
async def get_my_assigned_reviews(
    status: Optional[ReviewStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get reviews assigned to the current user"""
    from ..models.manual_review_models import ManualReviewQueue

    query = db.query(ManualReviewQueue).filter(
        ManualReviewQueue.assigned_to == current_user.id
    )

    if status:
        query = query.filter(ManualReviewQueue.status == status)

    reviews = query.order_by(
        ManualReviewQueue.priority.desc(), ManualReviewQueue.created_at.asc()
    ).all()

    return {
        "reviews": reviews,
        "total": len(reviews),
        "pending_count": sum(1 for r in reviews if r.status == ReviewStatus.IN_REVIEW),
    }
