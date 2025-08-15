# backend/modules/feedback/routers/reviews_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging

from core.database import get_db
from core.auth import get_current_user
from modules.feedback.services.review_service import ReviewService
from modules.feedback.services.moderation_service import create_moderation_service
from modules.feedback.services.aggregation_service import create_aggregation_service
from modules.feedback.schemas.feedback_schemas import (
    ReviewCreate,
    ReviewUpdate,
    ReviewModeration,
    ReviewResponse,
    ReviewSummary,
    ReviewFilters,
    BusinessResponseCreate,
    ReviewMediaCreate,
    ReviewVoteCreate,
    PaginatedResponse,
    ReviewListResponse,
)

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Create a new review"""

    try:
        # Validate customer ID matches current user
        if review_data.customer_id != current_user["id"]:
            raise PermissionError("Cannot create review for another customer")

        review_service = ReviewService(db)
        result = review_service.create_review(review_data, auto_verify=False)

        return result

    except Exception as e:
        logger.error(f"Error creating review: {e}")
        if isinstance(e, (ValueError, PermissionError)):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: int = Path(..., description="Review ID"), db: Session = Depends(get_db)
):
    """Get a specific review by ID"""

    try:
        review_service = ReviewService(db)
        result = review_service.get_review(review_id)

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/uuid/{review_uuid}", response_model=ReviewResponse)
async def get_review_by_uuid(
    review_uuid: str = Path(..., description="Review UUID"),
    db: Session = Depends(get_db),
):
    """Get a review by UUID"""

    try:
        review_service = ReviewService(db)
        result = review_service.get_review_by_uuid(review_uuid)

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting review {review_uuid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int = Path(..., description="Review ID"),
    update_data: ReviewUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Update an existing review"""

    try:
        review_service = ReviewService(db)
        result = review_service.update_review(
            review_id, update_data, customer_id=current_user["id"]
        )

        return result

    except (KeyError, PermissionError) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, KeyError) else 403, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{review_id}")
async def delete_review(
    review_id: int = Path(..., description="Review ID"),
    soft_delete: bool = Query(
        True, description="Whether to soft delete (hide) or hard delete"
    ),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Delete or hide a review"""

    try:
        review_service = ReviewService(db)
        result = review_service.delete_review(
            review_id, customer_id=current_user["id"], soft_delete=soft_delete
        )

        return result

    except (KeyError, PermissionError) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, KeyError) else 403, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=ReviewListResponse)
async def list_reviews(
    # Filtering parameters
    review_type: Optional[str] = Query(None, description="Filter by review type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    rating_min: Optional[float] = Query(
        None, ge=1.0, le=5.0, description="Minimum rating"
    ),
    rating_max: Optional[float] = Query(
        None, ge=1.0, le=5.0, description="Maximum rating"
    ),
    verified_only: Optional[bool] = Query(
        None, description="Show only verified reviews"
    ),
    with_media: Optional[bool] = Query(
        None, description="Show only reviews with media"
    ),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    order_id: Optional[int] = Query(None, description="Filter by order ID"),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    # Sorting parameters
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
):
    """List reviews with filtering, pagination, and sorting"""

    try:
        # Build filters
        filters = ReviewFilters()
        if review_type:
            filters.review_type = review_type
        if status:
            filters.status = status
        if rating_min is not None:
            filters.rating_min = rating_min
        if rating_max is not None:
            filters.rating_max = rating_max
        if verified_only is not None:
            filters.verified_only = verified_only
        if with_media is not None:
            filters.with_media = with_media
        if sentiment:
            filters.sentiment = sentiment
        if customer_id:
            filters.customer_id = customer_id
        if product_id:
            filters.product_id = product_id
        if order_id:
            filters.order_id = order_id

        review_service = ReviewService(db)
        result = review_service.list_reviews(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return ReviewListResponse(
            items=result.items,
            total=result.total,
            page=result.page,
            per_page=result.per_page,
            total_pages=result.total_pages,
            has_next=result.has_next,
            has_prev=result.has_prev,
        )

    except Exception as e:
        logger.error(f"Error listing reviews: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{review_id}/vote")
async def vote_on_review(
    review_id: int = Path(..., description="Review ID"),
    vote_data: ReviewVoteCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Vote on review helpfulness"""

    try:
        review_service = ReviewService(db)
        result = review_service.vote_on_review(review_id, current_user["id"], vote_data)

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error voting on review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{review_id}/business-response")
async def add_business_response(
    review_id: int = Path(..., description="Review ID"),
    response_data: BusinessResponseCreate = Body(...),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Add business response to a review (staff only)"""

    try:
        # Set responder info from current staff user
        if not response_data.responder_id:
            response_data.responder_id = current_staff["id"]
        if not response_data.responder_name:
            response_data.responder_name = current_staff.get("name", "Staff")

        review_service = ReviewService(db)
        result = review_service.add_business_response(review_id, response_data)

        return result

    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, KeyError) else 400, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error adding business response to review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{review_id}/media")
async def add_review_media(
    review_id: int = Path(..., description="Review ID"),
    media_data: List[ReviewMediaCreate] = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Add media attachments to a review"""

    try:
        review_service = ReviewService(db)
        result = review_service.add_review_media(
            review_id, media_data, customer_id=current_user["id"]
        )

        return result

    except (KeyError, PermissionError) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, KeyError) else 403, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error adding media to review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entity_type}/{entity_id}/aggregates")
async def get_review_aggregates(
    entity_type: str = Path(
        ..., pattern="^(product|service)$", description="Entity type"
    ),
    entity_id: int = Path(..., description="Entity ID"),
    force_refresh: bool = Query(False, description="Force recalculation"),
    db: Session = Depends(get_db),
):
    """Get aggregated review statistics for an entity"""

    try:
        aggregation_service = create_aggregation_service(db)
        result = aggregation_service.get_review_aggregates(
            entity_type, entity_id, force_refresh=force_refresh
        )

        return result

    except Exception as e:
        logger.error(f"Error getting aggregates for {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entity_type}/{entity_id}/insights")
async def get_review_insights(
    entity_type: str = Path(
        ..., pattern="^(product|service)$", description="Entity type"
    ),
    entity_id: int = Path(..., description="Entity ID"),
    db: Session = Depends(get_db),
):
    """Get detailed review insights for an entity"""

    try:
        aggregation_service = create_aggregation_service(db)
        result = aggregation_service.get_review_insights(entity_type, entity_id)

        return result

    except Exception as e:
        logger.error(f"Error getting insights for {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Staff/Admin endpoints


@router.post("/{review_id}/moderate", dependencies=[Depends(get_current_user)])
async def moderate_review(
    review_id: int = Path(..., description="Review ID"),
    moderation_data: ReviewModeration = Body(...),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Moderate a review (staff only)"""

    try:
        review_service = ReviewService(db)
        result = review_service.moderate_review(
            review_id, moderation_data, moderator_id=current_staff["id"]
        )

        return result

    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error moderating review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bulk-moderate", dependencies=[Depends(get_current_user)])
async def bulk_moderate_reviews(
    review_ids: List[int] = Body(..., description="List of review IDs"),
    action: str = Body(
        ..., pattern="^(approve|reject|flag|hide)$", description="Moderation action"
    ),
    notes: Optional[str] = Body(None, description="Moderation notes"),
    db: Session = Depends(get_db),
    current_staff: Dict = Depends(get_current_user),
):
    """Bulk moderate multiple reviews (staff only)"""

    try:
        moderation_service = create_moderation_service(db)
        result = moderation_service.bulk_moderate_reviews(
            review_ids, current_staff["id"], action, notes
        )

        return result

    except Exception as e:
        logger.error(f"Error bulk moderating reviews: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/moderation/queue", dependencies=[Depends(get_current_user)])
async def get_moderation_queue(
    priority: str = Query(
        "all", pattern="^(all|high|urgent)$", description="Priority filter"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Get reviews pending moderation (staff only)"""

    try:
        moderation_service = create_moderation_service(db)
        result = moderation_service.get_moderation_queue(
            content_type="review", priority=priority, page=page, per_page=per_page
        )

        return result

    except Exception as e:
        logger.error(f"Error getting moderation queue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/moderation/stats", dependencies=[Depends(get_current_user)])
async def get_moderation_stats(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
):
    """Get moderation statistics (staff only)"""

    try:
        from datetime import datetime

        start_dt = None
        end_dt = None

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        moderation_service = create_moderation_service(db)
        result = moderation_service.get_moderation_stats(start_dt, end_dt)

        return result

    except Exception as e:
        logger.error(f"Error getting moderation stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/top-rated/{entity_type}")
async def get_top_rated_entities(
    entity_type: str = Path(
        ..., pattern="^(product|service)$", description="Entity type"
    ),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    min_reviews: int = Query(5, ge=1, description="Minimum number of reviews"),
    db: Session = Depends(get_db),
):
    """Get top-rated entities"""

    try:
        aggregation_service = create_aggregation_service(db)
        result = aggregation_service.get_top_rated_entities(
            entity_type, limit=limit, min_reviews=min_reviews
        )

        return result

    except Exception as e:
        logger.error(f"Error getting top rated {entity_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trending/{entity_type}")
async def get_trending_entities(
    entity_type: str = Path(
        ..., pattern="^(product|service)$", description="Entity type"
    ),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    days_back: int = Query(7, ge=1, le=30, description="Days to look back"),
    db: Session = Depends(get_db),
):
    """Get trending entities based on recent review activity"""

    try:
        aggregation_service = create_aggregation_service(db)
        result = aggregation_service.get_trending_entities(
            entity_type, limit=limit, days_back=days_back
        )

        return result

    except Exception as e:
        logger.error(f"Error getting trending {entity_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/aggregates/update", dependencies=[Depends(get_current_user)])
async def update_review_aggregates(
    entity_type: str = Body(
        ..., pattern="^(product|service)$", description="Entity type"
    ),
    entity_ids: Optional[List[int]] = Body(
        None, description="Specific entity IDs (optional)"
    ),
    batch_size: int = Body(50, ge=1, le=100, description="Batch size"),
    db: Session = Depends(get_db),
):
    """Update review aggregates (staff only)"""

    try:
        aggregation_service = create_aggregation_service(db)
        result = aggregation_service.bulk_update_aggregates(
            entity_type, entity_ids=entity_ids, batch_size=batch_size
        )

        return result

    except Exception as e:
        logger.error(f"Error updating aggregates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
