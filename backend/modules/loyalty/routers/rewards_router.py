# backend/modules/loyalty/routers/rewards_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from core.database import get_db
from core.auth import get_current_user
from core.auth import User
from core.rate_limiting import rate_limit
from core.enhanced_rbac import (
    require_permission,
    ResourceType,
    ActionType,
    CommonPerms,
    require_any_permission,
    owner_or_permission,
)
from ..models.rewards_models import (
    RewardTemplate as RewardTemplateModel,
    CustomerReward as CustomerRewardModel,
)
from ..schemas.rewards_schemas import (
    RewardTemplate,
    RewardTemplateCreate,
    RewardTemplateUpdate,
    CustomerReward,
    CustomerRewardSummary,
    RewardSearchParams,
    RewardSearchResponse,
    RewardCampaign,
    RewardCampaignCreate,
    RewardCampaignUpdate,
    RewardRedemptionRequest,
    RewardRedemptionResponse,
    ManualRewardIssuance,
    BulkRewardIssuance,
    BulkRewardIssuanceResponse,
    OrderCompletionReward,
    OrderCompletionResponse,
    RewardAnalytics,
    CustomerLoyaltyStats,
    LoyaltyPointsTransaction,
)
from ..services.rewards_engine import RewardsEngine


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/loyalty/rewards", tags=["loyalty-rewards"])


# Legacy permission check function (deprecated - use decorators instead)
def check_rewards_permission(user: User, action: str, tenant_id: Optional[int] = None):
    """Check if user has rewards-related permissions (DEPRECATED)"""
    if tenant_id is None:
        tenant_id = user.default_tenant_id

    permission_key = f"rewards:{action}"
    if not user.has_permission(permission_key, tenant_id):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions for {permission_key} in tenant {tenant_id}",
        )


# Reward Template Management
@router.post("/templates", response_model=RewardTemplate)
@rate_limit(
    limit=10, window=60, per="user"
)  # 10 template creations per minute per user
@require_permission(ResourceType.REWARD, ActionType.WRITE)
async def create_reward_template(
    template_data: RewardTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new reward template"""

    try:
        rewards_engine = RewardsEngine(db)
        template = rewards_engine.create_reward_template(template_data.model_dump())
        return template
    except Exception as e:
        logger.error(f"Error creating reward template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create reward template")


@router.get("/templates", response_model=List[RewardTemplate])
@rate_limit(limit=100, window=60, per="user")  # 100 template reads per minute
@require_permission(ResourceType.REWARD, ActionType.READ)
async def list_reward_templates(
    active_only: bool = Query(True),
    reward_type: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List reward templates"""

    query = db.query(RewardTemplateModel)

    if active_only:
        query = query.filter(RewardTemplateModel.is_active == True)

    if reward_type:
        query = query.filter(RewardTemplateModel.reward_type == reward_type)

    if trigger_type:
        query = query.filter(RewardTemplateModel.trigger_type == trigger_type)

    templates = (
        query.order_by(
            RewardTemplateModel.priority.desc(), RewardTemplateModel.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return templates


@router.get("/templates/{template_id}", response_model=RewardTemplate)
async def get_reward_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific reward template"""
    check_rewards_permission(current_user, "read")

    template = (
        db.query(RewardTemplateModel)
        .filter(RewardTemplateModel.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Reward template not found")

    return template


@router.put("/templates/{template_id}", response_model=RewardTemplate)
async def update_reward_template(
    template_id: int,
    update_data: RewardTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a reward template"""
    check_rewards_permission(current_user, "write")

    template = (
        db.query(RewardTemplateModel)
        .filter(RewardTemplateModel.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Reward template not found")

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    logger.info(f"Updated reward template {template_id}")
    return template


@router.delete("/templates/{template_id}")
async def delete_reward_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a reward template"""
    check_rewards_permission(current_user, "write")

    template = (
        db.query(RewardTemplateModel)
        .filter(RewardTemplateModel.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Reward template not found")

    template.is_active = False
    db.commit()

    logger.info(f"Deactivated reward template {template_id}")
    return {"success": True, "message": "Reward template deactivated"}


# Customer Rewards
@router.get(
    "/customer/{customer_id}/rewards", response_model=List[CustomerRewardSummary]
)
async def get_customer_rewards(
    customer_id: int,
    status: Optional[str] = Query(None),
    valid_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all rewards for a customer"""
    check_rewards_permission(current_user, "read")

    try:
        rewards_engine = RewardsEngine(db)

        if valid_only and not status:
            rewards = rewards_engine.get_customer_available_rewards(customer_id)
        else:
            query = db.query(CustomerRewardModel).filter(
                CustomerRewardModel.customer_id == customer_id
            )

            if status:
                query = query.filter(CustomerRewardModel.status == status)

            rewards = query.order_by(CustomerRewardModel.created_at.desc()).all()

        # Convert to summary format
        summaries = []
        for reward in rewards:
            summary = CustomerRewardSummary(
                id=reward.id,
                code=reward.code,
                title=reward.title,
                reward_type=reward.reward_type,
                value=reward.value,
                percentage=reward.percentage,
                status=reward.status,
                valid_until=reward.valid_until,
                days_until_expiry=reward.days_until_expiry,
            )
            summaries.append(summary)

        return summaries

    except Exception as e:
        logger.error(f"Error getting customer rewards: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve customer rewards"
        )


@router.get("/search", response_model=RewardSearchResponse)
async def search_rewards(
    customer_id: Optional[int] = Query(None),
    template_id: Optional[int] = Query(None),
    reward_type: Optional[str] = Query(None),
    status: Optional[List[str]] = Query(None),
    valid_only: bool = Query(True),
    expiring_soon: Optional[int] = Query(None, ge=1, le=30),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search rewards with advanced filtering"""
    check_rewards_permission(current_user, "read")

    query = db.query(CustomerRewardModel)

    # Apply filters
    if customer_id:
        query = query.filter(CustomerRewardModel.customer_id == customer_id)

    if template_id:
        query = query.filter(CustomerRewardModel.template_id == template_id)

    if reward_type:
        query = query.filter(CustomerRewardModel.reward_type == reward_type)

    if status:
        query = query.filter(CustomerRewardModel.status.in_(status))

    if valid_only:
        from datetime import datetime

        now = datetime.utcnow()
        query = query.filter(
            CustomerRewardModel.valid_from <= now,
            CustomerRewardModel.valid_until > now,
            CustomerRewardModel.status == "available",
        )

    if expiring_soon:
        from datetime import datetime, timedelta

        expiry_cutoff = datetime.utcnow() + timedelta(days=expiring_soon)
        query = query.filter(CustomerRewardModel.valid_until <= expiry_cutoff)

    # Get total count
    total = query.count()

    # Apply sorting and pagination
    sort_column = getattr(CustomerRewardModel, sort_by, CustomerRewardModel.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column)

    offset = (page - 1) * page_size
    rewards = query.offset(offset).limit(page_size).all()

    # Convert to summaries
    summaries = []
    for reward in rewards:
        summary = CustomerRewardSummary(
            id=reward.id,
            code=reward.code,
            title=reward.title,
            reward_type=reward.reward_type,
            value=reward.value,
            percentage=reward.percentage,
            status=reward.status,
            valid_until=reward.valid_until,
            days_until_expiry=reward.days_until_expiry,
        )
        summaries.append(summary)

    total_pages = (total + page_size - 1) // page_size

    return RewardSearchResponse(
        rewards=summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# Reward Redemption
@router.post("/redeem", response_model=RewardRedemptionResponse)
async def redeem_reward(
    redemption_request: RewardRedemptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeem a reward against an order"""
    check_rewards_permission(current_user, "redeem")

    try:
        rewards_engine = RewardsEngine(db)
        result = rewards_engine.redeem_reward(
            reward_code=redemption_request.reward_code,
            order_id=redemption_request.order_id,
            staff_member_id=redemption_request.staff_member_id or current_user.id,
        )

        return RewardRedemptionResponse(**result)

    except Exception as e:
        logger.error(f"Error redeeming reward: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to redeem reward")


# Manual Reward Issuance
@router.post("/issue", response_model=CustomerReward)
async def issue_reward_manually(
    issuance_data: ManualRewardIssuance,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually issue a reward to a customer"""
    check_rewards_permission(current_user, "issue")

    try:
        rewards_engine = RewardsEngine(db)
        reward = rewards_engine.issue_reward_to_customer(
            customer_id=issuance_data.customer_id,
            template_id=issuance_data.template_id,
            issued_by=current_user.id,
            custom_data=(
                {"message": issuance_data.custom_message}
                if issuance_data.custom_message
                else None
            ),
        )

        return reward

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error issuing reward: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to issue reward")


@router.post("/issue/bulk", response_model=BulkRewardIssuanceResponse)
async def issue_rewards_bulk(
    bulk_issuance: BulkRewardIssuance,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue rewards to multiple customers"""
    check_rewards_permission(current_user, "issue")

    def process_bulk_issuance():
        rewards_engine = RewardsEngine(db)
        successful = 0
        failed = 0
        errors = []
        issued_codes = []

        for customer_id in bulk_issuance.customer_ids:
            try:
                reward = rewards_engine.issue_reward_to_customer(
                    customer_id=customer_id,
                    template_id=bulk_issuance.template_id,
                    issued_by=current_user.id,
                    custom_data=(
                        {"message": bulk_issuance.custom_message}
                        if bulk_issuance.custom_message
                        else None
                    ),
                )
                successful += 1
                issued_codes.append(reward.code)

            except Exception as e:
                failed += 1
                errors.append(f"Customer {customer_id}: {str(e)}")

        logger.info(
            f"Bulk reward issuance completed: {successful} successful, {failed} failed"
        )

    # Process in background for large bulk operations
    if len(bulk_issuance.customer_ids) > 10:
        background_tasks.add_task(process_bulk_issuance)
        return BulkRewardIssuanceResponse(
            total_customers=len(bulk_issuance.customer_ids),
            successful_issuances=0,
            failed_issuances=0,
            errors=["Processing in background - check logs for results"],
            issued_reward_codes=[],
        )
    else:
        # Process immediately for small batches
        process_bulk_issuance()
        return BulkRewardIssuanceResponse(
            total_customers=len(bulk_issuance.customer_ids),
            successful_issuances=len(bulk_issuance.customer_ids),  # Simplified for demo
            failed_issuances=0,
            errors=[],
            issued_reward_codes=[],
        )


# Order Processing Integration
@router.post("/process-order", response_model=OrderCompletionResponse)
async def process_order_completion(
    order_data: OrderCompletionReward,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process rewards and points for order completion"""
    check_rewards_permission(current_user, "process")

    try:
        rewards_engine = RewardsEngine(db)
        result = rewards_engine.process_order_completion(order_data.order_id)

        return OrderCompletionResponse(**result)

    except Exception as e:
        logger.error(f"Error processing order completion: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to process order completion"
        )


# Analytics and Reporting
@router.get("/analytics/template/{template_id}", response_model=RewardAnalytics)
async def get_template_analytics(
    template_id: int,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get analytics for a specific reward template"""
    check_rewards_permission(current_user, "read")

    try:
        from datetime import datetime

        rewards_engine = RewardsEngine(db)

        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        analytics = rewards_engine.get_reward_analytics(
            template_id=template_id, start_date=start_dt, end_date=end_dt
        )

        return RewardAnalytics(**analytics)

    except Exception as e:
        logger.error(f"Error getting template analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")


@router.get(
    "/customer/{customer_id}/loyalty-stats", response_model=CustomerLoyaltyStats
)
async def get_customer_loyalty_stats(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get loyalty statistics for a customer"""
    check_rewards_permission(current_user, "read")

    from modules.customers.models.customer_models import Customer

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get reward statistics
    total_rewards = (
        db.query(CustomerRewardModel)
        .filter(CustomerRewardModel.customer_id == customer_id)
        .count()
    )
    redeemed_rewards = (
        db.query(CustomerRewardModel)
        .filter(
            CustomerRewardModel.customer_id == customer_id,
            CustomerRewardModel.status == "redeemed",
        )
        .count()
    )

    # Calculate total discount received
    from ..models.rewards_models import RewardRedemption

    total_discount = (
        db.query(RewardRedemption)
        .filter(RewardRedemption.customer_id == customer_id)
        .with_entities(db.func.sum(RewardRedemption.discount_applied))
        .scalar()
        or 0
    )

    # Calculate this month's points activity
    from datetime import datetime, timedelta

    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    from ..models.rewards_models import LoyaltyPointsTransaction as LPTransaction

    points_earned_this_month = (
        db.query(LPTransaction)
        .filter(
            LPTransaction.customer_id == customer_id,
            LPTransaction.transaction_type == "earned",
            LPTransaction.created_at >= month_start,
        )
        .with_entities(db.func.sum(LPTransaction.points_change))
        .scalar()
        or 0
    )

    points_redeemed_this_month = abs(
        db.query(LPTransaction)
        .filter(
            LPTransaction.customer_id == customer_id,
            LPTransaction.transaction_type == "redeemed",
            LPTransaction.created_at >= month_start,
        )
        .with_entities(db.func.sum(LPTransaction.points_change))
        .scalar()
        or 0
    )

    # Calculate next tier points needed (simplified)
    tier_points_map = {
        "bronze": 0,
        "silver": 1000,
        "gold": 2500,
        "platinum": 5000,
        "vip": 10000,
    }
    current_tier_points = tier_points_map.get(customer.tier.value.lower(), 0)
    next_tier_points = None

    for tier, points in tier_points_map.items():
        if points > customer.lifetime_points:
            next_tier_points = points - customer.lifetime_points
            break

    return CustomerLoyaltyStats(
        customer_id=customer_id,
        loyalty_points=customer.loyalty_points,
        lifetime_points=customer.lifetime_points,
        tier=customer.tier.value,
        total_rewards_received=total_rewards,
        total_rewards_redeemed=redeemed_rewards,
        total_discount_received=float(total_discount),
        points_earned_this_month=points_earned_this_month,
        points_redeemed_this_month=points_redeemed_this_month,
        next_tier_points_needed=next_tier_points,
    )


# System Management
@router.post("/maintenance/expire-rewards")
async def expire_old_rewards(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Expire rewards that have passed their expiration date"""
    check_rewards_permission(current_user, "admin")

    try:
        rewards_engine = RewardsEngine(db)
        expired_count = rewards_engine.expire_old_rewards()

        return {"success": True, "expired_count": expired_count}

    except Exception as e:
        logger.error(f"Error expiring rewards: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to expire rewards")


@router.post("/maintenance/run-campaigns")
async def run_automated_campaigns(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run automated reward campaigns"""
    check_rewards_permission(current_user, "admin")

    def run_campaigns():
        try:
            rewards_engine = RewardsEngine(db)
            results = rewards_engine.run_automated_campaigns()
            logger.info(f"Campaign run completed: {results}")
        except Exception as e:
            logger.error(f"Error running campaigns: {str(e)}")

    background_tasks.add_task(run_campaigns)

    return {"success": True, "message": "Campaign processing started in background"}
