import asyncio
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException
import random
import logging

from ..schemas.dynamic_pricing_schemas import (
    DynamicPricingRequest,
    DynamicPricingResponse,
    PriceAdjustment,
    PricingContext,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300

    async def calculate_dynamic_price(
        self, request: DynamicPricingRequest
    ) -> DynamicPricingResponse:
        try:
            cache_key = (
                f"{request.menu_item_id}_{request.quantity}_"
                f"{hash(str(request.context))}"
            )

            if cache_key in self.cache:
                cached_result, timestamp = self.cache[cache_key]
                if (datetime.utcnow() - timestamp).seconds < self.cache_ttl:
                    return cached_result

            await asyncio.sleep(0.1)

            adjustments = []
            calculated_price = request.base_price

            if request.context:
                if request.context.time_of_day:
                    time_adjustment = self._calculate_time_adjustment(
                        request.context.time_of_day
                    )
                    if time_adjustment != 0:
                        adjustment_amount = request.base_price * Decimal(
                            str(time_adjustment)
                        )
                        calculated_price += adjustment_amount
                        adjustments.append(
                            PriceAdjustment(
                                adjustment_type="time_based",
                                adjustment_amount=adjustment_amount,
                                adjustment_percentage=time_adjustment * 100,
                                reason=(
                                    f"Time-based adjustment for "
                                    f"{request.context.time_of_day}"
                                ),
                            )
                        )

                if request.context.demand_level:
                    demand_adjustment = self._calculate_demand_adjustment(
                        request.context.demand_level
                    )
                    if demand_adjustment != 0:
                        adjustment_amount = request.base_price * Decimal(
                            str(demand_adjustment)
                        )
                        calculated_price += adjustment_amount
                        adjustments.append(
                            PriceAdjustment(
                                adjustment_type="demand",
                                adjustment_amount=adjustment_amount,
                                adjustment_percentage=demand_adjustment * 100,
                                reason=(
                                    f"Demand-based adjustment for "
                                    f"{request.context.demand_level} demand"
                                ),
                            )
                        )

                if request.context.inventory_level is not None:
                    inventory_adjustment = self._calculate_inventory_adjustment(
                        request.context.inventory_level
                    )
                    if inventory_adjustment != 0:
                        adjustment_amount = request.base_price * Decimal(
                            str(inventory_adjustment)
                        )
                        calculated_price += adjustment_amount
                        adjustments.append(
                            PriceAdjustment(
                                adjustment_type="inventory",
                                adjustment_amount=adjustment_amount,
                                adjustment_percentage=inventory_adjustment * 100,
                                reason=(
                                    f"Inventory-based adjustment for "
                                    f"{request.context.inventory_level}% "
                                    f"stock level"
                                ),
                            )
                        )

            calculated_price = max(
                calculated_price, request.base_price * Decimal("0.5")
            )
            calculated_price = min(
                calculated_price, request.base_price * Decimal("2.0")
            )

            response = DynamicPricingResponse(
                menu_item_id=request.menu_item_id,
                original_price=request.base_price,
                calculated_price=calculated_price,
                adjustments=adjustments,
                confidence_score=random.uniform(0.7, 0.95),
                pricing_source="ai_recommendation_service",
                timestamp=datetime.utcnow(),
            )

            self.cache[cache_key] = (response, datetime.utcnow())

            return response

        except Exception as e:
            logger.error(f"Error calculating dynamic price: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to calculate dynamic price"
            )

    def _calculate_time_adjustment(self, time_of_day: str) -> float:
        time_adjustments = {
            "breakfast": -0.05,
            "lunch": 0.10,
            "dinner": 0.15,
            "late_night": -0.10,
            "peak": 0.20,
            "off_peak": -0.05,
        }
        return time_adjustments.get(time_of_day.lower(), 0.0)

    def _calculate_demand_adjustment(self, demand_level: str) -> float:
        demand_adjustments = {
            "low": -0.10,
            "medium": 0.0,
            "high": 0.15,
            "very_high": 0.25,
        }
        return demand_adjustments.get(demand_level.lower(), 0.0)

    def _calculate_inventory_adjustment(self, inventory_level: float) -> float:
        if inventory_level < 20:
            return 0.10
        elif inventory_level < 50:
            return 0.05
        elif inventory_level > 90:
            return -0.05
        return 0.0

    async def get_menu_suggestions(self, context: PricingContext) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        return {
            "suggested_items": [101, 102, 103],
            "promotional_items": [201, 202],
            "context": context.dict() if context else {},
        }


recommendation_service = RecommendationService()
