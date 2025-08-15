from __future__ import annotations

"""backend/modules/menu/utils/dynamic_pricing_utils.py

Utility helpers to calculate dynamic pricing for menu items.  
This integrates with the existing AI recommendation / pricing engine that
already powers order-level dynamic pricing.  The helpers are intentionally
kept light-weight so they can be imported from synchronous as well as
asynchronous contexts (only the top-level `apply_dynamic_pricing` coroutine
is async).
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Dict, Any

# The recommendation & pricing primitives already exist in the orders module
from backend.modules.orders.services.ai_recommendation_service import (
    recommendation_service,
)
from backend.modules.orders.schemas.dynamic_pricing_schemas import (
    DynamicPricingRequest,
    PricingContext,
)

__all__ = [
    "build_pricing_context",
    "apply_dynamic_pricing",
]


def build_pricing_context() -> PricingContext:
    """Return a PricingContext capturing the current time-of-day, weekday,
    and a coarse demand / inventory estimate.

    This logic replicates the `_build_pricing_context` method that the orders
    module already uses so that menu-level dynamic pricing remains consistent
    with order-level pricing decisions.
    """

    now_utc = datetime.utcnow()
    current_hour = now_utc.hour
    current_day = now_utc.strftime("%A").lower()

    # --- Time-of-day bucket ----------------------------------------------
    if 6 <= current_hour < 10:
        time_of_day = "breakfast"
    elif 11 <= current_hour < 15:
        time_of_day = "lunch"
    elif 17 <= current_hour < 22:
        time_of_day = "dinner"
    elif 22 <= current_hour or current_hour < 6:
        time_of_day = "late_night"
    else:
        time_of_day = "off_peak"

    # --- Demand level heuristic ------------------------------------------
    if current_day in {"friday", "saturday"}:
        demand_level = "high"
    elif current_day in {"monday", "tuesday"}:
        demand_level = "low"
    else:
        demand_level = "medium"

    # NOTE: Inventory data is not yet wired through, so we use a placeholder.
    # This will be replaced once the Inventory → Menu integration is ready.
    inventory_level = 75.0  # percent in stock

    return PricingContext(
        time_of_day=time_of_day,
        day_of_week=current_day,
        demand_level=demand_level,
        inventory_level=inventory_level,
    )


async def apply_dynamic_pricing(
    items: Iterable[Any],
) -> Dict[int, float]:
    """Calculate dynamic prices for the supplied menu *SQLAlchemy* objects.

    Parameters
    ----------
    items:
        An iterable of `MenuItem` SQLAlchemy instances.  Only the `id` and
        `price` attributes are accessed, so the helper remains decoupled from
        the concrete model definition.

    Returns
    -------
    Dict[int, float]
        Mapping of *menu_item_id* → *calculated dynamic price* (as float).
        When the pricing engine fails for a specific item, the original price
        is returned so that menu rendering proceeds gracefully.
    """

    context = build_pricing_context()

    # Build dynamic-pricing requests for all items
    requests = [
        DynamicPricingRequest(
            menu_item_id=item.id,
            quantity=1,
            base_price=Decimal(str(item.price)),
            context=context,
        )
        for item in items
    ]

    # Kick off all calculations concurrently
    tasks = [recommendation_service.calculate_dynamic_price(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Map id → calculated price, falling back to original on error
    adjusted: Dict[int, float] = {}
    for item, res in zip(items, results):
        if isinstance(res, Exception):
            adjusted[item.id] = float(item.price)
        else:
            adjusted[item.id] = float(res.calculated_price)
    return adjusted
