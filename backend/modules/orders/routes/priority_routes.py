"""
API routes for order priority management system.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from core.database import get_db
from core.deps import get_current_user
from core.permissions import check_permission
from core.rbac_models import RBACUser as User

from ..models.priority_models import (
    PriorityRule,
    PriorityProfile,
    PriorityProfileRule,
    QueuePriorityConfig,
    OrderPriorityScore,
    PriorityAdjustmentLog,
    PriorityMetrics,
)
from ..models.queue_models import OrderQueue, QueueItem, QueueItemStatus
from ..schemas.priority_schemas import (
    PriorityRuleCreate,
    PriorityRuleUpdate,
    PriorityRuleResponse,
    PriorityRuleListResponse,
    PriorityProfileCreate,
    PriorityProfileUpdate,
    PriorityProfileResponse,
    PriorityProfileDetailResponse,
    PriorityProfileListResponse,
    QueuePriorityConfigCreate,
    QueuePriorityConfigUpdate,
    QueuePriorityConfigResponse,
    QueuePriorityConfigListResponse,
    OrderPriorityScoreResponse,
    PriorityAdjustmentRequest,
    PriorityAdjustmentResponse,
    QueueRebalanceRequest,
    QueueRebalanceResponse,
    PriorityMetricsQuery,
    PriorityMetricsResponse,
    BulkPriorityCalculateRequest,
    BulkPriorityCalculateResponse,
    # Additional schemas from main branch
    PriorityCalculationRequest,
    PriorityScoreResponse,
    ManualPriorityAdjustmentRequest,
    RebalanceQueueRequest,
    RebalanceQueueResponse,
    PriorityMetricsRequest,
    BatchProfileRuleUpdate,
)
from ..services.priority_service import PriorityService
from ..services.queue_service import QueueService

router = APIRouter(prefix="/api/v1/priority", tags=["priority"])


# Priority Rules endpoints
@router.get("/rules", response_model=PriorityRuleListResponse)
def list_priority_rules(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    algorithm_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all priority rules with pagination"""
    check_permission(current_user, "priority:read")

    query = db.query(PriorityRule)

    if is_active is not None:
        query = query.filter(PriorityRule.is_active == is_active)

    if algorithm_type:
        query = query.filter(PriorityRule.score_type == algorithm_type)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    rules = query.offset(offset).limit(per_page).all()

    return PriorityRuleListResponse(
        items=[PriorityRuleResponse.model_validate(rule) for rule in rules],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post(
    "/rules", response_model=PriorityRuleResponse, status_code=status.HTTP_201_CREATED
)
def create_priority_rule(
    rule: PriorityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new priority rule"""
    check_permission(current_user, "priority:write")

    # Check for duplicate name
    existing = db.query(PriorityRule).filter(PriorityRule.name == rule.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule with name '{rule.name}' already exists",
        )

    db_rule = PriorityRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)

    return PriorityRuleResponse.model_validate(db_rule)


@router.get("/rules/{rule_id}", response_model=PriorityRuleResponse)
def get_priority_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific priority rule"""
    check_permission(current_user, "priority:read")

    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority rule not found"
        )

    return PriorityRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=PriorityRuleResponse)
def update_priority_rule(
    rule_id: int,
    update: PriorityRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a priority rule"""
    check_permission(current_user, "priority:write")

    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority rule not found"
        )

    # Check for duplicate name if updating
    if update.name and update.name != rule.name:
        existing = (
            db.query(PriorityRule)
            .filter(PriorityRule.name == update.name, PriorityRule.id != rule_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule with name '{update.name}' already exists",
            )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)

    return PriorityRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_priority_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a priority rule"""
    check_permission(current_user, "priority:delete")

    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority rule not found"
        )

    # Check if rule is in use
    in_use = (
        db.query(PriorityProfileRule)
        .filter(PriorityProfileRule.rule_id == rule_id)
        .first()
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete rule that is in use by profiles",
        )

    db.delete(rule)
    db.commit()


# Priority Profiles endpoints
@router.get("/profiles", response_model=PriorityProfileListResponse)
def list_priority_profiles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    queue_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all priority profiles with pagination"""
    check_permission(current_user, "priority:read")

    query = db.query(PriorityProfile)

    if is_active is not None:
        query = query.filter(PriorityProfile.is_active == is_active)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    profiles = query.offset(offset).limit(per_page).all()

    # Filter by queue type if specified
    if queue_type:
        profiles = [
            p for p in profiles if not p.queue_types or queue_type in p.queue_types
        ]

    # Add rule count to each profile
    profile_responses = []
    for profile in profiles:
        profile_dict = PriorityProfileResponse.model_validate(profile).model_dump()
        profile_dict["rule_count"] = len(profile.profile_rules)
        profile_responses.append(PriorityProfileResponse(**profile_dict))

    return PriorityProfileListResponse(
        items=profile_responses,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post(
    "/profiles",
    response_model=PriorityProfileDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_priority_profile(
    profile: PriorityProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new priority profile"""
    check_permission(current_user, "priority:write")

    # Check for duplicate name
    existing = (
        db.query(PriorityProfile).filter(PriorityProfile.name == profile.name).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Profile with name '{profile.name}' already exists",
        )

    # If setting as default, unset other defaults
    if profile.is_default:
        db.query(PriorityProfile).filter(PriorityProfile.is_default == True).update(
            {"is_default": False}
        )

    # Create profile
    profile_data = profile.model_dump(exclude={"rules"})
    db_profile = PriorityProfile(**profile_data)
    db.add(db_profile)
    db.flush()

    # Create profile rules
    for rule_data in profile.rules:
        db_rule = PriorityProfileRule(
            profile_id=db_profile.id, **rule_data.model_dump()
        )
        db.add(db_rule)

    db.commit()
    db.refresh(db_profile)

    return PriorityProfileDetailResponse.model_validate(db_profile)


@router.get("/profiles/{profile_id}", response_model=PriorityProfileDetailResponse)
def get_priority_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific priority profile with its rules"""
    check_permission(current_user, "priority:read")

    profile = (
        db.query(PriorityProfile)
        .options(
            joinedload(PriorityProfile.profile_rules).joinedload(
                PriorityProfileRule.rule
            )
        )
        .filter(PriorityProfile.id == profile_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority profile not found"
        )

    return PriorityProfileDetailResponse.model_validate(profile)


@router.patch("/profiles/{profile_id}", response_model=PriorityProfileDetailResponse)
def update_priority_profile(
    profile_id: int,
    update: PriorityProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a priority profile"""
    check_permission(current_user, "priority:write")

    profile = db.query(PriorityProfile).filter(PriorityProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority profile not found"
        )

    # Check for duplicate name if updating
    if update.name and update.name != profile.name:
        existing = (
            db.query(PriorityProfile)
            .filter(
                PriorityProfile.name == update.name, PriorityProfile.id != profile_id
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Profile with name '{update.name}' already exists",
            )

    # If setting as default, unset other defaults
    if update.is_default is True:
        db.query(PriorityProfile).filter(
            PriorityProfile.is_default == True, PriorityProfile.id != profile_id
        ).update({"is_default": False})

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    # Load with relationships
    profile = (
        db.query(PriorityProfile)
        .options(
            joinedload(PriorityProfile.profile_rules).joinedload(
                PriorityProfileRule.rule
            )
        )
        .filter(PriorityProfile.id == profile_id)
        .first()
    )

    return PriorityProfileDetailResponse.model_validate(profile)


@router.post("/profiles/{profile_id}/rules")
def update_profile_rules(
    profile_id: int,
    update_data: BatchProfileRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update rules assigned to a profile"""
    check_permission(current_user, "priority:write")

    profile = db.query(PriorityProfile).filter(PriorityProfile.id == profile_id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority profile {profile_id} not found",
        )

    # Remove existing assignments
    db.query(PriorityProfileRule).filter(
        PriorityProfileRule.profile_id == profile_id
    ).delete()

    # Add new assignments
    for assignment in update_data.assignments:
        # Verify rule exists
        rule = (
            db.query(PriorityRule).filter(PriorityRule.id == assignment.rule_id).first()
        )
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Priority rule {assignment.rule_id} not found",
            )

        profile_rule = PriorityProfileRule(profile_id=profile_id, **assignment.dict())
        db.add(profile_rule)

    db.commit()

    return {"message": f"Updated {len(update_data.assignments)} rule assignments"}


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_priority_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a priority profile"""
    check_permission(current_user, "priority:delete")

    profile = db.query(PriorityProfile).filter(PriorityProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority profile not found"
        )

    # Check if profile is in use
    in_use = (
        db.query(QueuePriorityConfig)
        .filter(QueuePriorityConfig.profile_id == profile_id)
        .first()
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete profile that is in use by queues",
        )

    db.delete(profile)
    db.commit()


# Queue Priority Configuration endpoints
@router.get("/queue-configs", response_model=QueuePriorityConfigListResponse)
def list_queue_priority_configs(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """List all queue priority configurations"""
    check_permission(current_user, "priority:read")

    configs = (
        db.query(QueuePriorityConfig)
        .options(
            joinedload(QueuePriorityConfig.queue),
            joinedload(QueuePriorityConfig.profile),
        )
        .all()
    )

    # Build response with profile and queue names
    config_responses = []
    for config in configs:
        config_response = QueuePriorityConfigResponse.model_validate(config)
        config_response.profile_name = config.profile.name if config.profile else None
        config_response.queue_name = config.queue.name if config.queue else None
        config_responses.append(config_response)

    return QueuePriorityConfigListResponse(
        items=config_responses, total=len(config_responses)
    )


@router.post(
    "/queue-configs",
    response_model=QueuePriorityConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_queue_priority_config(
    config: QueuePriorityConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new queue priority configuration"""
    check_permission(current_user, "priority:write")

    # Check if queue already has config
    existing = (
        db.query(QueuePriorityConfig)
        .filter(QueuePriorityConfig.queue_id == config.queue_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Queue already has a priority configuration",
        )

    # Verify queue and profile exist
    queue = db.query(OrderQueue).filter(OrderQueue.id == config.queue_id).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found"
        )

    profile = (
        db.query(PriorityProfile)
        .filter(PriorityProfile.id == config.profile_id)
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Priority profile not found"
        )

    db_config = QueuePriorityConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    # Build response with names
    config_response = QueuePriorityConfigResponse.model_validate(db_config)
    config_response.profile_name = profile.name
    config_response.queue_name = queue.name

    return config_response


@router.get("/queue-configs/{config_id}", response_model=QueuePriorityConfigResponse)
def get_queue_priority_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific queue priority configuration"""
    check_permission(current_user, "priority:read")

    config = (
        db.query(QueuePriorityConfig)
        .options(
            joinedload(QueuePriorityConfig.queue),
            joinedload(QueuePriorityConfig.profile),
        )
        .filter(QueuePriorityConfig.id == config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue priority configuration not found",
        )

    config_response = QueuePriorityConfigResponse.model_validate(config)
    config_response.profile_name = config.profile.name if config.profile else None
    config_response.queue_name = config.queue.name if config.queue else None

    return config_response


@router.patch("/queue-configs/{config_id}", response_model=QueuePriorityConfigResponse)
def update_queue_priority_config(
    config_id: int,
    update: QueuePriorityConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a queue priority configuration"""
    check_permission(current_user, "priority:write")

    config = (
        db.query(QueuePriorityConfig)
        .filter(QueuePriorityConfig.id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue priority configuration not found",
        )

    # Verify new profile if updating
    if update.profile_id:
        profile = (
            db.query(PriorityProfile)
            .filter(PriorityProfile.id == update.profile_id)
            .first()
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Priority profile not found",
            )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)

    # Load with relationships
    config = (
        db.query(QueuePriorityConfig)
        .options(
            joinedload(QueuePriorityConfig.queue),
            joinedload(QueuePriorityConfig.profile),
        )
        .filter(QueuePriorityConfig.id == config_id)
        .first()
    )

    config_response = QueuePriorityConfigResponse.model_validate(config)
    config_response.profile_name = config.profile.name if config.profile else None
    config_response.queue_name = config.queue.name if config.queue else None

    return config_response


@router.delete("/queue-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_queue_priority_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a queue priority configuration"""
    check_permission(current_user, "priority:delete")

    config = (
        db.query(QueuePriorityConfig)
        .filter(QueuePriorityConfig.id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue priority configuration not found",
        )

    db.delete(config)
    db.commit()


# Priority Operations endpoints
@router.post("/calculate", response_model=OrderPriorityScoreResponse)
def calculate_order_priority(
    order_id: int,
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate priority score for a specific order in a queue"""
    check_permission(current_user, "priority:read")

    service = PriorityService(db)
    try:
        score = service.calculate_order_priority(order_id, queue_id)
        return OrderPriorityScoreResponse.model_validate(score)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/calculate-bulk", response_model=BulkPriorityCalculateResponse)
def calculate_bulk_priority(
    request: BulkPriorityCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate priority scores for multiple orders in a queue"""
    check_permission(current_user, "priority:write")

    service = PriorityService(db)
    start_time = time.time()

    items_processed = 0
    items_updated = 0
    errors = []
    score_changes = []

    # Get queue items to process
    query = db.query(QueueItem).filter(
        QueueItem.queue_id == request.queue_id,
        QueueItem.status.in_([QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION]),
    )

    if request.order_ids:
        query = query.filter(QueueItem.order_id.in_(request.order_ids))

    queue_items = query.all()

    for queue_item in queue_items:
        items_processed += 1
        try:
            # Get old score if exists
            old_score = (
                db.query(OrderPriorityScore)
                .filter(OrderPriorityScore.queue_item_id == queue_item.id)
                .first()
            )
            old_total = old_score.total_score if old_score else 0

            # Calculate new score
            new_score = service.calculate_order_priority(
                queue_item.order_id, request.queue_id
            )

            if request.apply_boost:
                # Apply boost if requested
                config = (
                    db.query(QueuePriorityConfig)
                    .filter(QueuePriorityConfig.queue_id == request.queue_id)
                    .first()
                )
                if config:
                    new_score = service._apply_boost(new_score, config, "bulk_boost")
                    if request.boost_duration_seconds:
                        new_score.boost_expires_at = datetime.utcnow() + timedelta(
                            seconds=request.boost_duration_seconds
                        )
                    db.commit()

            score_changes.append(abs(new_score.total_score - old_total))
            items_updated += 1

        except Exception as e:
            errors.append({"order_id": queue_item.order_id, "error": str(e)})

    # Resequence queue based on new scores
    service._resequence_queue_after_adjustment(request.queue_id)

    execution_time_ms = int((time.time() - start_time) * 1000)
    avg_score_change = sum(score_changes) / len(score_changes) if score_changes else 0

    return BulkPriorityCalculateResponse(
        queue_id=request.queue_id,
        items_processed=items_processed,
        items_updated=items_updated,
        average_score_change=avg_score_change,
        execution_time_ms=execution_time_ms,
        errors=errors,
    )


@router.post("/rebalance", response_model=QueueRebalanceResponse)
def rebalance_queue(
    request: QueueRebalanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rebalance a queue to ensure fairness"""
    check_permission(current_user, "priority:write")

    service = PriorityService(db)
    try:
        result = service.rebalance_queue(request.queue_id, request.force)
        result.dry_run = request.dry_run
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/adjust", response_model=PriorityAdjustmentResponse)
def adjust_priority_manually(
    adjustment: PriorityAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually adjust priority for a queue item"""
    check_permission(current_user, "priority:write")

    service = PriorityService(db)
    try:
        log = service.adjust_priority_manually(
            queue_item_id=adjustment.queue_item_id,
            new_score=adjustment.new_score,
            adjustment_type=adjustment.adjustment_type,
            adjustment_reason=adjustment.adjustment_reason,
            adjusted_by_id=current_user.id,
            duration_seconds=adjustment.duration_seconds,
        )
        return PriorityAdjustmentResponse.model_validate(log)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/queue/{queue_id}/sequence")
def get_queue_priority_sequence(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current priority-based sequence for a queue"""
    check_permission(current_user, "priority:read")

    service = PriorityService(db)
    return service.get_queue_priority_sequence(queue_id)


# Metrics endpoints
@router.post("/metrics", response_model=List[PriorityMetricsResponse])
def get_priority_metrics(
    query: PriorityMetricsQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get priority system metrics"""
    check_permission(current_user, "priority:read")

    # Build query
    metrics_query = db.query(PriorityMetrics).filter(
        PriorityMetrics.metric_date >= query.start_date,
        PriorityMetrics.metric_date <= query.end_date,
    )

    if query.queue_id:
        metrics_query = metrics_query.filter(PriorityMetrics.queue_id == query.queue_id)

    metrics = metrics_query.all()

    # Group and aggregate based on requested aggregation
    # This is simplified - real implementation would do proper aggregation
    results = []
    for metric in metrics:
        queue = db.query(OrderQueue).filter(OrderQueue.id == metric.queue_id).first()

        results.append(
            PriorityMetricsResponse(
                queue_id=metric.queue_id,
                queue_name=queue.name if queue else "Unknown",
                period=f"{metric.metric_date.date()} {metric.hour_of_day}:00",
                metrics={
                    "fairness": {
                        "gini_coefficient": metric.gini_coefficient,
                        "max_wait_variance": metric.max_wait_variance,
                        "position_change_avg": metric.position_change_avg,
                    },
                    "performance": {
                        "avg_calculation_time_ms": metric.avg_calculation_time_ms,
                        "total_calculations": metric.total_calculations,
                        "cache_hit_rate": metric.cache_hit_rate,
                    },
                    "rebalancing": {
                        "rebalance_count": metric.rebalance_count,
                        "avg_rebalance_impact": metric.avg_rebalance_impact,
                        "manual_adjustments": metric.manual_adjustments,
                    },
                },
            )
        )

    return results


# Import for time
import time
