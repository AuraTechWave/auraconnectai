# backend/modules/promotions/routers/coupon_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user, require_admin
from modules.customers.models.customer_models import Customer

from ..schemas.promotion_schemas import (
    CouponCreate, CouponBulkCreate, Coupon as CouponSchema,
    CouponValidationRequest, CouponValidationResponse
)
from ..services.coupon_service import CouponService

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.post("/", response_model=CouponSchema)
def create_coupon(
    coupon_data: CouponCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create a new coupon"""
    try:
        service = CouponService(db)
        coupon = service.create_coupon(
            coupon_data=coupon_data,
            generated_by=current_user.id if hasattr(current_user, 'id') else None
        )
        return coupon
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create coupon")


@router.post("/bulk", response_model=List[CouponSchema])
def create_bulk_coupons(
    bulk_data: CouponBulkCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create multiple coupons in bulk"""
    try:
        if bulk_data.quantity > 10000:
            raise HTTPException(status_code=400, detail="Maximum 10,000 coupons per batch")
        
        service = CouponService(db)
        coupons = service.create_bulk_coupons(
            bulk_data=bulk_data,
            generated_by=current_user.id if hasattr(current_user, 'id') else None
        )
        return coupons
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create bulk coupons")


@router.post("/validate", response_model=CouponValidationResponse)
def validate_coupon(
    validation_request: CouponValidationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Validate a coupon code and calculate potential discount"""
    try:
        service = CouponService(db)
        
        # Use current user's ID if not specified in request
        if not validation_request.customer_id and hasattr(current_user, 'id'):
            validation_request.customer_id = current_user.id
        
        result = service.validate_coupon(validation_request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to validate coupon")


@router.post("/{coupon_code}/use")
def use_coupon(
    coupon_code: str,
    order_id: int,
    discount_amount: float,
    customer_id: Optional[int] = None,
    usage_context: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Mark a coupon as used and record the usage"""
    try:
        service = CouponService(db)
        
        # Use current user's ID if not specified
        if not customer_id and hasattr(current_user, 'id'):
            customer_id = current_user.id
        
        usage = service.use_coupon(
            coupon_code=coupon_code,
            customer_id=customer_id,
            order_id=order_id,
            discount_amount=discount_amount,
            usage_context=usage_context
        )
        
        return {
            "message": "Coupon used successfully",
            "usage_id": usage.id,
            "discount_amount": discount_amount
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to use coupon")


@router.get("/customer/{customer_id}", response_model=List[CouponSchema])
def get_customer_coupons(
    customer_id: int,
    active_only: bool = True,
    include_expired: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get coupons available to a specific customer"""
    try:
        # Check if user can access this customer's coupons
        if (hasattr(current_user, 'id') and current_user.id != customer_id and 
            not hasattr(current_user, 'is_admin')):
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = CouponService(db)
        coupons = service.get_customer_coupons(
            customer_id=customer_id,
            active_only=active_only,
            include_expired=include_expired
        )
        return coupons
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get customer coupons")


@router.get("/my-coupons", response_model=List[CouponSchema])
def get_my_coupons(
    active_only: bool = True,
    include_expired: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get coupons available to the current user"""
    try:
        if not hasattr(current_user, 'id'):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        service = CouponService(db)
        coupons = service.get_customer_coupons(
            customer_id=current_user.id,
            active_only=active_only,
            include_expired=include_expired
        )
        return coupons
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get your coupons")


@router.get("/batch/{batch_id}", response_model=List[CouponSchema])
def get_batch_coupons(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all coupons from a specific batch"""
    try:
        service = CouponService(db)
        coupons = service.get_batch_coupons(batch_id)
        return coupons
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get batch coupons")


@router.get("/usage-history")
def get_coupon_usage_history(
    coupon_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get coupon usage history with filters"""
    try:
        service = CouponService(db)
        history = service.get_coupon_usage_history(
            coupon_id=coupon_id,
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Convert to dict format for API response
        result = []
        for usage in history:
            result.append({
                "id": usage.id,
                "coupon_id": usage.coupon_id,
                "coupon_code": usage.coupon.code if usage.coupon else None,
                "customer_id": usage.customer_id,
                "order_id": usage.order_id,
                "discount_amount": usage.discount_amount,
                "usage_context": usage.usage_context,
                "created_at": usage.created_at
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get usage history")


@router.post("/{coupon_id}/deactivate")
def deactivate_coupon(
    coupon_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Deactivate a coupon"""
    try:
        service = CouponService(db)
        success = service.deactivate_coupon(coupon_id, reason)
        
        if not success:
            raise HTTPException(status_code=404, detail="Coupon not found")
        
        return {"message": "Coupon deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to deactivate coupon")


@router.get("/analytics")
def get_coupon_analytics(
    promotion_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get coupon usage analytics"""
    try:
        service = CouponService(db)
        analytics = service.get_coupon_analytics(
            promotion_id=promotion_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not analytics:
            return {"message": "No coupon data found for the specified criteria"}
        
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get coupon analytics")


@router.post("/cleanup-expired")
def cleanup_expired_coupons(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Remove or deactivate expired coupons (admin/cron task)"""
    try:
        service = CouponService(db)
        expired_count = service.cleanup_expired_coupons()
        
        return {
            "message": "Expired coupons cleaned up",
            "expired_count": expired_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to cleanup expired coupons")


@router.get("/code/{coupon_code}", response_model=CouponSchema)
def get_coupon_by_code(
    coupon_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get coupon details by code (admin only)"""
    try:
        service = CouponService(db)
        
        # This would need to be implemented in the service
        from ..models.promotion_models import Coupon
        coupon = db.query(Coupon).filter(
            Coupon.code == coupon_code.upper()
        ).first()
        
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        
        return coupon
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get coupon")


@router.get("/generate-code")
def generate_coupon_code(
    length: int = Query(8, ge=4, le=20),
    prefix: Optional[str] = Query(None, max_length=10),
    suffix: Optional[str] = Query(None, max_length=10),
    exclude_ambiguous: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate a unique coupon code (for preview/testing)"""
    try:
        service = CouponService(db)
        code = service.generate_coupon_code(
            length=length,
            prefix=prefix,
            suffix=suffix,
            exclude_ambiguous=exclude_ambiguous
        )
        
        return {"code": code}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate coupon code")