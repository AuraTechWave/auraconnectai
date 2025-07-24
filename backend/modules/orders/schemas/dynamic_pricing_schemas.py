from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PricingContext(BaseModel):
    time_of_day: Optional[str] = None
    day_of_week: Optional[str] = None
    demand_level: Optional[str] = None
    inventory_level: Optional[float] = None
    weather: Optional[str] = None
    special_events: Optional[List[str]] = None


class DynamicPricingRequest(BaseModel):
    menu_item_id: int
    quantity: int
    base_price: Decimal
    context: Optional[PricingContext] = None


class PriceAdjustment(BaseModel):
    adjustment_type: str
    adjustment_amount: Decimal
    adjustment_percentage: Optional[float] = None
    reason: str


class DynamicPricingResponse(BaseModel):
    menu_item_id: int
    original_price: Decimal
    calculated_price: Decimal
    adjustments: List[PriceAdjustment]
    confidence_score: float
    pricing_source: str
    timestamp: datetime


class BulkPricingRequest(BaseModel):
    items: List[DynamicPricingRequest]
    context: Optional[PricingContext] = None


class BulkPricingResponse(BaseModel):
    pricing_results: List[DynamicPricingResponse]
    total_original_price: Decimal
    total_calculated_price: Decimal
    total_savings: Decimal


class ApplyDynamicPricingRequest(BaseModel):
    order_id: int
    force_recalculate: bool = False
