# backend/modules/insights/routes/insights_routes.py

"""
Insights module routes for business intelligence and analytics.
"""

from fastapi import APIRouter, Depends, Query, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from core.database import get_db
from core.auth import get_current_user
from core.error_handling import handle_api_errors, NotFoundError, APIValidationError
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services.insights_service import InsightsService
from ..services.notification_service import InsightNotificationService
from ..services.rating_service import InsightRatingService
from ..services.thread_service import InsightThreadService
from ..schemas.insight_schemas import (
    InsightCreate,
    InsightUpdate,
    InsightResponse,
    InsightListResponse,
    InsightFilters,
    InsightBatchAction,
    InsightSummary,
    InsightRatingCreate,
    InsightRatingResponse,
    InsightActionCreate,
    InsightActionResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationRuleResponse,
    InsightThreadResponse,
    ThreadFilters,
)
from ..models.insight_models import (
    InsightType,
    InsightSeverity,
    InsightStatus,
    InsightDomain,
)

router = APIRouter(prefix="/api/v1/insights", tags=["Insights"])


# ========== Insights CRUD ==========


@router.post("/", response_model=InsightResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_insight(
    insight_data: InsightCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new insight (usually system-generated).

    Returns:
        Created insight

    Raises:
        403: Insufficient permissions
        422: Validation error
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    service = InsightsService(db)
    insight = service.create_insight(
        insight_data, generated_by=f"user_{current_user.id}"
    )

    # Send notifications if configured
    notification_service = InsightNotificationService(db)
    await notification_service.process_new_insight(insight)

    return insight


@router.get("/", response_model=InsightListResponse)
@handle_api_errors
async def list_insights(
    # Filters
    domain: Optional[InsightDomain] = Query(
        None, description="Filter by business domain"
    ),
    type: Optional[InsightType] = Query(None, description="Filter by insight type"),
    severity: Optional[InsightSeverity] = Query(None, description="Filter by severity"),
    status: Optional[InsightStatus] = Query(None, description="Filter by status"),
    thread_id: Optional[str] = Query(None, description="Filter by thread ID"),
    date_from: Optional[date] = Query(None, description="Filter insights from date"),
    date_to: Optional[date] = Query(None, description="Filter insights to date"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    # Pagination
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    # Sorting
    sort_by: str = Query(
        "created_at", pattern="^(created_at|severity|impact_score|estimated_value)$"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List insights with comprehensive filters.

    Returns:
        Paginated list of insights

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    filters = InsightFilters(
        domain=domain,
        type=type,
        severity=severity,
        status=status,
        thread_id=thread_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        restaurant_id=current_user.restaurant_id,
    )

    service = InsightsService(db)
    insights, total = service.list_insights(
        filters=filters,
        skip=(page - 1) * size,
        limit=size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return InsightListResponse(
        items=insights,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/summary", response_model=InsightSummary)
@handle_api_errors
async def get_insights_summary(
    domain: Optional[InsightDomain] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get summary statistics for insights.

    Returns:
        Insight summary with counts and trends

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    return service.get_insights_summary(
        restaurant_id=current_user.restaurant_id, domain=domain, days=days
    )


@router.get("/{insight_id}", response_model=InsightResponse)
@handle_api_errors
async def get_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific insight by ID.

    Returns:
        Insight details

    Raises:
        403: Insufficient permissions
        404: Insight not found
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    insight = service.get_insight(insight_id)

    if not insight:
        raise NotFoundError("Insight", insight_id)

    # Verify restaurant access
    if insight.restaurant_id != current_user.restaurant_id:
        raise NotFoundError("Insight", insight_id)

    return insight


@router.put("/{insight_id}", response_model=InsightResponse)
@handle_api_errors
async def update_insight(
    insight_id: int,
    update_data: InsightUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an insight.

    Returns:
        Updated insight

    Raises:
        403: Insufficient permissions
        404: Insight not found
        422: Invalid status transition
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    service = InsightsService(db)
    insight = service.get_insight(insight_id)

    if not insight:
        raise NotFoundError("Insight", insight_id)

    if insight.restaurant_id != current_user.restaurant_id:
        raise NotFoundError("Insight", insight_id)

    # Validate status transitions
    if update_data.status:
        valid_transitions = {
            InsightStatus.ACTIVE: [
                InsightStatus.ACKNOWLEDGED,
                InsightStatus.RESOLVED,
                InsightStatus.DISMISSED,
            ],
            InsightStatus.ACKNOWLEDGED: [
                InsightStatus.RESOLVED,
                InsightStatus.DISMISSED,
            ],
            InsightStatus.RESOLVED: [],
            InsightStatus.DISMISSED: [],
            InsightStatus.EXPIRED: [],
        }

        if update_data.status not in valid_transitions.get(insight.status, []):
            raise APIValidationError(
                f"Invalid status transition from {insight.status} to {update_data.status}",
                {
                    "current_status": insight.status,
                    "requested_status": update_data.status,
                },
            )

    return service.update_insight(insight_id, update_data, current_user.id)


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an insight (soft delete).

    Returns:
        No content on success

    Raises:
        403: Insufficient permissions
        404: Insight not found
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    service = InsightsService(db)
    insight = service.get_insight(insight_id)

    if not insight:
        raise NotFoundError("Insight", insight_id)

    if insight.restaurant_id != current_user.restaurant_id:
        raise NotFoundError("Insight", insight_id)

    service.delete_insight(insight_id)


# ========== Batch Operations ==========


@router.post("/batch/acknowledge", response_model=Dict[str, Any])
@handle_api_errors
async def batch_acknowledge_insights(
    action: InsightBatchAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Acknowledge multiple insights at once.

    Returns:
        Operation summary

    Raises:
        403: Insufficient permissions
        422: Invalid insight IDs
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    service = InsightsService(db)
    success_count = 0
    errors = []

    for insight_id in action.insight_ids:
        try:
            insight = service.get_insight(insight_id)
            if insight and insight.restaurant_id == current_user.restaurant_id:
                service.acknowledge_insight(insight_id, current_user.id)
                success_count += 1
            else:
                errors.append({"id": insight_id, "error": "Not found or access denied"})
        except Exception as e:
            errors.append({"id": insight_id, "error": str(e)})

    return {
        "success_count": success_count,
        "errors": errors,
        "message": f"Acknowledged {success_count} insights",
    }


@router.post("/batch/dismiss", response_model=Dict[str, Any])
@handle_api_errors
async def batch_dismiss_insights(
    action: InsightBatchAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dismiss multiple insights at once.

    Returns:
        Operation summary

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    service = InsightsService(db)
    success_count = 0
    errors = []

    for insight_id in action.insight_ids:
        try:
            insight = service.get_insight(insight_id)
            if insight and insight.restaurant_id == current_user.restaurant_id:
                service.dismiss_insight(insight_id, current_user.id)
                success_count += 1
            else:
                errors.append({"id": insight_id, "error": "Not found or access denied"})
        except Exception as e:
            errors.append({"id": insight_id, "error": str(e)})

    return {
        "success_count": success_count,
        "errors": errors,
        "message": f"Dismissed {success_count} insights",
    }


# ========== Ratings and Actions ==========


@router.post("/{insight_id}/rate", response_model=InsightRatingResponse)
@handle_api_errors
async def rate_insight(
    insight_id: int,
    rating_data: InsightRatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rate an insight's usefulness.

    Returns:
        Created rating

    Raises:
        403: Insufficient permissions
        404: Insight not found
        409: Already rated by user
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    insight = service.get_insight(insight_id)

    if not insight:
        raise NotFoundError("Insight", insight_id)

    if insight.restaurant_id != current_user.restaurant_id:
        raise NotFoundError("Insight", insight_id)

    rating_service = InsightRatingService(db)
    return rating_service.create_rating(insight_id, current_user.id, rating_data)


@router.post("/{insight_id}/action", response_model=InsightActionResponse)
@handle_api_errors
async def log_insight_action(
    insight_id: int,
    action_data: InsightActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Log an action taken on an insight.

    Returns:
        Created action log

    Raises:
        403: Insufficient permissions
        404: Insight not found
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    insight = service.get_insight(insight_id)

    if not insight:
        raise NotFoundError("Insight", insight_id)

    if insight.restaurant_id != current_user.restaurant_id:
        raise NotFoundError("Insight", insight_id)

    return service.log_action(insight_id, current_user.id, action_data)


# ========== Threads ==========


@router.get("/threads", response_model=List[InsightThreadResponse])
@handle_api_errors
async def list_insight_threads(
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    is_recurring: Optional[bool] = Query(
        None, description="Filter by recurring status"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List insight threads.

    Returns:
        List of insight threads

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    filters = ThreadFilters(
        is_active=is_active,
        is_recurring=is_recurring,
        category=category,
        restaurant_id=current_user.restaurant_id,
    )

    thread_service = InsightThreadService(db)
    threads = thread_service.list_threads(
        filters=filters, skip=(page - 1) * size, limit=size
    )

    return threads


@router.get("/threads/{thread_id}", response_model=InsightThreadResponse)
@handle_api_errors
async def get_insight_thread(
    thread_id: str,
    include_insights: bool = Query(True, description="Include thread insights"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get insight thread details.

    Returns:
        Thread with insights

    Raises:
        403: Insufficient permissions
        404: Thread not found
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    thread_service = InsightThreadService(db)
    thread = thread_service.get_thread(thread_id, current_user.restaurant_id)

    if not thread:
        raise NotFoundError("Thread", thread_id)

    if include_insights:
        service = InsightsService(db)
        thread.insights = service.get_thread_insights(thread_id)

    return thread


# ========== Notification Rules ==========


@router.post(
    "/notification-rules",
    response_model=NotificationRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
@handle_api_errors
async def create_notification_rule(
    rule_data: NotificationRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create notification rule for insights.

    Returns:
        Created notification rule

    Raises:
        403: Insufficient permissions
        422: Validation error
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    notification_service = InsightNotificationService(db)
    rule = notification_service.create_rule(rule_data, current_user.restaurant_id)

    return rule


@router.get("/notification-rules", response_model=List[NotificationRuleResponse])
@handle_api_errors
async def list_notification_rules(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List notification rules.

    Returns:
        List of notification rules

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    notification_service = InsightNotificationService(db)
    rules = notification_service.list_rules(current_user.restaurant_id, is_active)

    return rules


@router.put("/notification-rules/{rule_id}", response_model=NotificationRuleResponse)
@handle_api_errors
async def update_notification_rule(
    rule_id: int,
    update_data: NotificationRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update notification rule.

    Returns:
        Updated notification rule

    Raises:
        403: Insufficient permissions
        404: Rule not found
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    notification_service = InsightNotificationService(db)
    rule = notification_service.update_rule(
        rule_id, update_data, current_user.restaurant_id
    )

    if not rule:
        raise NotFoundError("Notification rule", rule_id)

    return rule


@router.delete("/notification-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_notification_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete notification rule.

    Returns:
        No content on success

    Raises:
        403: Insufficient permissions
        404: Rule not found
    """
    check_permission(current_user, Permission.INSIGHTS_MANAGE)

    notification_service = InsightNotificationService(db)
    deleted = notification_service.delete_rule(rule_id, current_user.restaurant_id)

    if not deleted:
        raise NotFoundError("Notification rule", rule_id)


# ========== Analytics Endpoints ==========


@router.get("/analytics/trends", response_model=Dict[str, Any])
@handle_api_errors
async def get_insight_trends(
    domain: Optional[InsightDomain] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get insight trends over time.

    Returns:
        Trend data and analysis

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    return service.get_trend_analysis(
        restaurant_id=current_user.restaurant_id, domain=domain, days=days
    )


@router.get("/analytics/impact", response_model=Dict[str, Any])
@handle_api_errors
async def get_impact_analysis(
    start_date: Optional[date] = Query(None, description="Start date for analysis"),
    end_date: Optional[date] = Query(None, description="End date for analysis"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze business impact of insights.

    Returns:
        Impact analysis with estimated values

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_VIEW)

    service = InsightsService(db)
    return service.get_impact_analysis(
        restaurant_id=current_user.restaurant_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/analytics/export", response_model=Dict[str, str])
@handle_api_errors
async def export_insights(
    filters: InsightFilters = Body(...),
    format: str = Query("csv", pattern="^(csv|excel|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export insights data.

    Returns:
        Export file URL

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.INSIGHTS_EXPORT)

    service = InsightsService(db)
    file_url = await service.export_insights(
        filters=filters, format=format, user_id=current_user.id
    )

    return {"url": file_url, "format": format}
