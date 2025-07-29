# backend/modules/promotions/routers/promotion_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.core.database import get_db
from backend.modules.auth.dependencies import get_current_user, require_admin
from backend.modules.customers.models.customer_models import Customer

from ..models.promotion_models import Promotion
from ..schemas.promotion_schemas import (
    PromotionCreate, PromotionUpdate, Promotion as PromotionSchema,
    PromotionSummary, PromotionSearchParams, PromotionSearchResponse,
    ABTestConfig, DiscountCalculationRequest, DiscountCalculationResponse
)
from ..services.promotion_service import PromotionService
from ..services.discount_service import DiscountService

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.post("/", response_model=PromotionSchema)
def create_promotion(
    promotion_data: PromotionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create a new promotion"""
    try:
        service = PromotionService(db)
        promotion = service.create_promotion(
            promotion_data=promotion_data,
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        return promotion
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create promotion")


@router.get("/search", response_model=PromotionSearchResponse)
def search_promotions(
    query: Optional[str] = None,
    promotion_type: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    discount_type: Optional[List[str]] = Query(None),
    is_featured: Optional[bool] = None,
    is_public: Optional[bool] = None,
    start_date_from: Optional[datetime] = None,
    start_date_to: Optional[datetime] = None,
    target_customer_segment: Optional[str] = None,
    requires_coupon: Optional[bool] = None,
    stackable: Optional[bool] = None,
    min_discount_value: Optional[float] = None,
    max_discount_value: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "created_at",
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Search promotions with filters and pagination"""
    try:
        params = PromotionSearchParams(
            query=query,
            promotion_type=promotion_type,
            status=status,
            discount_type=discount_type,
            is_featured=is_featured,
            is_public=is_public,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            target_customer_segment=target_customer_segment,
            requires_coupon=requires_coupon,
            stackable=stackable,
            min_discount_value=min_discount_value,
            max_discount_value=max_discount_value,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        service = PromotionService(db)
        return service.search_promotions(params)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to search promotions")


@router.get("/active", response_model=List[PromotionSummary])
def get_active_promotions(
    customer_tier: Optional[str] = None,
    featured_only: bool = False,
    public_only: bool = True,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get currently active promotions"""
    try:
        service = PromotionService(db)
        
        customer_id = None
        if hasattr(current_user, 'id'):
            customer_id = current_user.id
        
        promotions = service.get_active_promotions(
            customer_id=customer_id,
            customer_tier=customer_tier,
            featured_only=featured_only,
            public_only=public_only
        )
        
        # Convert to summaries and limit results
        summaries = []
        for promo in promotions[:limit]:
            summaries.append(PromotionSummary(
                id=promo.id,
                uuid=promo.uuid,
                name=promo.name,
                promotion_type=promo.promotion_type,
                status=promo.status,
                discount_type=promo.discount_type,
                discount_value=promo.discount_value,
                start_date=promo.start_date,
                end_date=promo.end_date,
                current_uses=promo.current_uses,
                max_uses_total=promo.max_uses_total,
                is_featured=promo.is_featured,
                is_active=promo.is_active,
                days_remaining=promo.days_remaining
            ))
        
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get active promotions")


@router.get("/featured", response_model=List[PromotionSummary])
def get_featured_promotions(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get featured promotions for public display"""
    try:
        service = PromotionService(db)
        promotions = service.get_featured_promotions(limit=limit)
        
        summaries = []
        for promo in promotions:
            summaries.append(PromotionSummary(
                id=promo.id,
                uuid=promo.uuid,
                name=promo.name,
                promotion_type=promo.promotion_type,
                status=promo.status,
                discount_type=promo.discount_type,
                discount_value=promo.discount_value,
                start_date=promo.start_date,
                end_date=promo.end_date,
                current_uses=promo.current_uses,
                max_uses_total=promo.max_uses_total,
                is_featured=promo.is_featured,
                is_active=promo.is_active,
                days_remaining=promo.days_remaining
            ))
        
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get featured promotions")


@router.get("/{promotion_id}", response_model=PromotionSchema)
def get_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific promotion by ID"""
    try:
        service = PromotionService(db)
        promotion = service.get_promotion(promotion_id)
        
        if not promotion:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        # Check if user can view this promotion
        if not promotion.is_public and not hasattr(current_user, 'is_admin'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return promotion
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get promotion")


@router.put("/{promotion_id}", response_model=PromotionSchema)
def update_promotion(
    promotion_id: int,
    update_data: PromotionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Update an existing promotion"""
    try:
        service = PromotionService(db)
        promotion = service.update_promotion(
            promotion_id=promotion_id,
            update_data=update_data,
            updated_by=current_user.id if hasattr(current_user, 'id') else None
        )
        return promotion
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update promotion")


@router.post("/{promotion_id}/activate")
def activate_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Activate a promotion"""
    try:
        service = PromotionService(db)
        success = service.activate_promotion(promotion_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        return {"message": "Promotion activated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to activate promotion")


@router.post("/{promotion_id}/pause")
def pause_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Pause a promotion"""
    try:
        service = PromotionService(db)
        success = service.pause_promotion(promotion_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        return {"message": "Promotion paused successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to pause promotion")


@router.post("/{promotion_id}/cancel")
def cancel_promotion(
    promotion_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Cancel a promotion"""
    try:
        service = PromotionService(db)
        success = service.cancel_promotion(promotion_id, reason)
        
        if not success:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        return {"message": "Promotion cancelled successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to cancel promotion")


@router.post("/{promotion_id}/end")
def end_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """End a promotion (natural completion)"""
    try:
        service = PromotionService(db)
        success = service.end_promotion(promotion_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        return {"message": "Promotion ended successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to end promotion")


@router.post("/{promotion_id}/duplicate", response_model=PromotionSchema)
def duplicate_promotion(
    promotion_id: int,
    new_name: str,
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Duplicate an existing promotion with new dates"""
    try:
        service = PromotionService(db)
        duplicated = service.duplicate_promotion(
            promotion_id=promotion_id,
            new_name=new_name,
            start_date=start_date,
            end_date=end_date
        )
        return duplicated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to duplicate promotion")


@router.get("/{promotion_id}/analytics")
def get_promotion_analytics(
    promotion_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get comprehensive analytics for a promotion"""
    try:
        service = PromotionService(db)
        analytics = service.get_promotion_analytics_summary(
            promotion_id=promotion_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not analytics:
            raise HTTPException(status_code=404, detail="Promotion not found")
        
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get promotion analytics")


@router.post("/ab-test", response_model=List[PromotionSchema])
def create_ab_test(
    ab_config: ABTestConfig,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create A/B test promotions"""
    try:
        service = PromotionService(db)
        promotions = service.create_ab_test(ab_config)
        return promotions
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create A/B test")


@router.post("/calculate-discount", response_model=DiscountCalculationResponse)
def calculate_discount(
    request: DiscountCalculationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate discounts for an order"""
    try:
        service = DiscountService(db)
        
        # Use current user's ID if not specified in request
        if not request.customer_id and hasattr(current_user, 'id'):
            request.customer_id = current_user.id
        
        result = service.calculate_order_discounts(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to calculate discounts")


@router.post("/update-statuses")
def update_promotion_statuses(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Update promotion statuses based on schedule (admin/cron task)"""
    try:
        service = PromotionService(db)
        results = service.update_promotion_status_by_schedule()
        
        return {
            "message": "Promotion statuses updated",
            "activated": results["activated"],
            "expired": results["expired"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update promotion statuses")


@router.get("/{promotion_id}/performance")
def get_promotion_performance(
    promotion_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get performance metrics for a promotion"""
    try:
        service = DiscountService(db)
        metrics = service.get_promotion_performance_metrics(
            promotion_id=promotion_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Promotion not found or no data")
        
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get promotion performance")


@router.post("/validate-stackability")
def validate_promotion_stackability(
    promotion_ids: List[int],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Validate if promotions can be stacked together"""
    try:
        service = DiscountService(db)
        is_valid, errors = service.validate_promotion_stackability(promotion_ids)
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "promotion_ids": promotion_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to validate promotion stackability")