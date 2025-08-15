# backend/modules/promotions/services/order_promotion_service.py

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging

from ..models.promotion_models import PromotionUsage, Promotion
from ..schemas.promotion_schemas import (
    DiscountCalculationRequest,
    DiscountCalculationResponse,
)
from ..services.discount_service import DiscountService
from ..services.coupon_service import CouponService
from ..services.promotion_service import PromotionService
from ..services.referral_service import ReferralService

from modules.orders.models.order_models import Order, OrderItem
from modules.orders.services.order_calculation_service import OrderCalculationService
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class OrderPromotionService:
    """Service for integrating promotions with order processing"""

    def __init__(self, db: Session):
        self.db = db
        self.discount_service = DiscountService(db)
        self.coupon_service = CouponService(db)
        self.promotion_service = PromotionService(db)
        self.referral_service = ReferralService(db)
        self.calculation_service = OrderCalculationService(db)

    def calculate_order_discounts(
        self,
        order: Order,
        coupon_codes: Optional[List[str]] = None,
        promotion_ids: Optional[List[int]] = None,
    ) -> DiscountCalculationResponse:
        """
        Calculate discounts for an order

        Args:
            order: Order object to calculate discounts for
            coupon_codes: Optional list of coupon codes to apply
            promotion_ids: Optional list of promotion IDs to apply

        Returns:
            DiscountCalculationResponse with calculated discounts
        """
        try:
            # Prepare order items for discount calculation
            order_items = []
            for item in order.order_items:
                order_items.append(
                    {
                        "item_id": item.menu_item_id,
                        "quantity": item.quantity,
                        "price": float(item.price),
                        "category_id": getattr(item, "category_id", None),
                        "brand_id": getattr(item, "brand_id", None),
                    }
                )

            # Calculate total order amount
            order_total = sum(
                float(item.price) * item.quantity for item in order.order_items
            )

            # Get customer tier if available
            customer_tier = None
            if order.customer:
                customer_tier = getattr(order.customer, "tier", None)

            # Create discount calculation request
            request = DiscountCalculationRequest(
                customer_id=order.customer_id,
                order_total=order_total,
                order_items=order_items,
                coupon_codes=coupon_codes,
                promotion_ids=promotion_ids,
                customer_tier=customer_tier,
            )

            # Calculate discounts
            result = self.discount_service.calculate_order_discounts(request)

            logger.info(
                f"Calculated discounts for order {order.id}: "
                f"${result.total_discount:.2f} off ${result.original_total:.2f}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error calculating order discounts for order {order.id}: {str(e)}"
            )
            raise

    def apply_discounts_to_order(
        self,
        order: Order,
        discount_response: DiscountCalculationResponse,
        applied_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Apply calculated discounts to an order and record usage

        Args:
            order: Order to apply discounts to
            discount_response: Result from discount calculation
            applied_by: User ID who applied the discounts

        Returns:
            Dictionary with application results
        """
        try:
            if discount_response.total_discount <= 0:
                return {
                    "success": True,
                    "message": "No discounts to apply",
                    "total_discount": 0.0,
                    "promotions_applied": [],
                    "coupons_used": [],
                }

            # Record promotion usage for each applied promotion
            promotions_applied = []
            coupons_used = []

            for promotion in discount_response.applied_promotions:
                # Record promotion usage
                usage = self.promotion_service.record_promotion_usage(
                    promotion_id=promotion["promotion_id"],
                    customer_id=order.customer_id,
                    order_id=order.id,
                    discount_amount=promotion["discount_amount"],
                    original_order_amount=discount_response.original_total,
                    final_order_amount=discount_response.final_total,
                    usage_method="order_checkout",
                    staff_member_id=applied_by,
                )

                promotions_applied.append(
                    {
                        "promotion_id": promotion["promotion_id"],
                        "promotion_name": promotion["promotion_name"],
                        "discount_amount": promotion["discount_amount"],
                        "usage_id": usage.id,
                    }
                )

            # Mark coupons as used if any were applied
            for coupon_code in discount_response.applied_promotions or []:
                if coupon_code.get("coupon_code"):
                    # Find the coupon and mark it as used
                    from ..models.promotion_models import Coupon

                    coupon = (
                        self.db.query(Coupon)
                        .filter(Coupon.code == coupon_code["coupon_code"])
                        .first()
                    )

                    if coupon:
                        usage = self.coupon_service.use_coupon(
                            coupon_code=coupon_code["coupon_code"],
                            customer_id=order.customer_id,
                            order_id=order.id,
                            discount_amount=coupon_code["discount_amount"],
                            usage_context={
                                "order_total": discount_response.original_total,
                                "final_total": discount_response.final_total,
                            },
                        )

                        coupons_used.append(
                            {
                                "coupon_code": coupon_code["coupon_code"],
                                "discount_amount": coupon_code["discount_amount"],
                                "usage_id": usage.id,
                            }
                        )

            # Update order with discount information
            order.discount_amount = discount_response.total_discount
            order.total_amount = discount_response.original_total
            order.final_amount = discount_response.final_total

            # Store promotion and coupon details
            order.promotions_applied = [
                {
                    "promotion_id": p["promotion_id"],
                    "promotion_name": p["promotion_name"],
                    "discount_amount": p["discount_amount"],
                    "applied_at": datetime.utcnow().isoformat(),
                }
                for p in promotions_applied
            ]

            order.coupons_used = [
                {
                    "coupon_code": c["coupon_code"],
                    "discount_amount": c["discount_amount"],
                    "used_at": datetime.utcnow().isoformat(),
                }
                for c in coupons_used
            ]

            # Store detailed discount breakdown
            order.discount_breakdown = {
                "original_total": discount_response.original_total,
                "total_discount": discount_response.total_discount,
                "final_total": discount_response.final_total,
                "promotions": promotions_applied,
                "coupons": coupons_used,
                "applied_at": datetime.utcnow().isoformat(),
            }

            # Recalculate order totals with the new discount
            self.calculation_service.recalculate_with_discount(
                order=order, discount_amount=discount_response.total_discount
            )

            self.db.commit()

            logger.info(
                f"Applied discounts to order {order.id}: "
                f"${discount_response.total_discount:.2f} total discount"
            )

            return {
                "success": True,
                "message": f"Applied ${discount_response.total_discount:.2f} in discounts",
                "total_discount": discount_response.total_discount,
                "original_total": discount_response.original_total,
                "final_total": discount_response.final_total,
                "promotions_applied": promotions_applied,
                "coupons_used": coupons_used,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error applying discounts to order {order.id}: {str(e)}")
            raise

    def process_order_completion(self, order: Order) -> Dict[str, Any]:
        """
        Process order completion for promotion-related actions

        Args:
            order: Completed order

        Returns:
            Dictionary with processing results
        """
        try:
            results = {
                "referrals_processed": [],
                "rewards_issued": [],
                "analytics_updated": True,
            }

            # Process referral completions
            if order.customer_id:
                referral_results = self.referral_service.process_referral_completion(
                    order.id
                )
                results["referrals_processed"] = referral_results

                # Issue referral rewards for completed referrals
                for referral in referral_results:
                    try:
                        reward_result = self.referral_service.issue_referral_rewards(
                            referral["referral_id"]
                        )
                        results["rewards_issued"].append(reward_result)
                    except Exception as e:
                        logger.error(
                            f"Error issuing referral rewards for "
                            f"referral {referral['referral_id']}: {str(e)}"
                        )

            # Update promotion analytics
            self._update_promotion_analytics(order)

            logger.info(
                f"Processed order completion for order {order.id}: "
                f"{len(results['referrals_processed'])} referrals processed"
            )

            return results

        except Exception as e:
            logger.error(
                f"Error processing order completion for order {order.id}: {str(e)}"
            )
            return {"error": str(e)}

    def validate_promotion_eligibility(
        self, order: Order, promotion_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if an order is eligible for a specific promotion

        Args:
            order: Order to validate
            promotion_id: Promotion ID to check eligibility for

        Returns:
            Tuple of (is_eligible, error_message)
        """
        try:
            promotion = self.promotion_service.get_promotion(promotion_id)

            if not promotion:
                return False, "Promotion not found"

            if not promotion.is_active:
                return False, "Promotion is not active"

            # Check customer eligibility
            if order.customer_id and promotion.max_uses_per_customer:
                customer_usage = (
                    self.db.query(PromotionUsage)
                    .filter(
                        PromotionUsage.promotion_id == promotion_id,
                        PromotionUsage.customer_id == order.customer_id,
                    )
                    .count()
                )

                if customer_usage >= promotion.max_uses_per_customer:
                    return False, "Customer has exceeded usage limit for this promotion"

            # Check total usage limits
            if (
                promotion.max_uses_total
                and promotion.current_uses >= promotion.max_uses_total
            ):
                return False, "Promotion usage limit exceeded"

            # Check minimum order amount
            order_total = sum(
                float(item.price) * item.quantity for item in order.order_items
            )
            if promotion.min_order_amount and order_total < promotion.min_order_amount:
                return (
                    False,
                    f"Order total must be at least ${promotion.min_order_amount:.2f}",
                )

            # Check date validity
            now = datetime.utcnow()
            if promotion.start_date > now:
                return False, "Promotion has not started yet"

            if promotion.end_date <= now:
                return False, "Promotion has expired"

            return True, None

        except Exception as e:
            logger.error(f"Error validating promotion eligibility: {str(e)}")
            return False, "Error validating promotion eligibility"

    def get_applicable_promotions(self, order: Order) -> List[Dict[str, Any]]:
        """
        Get all applicable promotions for an order

        Args:
            order: Order to find promotions for

        Returns:
            List of applicable promotion dictionaries
        """
        try:
            # Get customer tier if available
            customer_tier = None
            if order.customer:
                customer_tier = getattr(order.customer, "tier", None)

            # Get active promotions
            active_promotions = self.promotion_service.get_active_promotions(
                customer_id=order.customer_id,
                customer_tier=customer_tier,
                featured_only=False,
                public_only=True,
            )

            applicable_promotions = []

            for promotion in active_promotions:
                is_eligible, error_message = self.validate_promotion_eligibility(
                    order, promotion.id
                )

                if is_eligible:
                    # Calculate potential discount
                    order_items = []
                    for item in order.order_items:
                        order_items.append(
                            {
                                "item_id": item.menu_item_id,
                                "quantity": item.quantity,
                                "price": float(item.price),
                                "category_id": getattr(item, "category_id", None),
                            }
                        )

                    order_total = sum(
                        float(item.price) * item.quantity for item in order.order_items
                    )

                    discount_amount = (
                        self.discount_service.calculate_promotion_discount(
                            promotion=promotion,
                            order_total=order_total,
                            order_items=order_items,
                            customer_id=order.customer_id,
                        )
                    )

                    applicable_promotions.append(
                        {
                            "promotion_id": promotion.id,
                            "promotion_name": promotion.name,
                            "promotion_type": promotion.promotion_type,
                            "discount_type": promotion.discount_type,
                            "discount_value": promotion.discount_value,
                            "potential_discount": discount_amount,
                            "stackable": promotion.stackable,
                            "auto_apply": promotion.auto_apply,
                            "requires_coupon": promotion.requires_coupon,
                        }
                    )

            # Sort by potential discount (highest first)
            applicable_promotions.sort(
                key=lambda x: x["potential_discount"], reverse=True
            )

            return applicable_promotions

        except Exception as e:
            logger.error(
                f"Error getting applicable promotions for order {order.id}: {str(e)}"
            )
            return []

    def _update_promotion_analytics(self, order: Order):
        """Update promotion analytics based on order completion"""
        try:
            # Get promotion usages for this order
            usages = (
                self.db.query(PromotionUsage)
                .filter(PromotionUsage.order_id == order.id)
                .all()
            )

            for usage in usages:
                promotion = usage.promotion
                if promotion:
                    # Update promotion metrics
                    promotion.revenue_generated += usage.final_order_amount
                    promotion.conversions += 1

                    # You could also update daily analytics here
                    # This would require a PromotionAnalytics model with daily aggregates

            self.db.commit()

        except Exception as e:
            logger.error(f"Error updating promotion analytics: {str(e)}")
            self.db.rollback()

    def get_order_promotion_summary(self, order_id: int) -> Dict[str, Any]:
        """
        Get a summary of all promotions applied to an order

        Args:
            order_id: Order ID to get summary for

        Returns:
            Dictionary with promotion summary
        """
        try:
            # Get promotion usages
            usages = (
                self.db.query(PromotionUsage)
                .filter(PromotionUsage.order_id == order_id)
                .all()
            )

            # Get coupon usages
            from ..models.promotion_models import CouponUsage, Coupon

            coupon_usages = (
                self.db.query(CouponUsage)
                .filter(CouponUsage.order_id == order_id)
                .all()
            )

            total_discount = sum(usage.discount_amount for usage in usages)
            total_discount += sum(usage.discount_amount for usage in coupon_usages)

            promotions_used = []
            for usage in usages:
                promotion = usage.promotion
                if promotion:
                    promotions_used.append(
                        {
                            "promotion_id": promotion.id,
                            "promotion_name": promotion.name,
                            "promotion_type": promotion.promotion_type,
                            "discount_amount": usage.discount_amount,
                            "used_at": usage.created_at,
                        }
                    )

            coupons_used = []
            for usage in coupon_usages:
                coupon = usage.coupon
                if coupon:
                    coupons_used.append(
                        {
                            "coupon_id": coupon.id,
                            "coupon_code": coupon.code,
                            "discount_amount": usage.discount_amount,
                            "used_at": usage.created_at,
                        }
                    )

            return {
                "order_id": order_id,
                "total_discount": total_discount,
                "promotions_used": promotions_used,
                "coupons_used": coupons_used,
                "total_savings": total_discount,
            }

        except Exception as e:
            logger.error(
                f"Error getting order promotion summary for order {order_id}: {str(e)}"
            )
            return {"error": str(e)}
