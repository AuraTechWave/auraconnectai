from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.pricing_controller import (
    calculate_pricing, apply_dynamic_pricing
)
from ..schemas.dynamic_pricing_schemas import (
    BulkPricingRequest, BulkPricingResponse, ApplyDynamicPricingRequest
)

router = APIRouter(prefix="/orders/pricing", tags=["Dynamic Pricing"])


@router.post("/calculate", response_model=BulkPricingResponse)
async def calculate_dynamic_prices(
    request: BulkPricingRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate dynamic prices for menu items based on AI recommendations.

    - **items**: List of menu items with quantities and base prices
    - **context**: Optional pricing context (time, demand, inventory levels)

    Returns calculated prices with adjustment details and confidence scores.
    Uses AI-driven pricing when available, falls back to static pricing
    if needed.
    """
    return await calculate_pricing(request, db)


@router.put("/{order_id}/apply-dynamic-pricing")
async def apply_dynamic_pricing_to_order(
    order_id: int,
    force_recalculate: bool = False,
    db: Session = Depends(get_db)
):
    """
    Apply dynamic pricing to an existing order.

    - **order_id**: ID of the order to update with dynamic pricing
    - **force_recalculate**: Whether to recalculate prices even if already
      dynamic

    Updates order items with AI-calculated prices and returns pricing details.
    Maintains audit trail of original prices and adjustment reasons.
    """
    request = ApplyDynamicPricingRequest(
        order_id=order_id,
        force_recalculate=force_recalculate
    )
    return await apply_dynamic_pricing(request, db)
