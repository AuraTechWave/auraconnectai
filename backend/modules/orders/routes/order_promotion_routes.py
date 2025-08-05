# backend/modules/orders/routes/order_promotion_routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from core.database import get_db
from core.auth import get_current_user, require_admin
from modules.promotions.services.order_promotion_service import OrderPromotionService
from modules.promotions.schemas.promotion_schemas import DiscountCalculationResponse

from ..models.order_models import Order
from ..services.order_service import get_order_by_id

router = APIRouter(prefix="/orders", tags=["Order Promotions"])


@router.post("/{order_id}/calculate-discounts", response_model=DiscountCalculationResponse)
async def calculate_order_discounts(
    order_id: int,
    coupon_codes: Optional[List[str]] = None,
    promotion_ids: Optional[List[int]] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate available discounts for an order"""
    try:
        order = await get_order_by_id(db, order_id)
        
        service = OrderPromotionService(db)
        result = service.calculate_order_discounts(
            order=order,
            coupon_codes=coupon_codes,
            promotion_ids=promotion_ids
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate discounts: {str(e)}")


@router.post("/{order_id}/apply-discounts")
async def apply_discounts_to_order(
    order_id: int,
    coupon_codes: Optional[List[str]] = None,
    promotion_ids: Optional[List[int]] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Apply discounts to an order"""
    try:
        order = await get_order_by_id(db, order_id)
        
        # Only allow applying discounts to pending or in-progress orders
        if order.status not in ["pending", "in_progress"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot apply discounts to order with status {order.status}"
            )
        
        service = OrderPromotionService(db)
        
        # First calculate the discounts
        discount_result = service.calculate_order_discounts(
            order=order,
            coupon_codes=coupon_codes,
            promotion_ids=promotion_ids
        )
        
        # Then apply them
        application_result = service.apply_discounts_to_order(
            order=order,
            discount_response=discount_result,
            applied_by=current_user.id if hasattr(current_user, 'id') else None
        )
        
        return {
            "message": "Discounts applied successfully",
            "discount_calculation": discount_result,
            "application_result": application_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply discounts: {str(e)}")


@router.get("/{order_id}/applicable-promotions")
async def get_applicable_promotions(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all applicable promotions for an order"""
    try:
        order = await get_order_by_id(db, order_id)
        
        service = OrderPromotionService(db)
        promotions = service.get_applicable_promotions(order)
        
        return {
            "order_id": order_id,
            "applicable_promotions": promotions,
            "count": len(promotions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get applicable promotions: {str(e)}")


@router.post("/{order_id}/validate-promotion/{promotion_id}")
async def validate_promotion_for_order(
    order_id: int,
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Validate if a specific promotion can be applied to an order"""
    try:
        order = await get_order_by_id(db, order_id)
        
        service = OrderPromotionService(db)
        is_eligible, error_message = service.validate_promotion_eligibility(order, promotion_id)
        
        return {
            "order_id": order_id,
            "promotion_id": promotion_id,
            "is_eligible": is_eligible,
            "error_message": error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate promotion: {str(e)}")


@router.get("/{order_id}/promotion-summary")
async def get_order_promotion_summary(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get summary of all promotions applied to an order"""
    try:
        # Verify order exists
        order = await get_order_by_id(db, order_id)
        
        service = OrderPromotionService(db)
        summary = service.get_order_promotion_summary(order_id)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get promotion summary: {str(e)}")


@router.post("/{order_id}/complete")
async def complete_order_with_promotions(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Complete an order and process promotion-related actions"""
    try:
        order = await get_order_by_id(db, order_id)
        
        # Verify order can be completed
        if order.status not in ["ready", "served"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete order with status {order.status}"
            )
        
        # Update order status to completed
        order.status = "completed"
        db.commit()
        db.refresh(order)
        
        # Process promotion-related completion actions
        service = OrderPromotionService(db)
        promotion_results = service.process_order_completion(order)
        
        return {
            "message": "Order completed successfully",
            "order_id": order_id,
            "promotion_processing": promotion_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to complete order: {str(e)}")


@router.post("/bulk-apply-promotion")
async def bulk_apply_promotion_to_orders(
    order_ids: List[int],
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Apply a promotion to multiple orders (admin only)"""
    try:
        service = OrderPromotionService(db)
        results = {
            "successful_orders": [],
            "failed_orders": [],
            "total_discount_applied": 0.0
        }
        
        for order_id in order_ids:
            try:
                order = await get_order_by_id(db, order_id)
                
                # Validate promotion eligibility
                is_eligible, error_message = service.validate_promotion_eligibility(
                    order, promotion_id
                )
                
                if not is_eligible:
                    results["failed_orders"].append({
                        "order_id": order_id,
                        "error": error_message
                    })
                    continue
                
                # Calculate and apply discount
                discount_result = service.calculate_order_discounts(
                    order=order,
                    promotion_ids=[promotion_id]
                )
                
                application_result = service.apply_discounts_to_order(
                    order=order,
                    discount_response=discount_result,
                    applied_by=current_user.id
                )
                
                results["successful_orders"].append({
                    "order_id": order_id,
                    "discount_applied": application_result["total_discount"]
                })
                
                results["total_discount_applied"] += application_result["total_discount"]
                
            except Exception as e:
                results["failed_orders"].append({
                    "order_id": order_id,
                    "error": str(e)
                })
        
        return {
            "message": f"Bulk promotion application completed",
            "results": results,
            "summary": {
                "total_orders": len(order_ids),
                "successful": len(results["successful_orders"]),
                "failed": len(results["failed_orders"]),
                "total_discount": results["total_discount_applied"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk apply promotion: {str(e)}")


@router.get("/promotion-analytics")
async def get_order_promotion_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    promotion_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get analytics on promotion usage in orders"""
    try:
        from ..models.promotion_models import PromotionUsage, Promotion
        from datetime import datetime
        
        query = db.query(PromotionUsage)
        
        # Apply filters
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(PromotionUsage.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(PromotionUsage.created_at <= end_dt)
        
        if promotion_id:
            query = query.filter(PromotionUsage.promotion_id == promotion_id)
        
        usages = query.all()
        
        # Calculate analytics
        total_usage = len(usages)
        total_discount = sum(usage.discount_amount for usage in usages)
        total_revenue_impact = sum(usage.final_order_amount for usage in usages)
        unique_customers = len(set(usage.customer_id for usage in usages if usage.customer_id))
        unique_orders = len(set(usage.order_id for usage in usages))
        
        # Promotion breakdown
        promotion_stats = {}
        for usage in usages:
            promo_id = usage.promotion_id
            if promo_id not in promotion_stats:
                promotion_stats[promo_id] = {
                    "promotion_id": promo_id,
                    "promotion_name": usage.promotion.name if usage.promotion else "Unknown",
                    "usage_count": 0,
                    "total_discount": 0.0,
                    "total_revenue": 0.0
                }
            
            promotion_stats[promo_id]["usage_count"] += 1
            promotion_stats[promo_id]["total_discount"] += usage.discount_amount
            promotion_stats[promo_id]["total_revenue"] += usage.final_order_amount
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "summary": {
                "total_usage": total_usage,
                "total_discount_given": round(total_discount, 2),
                "total_revenue_impact": round(total_revenue_impact, 2),
                "unique_customers": unique_customers,
                "unique_orders": unique_orders,
                "average_discount_per_order": round(total_discount / unique_orders, 2) if unique_orders > 0 else 0
            },
            "promotion_breakdown": list(promotion_stats.values())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get promotion analytics: {str(e)}")


@router.post("/auto-apply-promotions")
async def auto_apply_best_promotions(
    order_ids: List[int],
    max_promotions_per_order: int = 3,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Automatically apply the best available promotions to orders"""
    try:
        service = OrderPromotionService(db)
        results = {
            "processed_orders": [],
            "total_savings": 0.0
        }
        
        for order_id in order_ids:
            try:
                order = await get_order_by_id(db, order_id)
                
                # Get applicable promotions
                applicable_promotions = service.get_applicable_promotions(order)
                
                # Sort by potential discount and take the best ones
                best_promotions = sorted(
                    applicable_promotions,
                    key=lambda x: x["potential_discount"],
                    reverse=True
                )[:max_promotions_per_order]
                
                if not best_promotions:
                    results["processed_orders"].append({
                        "order_id": order_id,
                        "promotions_applied": 0,
                        "total_discount": 0.0,
                        "message": "No applicable promotions found"
                    })
                    continue
                
                # Apply the best promotions
                promotion_ids = [p["promotion_id"] for p in best_promotions if p["auto_apply"]]
                
                if promotion_ids:
                    discount_result = service.calculate_order_discounts(
                        order=order,
                        promotion_ids=promotion_ids
                    )
                    
                    application_result = service.apply_discounts_to_order(
                        order=order,
                        discount_response=discount_result,
                        applied_by=current_user.id if hasattr(current_user, 'id') else None
                    )
                    
                    results["processed_orders"].append({
                        "order_id": order_id,
                        "promotions_applied": len(promotion_ids),
                        "total_discount": application_result["total_discount"],
                        "message": "Promotions applied successfully"
                    })
                    
                    results["total_savings"] += application_result["total_discount"]
                else:
                    results["processed_orders"].append({
                        "order_id": order_id,
                        "promotions_applied": 0,
                        "total_discount": 0.0,
                        "message": "No auto-apply promotions available"
                    })
                
            except Exception as e:
                results["processed_orders"].append({
                    "order_id": order_id,
                    "promotions_applied": 0,
                    "total_discount": 0.0,
                    "message": f"Error: {str(e)}"
                })
        
        return {
            "message": "Auto-promotion application completed",
            "results": results,
            "summary": {
                "total_orders": len(order_ids),
                "total_savings": round(results["total_savings"], 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-apply promotions: {str(e)}")