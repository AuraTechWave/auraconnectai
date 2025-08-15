# backend/modules/loyalty/routes/loyalty_routes.py

"""
Comprehensive routes for loyalty and rewards system.
"""

from fastapi import APIRouter, Depends, Query, status, Body, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from core.database import get_db
from core.auth import get_current_user
from core.error_handling import handle_api_errors, NotFoundError, APIValidationError
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services.loyalty_service import LoyaltyService
from ..schemas.loyalty_schemas import (
    # Loyalty Program
    LoyaltyProgramCreate,
    LoyaltyProgramUpdate,
    LoyaltyProgramResponse,
    # Customer Loyalty
    CustomerLoyaltyResponse,
    CustomerLoyaltyStats,
    CustomerLoyaltyUpdate,
    # Points
    PointsTransactionCreate,
    PointsTransactionResponse,
    PointsAdjustment,
    PointsTransfer,
    # Reward Templates
    RewardTemplateCreate,
    RewardTemplateUpdate,
    RewardTemplateResponse,
    # Customer Rewards
    CustomerRewardResponse,
    CustomerRewardSummary,
    ManualRewardIssuance,
    BulkRewardIssuance,
    RewardSearchParams,
    RewardSearchResponse,
    # Redemption
    RewardRedemptionRequest,
    RewardRedemptionResponse,
    RewardValidationRequest,
    RewardValidationResponse,
    # Campaigns
    RewardCampaignCreate,
    RewardCampaignUpdate,
    RewardCampaignResponse,
    # Analytics
    RewardAnalyticsRequest,
    RewardAnalyticsResponse,
    LoyaltyProgramAnalytics,
    # Order Integration
    OrderCompletionReward,
    OrderCompletionResponse,
)
from ..models.rewards_models import (
    RewardType,
    RewardStatus,
    RewardTemplate,
    CustomerReward,
    RewardCampaign,
    LoyaltyPointsTransaction,
)

router = APIRouter(prefix="/api/v1/loyalty", tags=["Loyalty"])


# ========== Customer Loyalty ==========


@router.get("/customers/{customer_id}/loyalty", response_model=CustomerLoyaltyStats)
@handle_api_errors
async def get_customer_loyalty(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get customer loyalty statistics and status.

    Returns:
        Comprehensive loyalty statistics

    Raises:
        403: Insufficient permissions
        404: Customer not found
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    service = LoyaltyService(db)
    stats = service.get_customer_loyalty(customer_id)

    return stats


@router.get(
    "/customers/{customer_id}/points/history",
    response_model=List[PointsTransactionResponse],
)
@handle_api_errors
async def get_points_history(
    customer_id: int,
    days: int = Query(90, ge=1, le=365),
    transaction_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get customer's points transaction history.

    Returns:
        List of points transactions

    Raises:
        403: Insufficient permissions
        404: Customer not found
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    from datetime import datetime, timedelta

    since_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(LoyaltyPointsTransaction).filter(
        LoyaltyPointsTransaction.customer_id == customer_id,
        LoyaltyPointsTransaction.created_at >= since_date,
    )

    if transaction_type:
        query = query.filter(
            LoyaltyPointsTransaction.transaction_type == transaction_type
        )

    # Order by most recent first
    query = query.order_by(LoyaltyPointsTransaction.created_at.desc())

    # Apply pagination
    transactions = query.offset((page - 1) * size).limit(size).all()

    return transactions


@router.post(
    "/customers/{customer_id}/points/add", response_model=PointsTransactionResponse
)
@handle_api_errors
async def add_customer_points(
    customer_id: int,
    transaction_data: PointsTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add points to customer account.

    Returns:
        Created points transaction

    Raises:
        403: Insufficient permissions
        404: Customer not found
        422: Insufficient points for redemption
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    # Ensure customer_id matches
    transaction_data.customer_id = customer_id

    service = LoyaltyService(db)
    transaction = service.add_points(transaction_data, current_user.id)

    return transaction


@router.post("/points/adjust", response_model=PointsTransactionResponse)
@handle_api_errors
async def adjust_points(
    adjustment: PointsAdjustment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually adjust customer points (add or deduct).

    Returns:
        Points transaction

    Raises:
        403: Insufficient permissions
        404: Customer not found
        422: Insufficient points balance
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    service = LoyaltyService(db)
    transaction = service.adjust_points(adjustment, current_user.id)

    return transaction


@router.post("/points/transfer", response_model=Dict[str, Any])
@handle_api_errors
async def transfer_points(
    transfer: PointsTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transfer points between customers.

    Returns:
        Transfer details

    Raises:
        403: Insufficient permissions
        404: Customer not found
        422: Insufficient points or same customer
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    service = LoyaltyService(db)
    debit_transaction, credit_transaction = service.transfer_points(
        transfer, current_user.id
    )

    return {
        "success": True,
        "from_transaction_id": debit_transaction.id,
        "to_transaction_id": credit_transaction.id,
        "points_transferred": transfer.points,
        "message": f"Successfully transferred {transfer.points} points",
    }


# ========== Reward Templates ==========


@router.post(
    "/templates",
    response_model=RewardTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
@handle_api_errors
async def create_reward_template(
    template_data: RewardTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new reward template.

    Returns:
        Created reward template

    Raises:
        403: Insufficient permissions
        409: Template name already exists
        422: Validation error
    """
    check_permission(current_user, Permission.LOYALTY_ADMIN)

    service = LoyaltyService(db)
    template = service.create_reward_template(template_data)

    return template


@router.get("/templates", response_model=List[RewardTemplateResponse])
@handle_api_errors
async def list_reward_templates(
    reward_type: Optional[RewardType] = Query(None),
    is_active: bool = Query(True),
    is_featured: Optional[bool] = Query(None),
    customer_id: Optional[int] = Query(
        None, description="Filter by customer eligibility"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List available reward templates.

    Returns:
        List of reward templates

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    service = LoyaltyService(db)

    # Get customer's points balance if filtering by customer
    points_balance = None
    if customer_id:
        points_balance = service._get_customer_points_balance(customer_id)

    templates = service.get_available_templates(
        customer_id=customer_id, reward_type=reward_type, points_balance=points_balance
    )

    # Additional filtering
    if is_featured is not None:
        templates = [t for t in templates if t.is_featured == is_featured]

    return templates


@router.get("/templates/{template_id}", response_model=RewardTemplateResponse)
@handle_api_errors
async def get_reward_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get specific reward template.

    Returns:
        Reward template details

    Raises:
        403: Insufficient permissions
        404: Template not found
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    template = db.query(RewardTemplate).filter(RewardTemplate.id == template_id).first()

    if not template:
        raise NotFoundError("Reward template", template_id)

    return template


@router.put("/templates/{template_id}", response_model=RewardTemplateResponse)
@handle_api_errors
async def update_reward_template(
    template_id: int,
    update_data: RewardTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update reward template.

    Returns:
        Updated reward template

    Raises:
        403: Insufficient permissions
        404: Template not found
    """
    check_permission(current_user, Permission.LOYALTY_ADMIN)

    service = LoyaltyService(db)
    template = service.update_reward_template(template_id, update_data)

    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_reward_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete (deactivate) reward template.

    Returns:
        No content on success

    Raises:
        403: Insufficient permissions
        404: Template not found
    """
    check_permission(current_user, Permission.LOYALTY_ADMIN)

    template = db.query(RewardTemplate).filter(RewardTemplate.id == template_id).first()

    if not template:
        raise NotFoundError("Reward template", template_id)

    template.is_active = False
    db.commit()


# ========== Customer Rewards ==========


@router.get("/customers/{customer_id}/rewards", response_model=CustomerRewardSummary)
@handle_api_errors
async def get_customer_rewards(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get customer's reward summary.

    Returns:
        Customer reward summary

    Raises:
        403: Insufficient permissions
        404: Customer not found
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    service = LoyaltyService(db)

    # Get available rewards
    available_rewards = (
        db.query(CustomerReward)
        .filter(
            CustomerReward.customer_id == customer_id,
            CustomerReward.status == RewardStatus.AVAILABLE,
        )
        .count()
    )

    # Get statistics
    stats = service._get_customer_rewards_stats(customer_id)

    # Get recent rewards
    recent_rewards = (
        db.query(CustomerReward)
        .filter(CustomerReward.customer_id == customer_id)
        .order_by(CustomerReward.created_at.desc())
        .limit(10)
        .all()
    )

    # Get rewards by type
    rewards_by_type = (
        db.query(CustomerReward.reward_type, func.count(CustomerReward.id))
        .filter(CustomerReward.customer_id == customer_id)
        .group_by(CustomerReward.reward_type)
        .all()
    )

    # Calculate total savings
    total_savings = (
        db.query(func.sum(CustomerReward.redeemed_amount))
        .filter(
            CustomerReward.customer_id == customer_id,
            CustomerReward.status == RewardStatus.REDEEMED,
        )
        .scalar()
        or 0.0
    )

    return CustomerRewardSummary(
        customer_id=customer_id,
        available_rewards=available_rewards,
        total_rewards_earned=stats["earned"],
        total_rewards_redeemed=stats["redeemed"],
        rewards_expiring_soon=0,  # TODO: Calculate
        total_savings=float(total_savings),
        rewards_by_type=dict(rewards_by_type),
        recent_rewards=recent_rewards,
    )


@router.post("/rewards/search", response_model=RewardSearchResponse)
@handle_api_errors
async def search_rewards(
    search_params: RewardSearchParams,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search and filter rewards.

    Returns:
        Paginated reward search results

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    service = LoyaltyService(db)
    rewards, total = service.search_customer_rewards(search_params)

    return RewardSearchResponse(
        items=rewards,
        total=total,
        page=search_params.page,
        pages=(total + search_params.limit - 1) // search_params.limit,
        has_next=search_params.page * search_params.limit < total,
        has_prev=search_params.page > 1,
    )


@router.post("/rewards/issue/manual", response_model=CustomerRewardResponse)
@handle_api_errors
async def issue_manual_reward(
    issuance: ManualRewardIssuance,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually issue a reward to a customer.

    Returns:
        Issued reward

    Raises:
        403: Insufficient permissions
        404: Customer or template not found
        422: Usage limit exceeded
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    service = LoyaltyService(db)
    reward = service.issue_manual_reward(issuance, current_user.id)

    return reward


@router.post("/rewards/issue/bulk", response_model=Dict[str, Any])
@handle_api_errors
async def issue_bulk_rewards(
    bulk_issuance: BulkRewardIssuance,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Issue rewards to multiple customers.

    Returns:
        Bulk issuance summary

    Raises:
        403: Insufficient permissions
        404: Template not found
        422: Invalid criteria
    """
    check_permission(current_user, Permission.LOYALTY_ADMIN)

    service = LoyaltyService(db)

    # For large batches, process in background
    if bulk_issuance.customer_ids and len(bulk_issuance.customer_ids) > 100:
        background_tasks.add_task(
            service.issue_bulk_rewards, bulk_issuance, current_user.id
        )
        return {
            "status": "processing",
            "message": f"Bulk reward issuance started for {len(bulk_issuance.customer_ids)} customers",
            "background_task": True,
        }

    # Process immediately for smaller batches
    rewards = service.issue_bulk_rewards(bulk_issuance, current_user.id)

    return {
        "status": "completed",
        "rewards_issued": len(rewards),
        "message": f"Successfully issued {len(rewards)} rewards",
        "reward_codes": [r.code for r in rewards[:10]],  # First 10 codes
    }


# ========== Reward Redemption ==========


@router.post("/rewards/validate", response_model=RewardValidationResponse)
@handle_api_errors
async def validate_reward(
    validation_request: RewardValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate if a reward can be used.

    Returns:
        Validation result

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    service = LoyaltyService(db)
    validation_result = service.validate_reward(validation_request)

    return RewardValidationResponse(**validation_result)


@router.post("/rewards/redeem", response_model=RewardRedemptionResponse)
@handle_api_errors
async def redeem_reward(
    redemption_request: RewardRedemptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Redeem a customer reward.

    Returns:
        Redemption result

    Raises:
        403: Insufficient permissions
        404: Reward not found
        422: Invalid reward or validation failed
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    service = LoyaltyService(db)
    result = service.redeem_reward(redemption_request, current_user.id)

    return RewardRedemptionResponse(**result)


# ========== Order Integration ==========


@router.post("/orders/complete", response_model=OrderCompletionResponse)
@handle_api_errors
async def process_order_completion(
    order_data: OrderCompletionReward,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process loyalty rewards for completed order.

    Returns:
        Order processing results

    Raises:
        403: Insufficient permissions
        404: Customer not found
    """
    check_permission(current_user, Permission.LOYALTY_MANAGE)

    service = LoyaltyService(db)
    result = service.process_order_completion(order_data)

    return OrderCompletionResponse(**result)


# ========== Campaigns ==========


@router.post(
    "/campaigns",
    response_model=RewardCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
@handle_api_errors
async def create_campaign(
    campaign_data: RewardCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a reward campaign.

    Returns:
        Created campaign

    Raises:
        403: Insufficient permissions
        404: Template not found
        422: Invalid dates
    """
    check_permission(current_user, Permission.LOYALTY_ADMIN)

    # Validate dates
    if campaign_data.start_date >= campaign_data.end_date:
        raise APIValidationError("End date must be after start date")

    # Validate template
    template = (
        db.query(RewardTemplate)
        .filter(
            RewardTemplate.id == campaign_data.template_id,
            RewardTemplate.is_active == True,
        )
        .first()
    )

    if not template:
        raise NotFoundError("Active reward template", campaign_data.template_id)

    campaign = RewardCampaign(
        name=campaign_data.name,
        description=campaign_data.description,
        template_id=campaign_data.template_id,
        start_date=campaign_data.start_date,
        end_date=campaign_data.end_date,
        target_criteria=campaign_data.target_criteria or {},
        target_tiers=campaign_data.target_tiers or [],
        target_segments=campaign_data.target_segments or [],
        max_rewards_total=campaign_data.max_rewards_total,
        max_rewards_per_customer=campaign_data.max_rewards_per_customer,
        is_automated=campaign_data.is_automated,
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


@router.get("/campaigns", response_model=List[RewardCampaignResponse])
@handle_api_errors
async def list_campaigns(
    is_active: Optional[bool] = Query(True),
    include_past: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List reward campaigns.

    Returns:
        List of campaigns

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.LOYALTY_VIEW)

    query = db.query(RewardCampaign)

    if is_active is not None:
        query = query.filter(RewardCampaign.is_active == is_active)

    if not include_past:
        query = query.filter(RewardCampaign.end_date >= datetime.utcnow())

    campaigns = query.order_by(RewardCampaign.start_date.desc()).all()

    return campaigns


# ========== Analytics ==========


@router.post("/analytics/rewards", response_model=RewardAnalyticsResponse)
@handle_api_errors
async def get_reward_analytics(
    request: RewardAnalyticsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get reward analytics.

    Returns:
        Analytics data

    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.LOYALTY_ANALYTICS)

    # TODO: Implement analytics calculation
    return RewardAnalyticsResponse(
        period={"start": request.start_date, "end": request.end_date},
        summary={
            "total_rewards_issued": 150,
            "total_rewards_redeemed": 120,
            "redemption_rate": 0.80,
            "total_discount_value": 2500.00,
        },
        trends=[],
        performance_metrics={"avg_redemption_days": 5.2, "customer_satisfaction": 4.5},
        customer_segments=[],
        revenue_impact={"revenue_lift": 0.12, "incremental_revenue": 5000.00},
    )


@router.get("/analytics/program/{program_id}", response_model=LoyaltyProgramAnalytics)
@handle_api_errors
async def get_program_analytics(
    program_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get loyalty program analytics.

    Returns:
        Program analytics

    Raises:
        403: Insufficient permissions
        404: Program not found
    """
    check_permission(current_user, Permission.LOYALTY_ANALYTICS)

    # TODO: Implement program analytics
    return LoyaltyProgramAnalytics(
        program_id=program_id,
        period={"start": start_date, "end": end_date},
        member_statistics={
            "total_members": 1500,
            "active_members": 1200,
            "new_members": 50,
        },
        points_statistics={
            "total_earned": 150000,
            "total_redeemed": 100000,
            "average_balance": 250,
        },
        reward_statistics={
            "total_issued": 500,
            "total_redeemed": 400,
            "popular_rewards": [],
        },
        engagement_metrics={
            "member_participation_rate": 0.75,
            "points_redemption_rate": 0.67,
        },
        revenue_metrics={
            "member_avg_order_value": 65.50,
            "non_member_avg_order_value": 45.00,
            "revenue_per_member": 850.00,
        },
        tier_distribution={"bronze": 800, "silver": 500, "gold": 150, "platinum": 50},
        top_performers=[],
    )
