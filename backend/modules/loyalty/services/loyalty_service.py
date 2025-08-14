# backend/modules/loyalty/services/loyalty_service.py

"""
Core service for loyalty program management.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from typing import List, Optional, Dict, Any, Tuple

# Import configurable loyalty tier service from customer module
try:
    # The configurable tier service lives under the customer module
    from modules.customers.models.loyalty_config import LoyaltyService as TierConfigService  # type: ignore
except ModuleNotFoundError:  # Fallback in case import path changes in the future
    TierConfigService = None  # pragma: no cover

from datetime import datetime, timedelta, date
import logging
import random
import string
from decimal import Decimal

from ..models.rewards_models import (
    RewardTemplate, CustomerReward, RewardCampaign,
    RewardRedemption, LoyaltyPointsTransaction,
    RewardType, RewardStatus, TriggerType
)
from ..schemas.loyalty_schemas import (
    CustomerLoyaltyCreate, CustomerLoyaltyUpdate, CustomerLoyaltyStats,
    PointsTransactionCreate, PointsAdjustment, PointsTransfer,
    RewardTemplateCreate, RewardTemplateUpdate,
    CustomerRewardCreate, ManualRewardIssuance, BulkRewardIssuance,
    RewardRedemptionRequest, RewardValidationRequest,
    OrderCompletionReward, RewardSearchParams
)
from modules.customers.models import Customer
from core.error_handling import NotFoundError, APIValidationError, ConflictError

logger = logging.getLogger(__name__)


class LoyaltyService:
    """Service for managing loyalty programs and rewards"""
    
    def __init__(self, db: Session):
        self.db = db
        self.default_points_per_dollar = 1.0
        self.default_points_expiry_days = 365
    
    # ========== Customer Loyalty Management ==========
    
    def get_customer_loyalty(self, customer_id: int) -> Optional[CustomerLoyaltyStats]:
        """Get comprehensive customer loyalty statistics.
        
        Retrieves customer's complete loyalty profile including:
        - Current points balance (excluding expired points)
        - Lifetime points earned and spent
        - Current tier with benefits
        - Recent points history (last 90 days)
        - Rewards statistics (earned vs redeemed)
        - Average order value and visit frequency
        - Points expiring in next 30 days
        
        Args:
            customer_id: The customer's database ID
            
        Returns:
            CustomerLoyaltyStats object with complete loyalty profile
            
        Raises:
            NotFoundError: If customer doesn't exist
            
        Business Logic:
            - Tiers: Bronze (0-1999), Silver (2000-4999), Gold (5000-9999), Platinum (10000+)
            - Points expire after 365 days by default
            - Tier calculation based on lifetime earned points
        """
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id
        ).first()
        
        if not customer:
            raise NotFoundError("Customer", customer_id)
        
        # Get points balance and history
        points_balance = self._get_customer_points_balance(customer_id)
        points_history = self._get_points_history(customer_id, days=90)
        
        # Get rewards statistics
        rewards_stats = self._get_customer_rewards_stats(customer_id)
        
        # Calculate tier and benefits
        tier_info = self._calculate_customer_tier(customer_id, points_balance)
        
        # Get expiring points
        expiring_points = self._get_expiring_points(customer_id, days=30)
        
        return CustomerLoyaltyStats(
            customer_id=customer_id,
            points_balance=points_balance,
            lifetime_points_earned=self._get_lifetime_points_earned(customer_id),
            lifetime_points_spent=self._get_lifetime_points_spent(customer_id),
            current_tier=tier_info['current_tier'],
            tier_benefits=tier_info['benefits'],
            points_history=points_history,
            rewards_earned=rewards_stats['earned'],
            rewards_redeemed=rewards_stats['redeemed'],
            average_order_value=self._get_average_order_value(customer_id),
            visit_frequency=self._get_visit_frequency(customer_id),
            member_since=customer.created_at.date(),
            days_until_tier_upgrade=tier_info.get('days_until_upgrade'),
            points_expiring_30_days=expiring_points
        )
    
    def add_points(
        self,
        transaction_data: PointsTransactionCreate,
        staff_id: Optional[int] = None
    ) -> LoyaltyPointsTransaction:
        """Add points to customer account"""
        # Validate customer
        customer = self.db.query(Customer).filter(
            Customer.id == transaction_data.customer_id
        ).first()
        
        if not customer:
            raise NotFoundError("Customer", transaction_data.customer_id)
        
        # Get current balance
        current_balance = self._get_customer_points_balance(transaction_data.customer_id)
        
        # Validate transaction
        if transaction_data.transaction_type == "redeemed" and transaction_data.points_change > 0:
            transaction_data.points_change = -abs(transaction_data.points_change)
        
        new_balance = current_balance + transaction_data.points_change
        
        if new_balance < 0:
            raise APIValidationError(
                "Insufficient points balance",
                {"current_balance": current_balance, "requested": abs(transaction_data.points_change)}
            )
        
        # Create transaction
        transaction = LoyaltyPointsTransaction(
            customer_id=transaction_data.customer_id,
            transaction_type=transaction_data.transaction_type,
            points_change=transaction_data.points_change,
            points_balance_before=current_balance,
            points_balance_after=new_balance,
            reason=transaction_data.reason,
            order_id=transaction_data.order_id,
            reward_id=transaction_data.reward_id,
            source=transaction_data.source,
            reference_id=transaction_data.reference_id,
            staff_member_id=staff_id,
            transaction_data=transaction_data.metadata,
            expires_at=transaction_data.expires_at
        )
        
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        
        # Check for tier upgrade
        self._check_tier_upgrade(transaction_data.customer_id, new_balance)
        
        return transaction
    
    def adjust_points(
        self,
        adjustment: PointsAdjustment,
        staff_id: int
    ) -> LoyaltyPointsTransaction:
        """Manually adjust customer points"""
        transaction_type = "adjusted"
        
        transaction_data = PointsTransactionCreate(
            customer_id=adjustment.customer_id,
            transaction_type=transaction_type,
            points_change=adjustment.points,
            reason=adjustment.reason,
            source="manual",
            expires_at=adjustment.expires_at
        )
        
        transaction = self.add_points(transaction_data, staff_id)
        
        if adjustment.notify_customer:
            # TODO: Send notification to customer
            pass
        
        return transaction
    
    def transfer_points(
        self,
        transfer: PointsTransfer,
        staff_id: int
    ) -> Tuple[LoyaltyPointsTransaction, LoyaltyPointsTransaction]:
        """Transfer points between customers"""
        # Validate both customers exist
        from_customer = self.db.query(Customer).filter(
            Customer.id == transfer.from_customer_id
        ).first()
        to_customer = self.db.query(Customer).filter(
            Customer.id == transfer.to_customer_id
        ).first()
        
        if not from_customer:
            raise NotFoundError("From customer", transfer.from_customer_id)
        if not to_customer:
            raise NotFoundError("To customer", transfer.to_customer_id)
        
        # Check balance
        from_balance = self._get_customer_points_balance(transfer.from_customer_id)
        if from_balance < transfer.points:
            raise APIValidationError(
                "Insufficient points for transfer",
                {"available": from_balance, "requested": transfer.points}
            )
        
        # Create debit transaction
        debit_data = PointsTransactionCreate(
            customer_id=transfer.from_customer_id,
            transaction_type="transferred",
            points_change=-transfer.points,
            reason=f"{transfer.reason} - to customer {transfer.to_customer_id}",
            source="transfer"
        )
        debit_transaction = self.add_points(debit_data, staff_id)
        
        # Create credit transaction
        credit_data = PointsTransactionCreate(
            customer_id=transfer.to_customer_id,
            transaction_type="transferred",
            points_change=transfer.points,
            reason=f"{transfer.reason} - from customer {transfer.from_customer_id}",
            source="transfer",
            reference_id=str(debit_transaction.id)
        )
        credit_transaction = self.add_points(credit_data, staff_id)
        
        return debit_transaction, credit_transaction
    
    # ========== Reward Template Management ==========
    
    def create_reward_template(
        self,
        template_data: RewardTemplateCreate
    ) -> RewardTemplate:
        """Create a new reward template"""
        # Validate template
        self._validate_reward_template(template_data)
        
        # Check for duplicate name
        existing = self.db.query(RewardTemplate).filter(
            RewardTemplate.name == template_data.name
        ).first()
        
        if existing:
            raise ConflictError(
                "Reward template with this name already exists",
                {"name": template_data.name}
            )
        
        template = RewardTemplate(
            name=template_data.name,
            description=template_data.description,
            reward_type=template_data.reward_type,
            value=template_data.value,
            percentage=template_data.percentage,
            points_cost=template_data.points_cost,
            item_id=template_data.item_id,
            category_ids=template_data.category_ids or [],
            min_order_amount=template_data.min_order_amount,
            max_discount_amount=template_data.max_discount_amount,
            max_uses_per_customer=template_data.max_uses_per_customer,
            max_uses_total=template_data.max_uses_total,
            valid_days=template_data.valid_days,
            valid_from_date=template_data.valid_from_date,
            valid_until_date=template_data.valid_until_date,
            eligible_tiers=template_data.eligible_tiers or [],
            trigger_type=template_data.trigger_type,
            trigger_conditions=template_data.trigger_conditions or {},
            auto_apply=template_data.auto_apply,
            title=template_data.title,
            subtitle=template_data.subtitle,
            terms_and_conditions=template_data.terms_and_conditions,
            image_url=template_data.image_url,
            icon=template_data.icon,
            is_featured=template_data.is_featured,
            priority=template_data.priority
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def update_reward_template(
        self,
        template_id: int,
        update_data: RewardTemplateUpdate
    ) -> RewardTemplate:
        """Update reward template"""
        template = self.db.query(RewardTemplate).filter(
            RewardTemplate.id == template_id
        ).first()
        
        if not template:
            raise NotFoundError("Reward template", template_id)
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(template, field, value)
        
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    def get_available_templates(
        self,
        customer_id: Optional[int] = None,
        reward_type: Optional[RewardType] = None,
        points_balance: Optional[int] = None
    ) -> List[RewardTemplate]:
        """Get available reward templates"""
        query = self.db.query(RewardTemplate).filter(
            RewardTemplate.is_active == True
        )
        
        if reward_type:
            query = query.filter(RewardTemplate.reward_type == reward_type)
        
        # Filter by customer tier if customer provided
        if customer_id:
            tier = self._get_customer_tier(customer_id)
            query = query.filter(
                or_(
                    RewardTemplate.eligible_tiers == [],
                    RewardTemplate.eligible_tiers.contains([tier])
                )
            )
        
        # Filter by points cost if balance provided
        if points_balance is not None:
            query = query.filter(
                or_(
                    RewardTemplate.points_cost == None,
                    RewardTemplate.points_cost <= points_balance
                )
            )
        
        # Order by priority and name
        templates = query.order_by(
            desc(RewardTemplate.priority),
            RewardTemplate.name
        ).all()
        
        return templates
    
    # ========== Customer Rewards ==========
    
    def issue_reward(
        self,
        customer_id: int,
        template_id: int,
        trigger_data: Optional[Dict[str, Any]] = None,
        valid_days_override: Optional[int] = None,
        issued_by: Optional[int] = None
    ) -> CustomerReward:
        """Issue a reward to a customer"""
        # Validate customer and template
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise NotFoundError("Customer", customer_id)
        
        template = self.db.query(RewardTemplate).filter(
            RewardTemplate.id == template_id,
            RewardTemplate.is_active == True
        ).first()
        if not template:
            raise NotFoundError("Active reward template", template_id)
        
        # Check usage limits
        existing_count = self.db.query(CustomerReward).filter(
            CustomerReward.customer_id == customer_id,
            CustomerReward.template_id == template_id
        ).count()
        
        if template.max_uses_per_customer and existing_count >= template.max_uses_per_customer:
            raise APIValidationError(
                "Customer has reached the maximum uses for this reward",
                {"max_uses": template.max_uses_per_customer, "current_uses": existing_count}
            )
        
        # Generate unique code
        code = self._generate_reward_code()
        
        # Calculate validity
        valid_days = valid_days_override or template.valid_days
        valid_from = datetime.utcnow()
        valid_until = valid_from + timedelta(days=valid_days)
        
        # Apply template date restrictions
        if template.valid_from_date and valid_from < template.valid_from_date:
            valid_from = template.valid_from_date
        if template.valid_until_date and valid_until > template.valid_until_date:
            valid_until = template.valid_until_date
        
        # Create reward
        reward = CustomerReward(
            customer_id=customer_id,
            template_id=template_id,
            reward_type=template.reward_type,
            title=template.title,
            description=template.description,
            value=template.value,
            percentage=template.percentage,
            points_cost=template.points_cost,
            code=code,
            status=RewardStatus.AVAILABLE,
            valid_from=valid_from,
            valid_until=valid_until,
            issued_by=issued_by,
            trigger_data=trigger_data or {}
        )
        
        self.db.add(reward)
        
        # Update template statistics
        template.total_issued += 1
        
        # Deduct points if required
        if template.points_cost and template.points_cost > 0:
            points_transaction = PointsTransactionCreate(
                customer_id=customer_id,
                transaction_type="redeemed",
                points_change=-template.points_cost,
                reason=f"Redeemed for: {template.title}",
                reward_id=reward.id,
                source="reward_redemption"
            )
            self.add_points(points_transaction)
        
        self.db.commit()
        self.db.refresh(reward)
        
        return reward
    
    def issue_manual_reward(
        self,
        issuance: ManualRewardIssuance,
        staff_id: int
    ) -> CustomerReward:
        """Manually issue a reward to a customer"""
        reward = self.issue_reward(
            customer_id=issuance.customer_id,
            template_id=issuance.template_id,
            trigger_data={"reason": issuance.reason, "manual": True},
            valid_days_override=issuance.valid_days_override,
            issued_by=staff_id
        )
        
        if issuance.notify_customer:
            # TODO: Send notification
            pass
        
        return reward
    
    def issue_bulk_rewards(
        self,
        bulk_issuance: BulkRewardIssuance,
        staff_id: int
    ) -> List[CustomerReward]:
        """Issue rewards to multiple customers"""
        # Get target customers
        if bulk_issuance.customer_ids:
            customer_ids = bulk_issuance.customer_ids
        else:
            # Apply criteria to find customers
            customer_ids = self._find_customers_by_criteria(bulk_issuance.customer_criteria)
        
        issued_rewards = []
        errors = []
        
        for customer_id in customer_ids:
            try:
                reward = self.issue_reward(
                    customer_id=customer_id,
                    template_id=bulk_issuance.template_id,
                    trigger_data={
                        "reason": bulk_issuance.reason,
                        "bulk": True,
                        "batch_size": len(customer_ids)
                    },
                    issued_by=staff_id
                )
                issued_rewards.append(reward)
            except Exception as e:
                errors.append({"customer_id": customer_id, "error": str(e)})
                logger.error(f"Failed to issue reward to customer {customer_id}: {e}")
        
        if bulk_issuance.notify_customers and issued_rewards:
            # TODO: Send bulk notifications
            pass
        
        return issued_rewards
    
    def validate_reward(
        self,
        validation_request: RewardValidationRequest
    ) -> Dict[str, Any]:
        """Validate if a reward can be used"""
        reward = self.db.query(CustomerReward).filter(
            CustomerReward.code == validation_request.reward_code.upper()
        ).first()
        
        if not reward:
            return {
                "is_valid": False,
                "validation_errors": ["Invalid reward code"]
            }
        
        validation_errors = []
        
        # Check status
        if reward.status != RewardStatus.AVAILABLE:
            validation_errors.append(f"Reward is {reward.status}")
        
        # Check validity dates
        now = datetime.utcnow()
        if now < reward.valid_from:
            validation_errors.append("Reward is not yet valid")
        elif now > reward.valid_until:
            validation_errors.append("Reward has expired")
        
        # Check order amount
        template = reward.template
        if template.min_order_amount and validation_request.order_amount < template.min_order_amount:
            validation_errors.append(
                f"Minimum order amount of ${template.min_order_amount:.2f} required"
            )
        
        # Calculate discount
        discount_amount = self._calculate_discount(
            reward,
            validation_request.order_amount,
            validation_request.order_items
        )
        
        return {
            "is_valid": len(validation_errors) == 0,
            "reward_type": reward.reward_type.value if reward else None,
            "discount_amount": discount_amount,
            "applicable_items": None,  # TODO: Implement item-specific discounts
            "validation_errors": validation_errors,
            "terms_and_conditions": template.terms_and_conditions if template else None
        }
    
    def redeem_reward(
        self,
        redemption_request: RewardRedemptionRequest,
        staff_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Redeem a customer reward"""
        # Validate reward
        validation = self.validate_reward(
            RewardValidationRequest(
                reward_code=redemption_request.reward_code,
                order_amount=redemption_request.order_amount
            )
        )
        
        if not validation["is_valid"]:
            return {
                "success": False,
                "message": "; ".join(validation["validation_errors"])
            }
        
        # Get reward
        reward = self.db.query(CustomerReward).filter(
            CustomerReward.code == redemption_request.reward_code.upper()
        ).with_for_update().first()
        
        # Double-check status with lock
        if reward.status != RewardStatus.AVAILABLE:
            return {
                "success": False,
                "message": "Reward is no longer available"
            }
        
        # Mark as redeemed
        reward.status = RewardStatus.REDEEMED
        reward.redeemed_at = datetime.utcnow()
        reward.order_id = redemption_request.order_id
        reward.redeemed_amount = validation["discount_amount"]
        
        # Create redemption record
        redemption = RewardRedemption(
            reward_id=reward.id,
            customer_id=reward.customer_id,
            order_id=redemption_request.order_id,
            original_order_amount=redemption_request.order_amount,
            discount_applied=validation["discount_amount"],
            final_order_amount=redemption_request.order_amount - validation["discount_amount"],
            redemption_method="manual" if staff_id else "auto",
            staff_member_id=staff_id
        )
        
        self.db.add(redemption)
        
        # Update template statistics
        reward.template.total_redeemed += 1
        
        self.db.commit()
        
        return {
            "success": True,
            "reward_id": reward.id,
            "discount_amount": validation["discount_amount"],
            "final_order_amount": redemption.final_order_amount,
            "message": "Reward redeemed successfully",
            "redemption_id": redemption.id
        }
    
    def search_customer_rewards(
        self,
        search_params: RewardSearchParams
    ) -> Tuple[List[CustomerReward], int]:
        """Search customer rewards with filters"""
        query = self.db.query(CustomerReward)
        
        if search_params.customer_id:
            query = query.filter(CustomerReward.customer_id == search_params.customer_id)
        
        if search_params.reward_type:
            query = query.filter(CustomerReward.reward_type == search_params.reward_type)
        
        if search_params.status:
            query = query.filter(CustomerReward.status == search_params.status)
        
        if search_params.is_expired is not None:
            now = datetime.utcnow()
            if search_params.is_expired:
                query = query.filter(CustomerReward.valid_until < now)
            else:
                query = query.filter(CustomerReward.valid_until >= now)
        
        if search_params.min_value is not None:
            query = query.filter(CustomerReward.value >= search_params.min_value)
        
        if search_params.max_value is not None:
            query = query.filter(CustomerReward.value <= search_params.max_value)
        
        if search_params.valid_on_date:
            date_check = datetime.combine(search_params.valid_on_date, datetime.min.time())
            query = query.filter(
                CustomerReward.valid_from <= date_check,
                CustomerReward.valid_until >= date_check
            )
        
        if search_params.search_text:
            search_term = f"%{search_params.search_text}%"
            query = query.filter(
                or_(
                    CustomerReward.title.ilike(search_term),
                    CustomerReward.description.ilike(search_term),
                    CustomerReward.code.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(CustomerReward, search_params.sort_by, CustomerReward.created_at)
        if search_params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Apply pagination
        rewards = query.offset(
            (search_params.page - 1) * search_params.limit
        ).limit(search_params.limit).all()
        
        return rewards, total
    
    # ========== Order Integration ==========
    
    def process_order_completion(
        self,
        order_data: OrderCompletionReward
    ) -> Dict[str, Any]:
        """Process rewards and points for completed order"""
        results = {
            "points_earned": 0,
            "rewards_triggered": [],
            "tier_progress": {},
            "notifications_sent": False
        }
        
        # Calculate points earned
        points_earned = int(order_data.order_amount * self.default_points_per_dollar)
        
        if points_earned > 0:
            # Add points
            points_transaction = PointsTransactionCreate(
                customer_id=order_data.customer_id,
                transaction_type="earned",
                points_change=points_earned,
                reason=f"Order #{order_data.order_id} completed",
                order_id=order_data.order_id,
                source="order",
                expires_at=datetime.utcnow() + timedelta(days=self.default_points_expiry_days)
            )
            self.add_points(points_transaction)
            results["points_earned"] = points_earned
        
        # Check for triggered rewards
        triggered_rewards = self._check_reward_triggers(order_data)
        
        for template_id in triggered_rewards:
            try:
                reward = self.issue_reward(
                    customer_id=order_data.customer_id,
                    template_id=template_id,
                    trigger_data={
                        "order_id": order_data.order_id,
                        "order_amount": order_data.order_amount,
                        "trigger": "order_complete"
                    }
                )
                results["rewards_triggered"].append({
                    "reward_id": reward.id,
                    "title": reward.title,
                    "code": reward.code
                })
            except Exception as e:
                logger.error(f"Failed to issue triggered reward {template_id}: {e}")
        
        # Get tier progress
        new_balance = self._get_customer_points_balance(order_data.customer_id)
        tier_info = self._calculate_customer_tier(order_data.customer_id, new_balance)
        results["tier_progress"] = {
            "current_tier": tier_info["current_tier"],
            "points_to_next_tier": tier_info.get("points_to_next_tier"),
            "progress_percentage": tier_info.get("progress_percentage", 0)
        }
        
        # Send notifications
        if points_earned > 0 or results["rewards_triggered"]:
            # TODO: Send notification
            results["notifications_sent"] = True
        
        return results
    
    # ========== Helper Methods ==========
    
    def _get_customer_points_balance(self, customer_id: int) -> int:
        """Get current points balance for customer"""
        result = self.db.query(
            func.sum(LoyaltyPointsTransaction.points_change)
        ).filter(
            LoyaltyPointsTransaction.customer_id == customer_id,
            or_(
                LoyaltyPointsTransaction.expires_at == None,
                LoyaltyPointsTransaction.expires_at > datetime.utcnow()
            ),
            LoyaltyPointsTransaction.is_expired == False
        ).scalar()
        
        return result or 0
    
    def _get_lifetime_points_earned(self, customer_id: int) -> int:
        """Get total points earned by customer"""
        result = self.db.query(
            func.sum(LoyaltyPointsTransaction.points_change)
        ).filter(
            LoyaltyPointsTransaction.customer_id == customer_id,
            LoyaltyPointsTransaction.points_change > 0
        ).scalar()
        
        return result or 0
    
    def _get_lifetime_points_spent(self, customer_id: int) -> int:
        """Get total points spent by customer"""
        result = self.db.query(
            func.sum(func.abs(LoyaltyPointsTransaction.points_change))
        ).filter(
            LoyaltyPointsTransaction.customer_id == customer_id,
            LoyaltyPointsTransaction.points_change < 0
        ).scalar()
        
        return result or 0
    
    def _get_points_history(self, customer_id: int, days: int = 90) -> List[Dict[str, Any]]:
        """Get recent points transaction history"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        transactions = self.db.query(LoyaltyPointsTransaction).filter(
            LoyaltyPointsTransaction.customer_id == customer_id,
            LoyaltyPointsTransaction.created_at >= since_date
        ).order_by(desc(LoyaltyPointsTransaction.created_at)).limit(50).all()
        
        return [
            {
                "date": t.created_at,
                "type": t.transaction_type,
                "points": t.points_change,
                "balance": t.points_balance_after,
                "reason": t.reason,
                "order_id": t.order_id
            }
            for t in transactions
        ]
    
    def _get_customer_rewards_stats(self, customer_id: int) -> Dict[str, int]:
        """Get customer reward statistics"""
        earned = self.db.query(func.count(CustomerReward.id)).filter(
            CustomerReward.customer_id == customer_id
        ).scalar() or 0
        
        redeemed = self.db.query(func.count(CustomerReward.id)).filter(
            CustomerReward.customer_id == customer_id,
            CustomerReward.status == RewardStatus.REDEEMED
        ).scalar() or 0
        
        return {"earned": earned, "redeemed": redeemed}
    
    def _get_customer_tier(self, customer_id: int) -> str:
        """Determine customer's current tier using configurable tier definitions.

        Falls back to the legacy static calculation if the configurable service
        is unavailable (e.g. during certain unit-tests).
        """

        # Attempt to use advanced tier configuration if available
        if TierConfigService:
            customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
            if customer:
                tier_service = TierConfigService(self.db)
                return tier_service.calculate_tier_for_customer(customer)

        # Legacy static calculation (back-compat)
        lifetime_points = self._get_lifetime_points_earned(customer_id)

        if lifetime_points >= 20000:
            return "vip"
        elif lifetime_points >= 10000:
            return "platinum"
        elif lifetime_points >= 5000:
            return "gold"
        elif lifetime_points >= 2000:
            return "silver"
        else:
            return "bronze"
    
    def _calculate_customer_tier(
        self,
        customer_id: int,
        current_balance: int
    ) -> Dict[str, Any]:
        """Return detailed tier info (benefits, progress, etc.) using configurable tiers."""

        # Attempt to use advanced tier configuration if available
        if TierConfigService:
            customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
            if customer:
                tier_service = TierConfigService(self.db)
                tier_configs = tier_service.get_tier_configs()

                # Ensure configs are ordered correctly
                tier_configs.sort(key=lambda cfg: cfg.tier_order)

                lifetime_points = self._get_lifetime_points_earned(customer_id)
                current_tier = tier_service.calculate_tier_for_customer(customer)

                result: Dict[str, Any] = {
                    "current_tier": current_tier,
                    "benefits": tier_service.get_tier_benefits(current_tier)
                }

                # Determine next tier information
                tier_names = [cfg.tier_name for cfg in tier_configs]
                if current_tier in tier_names:
                    current_idx = tier_names.index(current_tier)
                    if current_idx < len(tier_configs) - 1:
                        next_cfg = tier_configs[current_idx + 1]
                        points_needed = (next_cfg.min_lifetime_points or 0) - lifetime_points
                        result.update(
                            {
                                "next_tier": next_cfg.tier_name,
                                "points_to_next_tier": max(0, points_needed),
                                "progress_percentage": min(100, (lifetime_points / (next_cfg.min_lifetime_points or 1)) * 100)
                            }
                        )

                return result

        # Fallback to legacy static tiers if config not available
        lifetime_points = self._get_lifetime_points_earned(customer_id)
        current_tier = self._get_customer_tier(customer_id)

        tiers = {
            "bronze": {"min": 0, "benefits": ["1x points earning"]},
            "silver": {"min": 2000, "benefits": ["1.2x points earning", "Birthday bonus"]},
            "gold": {"min": 5000, "benefits": ["1.5x points earning", "Birthday bonus", "Free delivery"]},
            "platinum": {"min": 10000, "benefits": ["2x points earning", "Birthday bonus", "Free delivery", "VIP support"]},
            "vip": {"min": 20000, "benefits": ["2.5x points earning", "Birthday bonus", "Free delivery", "VIP support", "Exclusive offers"]}
        }

        tier_order = ["bronze", "silver", "gold", "platinum", "vip"]
        current_idx = tier_order.index(current_tier)

        result = {
            "current_tier": current_tier,
            "benefits": tiers[current_tier]["benefits"]
        }

        if current_idx < len(tier_order) - 1:
            next_tier = tier_order[current_idx + 1]
            points_needed = tiers[next_tier]["min"] - lifetime_points
            result.update(
                {
                    "points_to_next_tier": max(0, points_needed),
                    "next_tier": next_tier,
                    "progress_percentage": min(100, (lifetime_points / tiers[next_tier]["min"]) * 100)
                }
            )

        return result
    
    def _get_expiring_points(self, customer_id: int, days: int = 30) -> int:
        """Get points expiring within specified days"""
        expiry_date = datetime.utcnow() + timedelta(days=days)
        
        result = self.db.query(
            func.sum(LoyaltyPointsTransaction.points_change)
        ).filter(
            LoyaltyPointsTransaction.customer_id == customer_id,
            LoyaltyPointsTransaction.points_change > 0,
            LoyaltyPointsTransaction.expires_at != None,
            LoyaltyPointsTransaction.expires_at <= expiry_date,
            LoyaltyPointsTransaction.expires_at > datetime.utcnow(),
            LoyaltyPointsTransaction.is_expired == False
        ).scalar()
        
        return result or 0
    
    def _get_average_order_value(self, customer_id: int) -> float:
        """Get customer's average order value"""
        # TODO: Integrate with orders module
        return 45.50  # Placeholder
    
    def _get_visit_frequency(self, customer_id: int) -> str:
        """Get customer's visit frequency"""
        # TODO: Calculate based on order history
        return "weekly"  # Placeholder
    
    def _check_tier_upgrade(self, customer_id: int, new_balance: int):
        """Check if customer qualifies for tier upgrade"""
        old_tier = self._get_customer_tier(customer_id)
        
        # Recalculate with new balance
        lifetime_points = self._get_lifetime_points_earned(customer_id)
        
        # Determine new tier
        if lifetime_points >= 10000:
            new_tier = "platinum"
        elif lifetime_points >= 5000:
            new_tier = "gold"
        elif lifetime_points >= 2000:
            new_tier = "silver"
        else:
            new_tier = "bronze"
        
        if new_tier != old_tier:
            # TODO: Trigger tier upgrade rewards and notifications
            logger.info(f"Customer {customer_id} upgraded from {old_tier} to {new_tier}")
    
    def _validate_reward_template(self, template_data: RewardTemplateCreate):
        """Validate reward template data"""
        if template_data.reward_type == RewardType.PERCENTAGE_DISCOUNT:
            if not template_data.percentage or template_data.percentage <= 0:
                raise APIValidationError("Percentage discount requires valid percentage")
        elif template_data.reward_type == RewardType.FIXED_DISCOUNT:
            if not template_data.value or template_data.value <= 0:
                raise APIValidationError("Fixed discount requires valid value")
        elif template_data.reward_type == RewardType.FREE_ITEM:
            if not template_data.item_id:
                raise APIValidationError("Free item reward requires item_id")
    
    def _generate_reward_code(self) -> str:
        """Generate unique reward code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Check if code exists
            existing = self.db.query(CustomerReward).filter(
                CustomerReward.code == code
            ).first()
            
            if not existing:
                return code
    
    def _calculate_discount(
        self,
        reward: CustomerReward,
        order_amount: float,
        order_items: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """Calculate discount amount for reward"""
        template = reward.template
        
        if reward.reward_type == RewardType.PERCENTAGE_DISCOUNT:
            discount = order_amount * (reward.percentage / 100)
        elif reward.reward_type == RewardType.FIXED_DISCOUNT:
            discount = min(reward.value, order_amount)
        elif reward.reward_type == RewardType.POINTS_DISCOUNT:
            # Convert points to dollar value (e.g., 100 points = $1)
            discount = min(reward.value, order_amount)
        else:
            discount = 0
        
        # Apply max discount limit
        if template.max_discount_amount:
            discount = min(discount, template.max_discount_amount)
        
        return round(discount, 2)
    
    def _find_customers_by_criteria(
        self,
        criteria: Dict[str, Any]
    ) -> List[int]:
        """Find customers matching criteria"""
        # TODO: Implement customer search based on criteria
        # For now, return empty list
        return []
    
    def _check_reward_triggers(
        self,
        order_data: OrderCompletionReward
    ) -> List[int]:
        """Check which reward templates should be triggered"""
        triggered = []
        
        # Get active templates with order completion trigger
        templates = self.db.query(RewardTemplate).filter(
            RewardTemplate.is_active == True,
            RewardTemplate.trigger_type == TriggerType.ORDER_COMPLETE
        ).all()
        
        for template in templates:
            conditions = template.trigger_conditions or {}
            
            # Check conditions
            if conditions.get("min_order_amount"):
                if order_data.order_amount < conditions["min_order_amount"]:
                    continue
            
            if conditions.get("nth_order"):
                # TODO: Check if this is the nth order
                pass
            
            # Check if customer already has this reward
            existing = self.db.query(CustomerReward).filter(
                CustomerReward.customer_id == order_data.customer_id,
                CustomerReward.template_id == template.id,
                CustomerReward.status == RewardStatus.AVAILABLE
            ).first()
            
            if not existing:
                triggered.append(template.id)
        
        return triggered