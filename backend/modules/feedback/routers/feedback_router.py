# backend/modules/feedback/routers/feedback_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging

from core.database import get_db
from core.auth import get_current_user, get_current_user_optional
from modules.feedback.services.feedback_service import FeedbackService
from modules.feedback.services.moderation_service import create_moderation_service
from modules.feedback.schemas.feedback_schemas import (
    FeedbackCreate,
    FeedbackUpdate,
    FeedbackResponse,
    FeedbackSummary,
    FeedbackFilters,
    FeedbackResponseCreate,
    FeedbackCategoryCreate,
    FeedbackCategoryUpdate,
    PaginatedResponse,
    FeedbackListResponse,
)

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
):
    """Create new feedback (anonymous or authenticated)"""

    try:
        # Allow anonymous feedback, but validate customer info
        if current_user and feedback_data.customer_id:
            if feedback_data.customer_id != current_user["id"]:
                raise PermissionError("Cannot create feedback for another customer")
        elif current_user and not feedback_data.customer_id:
            # Set customer ID from authenticated user
            feedback_data.customer_id = current_user["id"]

        # For anonymous feedback, customer_id will be None but email should be provided
        if not feedback_data.customer_id and not feedback_data.customer_email:
            raise ValueError("Either customer authentication or email is required")

        feedback_service = FeedbackService(db)
        result = feedback_service.create_feedback(feedback_data, auto_categorize=True)

        return result

    except Exception as e:
        logger.error(f"Error creating feedback: {e}")
        if isinstance(e, (ValueError, PermissionError)):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    db: Session = Depends(get_db),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    current_staff: Optional[Dict] = Depends(get_current_user),
):
    """Get specific feedback by ID"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.get_feedback(feedback_id)

        # Check permissions - only owner or staff can view
        if not current_staff:
            if not current_user or (
                result.customer_id and result.customer_id != current_user["id"]
            ):
                raise PermissionError("Cannot view another customer's feedback")

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/uuid/{feedback_uuid}", response_model=FeedbackResponse)
async def get_feedback_by_uuid(
    feedback_uuid: str = Path(..., description="Feedback UUID"),
    db: Session = Depends(get_db),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    current_staff: Optional[Dict] = Depends(get_current_user),
):
    """Get feedback by UUID"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.get_feedback_by_uuid(feedback_uuid)

        # Check permissions - only owner or staff can view
        if not current_staff:
            if not current_user or (
                result.customer_id and result.customer_id != current_user["id"]
            ):
                raise PermissionError("Cannot view another customer's feedback")

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting feedback {feedback_uuid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    dependencies=[Depends(get_current_user)],
)
async def update_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    update_data: FeedbackUpdate = Body(...),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Update feedback (staff only)"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.update_feedback(
            feedback_id, update_data, staff_id=current_staff["id"]
        )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=FeedbackListResponse)
async def list_feedback(
    # Filtering parameters
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    assigned_to: Optional[int] = Query(None, description="Filter by assignee"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    follow_up_required: Optional[bool] = Query(
        None, description="Filter by follow-up requirement"
    ),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    # Sorting parameters
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: Optional[Dict] = Depends(get_current_user_optional),
    current_staff: Optional[Dict] = Depends(get_current_user),
):
    """List feedback with filtering and pagination"""

    try:
        # Build filters
        filters = FeedbackFilters()
        if feedback_type:
            filters.feedback_type = feedback_type
        if status:
            filters.status = status
        if priority:
            filters.priority = priority
        if category:
            filters.category = category
        if assigned_to:
            filters.assigned_to = assigned_to
        if follow_up_required is not None:
            filters.follow_up_required = follow_up_required

        # Apply customer filter based on permissions
        if customer_id:
            if not current_staff:
                # Non-staff can only see their own feedback
                if not current_user or customer_id != current_user["id"]:
                    raise PermissionError("Cannot view another customer's feedback")
            filters.customer_id = customer_id
        elif not current_staff and current_user:
            # Regular users can only see their own feedback
            filters.customer_id = current_user["id"]
        elif not current_staff and not current_user:
            # Anonymous users cannot list feedback
            raise PermissionError("Authentication required to list feedback")

        feedback_service = FeedbackService(db)
        result = feedback_service.list_feedback(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return FeedbackListResponse(
            items=result.items,
            total=result.total,
            page=result.page,
            per_page=result.per_page,
            total_pages=result.total_pages,
            has_next=result.has_next,
            has_prev=result.has_prev,
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{feedback_id}/assign", dependencies=[Depends(get_current_user)])
async def assign_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    assignee_id: int = Body(..., description="Staff member to assign to"),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Assign feedback to a staff member (staff only)"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.assign_feedback(
            feedback_id, assignee_id, assigner_id=current_staff["id"]
        )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{feedback_id}/resolve", dependencies=[Depends(get_current_user)])
async def resolve_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    resolution_notes: str = Body(..., description="Resolution notes"),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Mark feedback as resolved (staff only)"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.resolve_feedback(
            feedback_id, resolution_notes, resolver_id=current_staff["id"]
        )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error resolving feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{feedback_id}/escalate", dependencies=[Depends(get_current_user)])
async def escalate_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    escalated_to: int = Body(..., description="Staff member to escalate to"),
    reason: Optional[str] = Body(None, description="Escalation reason"),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Escalate feedback to higher level support (staff only)"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.escalate_feedback(
            feedback_id, escalated_to, escalator_id=current_staff["id"], reason=reason
        )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error escalating feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{feedback_id}/responses")
async def add_feedback_response(
    feedback_id: int = Path(..., description="Feedback ID"),
    response_data: FeedbackResponseCreate = Body(...),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Add response to feedback (staff only)"""

    try:
        # Set responder info from current staff user
        if not response_data.responder_id:
            response_data.responder_id = current_staff["id"]
        if not response_data.responder_name:
            response_data.responder_name = current_staff.get("name", "Staff")

        feedback_service = FeedbackService(db)
        result = feedback_service.add_feedback_response(feedback_id, response_data)

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding response to feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics/overview", dependencies=[Depends(get_current_user)])
async def get_feedback_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
):
    """Get feedback analytics overview (staff only)"""

    try:
        from datetime import datetime

        start_dt = None
        end_dt = None

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        feedback_service = FeedbackService(db)
        result = feedback_service.get_feedback_analytics(start_dt, end_dt)

        return result

    except Exception as e:
        logger.error(f"Error getting feedback analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Category management endpoints


@router.post("/categories", dependencies=[Depends(get_current_user)])
async def create_feedback_category(
    category_data: FeedbackCategoryCreate = Body(...), db: Session = Depends(get_db)
):
    """Create a new feedback category (staff only)"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.create_feedback_category(category_data)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating feedback category: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories")
async def list_feedback_categories(
    include_inactive: bool = Query(False, description="Include inactive categories"),
    db: Session = Depends(get_db),
):
    """List all feedback categories"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.list_feedback_categories(include_inactive)

        return {"categories": result}

    except Exception as e:
        logger.error(f"Error listing feedback categories: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Moderation endpoints


@router.get("/moderation/queue", dependencies=[Depends(get_current_user)])
async def get_feedback_moderation_queue(
    priority: str = Query(
        "all", pattern="^(all|low|medium|high|urgent)$", description="Priority filter"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Get feedback pending moderation (staff only)"""

    try:
        moderation_service = create_moderation_service(db)
        result = moderation_service.get_moderation_queue(
            content_type="feedback", priority=priority, page=page, per_page=per_page
        )

        return result

    except Exception as e:
        logger.error(f"Error getting feedback moderation queue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{feedback_id}/moderate", dependencies=[Depends(get_current_user)])
async def moderate_feedback(
    feedback_id: int = Path(..., description="Feedback ID"),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Run moderation analysis on feedback (staff only)"""

    try:
        from modules.feedback.models.feedback_models import Feedback

        # Get feedback
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        moderation_service = create_moderation_service(db)
        result = moderation_service.moderate_feedback(feedback, auto_moderate=False)

        return {
            "feedback_id": feedback_id,
            "moderation_result": {
                "action": result.action,
                "confidence": result.confidence,
                "reasons": result.reasons,
                "severity_score": result.severity_score,
                "flagged_content": result.flagged_content,
            },
        }

    except Exception as e:
        logger.error(f"Error moderating feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Public endpoints for customer self-service


@router.get("/my/feedback", response_model=FeedbackListResponse)
async def get_my_feedback(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Get current user's feedback"""

    try:
        filters = FeedbackFilters(customer_id=current_user["id"])
        if status:
            filters.status = status

        feedback_service = FeedbackService(db)
        result = feedback_service.list_feedback(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by="created_at",
            sort_order="desc",
        )

        return FeedbackListResponse(
            items=result.items,
            total=result.total,
            page=result.page,
            per_page=result.per_page,
            total_pages=result.total_pages,
            has_next=result.has_next,
            has_prev=result.has_prev,
        )

    except Exception as e:
        logger.error(f"Error getting customer feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/my/feedback/{feedback_id}", response_model=FeedbackResponse)
async def get_my_feedback_detail(
    feedback_id: int = Path(..., description="Feedback ID"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Get specific feedback for current user"""

    try:
        feedback_service = FeedbackService(db)
        result = feedback_service.get_feedback(feedback_id)

        # Verify ownership
        if result.customer_id != current_user["id"]:
            raise HTTPException(
                status_code=403, detail="Cannot view another customer's feedback"
            )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting customer feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health check endpoint


@router.get("/health")
async def feedback_health_check():
    """Health check for feedback service"""

    return {
        "status": "healthy",
        "service": "feedback",
        "timestamp": "2024-01-01T12:00:00Z",
    }
