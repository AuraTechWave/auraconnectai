from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import logging

from ..models.order_models import Order, OrderItem
from ..schemas.dynamic_pricing_schemas import (
    DynamicPricingRequest, DynamicPricingResponse, BulkPricingRequest, 
    BulkPricingResponse, PricingContext, ApplyDynamicPricingRequest
)
from ..schemas.order_schemas import OrderOut
from ..enums.order_enums import PricingType, PricingAdjustmentReason
from .ai_recommendation_service import recommendation_service

logger = logging.getLogger(__name__)


class PricingService:
    def __init__(self, db: Session):
        self.db = db
        self.fallback_enabled = True
        
    async def calculate_dynamic_prices(
        self, 
        request: BulkPricingRequest
    ) -> BulkPricingResponse:
        try:
            pricing_results = []
            total_original = Decimal('0.00')
            total_calculated = Decimal('0.00')
            
            for item_request in request.items:
                if request.context:
                    item_request.context = request.context
                
                try:
                    pricing_result = await recommendation_service.calculate_dynamic_price(item_request)
                    pricing_results.append(pricing_result)
                    total_original += pricing_result.original_price * item_request.quantity
                    total_calculated += pricing_result.calculated_price * item_request.quantity
                    
                except Exception as e:
                    logger.warning(f"AI pricing failed for item {item_request.menu_item_id}: {str(e)}")
                    if self.fallback_enabled:
                        fallback_result = self._create_fallback_pricing(item_request)
                        pricing_results.append(fallback_result)
                        total_original += fallback_result.original_price * item_request.quantity
                        total_calculated += fallback_result.calculated_price * item_request.quantity
                    else:
                        raise HTTPException(
                            status_code=503,
                            detail=f"Pricing service unavailable for item {item_request.menu_item_id}"
                        )
            
            total_savings = total_original - total_calculated
            
            return BulkPricingResponse(
                pricing_results=pricing_results,
                total_original_price=total_original,
                total_calculated_price=total_calculated,
                total_savings=total_savings
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in bulk pricing calculation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate bulk pricing"
            )
    
    async def apply_dynamic_pricing_to_order(
        self, 
        request: ApplyDynamicPricingRequest
    ) -> Dict[str, Any]:
        try:
            order = self.db.query(Order).filter(Order.id == request.order_id).first()
            if not order:
                raise HTTPException(
                    status_code=404,
                    detail=f"Order with id {request.order_id} not found"
                )
            
            if not order.order_items:
                raise HTTPException(
                    status_code=400,
                    detail="Order has no items to price"
                )
            
            context = self._build_pricing_context()
            
            bulk_request = BulkPricingRequest(
                items=[
                    DynamicPricingRequest(
                        menu_item_id=item.menu_item_id,
                        quantity=item.quantity,
                        base_price=item.price,
                        context=context
                    )
                    for item in order.order_items
                ],
                context=context
            )
            
            pricing_response = await self.calculate_dynamic_prices(bulk_request)
            
            updated_items = []
            for i, item in enumerate(order.order_items):
                pricing_result = pricing_response.pricing_results[i]
                
                if request.force_recalculate or item.pricing_type != PricingType.DYNAMIC.value:
                    item.original_price = item.price
                    item.price = pricing_result.calculated_price
                    item.pricing_type = PricingType.DYNAMIC.value
                    item.pricing_source = pricing_result.pricing_source
                    
                    if pricing_result.adjustments:
                        primary_adjustment = pricing_result.adjustments[0]
                        item.adjustment_reason = primary_adjustment.adjustment_type
                    
                    updated_items.append({
                        "item_id": item.id,
                        "menu_item_id": item.menu_item_id,
                        "original_price": float(item.original_price or item.price),
                        "new_price": float(item.price),
                        "adjustments": [adj.dict() for adj in pricing_result.adjustments]
                    })
            
            self.db.commit()
            
            self._log_pricing_decision(request.order_id, pricing_response, updated_items)
            
            return {
                "message": "Dynamic pricing applied successfully",
                "order_id": request.order_id,
                "updated_items": updated_items,
                "total_original_price": float(pricing_response.total_original_price),
                "total_calculated_price": float(pricing_response.total_calculated_price),
                "total_savings": float(pricing_response.total_savings)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error applying dynamic pricing to order {request.order_id}: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to apply dynamic pricing to order"
            )
    
    def _create_fallback_pricing(self, request: DynamicPricingRequest) -> DynamicPricingResponse:
        return DynamicPricingResponse(
            menu_item_id=request.menu_item_id,
            original_price=request.base_price,
            calculated_price=request.base_price,
            adjustments=[],
            confidence_score=1.0,
            pricing_source="static_fallback",
            timestamp=datetime.now()
        )
    
    def _build_pricing_context(self) -> PricingContext:
        current_hour = datetime.now().hour
        current_day = datetime.now().strftime("%A").lower()
        
        time_of_day = "off_peak"
        if 6 <= current_hour < 10:
            time_of_day = "breakfast"
        elif 11 <= current_hour < 15:
            time_of_day = "lunch"
        elif 17 <= current_hour < 22:
            time_of_day = "dinner"
        elif 22 <= current_hour or current_hour < 6:
            time_of_day = "late_night"
        
        demand_level = "medium"
        if current_day in ["friday", "saturday"]:
            demand_level = "high"
        elif current_day in ["monday", "tuesday"]:
            demand_level = "low"
        
        return PricingContext(
            time_of_day=time_of_day,
            day_of_week=current_day,
            demand_level=demand_level,
            inventory_level=75.0
        )
    
    def _log_pricing_decision(
        self, 
        order_id: int, 
        pricing_response: BulkPricingResponse, 
        updated_items: List[Dict[str, Any]]
    ):
        logger.info(f"Dynamic pricing applied to order {order_id}: "
                   f"Original: ${pricing_response.total_original_price}, "
                   f"Calculated: ${pricing_response.total_calculated_price}, "
                   f"Savings: ${pricing_response.total_savings}, "
                   f"Items updated: {len(updated_items)}")


async def get_pricing_service(db: Session) -> PricingService:
    return PricingService(db)
