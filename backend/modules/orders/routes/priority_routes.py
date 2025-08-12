"""
API routes for order prioritization management.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.database import get_db
from core.auth import get_current_user
from modules.auth.models import User
from ..models.priority_models import (
    PriorityRule, PriorityProfile, QueuePriorityConfig,
    PriorityProfileRule, OrderPriorityScore, PriorityMetrics
)
from ..schemas.priority_schemas import (
    PriorityRuleCreate, PriorityRuleUpdate, PriorityRuleResponse,
    PriorityProfileCreate, PriorityProfileUpdate, PriorityProfileResponse,
    QueuePriorityConfigCreate, QueuePriorityConfigUpdate, QueuePriorityConfigResponse,
    PriorityCalculationRequest, PriorityScoreResponse,
    ManualPriorityAdjustmentRequest, PriorityAdjustmentResponse,
    RebalanceQueueRequest, RebalanceQueueResponse,
    PriorityMetricsRequest, PriorityMetricsResponse,
    BatchProfileRuleUpdate
)
from ..services.priority_service import PriorityService
from ..services.queue_service import QueueService

router = APIRouter(prefix="/api/v1/priorities", tags=["Order Prioritization"])


# Priority Rules Management
@router.post("/rules", response_model=PriorityRuleResponse)
def create_priority_rule(
    rule_data: PriorityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new priority rule"""
    # Check for duplicate name
    existing = db.query(PriorityRule).filter(
        PriorityRule.name == rule_data.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule with name '{rule_data.name}' already exists"
        )
    
    rule = PriorityRule(**rule_data.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return rule


@router.get("/rules", response_model=List[PriorityRuleResponse])
def list_priority_rules(
    algorithm_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all priority rules"""
    query = db.query(PriorityRule)
    
    if algorithm_type:
        query = query.filter(PriorityRule.algorithm_type == algorithm_type)
    if is_active is not None:
        query = query.filter(PriorityRule.is_active == is_active)
    
    return query.order_by(PriorityRule.name).all()


@router.get("/rules/{rule_id}", response_model=PriorityRuleResponse)
def get_priority_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific priority rule"""
    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority rule {rule_id} not found"
        )
    return rule


@router.patch("/rules/{rule_id}", response_model=PriorityRuleResponse)
def update_priority_rule(
    rule_id: int,
    update_data: PriorityRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a priority rule"""
    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority rule {rule_id} not found"
        )
    
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(rule, field, value)
    
    db.commit()
    db.refresh(rule)
    
    return rule


@router.delete("/rules/{rule_id}")
def delete_priority_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a priority rule"""
    rule = db.query(PriorityRule).filter(PriorityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority rule {rule_id} not found"
        )
    
    # Check if rule is used in any profiles
    used_in_profiles = db.query(PriorityProfileRule).filter(
        PriorityProfileRule.rule_id == rule_id
    ).count()
    
    if used_in_profiles > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete rule used in {used_in_profiles} profiles"
        )
    
    db.delete(rule)
    db.commit()
    
    return {"message": f"Priority rule {rule_id} deleted successfully"}


# Priority Profiles Management
@router.post("/profiles", response_model=PriorityProfileResponse)
def create_priority_profile(
    profile_data: PriorityProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new priority profile"""
    # Check for duplicate name
    existing = db.query(PriorityProfile).filter(
        PriorityProfile.name == profile_data.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile with name '{profile_data.name}' already exists"
        )
    
    # If setting as default, unset other defaults
    if profile_data.is_default:
        db.query(PriorityProfile).update({"is_default": False})
    
    # Create profile
    profile_dict = profile_data.dict(exclude={"rule_assignments"})
    profile = PriorityProfile(**profile_dict)
    db.add(profile)
    db.flush()
    
    # Add rule assignments
    for assignment in profile_data.rule_assignments:
        profile_rule = PriorityProfileRule(
            profile_id=profile.id,
            **assignment
        )
        db.add(profile_rule)
    
    db.commit()
    db.refresh(profile)
    
    # Add rule count
    profile.rule_count = len(profile.profile_rules)
    
    return profile


@router.get("/profiles", response_model=List[PriorityProfileResponse])
def list_priority_profiles(
    is_active: Optional[bool] = None,
    queue_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all priority profiles"""
    query = db.query(PriorityProfile)
    
    if is_active is not None:
        query = query.filter(PriorityProfile.is_active == is_active)
    
    profiles = query.order_by(PriorityProfile.name).all()
    
    # Filter by queue type if specified
    if queue_type:
        profiles = [p for p in profiles if not p.queue_types or queue_type in p.queue_types]
    
    # Add rule counts
    for profile in profiles:
        profile.rule_count = len(profile.profile_rules)
    
    return profiles


@router.get("/profiles/{profile_id}", response_model=PriorityProfileResponse)
def get_priority_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific priority profile with its rules"""
    profile = db.query(PriorityProfile).filter(
        PriorityProfile.id == profile_id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority profile {profile_id} not found"
        )
    
    profile.rule_count = len(profile.profile_rules)
    return profile


@router.patch("/profiles/{profile_id}", response_model=PriorityProfileResponse)
def update_priority_profile(
    profile_id: int,
    update_data: PriorityProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a priority profile"""
    profile = db.query(PriorityProfile).filter(
        PriorityProfile.id == profile_id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority profile {profile_id} not found"
        )
    
    # If setting as default, unset other defaults
    if update_data.is_default:
        db.query(PriorityProfile).filter(
            PriorityProfile.id != profile_id
        ).update({"is_default": False})
    
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    
    profile.rule_count = len(profile.profile_rules)
    return profile


@router.post("/profiles/{profile_id}/rules")
def update_profile_rules(
    profile_id: int,
    update_data: BatchProfileRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update rules assigned to a profile"""
    profile = db.query(PriorityProfile).filter(
        PriorityProfile.id == profile_id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority profile {profile_id} not found"
        )
    
    # Remove existing assignments
    db.query(PriorityProfileRule).filter(
        PriorityProfileRule.profile_id == profile_id
    ).delete()
    
    # Add new assignments
    for assignment in update_data.assignments:
        # Verify rule exists
        rule = db.query(PriorityRule).filter(
            PriorityRule.id == assignment.rule_id
        ).first()
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Priority rule {assignment.rule_id} not found"
            )
        
        profile_rule = PriorityProfileRule(
            profile_id=profile_id,
            **assignment.dict()
        )
        db.add(profile_rule)
    
    db.commit()
    
    return {"message": f"Updated {len(update_data.assignments)} rule assignments"}


# Queue Priority Configuration
@router.post("/queues/config", response_model=QueuePriorityConfigResponse)
def configure_queue_priority(
    config_data: QueuePriorityConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Configure priority settings for a queue"""
    # Check if config already exists
    existing = db.query(QueuePriorityConfig).filter(
        QueuePriorityConfig.queue_id == config_data.queue_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Priority configuration already exists for queue {config_data.queue_id}"
        )
    
    # Verify profile exists
    profile = db.query(PriorityProfile).filter(
        PriorityProfile.id == config_data.priority_profile_id
    ).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Priority profile {config_data.priority_profile_id} not found"
        )
    
    config = QueuePriorityConfig(**config_data.dict())
    db.add(config)
    db.commit()
    db.refresh(config)
    
    config.profile_name = profile.name
    return config


@router.get("/queues/{queue_id}/config", response_model=QueuePriorityConfigResponse)
def get_queue_priority_config(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get priority configuration for a queue"""
    config = db.query(QueuePriorityConfig).filter(
        QueuePriorityConfig.queue_id == queue_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No priority configuration found for queue {queue_id}"
        )
    
    if config.priority_profile:
        config.profile_name = config.priority_profile.name
    
    return config


@router.patch("/queues/{queue_id}/config", response_model=QueuePriorityConfigResponse)
def update_queue_priority_config(
    queue_id: int,
    update_data: QueuePriorityConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update priority configuration for a queue"""
    config = db.query(QueuePriorityConfig).filter(
        QueuePriorityConfig.queue_id == queue_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No priority configuration found for queue {queue_id}"
        )
    
    # Verify new profile if changing
    if update_data.priority_profile_id:
        profile = db.query(PriorityProfile).filter(
            PriorityProfile.id == update_data.priority_profile_id
        ).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Priority profile {update_data.priority_profile_id} not found"
            )
    
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    if config.priority_profile:
        config.profile_name = config.priority_profile.name
    
    return config


# Priority Calculation and Management
@router.post("/calculate", response_model=PriorityScoreResponse)
def calculate_order_priority(
    request: PriorityCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate priority score for an order"""
    priority_service = PriorityService(db)
    
    try:
        score = priority_service.calculate_order_priority(
            order_id=request.order_id,
            queue_id=request.queue_id,
            profile_override=request.profile_override
        )
        return score
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/adjust", response_model=PriorityAdjustmentResponse)
def adjust_order_priority(
    adjustment: ManualPriorityAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually adjust order priority"""
    priority_service = PriorityService(db)
    
    try:
        result = priority_service.adjust_priority_manual(
            order_id=adjustment.order_id,
            queue_id=adjustment.queue_id,
            new_priority=adjustment.new_priority,
            reason=adjustment.reason,
            user_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/rebalance", response_model=RebalanceQueueResponse)
def rebalance_queue(
    request: RebalanceQueueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rebalance queue based on current priorities"""
    queue_service = QueueService(db)
    
    result = queue_service.rebalance_queue_priorities(
        queue_id=request.queue_id,
        user_id=current_user.id
    )
    
    return RebalanceQueueResponse(**result)


# Priority Metrics
@router.post("/metrics", response_model=PriorityMetricsResponse)
def get_priority_metrics(
    request: PriorityMetricsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get priority algorithm performance metrics"""
    query = db.query(PriorityMetrics).filter(
        and_(
            PriorityMetrics.metric_date >= request.start_date,
            PriorityMetrics.metric_date <= request.end_date
        )
    )
    
    if request.profile_id:
        query = query.filter(PriorityMetrics.profile_id == request.profile_id)
    if request.queue_id:
        query = query.filter(PriorityMetrics.queue_id == request.queue_id)
    
    metrics = query.all()
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics found for the specified period"
        )
    
    # Aggregate metrics
    total_metrics = len(metrics)
    
    return {
        "profile_id": request.profile_id,
        "queue_id": request.queue_id,
        "period": {
            "start": request.start_date,
            "end": request.end_date
        },
        "effectiveness": {
            "avg_wait_time_reduction": sum(m.avg_wait_time_reduction or 0 for m in metrics) / total_metrics,
            "on_time_delivery_rate": sum(m.on_time_delivery_rate or 0 for m in metrics) / total_metrics,
            "vip_satisfaction_score": sum(m.vip_satisfaction_score or 0 for m in metrics) / total_metrics
        },
        "fairness": {
            "fairness_index": sum(m.fairness_index or 0 for m in metrics) / total_metrics,
            "max_wait_time_ratio": max(m.max_wait_time_ratio or 0 for m in metrics),
            "priority_override_count": sum(m.priority_override_count or 0 for m in metrics)
        },
        "performance": {
            "avg_calculation_time_ms": sum(m.avg_calculation_time_ms or 0 for m in metrics) / total_metrics,
            "rebalance_count": sum(m.rebalance_count or 0 for m in metrics),
            "avg_position_changes": sum(m.avg_position_changes or 0 for m in metrics) / total_metrics
        },
        "business_impact": {
            "revenue_impact": sum(m.revenue_impact or 0 for m in metrics),
            "customer_complaints": sum(m.customer_complaints or 0 for m in metrics),
            "staff_overrides": sum(m.staff_overrides or 0 for m in metrics)
        }
    }