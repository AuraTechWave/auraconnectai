# backend/modules/analytics/routers/predictive/stock_router.py

"""
Stock optimization endpoints for predictive analytics.

Handles inventory optimization and stock recommendations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.modules.analytics.schemas.predictive_analytics_schemas import (
    StockOptimizationRequest, StockOptimizationResult,
    InventoryHealthCheck, InventoryHealthReport
)
from backend.modules.analytics.services.stock_optimization_service import StockOptimizationService
from backend.modules.analytics.services.permissions import require_analytics_permission
from backend.modules.analytics.constants import (
    MAX_PRODUCTS_PER_OPTIMIZATION,
    DEFAULT_SERVICE_LEVEL,
    MIN_SERVICE_LEVEL,
    MAX_SERVICE_LEVEL
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stock", tags=["predictive-stock"])


@router.post("/optimize", response_model=StockOptimizationResult)
async def optimize_stock_levels(
    request: StockOptimizationRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> StockOptimizationResult:
    """
    Optimize stock levels for selected products.
    
    Args:
        request: Stock optimization parameters
        
    Returns:
        StockOptimizationResult with recommendations
        
    Example Response:
        {
            "recommendations": [
                {
                    "product_id": 1,
                    "product_name": "Espresso Beans",
                    "current_stock": 50,
                    "recommended_stock": 120,
                    "reorder_point": 80,
                    "reorder_quantity": 100,
                    "safety_stock": 40,
                    "expected_stockout_risk": 0.05,
                    "investment_required": 700.00,
                    "reasoning": "Based on 20 daily demand with 2-day lead time"
                }
            ],
            "total_investment_required": 2100.00,
            "expected_service_level": 0.95,
            "optimization_summary": {
                "products_analyzed": 3,
                "products_needing_reorder": 2,
                "potential_cost_savings": 150.00
            }
        }
    
    Raises:
        HTTPException: 400 if invalid parameters, 403 if unauthorized
    """
    require_analytics_permission(current_user, "manage_inventory")
    
    # Validate request
    if len(request.product_ids) > MAX_PRODUCTS_PER_OPTIMIZATION:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PRODUCTS_PER_OPTIMIZATION} products per optimization"
        )
    
    if request.service_level:
        if not MIN_SERVICE_LEVEL <= request.service_level <= MAX_SERVICE_LEVEL:
            raise HTTPException(
                status_code=400,
                detail=f"Service level must be between {MIN_SERVICE_LEVEL} and {MAX_SERVICE_LEVEL}"
            )
    
    try:
        service = StockOptimizationService(db)
        result = await service.optimize_stock_levels(request)
        
        logger.info(
            f"Stock optimization completed for {len(request.product_ids)} products "
            f"by user {current_user.id}"
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid optimization request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Stock optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Stock optimization failed. Please try again later."
        )


@router.post("/health-check", response_model=InventoryHealthReport)
async def check_inventory_health(
    request: InventoryHealthCheck,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> InventoryHealthReport:
    """
    Perform comprehensive inventory health check.
    
    Args:
        request: Health check parameters
        
    Returns:
        InventoryHealthReport with issues and recommendations
        
    Example Response:
        {
            "overall_health_score": 75.5,
            "total_products_analyzed": 50,
            "critical_issues": [
                {
                    "issue_type": "stockout_imminent",
                    "severity": "critical",
                    "affected_products": [1, 3, 5],
                    "description": "3 products will stock out within 2 days",
                    "recommended_action": "Expedite orders immediately"
                }
            ],
            "warnings": [
                {
                    "issue_type": "overstock",
                    "severity": "medium",
                    "affected_products": [10, 15],
                    "description": "2 products have excess inventory",
                    "recommended_action": "Consider promotions"
                }
            ],
            "metrics": {
                "stockout_rate": 0.06,
                "overstock_rate": 0.04,
                "dead_stock_value": 500.00,
                "inventory_turnover": 12.5
            }
        }
    """
    require_analytics_permission(current_user, "view_inventory_analytics")
    
    try:
        service = StockOptimizationService(db)
        report = await service.check_inventory_health(request)
        
        return report
        
    except Exception as e:
        logger.error(f"Inventory health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Health check failed. Please try again later."
        )


@router.get("/reorder-alerts", response_model=List[dict])
async def get_reorder_alerts(
    days_ahead: int = Query(7, ge=1, le=30, description="Days to look ahead"),
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> List[dict]:
    """
    Get products that need reordering within specified timeframe.
    
    Args:
        days_ahead: Number of days to look ahead
        severity: Filter by alert severity
        
    Returns:
        List of reorder alerts
        
    Example Response:
        [
            {
                "product_id": 1,
                "product_name": "Coffee Beans",
                "current_stock": 20,
                "daily_usage": 10,
                "days_until_stockout": 2,
                "reorder_point": 30,
                "suggested_order_quantity": 100,
                "severity": "high",
                "estimated_stockout_date": "2024-02-03"
            }
        ]
    """
    require_analytics_permission(current_user, "view_inventory_analytics")
    
    try:
        service = StockOptimizationService(db)
        alerts = await service.get_reorder_alerts(
            days_ahead=days_ahead,
            severity_filter=severity
        )
        
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to get reorder alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve reorder alerts."
        )


@router.post("/eoq-calculate")
async def calculate_eoq(
    product_id: int,
    annual_demand: float = Query(..., gt=0, description="Annual demand quantity"),
    ordering_cost: float = Query(..., gt=0, description="Cost per order"),
    holding_cost_rate: float = Query(0.2, gt=0, le=1, description="Annual holding cost rate"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> dict:
    """
    Calculate Economic Order Quantity for a product.
    
    Args:
        product_id: Product to calculate EOQ for
        annual_demand: Expected annual demand
        ordering_cost: Fixed cost per order
        holding_cost_rate: Annual holding cost as percentage of product cost
        
    Returns:
        EOQ calculation results
        
    Example Response:
        {
            "product_id": 1,
            "product_name": "Coffee Beans",
            "eoq": 316,
            "annual_ordering_cost": 632.45,
            "annual_holding_cost": 632.45,
            "total_annual_cost": 1264.90,
            "orders_per_year": 12.6,
            "days_between_orders": 29
        }
    """
    require_analytics_permission(current_user, "view_inventory_analytics")
    
    try:
        service = StockOptimizationService(db)
        result = await service.calculate_eoq_for_product(
            product_id=product_id,
            annual_demand=annual_demand,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid EOQ calculation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"EOQ calculation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="EOQ calculation failed."
        )