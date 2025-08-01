# backend/modules/promotions/services/customer_integration_service.py

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import logging

from ..services.referral_service import ReferralService
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class CustomerIntegrationService:
    """Service for integrating promotions with customer lifecycle events"""
    
    def __init__(self, db: Session):
        self.db = db
        self.referral_service = ReferralService(db)
    
    def process_customer_signup(
        self,
        customer: Customer,
        referral_code: Optional[str] = None,
        signup_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process customer signup for promotion-related actions
        
        Args:
            customer: Newly created customer
            referral_code: Optional referral code used during signup
            signup_source: Source of the signup (web, app, etc.)
            
        Returns:
            Dictionary with processing results
        """
        try:
            results = {
                "customer_id": customer.id,
                "referral_processed": False,
                "referral_details": None,
                "welcome_promotions": [],
                "errors": []
            }
            
            # Process referral if referral code was provided
            if referral_code:
                try:
                    referral_results = self.referral_service.process_referral_signup(
                        referee_email=customer.email,
                        referee_id=customer.id
                    )
                    
                    if referral_results:
                        results["referral_processed"] = True
                        results["referral_details"] = {
                            "referral_code": referral_code,
                            "updated_referrals": len(referral_results),
                            "referral_ids": [r.id for r in referral_results]
                        }
                        
                        logger.info(f"Processed referral signup for customer {customer.id} "
                                   f"with code {referral_code}")
                except Exception as e:
                    logger.error(f"Error processing referral signup: {str(e)}")
                    results["errors"].append(f"Referral processing failed: {str(e)}")
            
            # Create welcome promotions or coupons for new customers
            welcome_promotions = self._create_welcome_promotions(customer)
            results["welcome_promotions"] = welcome_promotions
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing customer signup for customer {customer.id}: {str(e)}")
            return {
                "customer_id": customer.id,
                "error": str(e),
                "referral_processed": False
            }
    
    def process_customer_first_order(
        self,
        customer: Customer,
        order_amount: float
    ) -> Dict[str, Any]:
        """
        Process customer's first order for promotion eligibility
        
        Args:
            customer: Customer making first order
            order_amount: Amount of the first order
            
        Returns:
            Dictionary with processing results
        """
        try:
            results = {
                "customer_id": customer.id,
                "first_order_bonuses": [],
                "referral_completions": [],
                "tier_updates": []
            }
            
            # Check for first-order promotions
            # This could include welcome discounts, bonus points, etc.
            
            # Update customer tier if applicable
            if hasattr(customer, 'tier') and order_amount >= 100:
                # Example: Upgrade to Bronze tier after first order over $100
                if customer.tier == 'new':
                    customer.tier = 'bronze'
                    results["tier_updates"].append({
                        "previous_tier": "new",
                        "new_tier": "bronze",
                        "reason": "first_order_over_100"
                    })
            
            self.db.commit()
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing first order for customer {customer.id}: {str(e)}")
            self.db.rollback()
            return {"error": str(e)}
    
    def _create_welcome_promotions(self, customer: Customer) -> List[Dict[str, Any]]:
        """Create welcome promotions for new customers"""
        try:
            welcome_promotions = []
            
            # Example: Create a welcome discount coupon
            # This would integrate with your coupon service
            from ..services.coupon_service import CouponService
            from ..services.promotion_service import PromotionService
            
            coupon_service = CouponService(self.db)
            promotion_service = PromotionService(self.db)
            
            # Find active welcome promotions
            from ..models.promotion_models import Promotion, PromotionStatus
            from datetime import datetime
            
            welcome_promotions_query = self.db.query(Promotion).filter(
                Promotion.status == PromotionStatus.ACTIVE,
                Promotion.start_date <= datetime.utcnow(),
                Promotion.end_date >= datetime.utcnow(),
                Promotion.target_customer_segments.contains(["new_customer"])
            ).all()
            
            for promotion in welcome_promotions_query:
                try:
                    # Create a customer-specific coupon for this promotion
                    from ..schemas.promotion_schemas import CouponCreate
                    
                    coupon_data = CouponCreate(
                        promotion_id=promotion.id,
                        customer_id=customer.id,
                        customer_email=customer.email,
                        generation_method="welcome_signup"
                    )
                    
                    coupon = coupon_service.create_coupon(coupon_data)
                    
                    welcome_promotions.append({
                        "promotion_id": promotion.id,
                        "promotion_name": promotion.name,
                        "coupon_id": coupon.id,
                        "coupon_code": coupon.code,
                        "discount_type": promotion.discount_type,
                        "discount_value": promotion.discount_value
                    })
                    
                except Exception as e:
                    logger.error(f"Error creating welcome coupon for promotion {promotion.id}: {str(e)}")
                    continue
            
            if welcome_promotions:
                logger.info(f"Created {len(welcome_promotions)} welcome promotions for customer {customer.id}")
            
            return welcome_promotions
            
        except Exception as e:
            logger.error(f"Error creating welcome promotions for customer {customer.id}: {str(e)}")
            return []
    
    def process_customer_tier_change(
        self,
        customer: Customer,
        old_tier: str,
        new_tier: str
    ) -> Dict[str, Any]:
        """
        Process customer tier change for promotion eligibility
        
        Args:
            customer: Customer whose tier changed
            old_tier: Previous tier
            new_tier: New tier
            
        Returns:
            Dictionary with processing results
        """
        try:
            results = {
                "customer_id": customer.id,
                "tier_change": {
                    "old_tier": old_tier,
                    "new_tier": new_tier
                },
                "new_promotions": [],
                "tier_benefits": []
            }
            
            # Find promotions available to the new tier
            from ..models.promotion_models import Promotion, PromotionStatus
            from datetime import datetime
            
            tier_promotions = self.db.query(Promotion).filter(
                Promotion.status == PromotionStatus.ACTIVE,
                Promotion.start_date <= datetime.utcnow(),
                Promotion.end_date >= datetime.utcnow(),
                Promotion.target_tiers.contains([new_tier])
            ).all()
            
            # Create tier-specific welcome promotions
            for promotion in tier_promotions:
                results["new_promotions"].append({
                    "promotion_id": promotion.id,
                    "promotion_name": promotion.name,
                    "promotion_type": promotion.promotion_type,
                    "requires_coupon": promotion.requires_coupon
                })
            
            logger.info(f"Processed tier change for customer {customer.id}: "
                       f"{old_tier} -> {new_tier}, {len(tier_promotions)} new promotions available")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing tier change for customer {customer.id}: {str(e)}")
            return {"error": str(e)}
    
    def get_customer_promotion_history(
        self,
        customer_id: int,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get comprehensive promotion history for a customer
        
        Args:
            customer_id: Customer ID
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with promotion history
        """
        try:
            from ..models.promotion_models import PromotionUsage, CouponUsage
            
            # Get promotion usages
            promotion_usages = self.db.query(PromotionUsage).filter(
                PromotionUsage.customer_id == customer_id
            ).order_by(PromotionUsage.created_at.desc()).limit(limit).all()
            
            # Get coupon usages
            coupon_usages = self.db.query(CouponUsage).filter(
                CouponUsage.customer_id == customer_id
            ).order_by(CouponUsage.created_at.desc()).limit(limit).all()
            
            # Get referrals made and received
            referrals_made = self.referral_service.get_customer_referrals(
                customer_id=customer_id,
                as_referrer=True
            )
            
            referrals_received = self.referral_service.get_customer_referrals(
                customer_id=customer_id,
                as_referrer=False
            )
            
            # Calculate totals
            total_savings = sum(usage.discount_amount for usage in promotion_usages)
            total_savings += sum(usage.discount_amount for usage in coupon_usages)
            
            return {
                "customer_id": customer_id,
                "summary": {
                    "total_promotions_used": len(promotion_usages),
                    "total_coupons_used": len(coupon_usages),
                    "total_savings": round(total_savings, 2),
                    "referrals_made": len(referrals_made),
                    "referrals_received": len(referrals_received)
                },
                "recent_promotions": [
                    {
                        "promotion_id": usage.promotion_id,
                        "promotion_name": usage.promotion.name if usage.promotion else "Unknown",
                        "discount_amount": usage.discount_amount,
                        "order_id": usage.order_id,
                        "used_at": usage.created_at
                    }
                    for usage in promotion_usages[:10]
                ],
                "recent_coupons": [
                    {
                        "coupon_code": usage.coupon.code if usage.coupon else "Unknown",
                        "discount_amount": usage.discount_amount,
                        "order_id": usage.order_id,
                        "used_at": usage.created_at
                    }
                    for usage in coupon_usages[:10]
                ],
                "referrals_summary": {
                    "made": len(referrals_made),
                    "received": len(referrals_received),
                    "completed": len([r for r in referrals_made if r.status == "completed"]),
                    "rewarded": len([r for r in referrals_made if r.status == "rewarded"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting promotion history for customer {customer_id}: {str(e)}")
            return {"error": str(e)}