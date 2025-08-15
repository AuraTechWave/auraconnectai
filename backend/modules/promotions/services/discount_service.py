# backend/modules/promotions/services/discount_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from ..models.promotion_models import (
    Promotion,
    PromotionUsage,
    PromotionType,
    PromotionStatus,
    DiscountTarget,
)
from ..schemas.promotion_schemas import (
    DiscountCalculationRequest,
    DiscountCalculationResponse,
)
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class DiscountCalculationResult:
    """Result of discount calculation"""

    def __init__(self):
        self.original_total = 0.0
        self.final_total = 0.0
        self.total_discount = 0.0
        self.applied_promotions = []
        self.applicable_promotions = []
        self.invalid_coupons = []
        self.warnings = []
        self.item_discounts = {}  # item_id -> discount_amount
        self.shipping_discount = 0.0


class DiscountService:
    """Service for calculating discounts and applying promotions"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_order_discounts(
        self, request: DiscountCalculationRequest
    ) -> DiscountCalculationResponse:
        """
        Calculate all applicable discounts for an order

        Args:
            request: Discount calculation request with order details

        Returns:
            DiscountCalculationResponse with calculated discounts
        """
        try:
            result = DiscountCalculationResult()
            result.original_total = request.order_total
            result.final_total = request.order_total

            # Get customer information if provided
            customer = None
            if request.customer_id:
                customer = (
                    self.db.query(Customer)
                    .filter(Customer.id == request.customer_id)
                    .first()
                )

            # Find applicable promotions
            applicable_promotions = self._find_applicable_promotions(
                customer=customer,
                order_total=request.order_total,
                order_items=request.order_items,
                customer_tier=request.customer_tier,
                coupon_codes=request.coupon_codes,
                promotion_ids=request.promotion_ids,
            )

            result.applicable_promotions = applicable_promotions

            # Validate and process coupons
            valid_coupon_promotions = []
            if request.coupon_codes:
                from .coupon_service import CouponService

                coupon_service = CouponService(self.db)

                for coupon_code in request.coupon_codes:
                    from ..schemas.promotion_schemas import CouponValidationRequest

                    validation_request = CouponValidationRequest(
                        code=coupon_code,
                        customer_id=request.customer_id,
                        order_total=request.order_total,
                        order_items=request.order_items,
                    )

                    validation_result = coupon_service.validate_coupon(
                        validation_request
                    )

                    if validation_result.is_valid and validation_result.coupon:
                        valid_coupon_promotions.append(
                            validation_result.coupon.promotion
                        )
                    else:
                        result.invalid_coupons.append(coupon_code)
                        if validation_result.error_message:
                            result.warnings.append(validation_result.error_message)

            # Combine applicable promotions with valid coupon promotions
            all_promotions = applicable_promotions + valid_coupon_promotions

            # Remove duplicates
            unique_promotions = {}
            for promo in all_promotions:
                unique_promotions[promo.id] = promo
            all_promotions = list(unique_promotions.values())

            # Sort promotions by priority and stackability
            sorted_promotions = self._sort_promotions_for_application(all_promotions)

            # Apply promotions
            applied_promotions = self._apply_promotions(
                promotions=sorted_promotions,
                order_total=request.order_total,
                order_items=request.order_items,
                customer=customer,
                result=result,
            )

            result.applied_promotions = applied_promotions

            # Calculate final totals
            result.total_discount = result.original_total - result.final_total

            return DiscountCalculationResponse(
                original_total=result.original_total,
                final_total=max(0, result.final_total),  # Never go below 0
                total_discount=result.total_discount,
                applied_promotions=result.applied_promotions,
                applicable_promotions=[
                    self._promotion_to_dict(p) for p in result.applicable_promotions
                ],
                invalid_coupons=result.invalid_coupons,
                warnings=result.warnings,
            )

        except Exception as e:
            logger.error(f"Error calculating order discounts: {str(e)}")
            return DiscountCalculationResponse(
                original_total=request.order_total,
                final_total=request.order_total,
                total_discount=0.0,
                applied_promotions=[],
                applicable_promotions=[],
                invalid_coupons=request.coupon_codes or [],
                warnings=[f"Error calculating discounts: {str(e)}"],
            )

    def calculate_promotion_discount(
        self,
        promotion: Promotion,
        order_total: float,
        order_items: List[Dict[str, Any]],
        customer_id: Optional[int] = None,
    ) -> float:
        """
        Calculate discount for a specific promotion

        Args:
            promotion: Promotion to calculate discount for
            order_total: Total order amount
            order_items: List of order items
            customer_id: Optional customer ID

        Returns:
            Calculated discount amount
        """
        try:
            if promotion.promotion_type == PromotionType.PERCENTAGE_DISCOUNT:
                discount = order_total * (promotion.discount_value / 100)
                if promotion.max_discount_amount:
                    discount = min(discount, promotion.max_discount_amount)
                return discount

            elif promotion.promotion_type == PromotionType.FIXED_DISCOUNT:
                return min(promotion.discount_value, order_total)

            elif promotion.promotion_type == PromotionType.FREE_SHIPPING:
                # Calculate shipping cost from order items or use fixed value
                shipping_cost = self._calculate_shipping_cost(order_items)
                return min(promotion.discount_value or shipping_cost, shipping_cost)

            elif promotion.promotion_type == PromotionType.BOGO:
                return self._calculate_bogo_discount(promotion, order_items)

            elif promotion.promotion_type == PromotionType.TIERED_DISCOUNT:
                return self._calculate_tiered_discount(promotion, order_total)

            elif promotion.promotion_type == PromotionType.BUNDLE_DISCOUNT:
                return self._calculate_bundle_discount(promotion, order_items)

            elif promotion.promotion_type == PromotionType.CASHBACK:
                # Cashback doesn't reduce order total, but provides future credit
                return 0.0

            else:
                logger.warning(f"Unknown promotion type: {promotion.promotion_type}")
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating promotion discount: {str(e)}")
            return 0.0

    def _find_applicable_promotions(
        self,
        customer: Optional[Customer],
        order_total: float,
        order_items: List[Dict[str, Any]],
        customer_tier: Optional[str],
        coupon_codes: Optional[List[str]] = None,
        promotion_ids: Optional[List[int]] = None,
    ) -> List[Promotion]:
        """Find all applicable promotions for the order"""

        query = self.db.query(Promotion).filter(
            Promotion.status == PromotionStatus.ACTIVE,
            Promotion.start_date <= datetime.utcnow(),
            Promotion.end_date >= datetime.utcnow(),
            Promotion.auto_apply == True,  # Only auto-apply promotions
        )

        # Filter by specific promotion IDs if provided
        if promotion_ids:
            query = query.filter(Promotion.id.in_(promotion_ids))

        # Filter by minimum order amount
        query = query.filter(
            or_(
                Promotion.min_order_amount.is_(None),
                Promotion.min_order_amount <= order_total,
            )
        )

        # Filter by customer tier
        if customer_tier:
            query = query.filter(
                or_(
                    Promotion.target_tiers.is_(None),
                    Promotion.target_tiers.contains([customer_tier]),
                )
            )

        # Filter by usage limits
        if customer:
            # Check customer usage limits
            query = query.filter(
                or_(
                    Promotion.max_uses_per_customer.is_(None),
                    Promotion.max_uses_per_customer
                    > func.coalesce(
                        self.db.query(func.count(PromotionUsage.id))
                        .filter(
                            PromotionUsage.promotion_id == Promotion.id,
                            PromotionUsage.customer_id == customer.id,
                        )
                        .scalar_subquery(),
                        0,
                    ),
                )
            )

        # Filter by total usage limits
        query = query.filter(
            or_(
                Promotion.max_uses_total.is_(None),
                Promotion.max_uses_total > Promotion.current_uses,
            )
        )

        promotions = query.order_by(Promotion.priority.desc()).all()

        # Additional filtering based on conditions
        applicable_promotions = []
        for promotion in promotions:
            if self._check_promotion_conditions(promotion, customer, order_items):
                applicable_promotions.append(promotion)

        return applicable_promotions

    def _check_promotion_conditions(
        self,
        promotion: Promotion,
        customer: Optional[Customer],
        order_items: List[Dict[str, Any]],
    ) -> bool:
        """Check if promotion conditions are met"""

        if not promotion.conditions:
            return True

        conditions = promotion.conditions

        # Check customer segment conditions
        if "customer_segments" in conditions and customer:
            required_segments = conditions["customer_segments"]
            # This would need integration with customer segmentation system
            # For now, assume condition is met
            pass

        # Check item quantity conditions
        if "min_items" in conditions:
            total_items = sum(item.get("quantity", 1) for item in order_items)
            if total_items < conditions["min_items"]:
                return False

        # Check specific item conditions
        if "required_items" in conditions:
            required_items = conditions["required_items"]
            order_item_ids = [item.get("item_id") for item in order_items]
            if not any(item_id in order_item_ids for item_id in required_items):
                return False

        # Check category conditions
        if "required_categories" in conditions:
            required_categories = conditions["required_categories"]
            order_categories = [item.get("category_id") for item in order_items]
            if not any(cat_id in order_categories for cat_id in required_categories):
                return False

        # Check time-based conditions
        if "time_restrictions" in conditions:
            time_restrictions = conditions["time_restrictions"]
            current_time = datetime.utcnow()

            if "hours" in time_restrictions:
                allowed_hours = time_restrictions["hours"]
                if current_time.hour not in allowed_hours:
                    return False

            if "days_of_week" in time_restrictions:
                allowed_days = time_restrictions["days_of_week"]
                if current_time.weekday() not in allowed_days:
                    return False

        return True

    def _sort_promotions_for_application(
        self, promotions: List[Promotion]
    ) -> List[Promotion]:
        """Sort promotions for optimal application"""

        # Separate stackable and non-stackable promotions
        stackable = [p for p in promotions if p.stackable]
        non_stackable = [p for p in promotions if not p.stackable]

        # Sort by priority (higher first), then by discount value
        stackable.sort(key=lambda p: (p.priority, p.discount_value), reverse=True)
        non_stackable.sort(key=lambda p: (p.priority, p.discount_value), reverse=True)

        # For non-stackable, we'll only apply the best one
        # For stackable, we can apply multiple
        if non_stackable:
            # Take the best non-stackable promotion
            best_non_stackable = non_stackable[0]

            # Compare with stacked stackable promotions
            stackable_total_discount = sum(
                self._estimate_promotion_discount(p) for p in stackable
            )
            non_stackable_discount = self._estimate_promotion_discount(
                best_non_stackable
            )

            if non_stackable_discount > stackable_total_discount:
                return [best_non_stackable]
            else:
                return stackable

        return stackable

    def _estimate_promotion_discount(self, promotion: Promotion) -> float:
        """Estimate discount value for sorting purposes"""
        if promotion.promotion_type == PromotionType.PERCENTAGE_DISCOUNT:
            # Use max discount amount as estimate
            return promotion.max_discount_amount or (
                promotion.discount_value * 10
            )  # Rough estimate
        elif promotion.promotion_type == PromotionType.FIXED_DISCOUNT:
            return promotion.discount_value
        else:
            return promotion.discount_value or 0.0

    def _apply_promotions(
        self,
        promotions: List[Promotion],
        order_total: float,
        order_items: List[Dict[str, Any]],
        customer: Optional[Customer],
        result: DiscountCalculationResult,
    ) -> List[Dict[str, Any]]:
        """Apply promotions and calculate discounts"""

        applied_promotions = []
        current_total = order_total

        for promotion in promotions:
            discount_amount = self.calculate_promotion_discount(
                promotion=promotion,
                order_total=current_total,
                order_items=order_items,
                customer_id=customer.id if customer else None,
            )

            if discount_amount > 0:
                # Apply the discount
                current_total -= discount_amount
                current_total = max(0, current_total)  # Never go below 0

                applied_promotion = {
                    "promotion_id": promotion.id,
                    "promotion_name": promotion.name,
                    "promotion_type": promotion.promotion_type,
                    "discount_amount": round(discount_amount, 2),
                    "discount_type": promotion.discount_type,
                    "discount_value": promotion.discount_value,
                }

                applied_promotions.append(applied_promotion)

                # Update result
                result.final_total = current_total

                # Break if not stackable and we've applied one
                if not promotion.stackable:
                    break

        return applied_promotions

    def _calculate_bogo_discount(
        self, promotion: Promotion, order_items: List[Dict[str, Any]]
    ) -> float:
        """Calculate Buy One Get One discount"""

        total_discount = 0.0
        conditions = promotion.conditions or {}

        # Get BOGO configuration
        buy_quantity = conditions.get("buy_quantity", 1)
        get_quantity = conditions.get("get_quantity", 1)
        get_discount_percent = conditions.get(
            "get_discount_percent", 100
        )  # 100% = free

        # Filter eligible items
        eligible_items = self._filter_eligible_items(promotion, order_items)

        # Sort by price (apply discount to cheaper items)
        eligible_items.sort(key=lambda x: x.get("price", 0))

        for item in eligible_items:
            item_quantity = item.get("quantity", 1)
            item_price = item.get("price", 0)

            # Calculate how many BOGO sets this item can form
            bogo_sets = item_quantity // (buy_quantity + get_quantity)

            # Calculate discount for complete BOGO sets
            discounted_items = bogo_sets * get_quantity
            discount_per_item = item_price * (get_discount_percent / 100)
            total_discount += discounted_items * discount_per_item

        return total_discount

    def _calculate_tiered_discount(
        self, promotion: Promotion, order_total: float
    ) -> float:
        """Calculate tiered discount based on order total"""

        conditions = promotion.conditions or {}
        tiers = conditions.get("tiers", [])

        if not tiers:
            return 0.0

        # Sort tiers by threshold descending to find the highest applicable tier
        sorted_tiers = sorted(tiers, key=lambda x: x.get("threshold", 0), reverse=True)

        for tier in sorted_tiers:
            threshold = tier.get("threshold", 0)
            if order_total >= threshold:
                discount_type = tier.get("discount_type", "percentage")
                discount_value = tier.get("discount_value", 0)

                if discount_type == "percentage":
                    discount = order_total * (discount_value / 100)
                    max_discount = tier.get("max_discount")
                    if max_discount:
                        discount = min(discount, max_discount)
                    return discount
                elif discount_type == "fixed":
                    return min(discount_value, order_total)

        return 0.0

    def _calculate_bundle_discount(
        self, promotion: Promotion, order_items: List[Dict[str, Any]]
    ) -> float:
        """Calculate bundle discount"""

        conditions = promotion.conditions or {}
        required_items = conditions.get("bundle_items", [])

        if not required_items:
            return 0.0

        # Check if all required items are in the order
        order_item_ids = [item.get("item_id") for item in order_items]

        for required_item in required_items:
            item_id = required_item.get("item_id")
            required_quantity = required_item.get("quantity", 1)

            # Find the item in the order
            order_item = next(
                (item for item in order_items if item.get("item_id") == item_id), None
            )

            if not order_item or order_item.get("quantity", 0) < required_quantity:
                return 0.0  # Bundle requirements not met

        # Calculate bundle discount
        if promotion.discount_type == "percentage":
            bundle_total = sum(
                item.get("price", 0) * item.get("quantity", 1)
                for item in order_items
                if item.get("item_id") in [ri.get("item_id") for ri in required_items]
            )
            return bundle_total * (promotion.discount_value / 100)
        elif promotion.discount_type == "fixed":
            return promotion.discount_value

        return 0.0

    def _filter_eligible_items(
        self, promotion: Promotion, order_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter order items that are eligible for the promotion"""

        if promotion.target_type == DiscountTarget.ORDER_TOTAL:
            return order_items

        eligible_items = []

        for item in order_items:
            if promotion.target_type == DiscountTarget.SPECIFIC_ITEMS:
                target_items = promotion.target_items or {}
                item_ids = target_items.get("item_ids", [])
                if item.get("item_id") in item_ids:
                    eligible_items.append(item)

            elif promotion.target_type == DiscountTarget.CATEGORIES:
                target_items = promotion.target_items or {}
                category_ids = target_items.get("category_ids", [])
                if item.get("category_id") in category_ids:
                    eligible_items.append(item)

            elif promotion.target_type == DiscountTarget.BRANDS:
                target_items = promotion.target_items or {}
                brand_ids = target_items.get("brand_ids", [])
                if item.get("brand_id") in brand_ids:
                    eligible_items.append(item)

        return eligible_items

    def _calculate_shipping_cost(self, order_items: List[Dict[str, Any]]) -> float:
        """Calculate shipping cost from order items"""
        # This would integrate with shipping calculation service
        # For now, return a default shipping cost
        return 5.0

    def _promotion_to_dict(self, promotion: Promotion) -> Dict[str, Any]:
        """Convert promotion to dictionary"""
        return {
            "id": promotion.id,
            "name": promotion.name,
            "title": promotion.title,
            "promotion_type": promotion.promotion_type,
            "discount_type": promotion.discount_type,
            "discount_value": promotion.discount_value,
            "min_order_amount": promotion.min_order_amount,
            "max_discount_amount": promotion.max_discount_amount,
            "stackable": promotion.stackable,
            "auto_apply": promotion.auto_apply,
            "priority": promotion.priority,
        }

    def get_promotion_performance_metrics(
        self,
        promotion_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get performance metrics for a promotion"""
        try:
            query = self.db.query(PromotionUsage).filter(
                PromotionUsage.promotion_id == promotion_id
            )

            if start_date:
                query = query.filter(PromotionUsage.created_at >= start_date)

            if end_date:
                query = query.filter(PromotionUsage.created_at <= end_date)

            usages = query.all()

            if not usages:
                return {
                    "total_usage": 0,
                    "total_discount": 0.0,
                    "total_revenue": 0.0,
                    "average_discount": 0.0,
                    "average_order_value": 0.0,
                    "unique_customers": 0,
                }

            total_usage = len(usages)
            total_discount = sum(usage.discount_amount for usage in usages)
            total_revenue = sum(usage.final_order_amount for usage in usages)
            unique_customers = len(
                set(usage.customer_id for usage in usages if usage.customer_id)
            )

            return {
                "total_usage": total_usage,
                "total_discount": round(total_discount, 2),
                "total_revenue": round(total_revenue, 2),
                "average_discount": round(total_discount / total_usage, 2),
                "average_order_value": round(total_revenue / total_usage, 2),
                "unique_customers": unique_customers,
            }

        except Exception as e:
            logger.error(f"Error getting promotion performance metrics: {str(e)}")
            return {}

    def validate_promotion_stackability(
        self, promotion_ids: List[int]
    ) -> Tuple[bool, List[str]]:
        """
        Validate if promotions can be stacked together

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            promotions = (
                self.db.query(Promotion).filter(Promotion.id.in_(promotion_ids)).all()
            )

            errors = []

            # Check if any non-stackable promotions
            non_stackable = [p for p in promotions if not p.stackable]
            if len(non_stackable) > 1:
                errors.append("Cannot stack multiple non-stackable promotions")

            if non_stackable and len(promotions) > 1:
                errors.append(
                    "Cannot stack non-stackable promotion with other promotions"
                )

            # Check for conflicting promotion types
            promotion_types = [p.promotion_type for p in promotions]
            if promotion_types.count(PromotionType.FREE_SHIPPING) > 1:
                errors.append("Cannot stack multiple free shipping promotions")

            return len(errors) == 0, errors

        except Exception as e:
            logger.error(f"Error validating promotion stackability: {str(e)}")
            return False, ["Error validating promotion compatibility"]
