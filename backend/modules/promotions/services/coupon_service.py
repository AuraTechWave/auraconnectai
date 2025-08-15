# backend/modules/promotions/services/coupon_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import string
import secrets
import random
import logging

from ..models.promotion_models import (
    Coupon,
    CouponUsage,
    Promotion,
    CouponType,
    PromotionStatus,
)
from ..schemas.promotion_schemas import (
    CouponCreate,
    CouponBulkCreate,
    CouponValidationRequest,
    CouponValidationResponse,
)
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class CouponService:
    """Service for managing coupons and coupon codes"""

    def __init__(self, db: Session):
        self.db = db

    def generate_coupon_code(
        self,
        length: int = 8,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        exclude_ambiguous: bool = True,
    ) -> str:
        """
        Generate a unique coupon code

        Args:
            length: Length of the random part
            prefix: Optional prefix
            suffix: Optional suffix
            exclude_ambiguous: Exclude ambiguous characters (0, O, 1, I, etc.)
        """
        # Character sets
        if exclude_ambiguous:
            # Exclude visually similar characters
            chars = string.ascii_uppercase + string.digits
            chars = chars.translate(str.maketrans("", "", "01IO"))
        else:
            chars = string.ascii_uppercase + string.digits

        # Generate random part
        random_part = "".join(secrets.choice(chars) for _ in range(length))

        # Combine with prefix/suffix
        code = ""
        if prefix:
            code += prefix.upper()
        code += random_part
        if suffix:
            code += suffix.upper()

        # Ensure uniqueness
        max_attempts = 100
        attempts = 0

        while attempts < max_attempts:
            existing = self.db.query(Coupon).filter(Coupon.code == code).first()
            if not existing:
                return code

            # Generate new random part
            random_part = "".join(secrets.choice(chars) for _ in range(length))
            code = ""
            if prefix:
                code += prefix.upper()
            code += random_part
            if suffix:
                code += suffix.upper()

            attempts += 1

        raise ValueError(
            f"Could not generate unique coupon code after {max_attempts} attempts"
        )

    def create_coupon(
        self, coupon_data: CouponCreate, generated_by: Optional[int] = None
    ) -> Coupon:
        """Create a single coupon"""
        try:
            # Validate promotion exists and is active
            promotion = (
                self.db.query(Promotion)
                .filter(
                    Promotion.id == coupon_data.promotion_id,
                    Promotion.status != PromotionStatus.CANCELLED,
                )
                .first()
            )

            if not promotion:
                raise ValueError(
                    f"Promotion {coupon_data.promotion_id} not found or cancelled"
                )

            # Generate code if not provided
            code = coupon_data.code
            if not code:
                code = self.generate_coupon_code()
            else:
                # Check if code already exists
                existing = self.db.query(Coupon).filter(Coupon.code == code).first()
                if existing:
                    raise ValueError(f"Coupon code '{code}' already exists")

            # Set validity dates based on promotion if not specified
            valid_from = coupon_data.valid_from or promotion.start_date
            valid_until = coupon_data.valid_until or promotion.end_date

            # Create coupon
            coupon = Coupon(
                promotion_id=coupon_data.promotion_id,
                code=code,
                coupon_type=coupon_data.coupon_type,
                max_uses=coupon_data.max_uses,
                customer_id=coupon_data.customer_id,
                customer_email=coupon_data.customer_email,
                valid_from=valid_from,
                valid_until=valid_until,
                batch_id=coupon_data.batch_id,
                generation_method=coupon_data.generation_method,
                generated_by=generated_by,
            )

            self.db.add(coupon)
            self.db.commit()
            self.db.refresh(coupon)

            logger.info(
                f"Created coupon: {code} for promotion {coupon_data.promotion_id}"
            )
            return coupon

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating coupon: {str(e)}")
            raise

    def create_bulk_coupons(
        self, bulk_data: CouponBulkCreate, generated_by: Optional[int] = None
    ) -> List[Coupon]:
        """Create multiple coupons in bulk"""
        try:
            # Validate promotion
            promotion = (
                self.db.query(Promotion)
                .filter(
                    Promotion.id == bulk_data.promotion_id,
                    Promotion.status != PromotionStatus.CANCELLED,
                )
                .first()
            )

            if not promotion:
                raise ValueError(
                    f"Promotion {bulk_data.promotion_id} not found or cancelled"
                )

            # Generate batch ID
            batch_id = f"BULK_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4).upper()}"

            # Set validity dates
            valid_from = bulk_data.valid_from or promotion.start_date
            valid_until = bulk_data.valid_until or promotion.end_date

            coupons = []
            created_codes = set()

            for i in range(bulk_data.quantity):
                # Generate unique code
                max_attempts = 10
                attempts = 0
                code = None

                while attempts < max_attempts:
                    code = self.generate_coupon_code(
                        length=bulk_data.length,
                        prefix=bulk_data.prefix,
                        suffix=bulk_data.suffix,
                    )

                    # Check against database and current batch
                    existing = self.db.query(Coupon).filter(Coupon.code == code).first()
                    if not existing and code not in created_codes:
                        created_codes.add(code)
                        break

                    attempts += 1

                if not code or attempts >= max_attempts:
                    raise ValueError(f"Could not generate unique code for coupon {i+1}")

                coupon = Coupon(
                    promotion_id=bulk_data.promotion_id,
                    code=code,
                    coupon_type=bulk_data.coupon_type,
                    max_uses=bulk_data.max_uses,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    batch_id=batch_id,
                    generation_method="bulk",
                    generated_by=generated_by,
                )

                coupons.append(coupon)

            # Bulk insert
            self.db.bulk_save_objects(coupons)
            self.db.commit()

            # Refresh objects to get IDs
            created_coupons = (
                self.db.query(Coupon).filter(Coupon.batch_id == batch_id).all()
            )

            logger.info(f"Created {len(created_coupons)} coupons in batch {batch_id}")
            return created_coupons

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating bulk coupons: {str(e)}")
            raise

    def validate_coupon(
        self, validation_request: CouponValidationRequest
    ) -> CouponValidationResponse:
        """
        Validate a coupon code and calculate potential discount

        Args:
            validation_request: Coupon validation request with code and order details

        Returns:
            CouponValidationResponse with validation results
        """
        try:
            # Get coupon with promotion details
            coupon = (
                self.db.query(Coupon)
                .options(joinedload(Coupon.promotion))
                .filter(
                    Coupon.code == validation_request.code.upper(),
                    Coupon.is_active == True,
                )
                .first()
            )

            if not coupon:
                return CouponValidationResponse(
                    is_valid=False, error_message="Coupon code not found or inactive"
                )

            # Check coupon validity
            now = datetime.utcnow()

            # Check date validity
            if coupon.valid_from and now < coupon.valid_from:
                return CouponValidationResponse(
                    is_valid=False,
                    coupon=coupon,
                    error_message="Coupon is not yet valid",
                )

            if coupon.valid_until and now > coupon.valid_until:
                return CouponValidationResponse(
                    is_valid=False, coupon=coupon, error_message="Coupon has expired"
                )

            # Check usage limits
            if coupon.current_uses >= coupon.max_uses:
                return CouponValidationResponse(
                    is_valid=False,
                    coupon=coupon,
                    error_message="Coupon usage limit exceeded",
                )

            # Check customer-specific coupons
            if (
                coupon.customer_id
                and validation_request.customer_id != coupon.customer_id
            ):
                return CouponValidationResponse(
                    is_valid=False,
                    coupon=coupon,
                    error_message="Coupon is not valid for this customer",
                )

            # Check customer usage limits
            if validation_request.customer_id:
                customer_usage_count = (
                    self.db.query(CouponUsage)
                    .filter(
                        CouponUsage.coupon_id == coupon.id,
                        CouponUsage.customer_id == validation_request.customer_id,
                    )
                    .count()
                )

                promotion_usage_count = (
                    self.db.query(CouponUsage)
                    .join(Coupon)
                    .filter(
                        Coupon.promotion_id == coupon.promotion_id,
                        CouponUsage.customer_id == validation_request.customer_id,
                    )
                    .count()
                )

                if (
                    coupon.promotion.max_uses_per_customer
                    and promotion_usage_count >= coupon.promotion.max_uses_per_customer
                ):
                    return CouponValidationResponse(
                        is_valid=False,
                        coupon=coupon,
                        error_message="Customer has exceeded usage limit for this promotion",
                    )

            # Check promotion validity
            promotion = coupon.promotion
            if not promotion.is_active:
                return CouponValidationResponse(
                    is_valid=False,
                    coupon=coupon,
                    error_message="Associated promotion is not active",
                )

            # Check minimum order amount
            if (
                promotion.min_order_amount
                and validation_request.order_total < promotion.min_order_amount
            ):
                return CouponValidationResponse(
                    is_valid=False,
                    coupon=coupon,
                    error_message=f"Minimum order amount of ${promotion.min_order_amount:.2f} required",
                )

            # Calculate discount
            from .discount_service import DiscountService

            discount_service = DiscountService(self.db)

            discount_amount = discount_service.calculate_promotion_discount(
                promotion=promotion,
                order_total=validation_request.order_total,
                order_items=validation_request.order_items or [],
                customer_id=validation_request.customer_id,
            )

            return CouponValidationResponse(
                is_valid=True,
                coupon=coupon,
                discount_amount=discount_amount,
                applicable_items=validation_request.order_items,  # Could be filtered based on promotion rules
            )

        except Exception as e:
            logger.error(f"Error validating coupon {validation_request.code}: {str(e)}")
            return CouponValidationResponse(
                is_valid=False, error_message="Error validating coupon code"
            )

    def use_coupon(
        self,
        coupon_code: str,
        customer_id: Optional[int],
        order_id: int,
        discount_amount: float,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> CouponUsage:
        """
        Mark a coupon as used and record the usage

        Args:
            coupon_code: The coupon code being used
            customer_id: Customer using the coupon
            order_id: Order the coupon is applied to
            discount_amount: Amount of discount applied
            usage_context: Additional context data

        Returns:
            CouponUsage record
        """
        try:
            # Get coupon
            coupon = (
                self.db.query(Coupon).filter(Coupon.code == coupon_code.upper()).first()
            )

            if not coupon:
                raise ValueError(f"Coupon {coupon_code} not found")

            # Increment usage count
            coupon.current_uses += 1

            # Deactivate if max uses reached
            if coupon.current_uses >= coupon.max_uses:
                coupon.is_active = False

            # Create usage record
            usage = CouponUsage(
                coupon_id=coupon.id,
                customer_id=customer_id,
                order_id=order_id,
                discount_amount=discount_amount,
                usage_context=usage_context or {},
            )

            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

            logger.info(
                f"Coupon {coupon_code} used for order {order_id}, discount: ${discount_amount:.2f}"
            )
            return usage

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error using coupon {coupon_code}: {str(e)}")
            raise

    def get_customer_coupons(
        self, customer_id: int, active_only: bool = True, include_expired: bool = False
    ) -> List[Coupon]:
        """Get coupons available to a specific customer"""
        query = (
            self.db.query(Coupon)
            .options(joinedload(Coupon.promotion))
            .filter(
                or_(
                    Coupon.customer_id == customer_id,
                    Coupon.customer_id.is_(None),  # Public coupons
                )
            )
        )

        if active_only:
            query = query.filter(Coupon.is_active == True)

        if not include_expired:
            now = datetime.utcnow()
            query = query.filter(
                or_(Coupon.valid_until.is_(None), Coupon.valid_until > now)
            )

        return query.order_by(Coupon.valid_until.asc()).all()

    def get_coupon_usage_history(
        self,
        coupon_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[CouponUsage]:
        """Get coupon usage history with filters"""
        query = self.db.query(CouponUsage).options(
            joinedload(CouponUsage.coupon), joinedload(CouponUsage.customer)
        )

        if coupon_id:
            query = query.filter(CouponUsage.coupon_id == coupon_id)

        if customer_id:
            query = query.filter(CouponUsage.customer_id == customer_id)

        if start_date:
            query = query.filter(CouponUsage.created_at >= start_date)

        if end_date:
            query = query.filter(CouponUsage.created_at <= end_date)

        return query.order_by(CouponUsage.created_at.desc()).limit(limit).all()

    def deactivate_coupon(self, coupon_id: int, reason: Optional[str] = None) -> bool:
        """Deactivate a coupon"""
        try:
            coupon = self.db.query(Coupon).filter(Coupon.id == coupon_id).first()
            if not coupon:
                return False

            coupon.is_active = False
            self.db.commit()

            logger.info(
                f"Deactivated coupon {coupon.code}, reason: {reason or 'Manual'}"
            )
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deactivating coupon {coupon_id}: {str(e)}")
            return False

    def get_batch_coupons(self, batch_id: str) -> List[Coupon]:
        """Get all coupons from a specific batch"""
        return (
            self.db.query(Coupon)
            .filter(Coupon.batch_id == batch_id)
            .order_by(Coupon.created_at)
            .all()
        )

    def get_coupon_analytics(
        self,
        promotion_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get coupon usage analytics"""
        try:
            query = self.db.query(Coupon)

            if promotion_id:
                query = query.filter(Coupon.promotion_id == promotion_id)

            if start_date:
                query = query.filter(Coupon.created_at >= start_date)

            if end_date:
                query = query.filter(Coupon.created_at <= end_date)

            # Basic stats
            total_coupons = query.count()
            active_coupons = query.filter(Coupon.is_active == True).count()
            used_coupons = query.filter(Coupon.current_uses > 0).count()

            # Usage stats
            usage_query = self.db.query(CouponUsage).join(Coupon)

            if promotion_id:
                usage_query = usage_query.filter(Coupon.promotion_id == promotion_id)

            if start_date:
                usage_query = usage_query.filter(CouponUsage.created_at >= start_date)

            if end_date:
                usage_query = usage_query.filter(CouponUsage.created_at <= end_date)

            total_usage = usage_query.count()
            total_discount = (
                usage_query.with_entities(
                    func.sum(CouponUsage.discount_amount)
                ).scalar()
                or 0.0
            )

            # Calculate rates
            usage_rate = (total_usage / total_coupons * 100) if total_coupons > 0 else 0

            return {
                "total_coupons": total_coupons,
                "active_coupons": active_coupons,
                "used_coupons": used_coupons,
                "total_usage": total_usage,
                "usage_rate": round(usage_rate, 2),
                "total_discount_amount": round(total_discount, 2),
                "average_discount": (
                    round(total_discount / total_usage, 2) if total_usage > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting coupon analytics: {str(e)}")
            return {}

    def cleanup_expired_coupons(self) -> int:
        """Remove or deactivate expired coupons"""
        try:
            now = datetime.utcnow()

            # Deactivate expired coupons
            expired_count = (
                self.db.query(Coupon)
                .filter(Coupon.is_active == True, Coupon.valid_until < now)
                .update({"is_active": False})
            )

            self.db.commit()

            logger.info(f"Deactivated {expired_count} expired coupons")
            return expired_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning up expired coupons: {str(e)}")
            return 0
