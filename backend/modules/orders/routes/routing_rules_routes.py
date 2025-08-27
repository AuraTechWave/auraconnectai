"""
API routes for order routing rules management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session

from core.database import get_db
from core.decorators import handle_api_errors
from core.auth import get_current_user
from core.rbac_models import RBACUser as User
from ..models.routing_models import RuleStatus, RouteTargetType
from ..schemas.routing_schemas import (
    RoutingRuleCreate,
    RoutingRuleUpdate,
    RoutingRuleResponse,
    RouteEvaluationRequest,
    RouteEvaluationResult,
    RouteOverrideCreate,
    RouteOverrideResponse,
    StaffCapabilityCreate,
    StaffCapabilityResponse,
    TeamRoutingConfigCreate,
    TeamRoutingConfigResponse,
    TeamMemberCreate,
    TeamMemberResponse,
    RoutingRuleTestRequest,
    RoutingRuleTestResult,
    RoutingLogQuery,
    RoutingLogResponse,
    BulkRuleStatusUpdate,
)
from ..services.routing_rule_service import RoutingRuleService

router = APIRouter(prefix="/api/v1/orders/routing", tags=["order-routing"])


# Rule Management Endpoints
@router.post("/rules", response_model=RoutingRuleResponse)
@handle_api_errors
async def create_routing_rule(
    rule_data: RoutingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new order routing rule.

    Rules consist of:
    - Conditions: What to match (order type, customer, items, etc.)
    - Actions: What to do when matched (route, notify, split, etc.)
    - Target: Where to route (station, staff, team, queue)

    Rules are evaluated in priority order (highest first).
    """
    service = RoutingRuleService(db)
    return service.create_routing_rule(rule_data, current_user.id)


@router.get("/rules", response_model=List[RoutingRuleResponse])
@handle_api_errors
async def list_routing_rules(
    status: Optional[RuleStatus] = Query(None, description="Filter by rule status"),
    target_type: Optional[RouteTargetType] = Query(
        None, description="Filter by target type"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all routing rules with optional filters.

    Returns rules ordered by priority (highest first).
    """
    service = RoutingRuleService(db)
    return service.list_routing_rules(status, target_type, limit, offset)


@router.get("/rules/{rule_id}", response_model=RoutingRuleResponse)
@handle_api_errors
async def get_routing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific routing rule with all conditions and actions.
    """
    service = RoutingRuleService(db)
    return service.get_routing_rule(rule_id)


@router.put("/rules/{rule_id}", response_model=RoutingRuleResponse)
@handle_api_errors
async def update_routing_rule(
    rule_id: int,
    update_data: RoutingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a routing rule.

    Note: To update conditions or actions, use the dedicated endpoints.
    """
    service = RoutingRuleService(db)
    return service.update_routing_rule(rule_id, update_data, current_user.id)


@router.delete("/rules/{rule_id}")
@handle_api_errors
async def delete_routing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a routing rule and all its conditions and actions.
    """
    service = RoutingRuleService(db)
    service.delete_routing_rule(rule_id)
    return {"message": f"Routing rule {rule_id} deleted successfully"}


@router.post("/rules/bulk/status", response_model=dict)
@handle_api_errors
async def bulk_update_rule_status(
    bulk_update: BulkRuleStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update status for multiple rules at once.

    Useful for:
    - Activating/deactivating rule sets
    - Emergency disabling of rules
    - Testing rule combinations
    """
    service = RoutingRuleService(db)
    updated_count = 0

    for rule_id in bulk_update.rule_ids:
        try:
            update = RoutingRuleUpdate(status=bulk_update.status)
            service.update_routing_rule(rule_id, update, current_user.id)
            updated_count += 1
        except:
            pass

    return {
        "updated_count": updated_count,
        "total_requested": len(bulk_update.rule_ids),
        "new_status": bulk_update.status.value,
    }


# Rule Evaluation Endpoints
@router.post("/evaluate", response_model=RouteEvaluationResult)
@handle_api_errors
async def evaluate_order_routing(
    evaluation_request: RouteEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate routing rules for an order and determine where to route it.

    This endpoint:
    1. Checks for manual overrides
    2. Evaluates all active rules in priority order
    3. Returns the routing decision
    4. Optionally applies the routing (if not in test mode)
    """
    service = RoutingRuleService(db)
    return service.evaluate_order_routing(evaluation_request)


@router.post("/test", response_model=RoutingRuleTestResult)
@handle_api_errors
async def test_routing_rules(
    test_request: RoutingRuleTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test routing rules with mock order data.

    Useful for:
    - Testing new rules before activation
    - Debugging rule conditions
    - Simulating different order scenarios
    """
    service = RoutingRuleService(db)
    return service.test_routing_rules(test_request)


# Override Management
@router.post("/overrides", response_model=RouteOverrideResponse)
@handle_api_errors
async def create_route_override(
    override_data: RouteOverrideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a manual routing override for an order.

    Overrides bypass all routing rules and force routing to a specific target.
    Can be temporary (with expiration) or permanent.
    """
    service = RoutingRuleService(db)
    return service.create_route_override(override_data, current_user.id)


@router.get(
    "/overrides/order/{order_id}", response_model=Optional[RouteOverrideResponse]
)
@handle_api_errors
async def get_order_override(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get active routing override for an order (if any).
    """
    from ..models.routing_models import RouteOverride
    from sqlalchemy import or_
    from datetime import datetime

    override = (
        db.query(RouteOverride)
        .filter(
            RouteOverride.order_id == order_id,
            or_(
                RouteOverride.expires_at.is_(None),
                RouteOverride.expires_at > datetime.utcnow(),
            ),
        )
        .first()
    )

    return override


@router.delete("/overrides/order/{order_id}")
@handle_api_errors
async def delete_order_override(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove routing override for an order.
    """
    from ..models.routing_models import RouteOverride

    override = (
        db.query(RouteOverride).filter(RouteOverride.order_id == order_id).first()
    )

    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No override found for order {order_id}",
        )

    db.delete(override)
    db.commit()

    return {"message": f"Override for order {order_id} removed"}


# Staff Capability Management
@router.post("/staff/capabilities", response_model=StaffCapabilityResponse)
@handle_api_errors
async def create_staff_capability(
    capability_data: StaffCapabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Define a routing capability for a staff member.

    Capabilities define what types of orders a staff member can handle:
    - Categories (e.g., "grill", "salad", "dessert")
    - Skills (e.g., "sushi_chef", "bartender")
    - Certifications (e.g., "alcohol_service", "allergen_handling")
    """
    service = RoutingRuleService(db)
    return service.create_staff_capability(capability_data)


@router.get(
    "/staff/{staff_id}/capabilities", response_model=List[StaffCapabilityResponse]
)
@handle_api_errors
async def get_staff_capabilities(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all routing capabilities for a staff member.
    """
    service = RoutingRuleService(db)
    return service.get_staff_capabilities(staff_id)


@router.put("/staff/capabilities/{capability_id}/availability")
@handle_api_errors
async def update_capability_availability(
    capability_id: int,
    is_available: bool = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update availability of a staff capability.

    Useful for temporarily disabling capabilities (e.g., equipment down, staff break).
    """
    from ..models.routing_models import StaffRoutingCapability

    capability = (
        db.query(StaffRoutingCapability)
        .filter(StaffRoutingCapability.id == capability_id)
        .first()
    )

    if not capability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )

    capability.is_available = is_available
    db.commit()

    return {
        "capability_id": capability_id,
        "is_available": is_available,
        "message": f"Capability {'enabled' if is_available else 'disabled'}",
    }


# Team Management
@router.post("/teams", response_model=TeamRoutingConfigResponse)
@handle_api_errors
async def create_routing_team(
    team_data: TeamRoutingConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a routing team for load balancing.

    Teams can use different routing strategies:
    - round_robin: Distribute evenly
    - least_loaded: Send to member with fewest orders
    - skill_based: Match order requirements to member skills
    """
    service = RoutingRuleService(db)
    return service.create_team(team_data)


@router.get("/teams", response_model=List[TeamRoutingConfigResponse])
@handle_api_errors
async def list_routing_teams(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all routing teams.
    """
    from ..models.routing_models import TeamRoutingConfig

    query = db.query(TeamRoutingConfig)
    if is_active is not None:
        query = query.filter(TeamRoutingConfig.is_active == is_active)

    return query.all()


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
@handle_api_errors
async def add_team_member(
    team_id: int,
    member_data: TeamMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a staff member to a routing team.
    """
    if member_data.team_id != team_id:
        member_data.team_id = team_id

    service = RoutingRuleService(db)
    return service.add_team_member(member_data)


@router.get("/teams/{team_id}/members", response_model=List[TeamMemberResponse])
@handle_api_errors
async def get_team_members(
    team_id: int,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all members of a routing team.
    """
    from ..models.routing_models import TeamMember

    query = db.query(TeamMember).filter(TeamMember.team_id == team_id)
    if not include_inactive:
        query = query.filter(TeamMember.is_active == True)

    return query.all()


# Routing Logs and Analytics
@router.post("/logs/query", response_model=List[RoutingLogResponse])
@handle_api_errors
async def query_routing_logs(
    query_params: RoutingLogQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Query routing rule evaluation logs.

    Useful for:
    - Debugging rule behavior
    - Performance monitoring
    - Audit trails
    """
    from ..models.routing_models import RoutingRuleLog

    query = db.query(RoutingRuleLog)

    if query_params.rule_id:
        query = query.filter(RoutingRuleLog.rule_id == query_params.rule_id)

    if query_params.order_id:
        query = query.filter(RoutingRuleLog.order_id == query_params.order_id)

    if query_params.matched_only:
        query = query.filter(RoutingRuleLog.matched == True)

    if query_params.error_only:
        query = query.filter(RoutingRuleLog.error_occurred == True)

    if query_params.start_date:
        query = query.filter(RoutingRuleLog.created_at >= query_params.start_date)

    if query_params.end_date:
        query = query.filter(RoutingRuleLog.created_at <= query_params.end_date)

    return (
        query.order_by(RoutingRuleLog.created_at.desc())
        .offset(query_params.offset)
        .limit(query_params.limit)
        .all()
    )


@router.get("/conflicts")
@handle_api_errors
async def check_rule_conflicts(
    rule_id: Optional[int] = Query(
        None, description="Check conflicts for specific rule"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check for conflicts between routing rules.

    Detects:
    - Priority conflicts (rules with same priority)
    - Condition overlaps (rules that could match same orders)

    Returns list of potential conflicts with severity levels.
    """
    service = RoutingRuleService(db)
    conflicts = service.detect_rule_conflicts(rule_id)

    return {
        "rule_id": rule_id,
        "total_conflicts": len(conflicts),
        "conflicts": conflicts,
        "summary": {
            "high_severity": len([c for c in conflicts if c.get("severity") == "high"]),
            "medium_severity": len(
                [c for c in conflicts if c.get("severity") == "medium"]
            ),
            "low_severity": len([c for c in conflicts if c.get("severity") == "low"]),
        },
    }


@router.get("/analytics/rule-performance")
@handle_api_errors
async def get_rule_performance_analytics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get performance analytics for routing rules.

    Returns:
    - Match rates for each rule
    - Average evaluation times
    - Most/least used rules
    - Error rates
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from ..models.routing_models import OrderRoutingRule, RoutingRuleLog

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get rule statistics
    rule_stats = (
        db.query(
            RoutingRuleLog.rule_id,
            OrderRoutingRule.name,
            func.count(RoutingRuleLog.id).label("total_evaluations"),
            func.sum(func.cast(RoutingRuleLog.matched, type_=db.Integer)).label(
                "match_count"
            ),
            func.avg(RoutingRuleLog.evaluation_time_ms).label("avg_eval_time"),
            func.sum(func.cast(RoutingRuleLog.error_occurred, type_=db.Integer)).label(
                "error_count"
            ),
        )
        .join(OrderRoutingRule, OrderRoutingRule.id == RoutingRuleLog.rule_id)
        .filter(RoutingRuleLog.created_at >= cutoff_date)
        .group_by(RoutingRuleLog.rule_id, OrderRoutingRule.name)
        .all()
    )

    # Format results
    results = []
    for stat in rule_stats:
        match_rate = (
            (stat.match_count / stat.total_evaluations * 100)
            if stat.total_evaluations > 0
            else 0
        )
        error_rate = (
            (stat.error_count / stat.total_evaluations * 100)
            if stat.total_evaluations > 0
            else 0
        )

        results.append(
            {
                "rule_id": stat.rule_id,
                "rule_name": stat.name,
                "total_evaluations": stat.total_evaluations,
                "match_count": stat.match_count,
                "match_rate": round(match_rate, 2),
                "avg_evaluation_time_ms": (
                    round(stat.avg_eval_time, 2) if stat.avg_eval_time else 0
                ),
                "error_count": stat.error_count,
                "error_rate": round(error_rate, 2),
            }
        )

    # Sort by match count
    results.sort(key=lambda x: x["match_count"], reverse=True)

    return {
        "period_days": days,
        "rule_performance": results,
        "summary": {
            "total_rules": len(results),
            "active_rules": len([r for r in results if r["total_evaluations"] > 0]),
            "avg_match_rate": (
                round(sum(r["match_rate"] for r in results) / len(results), 2)
                if results
                else 0
            ),
        },
    }
