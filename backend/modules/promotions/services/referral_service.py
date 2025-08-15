# backend/modules/promotions/services/referral_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import string
import logging

from ..models.promotion_models import ReferralProgram, CustomerReferral, ReferralStatus
from ..schemas.promotion_schemas import ReferralProgramCreate, CustomerReferralCreate
from modules.customers.models.customer_models import Customer
from modules.orders.models.order_models import Order

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for managing referral programs and customer referrals"""

    def __init__(self, db: Session):
        self.db = db

    def generate_referral_code(self, customer_id: int, length: int = 8) -> str:
        """
        Generate a unique referral code for a customer

        Args:
            customer_id: ID of the referring customer
            length: Length of the random part of the code

        Returns:
            Unique referral code
        """
        # Get customer for prefix
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Create prefix from customer name/email
        prefix = ""
        if customer.first_name:
            prefix = customer.first_name[:3].upper()
        elif customer.email:
            prefix = customer.email[:3].upper()
        else:
            prefix = "REF"

        # Character set for random part (exclude ambiguous characters)
        chars = string.ascii_uppercase + string.digits
        chars = chars.translate(str.maketrans("", "", "01IO"))

        max_attempts = 100
        for attempt in range(max_attempts):
            # Generate random part
            random_part = "".join(secrets.choice(chars) for _ in range(length))
            code = f"{prefix}{random_part}"

            # Check uniqueness
            existing = (
                self.db.query(CustomerReferral)
                .filter(CustomerReferral.referral_code == code)
                .first()
            )

            if not existing:
                return code

        raise ValueError(
            f"Could not generate unique referral code after {max_attempts} attempts"
        )

    def create_referral_program(
        self, program_data: ReferralProgramCreate, created_by: Optional[int] = None
    ) -> ReferralProgram:
        """Create a new referral program"""
        try:
            program = ReferralProgram(
                name=program_data.name,
                description=program_data.description,
                referrer_reward_type=program_data.referrer_reward_type,
                referrer_reward_value=program_data.referrer_reward_value,
                referee_reward_type=program_data.referee_reward_type,
                referee_reward_value=program_data.referee_reward_value,
                min_referee_order_amount=program_data.min_referee_order_amount,
                max_referrals_per_customer=program_data.max_referrals_per_customer,
                referral_validity_days=program_data.referral_validity_days,
                start_date=program_data.start_date,
                end_date=program_data.end_date,
            )

            self.db.add(program)
            self.db.commit()
            self.db.refresh(program)

            logger.info(f"Created referral program: {program.name} (ID: {program.id})")
            return program

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating referral program: {str(e)}")
            raise

    def create_referral(
        self, referral_data: CustomerReferralCreate, program_id: Optional[int] = None
    ) -> CustomerReferral:
        """
        Create a new customer referral

        Args:
            referral_data: Referral creation data
            program_id: Specific program ID (uses active program if not specified)

        Returns:
            Created CustomerReferral
        """
        try:
            # Get active referral program
            if program_id:
                program = (
                    self.db.query(ReferralProgram)
                    .filter(
                        ReferralProgram.id == program_id,
                        ReferralProgram.is_active == True,
                    )
                    .first()
                )
            else:
                program = (
                    self.db.query(ReferralProgram)
                    .filter(
                        ReferralProgram.is_active == True,
                        ReferralProgram.start_date <= datetime.utcnow(),
                        or_(
                            ReferralProgram.end_date.is_(None),
                            ReferralProgram.end_date > datetime.utcnow(),
                        ),
                    )
                    .first()
                )

            if not program:
                raise ValueError("No active referral program found")

            # Validate referrer exists
            referrer = (
                self.db.query(Customer)
                .filter(Customer.id == referral_data.referrer_id)
                .first()
            )

            if not referrer:
                raise ValueError(f"Referrer {referral_data.referrer_id} not found")

            # Check referral limits
            if program.max_referrals_per_customer:
                existing_referrals = (
                    self.db.query(CustomerReferral)
                    .filter(
                        CustomerReferral.program_id == program.id,
                        CustomerReferral.referrer_id == referral_data.referrer_id,
                        CustomerReferral.status != ReferralStatus.CANCELLED,
                    )
                    .count()
                )

                if existing_referrals >= program.max_referrals_per_customer:
                    raise ValueError(
                        f"Customer has reached maximum referrals limit ({program.max_referrals_per_customer})"
                    )

            # Check if referee email is already referred by this customer
            existing_referral = (
                self.db.query(CustomerReferral)
                .filter(
                    CustomerReferral.program_id == program.id,
                    CustomerReferral.referrer_id == referral_data.referrer_id,
                    CustomerReferral.referee_email == referral_data.referee_email,
                    CustomerReferral.status.in_(
                        [ReferralStatus.PENDING, ReferralStatus.COMPLETED]
                    ),
                )
                .first()
            )

            if existing_referral:
                raise ValueError(
                    "This email has already been referred by this customer"
                )

            # Check if referee email belongs to existing customer who was already referred
            referee_customer = (
                self.db.query(Customer)
                .filter(Customer.email == referral_data.referee_email)
                .first()
            )

            if referee_customer:
                existing_referee_referral = (
                    self.db.query(CustomerReferral)
                    .filter(
                        CustomerReferral.program_id == program.id,
                        CustomerReferral.referee_id == referee_customer.id,
                        CustomerReferral.status.in_(
                            [ReferralStatus.COMPLETED, ReferralStatus.REWARDED]
                        ),
                    )
                    .first()
                )

                if existing_referee_referral:
                    raise ValueError(
                        "This customer has already been referred in this program"
                    )

            # Generate referral code
            referral_code = self.generate_referral_code(referral_data.referrer_id)

            # Calculate expiration date
            expires_at = datetime.utcnow() + timedelta(
                days=program.referral_validity_days
            )

            # Create referral
            referral = CustomerReferral(
                program_id=program.id,
                referrer_id=referral_data.referrer_id,
                referee_email=referral_data.referee_email,
                referral_code=referral_code,
                expires_at=expires_at,
            )

            self.db.add(referral)
            self.db.commit()
            self.db.refresh(referral)

            # Update program statistics
            program.total_referrals += 1
            self.db.commit()

            logger.info(
                f"Created referral: {referral_code} from customer {referral_data.referrer_id} "
                f"to {referral_data.referee_email}"
            )

            return referral

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating referral: {str(e)}")
            raise

    def process_referral_signup(
        self, referee_email: str, referee_id: int
    ) -> List[CustomerReferral]:
        """
        Process when a referred customer signs up

        Args:
            referee_email: Email of the new customer
            referee_id: ID of the newly created customer

        Returns:
            List of updated referrals
        """
        try:
            # Find pending referrals for this email
            pending_referrals = (
                self.db.query(CustomerReferral)
                .filter(
                    CustomerReferral.referee_email == referee_email,
                    CustomerReferral.status == ReferralStatus.PENDING,
                    CustomerReferral.expires_at > datetime.utcnow(),
                )
                .all()
            )

            updated_referrals = []

            for referral in pending_referrals:
                # Link to the new customer
                referral.referee_id = referee_id
                updated_referrals.append(referral)

            self.db.commit()

            logger.info(
                f"Updated {len(updated_referrals)} referrals for new customer {referee_id}"
            )
            return updated_referrals

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing referral signup: {str(e)}")
            raise

    def process_referral_completion(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Process referral completion when referee makes qualifying order

        Args:
            order_id: ID of the qualifying order

        Returns:
            List of processed referrals with reward information
        """
        try:
            # Get order details
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order or not order.customer_id:
                return []

            # Find referrals to complete
            referrals_to_complete = (
                self.db.query(CustomerReferral)
                .options(joinedload(CustomerReferral.program))
                .filter(
                    CustomerReferral.referee_id == order.customer_id,
                    CustomerReferral.status == ReferralStatus.PENDING,
                    CustomerReferral.expires_at > datetime.utcnow(),
                )
                .all()
            )

            processed_referrals = []

            for referral in referrals_to_complete:
                program = referral.program

                # Check if order meets minimum amount requirement
                if (
                    program.min_referee_order_amount
                    and order.total < program.min_referee_order_amount
                ):
                    continue

                # Complete the referral
                referral.status = ReferralStatus.COMPLETED
                referral.completed_at = datetime.utcnow()
                referral.qualifying_order_id = order_id

                # Set reward amounts
                referral.referrer_reward_amount = program.referrer_reward_value
                referral.referee_reward_amount = program.referee_reward_value

                # Update program statistics
                program.successful_referrals += 1

                processed_referrals.append(
                    {
                        "referral_id": referral.id,
                        "referral_code": referral.referral_code,
                        "referrer_id": referral.referrer_id,
                        "referee_id": referral.referee_id,
                        "program_id": referral.program_id,
                        "referrer_reward_type": program.referrer_reward_type,
                        "referrer_reward_amount": referral.referrer_reward_amount,
                        "referee_reward_type": program.referee_reward_type,
                        "referee_reward_amount": referral.referee_reward_amount,
                    }
                )

            self.db.commit()

            logger.info(
                f"Completed {len(processed_referrals)} referrals for order {order_id}"
            )
            return processed_referrals

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing referral completion: {str(e)}")
            raise

    def issue_referral_rewards(self, referral_id: int) -> Dict[str, Any]:
        """
        Issue rewards for a completed referral

        Args:
            referral_id: ID of the completed referral

        Returns:
            Dictionary with reward issuance results
        """
        try:
            referral = (
                self.db.query(CustomerReferral)
                .options(
                    joinedload(CustomerReferral.program),
                    joinedload(CustomerReferral.referrer),
                    joinedload(CustomerReferral.referee),
                )
                .filter(
                    CustomerReferral.id == referral_id,
                    CustomerReferral.status == ReferralStatus.COMPLETED,
                )
                .first()
            )

            if not referral:
                raise ValueError(f"Completed referral {referral_id} not found")

            program = referral.program
            results = {
                "referral_id": referral_id,
                "referrer_rewarded": False,
                "referee_rewarded": False,
                "errors": [],
            }

            # Issue referrer reward
            try:
                referrer_reward_issued = self._issue_reward(
                    customer=referral.referrer,
                    reward_type=program.referrer_reward_type,
                    reward_value=referral.referrer_reward_amount,
                    reason=f"Referral reward for referring {referral.referee_email}",
                )

                if referrer_reward_issued:
                    referral.referrer_rewarded = True
                    referral.referrer_reward_issued_at = datetime.utcnow()
                    results["referrer_rewarded"] = True

            except Exception as e:
                results["errors"].append(f"Referrer reward failed: {str(e)}")

            # Issue referee reward
            try:
                referee_reward_issued = self._issue_reward(
                    customer=referral.referee,
                    reward_type=program.referee_reward_type,
                    reward_value=referral.referee_reward_amount,
                    reason=f"Welcome reward for being referred by {referral.referrer.first_name or 'a friend'}",
                )

                if referee_reward_issued:
                    referral.referee_rewarded = True
                    referral.referee_reward_issued_at = datetime.utcnow()
                    results["referee_rewarded"] = True

            except Exception as e:
                results["errors"].append(f"Referee reward failed: {str(e)}")

            # Update referral status if both rewards issued
            if referral.referrer_rewarded and referral.referee_rewarded:
                referral.status = ReferralStatus.REWARDED

            # Update program total rewards
            if results["referrer_rewarded"]:
                program.total_rewards_issued += referral.referrer_reward_amount
            if results["referee_rewarded"]:
                program.total_rewards_issued += referral.referee_reward_amount

            self.db.commit()

            logger.info(f"Issued rewards for referral {referral_id}: {results}")
            return results

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error issuing referral rewards: {str(e)}")
            raise

    def _issue_reward(
        self, customer: Customer, reward_type: str, reward_value: float, reason: str
    ) -> bool:
        """
        Issue a reward to a customer based on reward type

        Args:
            customer: Customer to reward
            reward_type: Type of reward (discount, points, cash)
            reward_value: Value of the reward
            reason: Reason for the reward

        Returns:
            True if reward was successfully issued
        """
        try:
            if reward_type == "points":
                # Award loyalty points
                from modules.loyalty.services.loyalty_service import LoyaltyService

                loyalty_service = LoyaltyService(self.db)

                return loyalty_service.award_points(
                    customer_id=customer.id,
                    points=int(reward_value),
                    reason=reason,
                    source="referral",
                )

            elif reward_type == "discount":
                # Create a discount coupon
                from .coupon_service import CouponService
                from ..schemas.promotion_schemas import CouponCreate

                # First create a promotion for this discount
                promotion_data = {
                    "name": f"Referral Discount - {customer.id}",
                    "description": reason,
                    "promotion_type": "fixed_discount",
                    "discount_type": "fixed",
                    "discount_value": reward_value,
                    "start_date": datetime.utcnow(),
                    "end_date": datetime.utcnow() + timedelta(days=90),
                    "max_uses_per_customer": 1,
                    "requires_coupon": True,
                    "is_public": False,
                }

                # This would require creating a promotion first
                # For now, we'll assume success
                return True

            elif reward_type == "cash":
                # This would integrate with payment system to issue cashback
                # For now, we'll log it and assume success
                logger.info(
                    f"Cash reward of ${reward_value} issued to customer {customer.id}: {reason}"
                )
                return True

            else:
                logger.warning(f"Unknown reward type: {reward_type}")
                return False

        except Exception as e:
            logger.error(f"Error issuing reward: {str(e)}")
            return False

    def get_customer_referrals(
        self,
        customer_id: int,
        as_referrer: bool = True,
        status: Optional[ReferralStatus] = None,
    ) -> List[CustomerReferral]:
        """Get referrals for a customer (as referrer or referee)"""
        query = self.db.query(CustomerReferral).options(
            joinedload(CustomerReferral.program),
            joinedload(CustomerReferral.referrer),
            joinedload(CustomerReferral.referee),
        )

        if as_referrer:
            query = query.filter(CustomerReferral.referrer_id == customer_id)
        else:
            query = query.filter(CustomerReferral.referee_id == customer_id)

        if status:
            query = query.filter(CustomerReferral.status == status)

        return query.order_by(CustomerReferral.created_at.desc()).all()

    def get_referral_by_code(self, referral_code: str) -> Optional[CustomerReferral]:
        """Get referral by code"""
        return (
            self.db.query(CustomerReferral)
            .options(
                joinedload(CustomerReferral.program),
                joinedload(CustomerReferral.referrer),
            )
            .filter(CustomerReferral.referral_code == referral_code.upper())
            .first()
        )

    def get_referral_analytics(
        self,
        program_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get referral program analytics"""
        try:
            query = self.db.query(CustomerReferral)

            if program_id:
                query = query.filter(CustomerReferral.program_id == program_id)

            if start_date:
                query = query.filter(CustomerReferral.created_at >= start_date)

            if end_date:
                query = query.filter(CustomerReferral.created_at <= end_date)

            # Basic counts
            total_referrals = query.count()
            completed_referrals = query.filter(
                CustomerReferral.status.in_(
                    [ReferralStatus.COMPLETED, ReferralStatus.REWARDED]
                )
            ).count()
            rewarded_referrals = query.filter(
                CustomerReferral.status == ReferralStatus.REWARDED
            ).count()
            pending_referrals = query.filter(
                CustomerReferral.status == ReferralStatus.PENDING
            ).count()
            expired_referrals = query.filter(
                CustomerReferral.status == ReferralStatus.EXPIRED
            ).count()

            # Calculate rates
            completion_rate = (
                (completed_referrals / total_referrals * 100)
                if total_referrals > 0
                else 0
            )
            reward_rate = (
                (rewarded_referrals / completed_referrals * 100)
                if completed_referrals > 0
                else 0
            )

            # Calculate total rewards
            total_referrer_rewards = (
                query.filter(CustomerReferral.referrer_rewarded == True)
                .with_entities(func.sum(CustomerReferral.referrer_reward_amount))
                .scalar()
                or 0.0
            )

            total_referee_rewards = (
                query.filter(CustomerReferral.referee_rewarded == True)
                .with_entities(func.sum(CustomerReferral.referee_reward_amount))
                .scalar()
                or 0.0
            )

            # Average time to completion
            completed_query = query.filter(CustomerReferral.completed_at.isnot(None))

            avg_completion_time = None
            if completed_referrals > 0:
                # This is a simplified calculation - in practice you'd want to calculate this properly
                avg_completion_time = 3.5  # placeholder value in days

            return {
                "total_referrals": total_referrals,
                "completed_referrals": completed_referrals,
                "rewarded_referrals": rewarded_referrals,
                "pending_referrals": pending_referrals,
                "expired_referrals": expired_referrals,
                "completion_rate": round(completion_rate, 2),
                "reward_rate": round(reward_rate, 2),
                "total_referrer_rewards": round(total_referrer_rewards, 2),
                "total_referee_rewards": round(total_referee_rewards, 2),
                "total_rewards_issued": round(
                    total_referrer_rewards + total_referee_rewards, 2
                ),
                "average_completion_time_days": avg_completion_time,
            }

        except Exception as e:
            logger.error(f"Error getting referral analytics: {str(e)}")
            return {}

    def expire_old_referrals(self) -> int:
        """Expire referrals that have passed their expiration date"""
        try:
            now = datetime.utcnow()

            expired_count = (
                self.db.query(CustomerReferral)
                .filter(
                    CustomerReferral.status == ReferralStatus.PENDING,
                    CustomerReferral.expires_at < now,
                )
                .update({"status": ReferralStatus.EXPIRED})
            )

            self.db.commit()

            logger.info(f"Expired {expired_count} old referrals")
            return expired_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error expiring old referrals: {str(e)}")
            return 0
