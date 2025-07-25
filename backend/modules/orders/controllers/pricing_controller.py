from sqlalchemy.orm import Session
from typing import Dict, Any

from ..services.pricing_service import get_pricing_service
from ..schemas.dynamic_pricing_schemas import (
    BulkPricingRequest, BulkPricingResponse, ApplyDynamicPricingRequest
)


async def calculate_pricing(
    request: BulkPricingRequest,
    db: Session
) -> BulkPricingResponse:
    pricing_service = await get_pricing_service(db)
    return await pricing_service.calculate_dynamic_prices(request)


async def apply_dynamic_pricing(
    request: ApplyDynamicPricingRequest,
    db: Session
) -> Dict[str, Any]:
    pricing_service = await get_pricing_service(db)
    return await pricing_service.apply_dynamic_pricing_to_order(request)
