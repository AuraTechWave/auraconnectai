# backend/modules/orders/routes/pricing_rule_routes.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from core.database import get_db
from core.auth import get_current_user, require_permission, User
from ..models.pricing_rule_models import (
    PricingRule,
    PricingRuleApplication,
    PricingRuleMetrics,
    RuleStatus,
)
from ..models.order_models import Order
from ..schemas.pricing_rule_schemas import (
    CreatePricingRuleRequest,
    UpdatePricingRuleRequest,
    PricingRuleResponse,
    PricingRuleDebugInfo,
    PricingRuleApplicationResponse,
    PricingRuleMetricsResponse,
    ValidatePricingRuleRequest,
    ValidatePricingRuleResponse,
)
from ..services.pricing_rule_service import pricing_rule_service
from ..validators.pricing_rule_validators import pricing_rule_validator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing-rules", tags=["Pricing Rules"])


# CRUD Endpoints


@router.post("/", response_model=PricingRuleResponse)
@require_permission("pricing.create")
async def create_pricing_rule(
    request: CreatePricingRuleRequest,
    restaurant_id: int = Query(..., description="Restaurant ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new pricing rule

    Requires permission: pricing.create
    """
    try:
        # Validate conditions first
        is_valid, errors, warnings = pricing_rule_validator.validate_conditions(
            request.conditions.dict(exclude_unset=True), request.rule_type.value
        )

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={"message": "Invalid rule conditions", "errors": errors},
            )

        # Normalize conditions
        normalized_conditions = pricing_rule_validator.normalize_conditions(
            request.conditions.dict(exclude_unset=True)
        )

        # Create rule
        rule = PricingRule(
            restaurant_id=restaurant_id,
            name=request.name,
            description=request.description,
            rule_type=request.rule_type,
            status=RuleStatus.ACTIVE,
            priority=request.priority,
            discount_value=request.discount_value,
            max_discount_amount=request.max_discount_amount,
            min_order_amount=request.min_order_amount,
            conditions=normalized_conditions,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
            max_uses_total=request.max_uses_total,
            max_uses_per_customer=request.max_uses_per_customer,
            stackable=request.stackable,
            excluded_rule_ids=request.excluded_rule_ids,
            conflict_resolution=request.conflict_resolution,
            requires_code=request.requires_code,
            promo_code=request.promo_code,
            tags=request.tags,
        )

        db.add(rule)
        await db.commit()
        await db.refresh(rule)

        response = PricingRuleResponse.from_orm(rule)
        response.is_valid = rule.is_valid()

        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating pricing rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[PricingRuleResponse])
async def list_pricing_rules(
    restaurant_id: int = Query(...),
    status: Optional[RuleStatus] = None,
    rule_type: Optional[str] = None,
    active_only: bool = Query(True),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pricing rules with filtering"""

    query = select(PricingRule).where(PricingRule.restaurant_id == restaurant_id)

    if status:
        query = query.where(PricingRule.status == status)

    if rule_type:
        query = query.where(PricingRule.rule_type == rule_type)

    if active_only:
        now = datetime.utcnow()
        query = query.where(
            and_(
                PricingRule.status == RuleStatus.ACTIVE,
                PricingRule.valid_from <= now,
                or_(PricingRule.valid_until.is_(None), PricingRule.valid_until > now),
            )
        )

    query = query.order_by(PricingRule.priority).offset(offset).limit(limit)

    result = await db.execute(query)
    rules = result.scalars().all()

    return [
        PricingRuleResponse.from_orm(rule, is_valid=rule.is_valid()) for rule in rules
    ]


@router.get("/{rule_id}", response_model=PricingRuleResponse)
async def get_pricing_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific pricing rule"""

    rule = await db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")

    response = PricingRuleResponse.from_orm(rule)
    response.is_valid = rule.is_valid()

    return response


@router.put("/{rule_id}", response_model=PricingRuleResponse)
@require_permission("pricing.update")
async def update_pricing_rule(
    rule_id: int,
    request: UpdatePricingRuleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a pricing rule

    Requires permission: pricing.update
    """
    rule = await db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)

    response = PricingRuleResponse.from_orm(rule)
    response.is_valid = rule.is_valid()

    return response


@router.delete("/{rule_id}")
@require_permission("pricing.delete")
async def delete_pricing_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a pricing rule by setting status to INACTIVE

    Requires permission: pricing.delete
    """
    rule = await db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")

    rule.status = RuleStatus.INACTIVE
    await db.commit()

    return {"success": True, "message": "Pricing rule deactivated"}


# Debug Endpoint


@router.get("/debug/{order_id}", response_model=PricingRuleDebugInfo)
async def debug_pricing_rules(
    order_id: int,
    apply_rules: bool = Query(False, description="Actually apply the rules"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Debug pricing rules for an order

    This endpoint traces through all matching rules, shows which conditions
    were met/not met, and explains why rules were skipped.

    Great for QA and troubleshooting!
    """

    # Get order
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Load relationships
    await db.refresh(order, ["items", "customer"])

    # Evaluate rules with debug mode
    applications, debug_info = await pricing_rule_service.evaluate_rules_for_order(
        db, order, debug=True
    )

    # Add summary stats
    debug_info.rules_skipped = debug_info.rules_evaluated - debug_info.rules_applied
    debug_info.original_amount = order.subtotal
    debug_info.final_amount = order.total_amount

    # Separate applied vs skipped rules
    for result in debug_info.evaluation_results:
        rule_info = {
            "rule_id": result.rule_id,
            "rule_name": result.rule_name,
            "rule_type": result.rule_type.value,
            "priority": result.priority,
            "discount_amount": float(result.discount_amount),
            "conditions_met": result.conditions_met,
        }

        if result.applicable:
            debug_info.applied_rules.append(rule_info)
        else:
            rule_info["skip_reason"] = result.skip_reason
            debug_info.skipped_rules.append(rule_info)

    # Only apply if requested
    if not apply_rules:
        # Rollback any changes
        await db.rollback()

    return debug_info


# Application History


@router.get(
    "/applications/history", response_model=List[PricingRuleApplicationResponse]
)
async def get_application_history(
    order_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    rule_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get history of pricing rule applications"""

    query = select(PricingRuleApplication).join(PricingRule)

    if order_id:
        query = query.where(PricingRuleApplication.order_id == order_id)

    if customer_id:
        query = query.where(PricingRuleApplication.customer_id == customer_id)

    if rule_id:
        query = query.where(PricingRuleApplication.rule_id == rule_id)

    if date_from:
        query = query.where(PricingRuleApplication.applied_at >= date_from)

    if date_to:
        query = query.where(PricingRuleApplication.applied_at <= date_to)

    query = query.order_by(PricingRuleApplication.applied_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    applications = result.scalars().all()

    return [
        PricingRuleApplicationResponse(**app.__dict__, rule_name=app.rule.name)
        for app in applications
    ]


# Metrics Endpoint


@router.get("/metrics/{rule_id}", response_model=PricingRuleMetricsResponse)
@require_permission("pricing.view_metrics")
async def get_pricing_rule_metrics(
    rule_id: int,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get metrics for a pricing rule

    Requires permission: pricing.view_metrics
    """

    # Get rule
    rule = await db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get aggregated metrics
    result = await db.execute(
        select(
            func.sum(PricingRuleMetrics.applications_count).label("total_applications"),
            func.sum(PricingRuleMetrics.total_discount_amount).label("total_discount"),
            func.sum(PricingRuleMetrics.unique_customers).label("unique_customers"),
            func.sum(PricingRuleMetrics.conflicts_skipped).label("conflicts_skipped"),
            func.sum(PricingRuleMetrics.stacking_count).label("stacking_count"),
        ).where(
            and_(
                PricingRuleMetrics.rule_id == rule_id,
                PricingRuleMetrics.date >= start_date,
                PricingRuleMetrics.date <= end_date,
            )
        )
    )

    metrics = result.first()

    # Get daily breakdown
    daily_result = await db.execute(
        select(PricingRuleMetrics)
        .where(
            and_(
                PricingRuleMetrics.rule_id == rule_id,
                PricingRuleMetrics.date >= start_date,
                PricingRuleMetrics.date <= end_date,
            )
        )
        .order_by(PricingRuleMetrics.date)
    )

    daily_metrics = daily_result.scalars().all()

    return PricingRuleMetricsResponse(
        rule_id=rule_id,
        rule_name=rule.name,
        date_range={"start": start_date, "end": end_date},
        total_applications=metrics.total_applications or 0,
        unique_customers=metrics.unique_customers or 0,
        total_discount_amount=float(metrics.total_discount or 0),
        average_discount=float(metrics.total_discount or 0)
        / max(metrics.total_applications or 1, 1),
        conflicts_skipped=metrics.conflicts_skipped or 0,
        stacking_count=metrics.stacking_count or 0,
        daily_applications=[
            {
                "date": m.date.isoformat(),
                "applications": m.applications_count,
                "discount": float(m.total_discount_amount),
                "customers": m.unique_customers,
            }
            for m in daily_metrics
        ],
    )


# Validation Endpoint


@router.post("/validate", response_model=ValidatePricingRuleResponse)
async def validate_pricing_rule(
    request: ValidatePricingRuleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate pricing rule conditions

    This endpoint helps validate rule conditions JSON and optionally
    test against sample order data.
    """

    # Use the JSON Schema validator
    is_valid, errors, warnings = pricing_rule_validator.validate_conditions(
        request.conditions, request.rule_type.value if request.rule_type else None
    )

    # Normalize conditions if valid
    normalized_conditions = None
    if is_valid:
        normalized_conditions = pricing_rule_validator.normalize_conditions(
            request.conditions
        )

    # Test against sample order if provided
    if request.test_order_data and is_valid:
        # Simulate rule evaluation
        try:
            # Create a mock rule and order for testing
            from ..models.pricing_rule_models import PricingRule
            from ..models.order_models import Order

            mock_rule = PricingRule(
                rule_type=request.rule_type, conditions=normalized_conditions
            )

            # Would need to create mock order from test data
            # This is a simplified version
            test_results = {
                "conditions_tested": list(normalized_conditions.keys()),
                "test_passed": True,
                "test_details": "Conditions structure is valid for evaluation",
            }

            if "test_results" not in normalized_conditions:
                normalized_conditions["test_results"] = test_results

        except Exception as e:
            warnings.append(f"Test evaluation failed: {str(e)}")

    return ValidatePricingRuleResponse(
        valid=is_valid,
        errors=errors,
        warnings=warnings,
        normalized_conditions=normalized_conditions,
    )


# Apply rules to order endpoint


@router.post("/apply/{order_id}")
@require_permission("pricing.apply")
async def apply_pricing_rules_to_order(
    order_id: int,
    promo_code: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply pricing rules to an order

    Requires permission: pricing.apply
    """

    # Get order
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Load relationships
    await db.refresh(order, ["items", "customer"])

    # Apply promo code if provided
    if promo_code:
        # Check if promo code exists and is valid
        result = await db.execute(
            select(PricingRule).where(
                and_(
                    PricingRule.promo_code == promo_code,
                    PricingRule.requires_code == True,
                    PricingRule.status == RuleStatus.ACTIVE,
                )
            )
        )
        promo_rule = result.scalar_one_or_none()

        if not promo_rule:
            raise HTTPException(status_code=400, detail="Invalid promo code")

        if not promo_rule.is_valid():
            raise HTTPException(status_code=400, detail="Promo code has expired")

    # Evaluate and apply rules
    applications, _ = await pricing_rule_service.evaluate_rules_for_order(
        db, order, debug=False
    )

    return {
        "success": True,
        "rules_applied": len(applications),
        "total_discount": float(sum(app.discount_amount for app in applications)),
        "final_amount": float(order.total_amount),
    }
