# backend/modules/promotions/services/idempotent_discount_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import hashlib
import json
import uuid

from modules.promotions.models.promotion_models import (
    Promotion,
    Coupon,
    PromotionUsage,
    CouponUsage,
    PromotionStatus,
)
from modules.promotions.services.discount_service import DiscountCalculationService
from modules.promotions.services.cache_service import cache_service
from modules.orders.models.order_models import Order

logger = logging.getLogger(__name__)


class IdempotentDiscountService:
    """Service for applying discounts with idempotency guarantees"""

    def __init__(self, db: Session):
        self.db = db
        self.discount_service = DiscountCalculationService(db)
        self.cache = cache_service

    def generate_operation_key(
        self,
        order_id: int,
        promotion_ids: List[int],
        coupon_codes: List[str],
        customer_id: int,
    ) -> str:
        """Generate unique key for discount operation"""
        operation_data = {
            "order_id": order_id,
            "promotion_ids": sorted(promotion_ids),
            "coupon_codes": sorted(coupon_codes),
            "customer_id": customer_id,
        }

        operation_str = json.dumps(operation_data, sort_keys=True)
        return hashlib.sha256(operation_str.encode()).hexdigest()

    def check_existing_discount_application(
        self,
        order_id: int,
        promotion_ids: List[int] = None,
        coupon_codes: List[str] = None,
    ) -> Dict[str, Any]:
        """Check if discounts have already been applied to this order"""

        existing_applications = {
            "promotions": [],
            "coupons": [],
            "total_discount": 0.0,
            "has_applications": False,
        }

        # Check for existing promotion usage
        if promotion_ids:
            existing_promo_usage = (
                self.db.query(PromotionUsage)
                .filter(
                    PromotionUsage.order_id == order_id,
                    PromotionUsage.promotion_id.in_(promotion_ids),
                )
                .all()
            )

            for usage in existing_promo_usage:
                existing_applications["promotions"].append(
                    {
                        "promotion_id": usage.promotion_id,
                        "discount_amount": float(usage.discount_amount),
                        "applied_at": usage.created_at.isoformat(),
                    }
                )
                existing_applications["total_discount"] += float(usage.discount_amount)

        # Check for existing coupon usage
        if coupon_codes:
            # Get coupon IDs for the codes
            coupons = self.db.query(Coupon).filter(Coupon.code.in_(coupon_codes)).all()
            coupon_ids = [c.id for c in coupons]

            if coupon_ids:
                existing_coupon_usage = (
                    self.db.query(CouponUsage)
                    .filter(
                        CouponUsage.order_id == order_id,
                        CouponUsage.coupon_id.in_(coupon_ids),
                    )
                    .all()
                )

                for usage in existing_coupon_usage:
                    coupon = next((c for c in coupons if c.id == usage.coupon_id), None)
                    existing_applications["coupons"].append(
                        {
                            "coupon_code": coupon.code if coupon else "unknown",
                            "coupon_id": usage.coupon_id,
                            "discount_amount": float(usage.discount_amount),
                            "applied_at": usage.created_at.isoformat(),
                        }
                    )
                    existing_applications["total_discount"] += float(
                        usage.discount_amount
                    )

        existing_applications["has_applications"] = (
            len(existing_applications["promotions"]) > 0
            or len(existing_applications["coupons"]) > 0
        )

        return existing_applications

    def apply_discount_idempotent(
        self,
        order_id: int,
        order_items: List[Dict[str, Any]],
        customer_id: int,
        promotion_ids: List[int] = None,
        coupon_codes: List[str] = None,
        idempotency_key: Optional[str] = None,
        force_reapply: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply discounts to order with idempotency guarantees

        Args:
            order_id: ID of the order
            order_items: List of order items
            customer_id: Customer ID
            promotion_ids: List of promotion IDs to apply
            coupon_codes: List of coupon codes to apply
            idempotency_key: Client-provided idempotency key
            force_reapply: Whether to force reapplication of discounts

        Returns:
            Dictionary with application results
        """

        try:
            # Generate operation key if not provided
            if not idempotency_key:
                idempotency_key = self.generate_operation_key(
                    order_id, promotion_ids or [], coupon_codes or [], customer_id
                )

            # Check cache for previous results
            cache_key = f"discount_application:{idempotency_key}"
            cached_result = self.cache.get(cache_key)

            if cached_result and not force_reapply:
                logger.info(
                    f"Returning cached discount application result for key: {idempotency_key}"
                )
                return cached_result

            # Check for existing applications in database
            existing = self.check_existing_discount_application(
                order_id, promotion_ids, coupon_codes
            )

            if existing["has_applications"] and not force_reapply:
                result = {
                    "success": True,
                    "idempotent": True,
                    "message": "Discounts already applied to this order",
                    "existing_applications": existing,
                    "total_discount_applied": existing["total_discount"],
                    "applied_at": datetime.utcnow().isoformat(),
                }

                # Cache the result
                self.cache.set(cache_key, result, ttl=3600)
                return result

            # Get the order
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order:
                raise ValueError(f"Order {order_id} not found")

            # Begin discount application transaction
            application_results = {
                "promotions_applied": [],
                "coupons_applied": [],
                "total_discount": 0.0,
                "errors": [],
            }

            # Apply promotions
            if promotion_ids:
                for promotion_id in promotion_ids:
                    try:
                        promo_result = self._apply_single_promotion(
                            order,
                            order_items,
                            customer_id,
                            promotion_id,
                            idempotency_key,
                        )

                        if promo_result["success"]:
                            application_results["promotions_applied"].append(
                                promo_result
                            )
                            application_results["total_discount"] += promo_result[
                                "discount_amount"
                            ]
                        else:
                            application_results["errors"].append(promo_result)

                    except Exception as e:
                        error_result = {
                            "promotion_id": promotion_id,
                            "success": False,
                            "error": str(e),
                        }
                        application_results["errors"].append(error_result)
                        logger.error(f"Error applying promotion {promotion_id}: {e}")

            # Apply coupons
            if coupon_codes:
                for coupon_code in coupon_codes:
                    try:
                        coupon_result = self._apply_single_coupon(
                            order,
                            order_items,
                            customer_id,
                            coupon_code,
                            idempotency_key,
                        )

                        if coupon_result["success"]:
                            application_results["coupons_applied"].append(coupon_result)
                            application_results["total_discount"] += coupon_result[
                                "discount_amount"
                            ]
                        else:
                            application_results["errors"].append(coupon_result)

                    except Exception as e:
                        error_result = {
                            "coupon_code": coupon_code,
                            "success": False,
                            "error": str(e),
                        }
                        application_results["errors"].append(error_result)
                        logger.error(f"Error applying coupon {coupon_code}: {e}")

            # Update order totals
            if application_results["total_discount"] > 0:
                self._update_order_totals(order, application_results["total_discount"])

            # Commit transaction
            self.db.commit()

            # Prepare final result
            final_result = {
                "success": True,
                "idempotent": False,
                "idempotency_key": idempotency_key,
                "order_id": order_id,
                "customer_id": customer_id,
                "application_results": application_results,
                "total_discount_applied": application_results["total_discount"],
                "promotions_count": len(application_results["promotions_applied"]),
                "coupons_count": len(application_results["coupons_applied"]),
                "errors_count": len(application_results["errors"]),
                "applied_at": datetime.utcnow().isoformat(),
            }

            # Cache the result
            self.cache.set(cache_key, final_result, ttl=3600)

            # Invalidate related caches
            self._invalidate_related_caches(
                order_id, customer_id, promotion_ids, coupon_codes
            )

            logger.info(
                f"Successfully applied discounts to order {order_id}. Total discount: {application_results['total_discount']}"
            )

            return final_result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in idempotent discount application: {e}")

            error_result = {
                "success": False,
                "idempotent": False,
                "error": str(e),
                "order_id": order_id,
                "failed_at": datetime.utcnow().isoformat(),
            }

            return error_result

    def _apply_single_promotion(
        self,
        order: Order,
        order_items: List[Dict[str, Any]],
        customer_id: int,
        promotion_id: int,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """Apply a single promotion with duplicate detection"""

        # Check if this promotion has already been applied to this order
        existing_usage = (
            self.db.query(PromotionUsage)
            .filter(
                PromotionUsage.order_id == order.id,
                PromotionUsage.promotion_id == promotion_id,
            )
            .first()
        )

        if existing_usage:
            return {
                "promotion_id": promotion_id,
                "success": True,
                "already_applied": True,
                "discount_amount": float(existing_usage.discount_amount),
                "usage_id": existing_usage.id,
            }

        # Calculate discount
        discount_amount = self.discount_service.calculate_discount(
            promotion_id, order_items, customer_id
        )

        if discount_amount <= 0:
            return {
                "promotion_id": promotion_id,
                "success": False,
                "error": "No discount applicable",
                "discount_amount": 0.0,
            }

        # Create usage record
        usage_record = PromotionUsage(
            promotion_id=promotion_id,
            customer_id=customer_id,
            order_id=order.id,
            discount_amount=discount_amount,
            final_order_amount=order.total_amount - discount_amount,
            metadata={
                "idempotency_key": idempotency_key,
                "order_items": order_items,
                "applied_method": "idempotent_service",
            },
            created_at=datetime.utcnow(),
        )

        self.db.add(usage_record)
        self.db.flush()  # Get the ID

        # Update promotion usage count
        promotion = (
            self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
        )
        if promotion:
            promotion.current_uses = (promotion.current_uses or 0) + 1

        return {
            "promotion_id": promotion_id,
            "success": True,
            "already_applied": False,
            "discount_amount": float(discount_amount),
            "usage_id": usage_record.id,
        }

    def _apply_single_coupon(
        self,
        order: Order,
        order_items: List[Dict[str, Any]],
        customer_id: int,
        coupon_code: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """Apply a single coupon with duplicate detection"""

        # Get coupon
        coupon = self.db.query(Coupon).filter(Coupon.code == coupon_code).first()
        if not coupon:
            return {
                "coupon_code": coupon_code,
                "success": False,
                "error": "Coupon not found",
            }

        # Check if this coupon has already been applied to this order
        existing_usage = (
            self.db.query(CouponUsage)
            .filter(
                CouponUsage.order_id == order.id, CouponUsage.coupon_id == coupon.id
            )
            .first()
        )

        if existing_usage:
            return {
                "coupon_code": coupon_code,
                "coupon_id": coupon.id,
                "success": True,
                "already_applied": True,
                "discount_amount": float(existing_usage.discount_amount),
                "usage_id": existing_usage.id,
            }

        # Validate coupon
        from modules.promotions.services.coupon_service import CouponService

        coupon_service = CouponService(self.db)

        is_valid, reason, _ = coupon_service.validate_coupon_code(
            coupon_code, customer_id
        )
        if not is_valid:
            return {
                "coupon_code": coupon_code,
                "coupon_id": coupon.id,
                "success": False,
                "error": f"Coupon validation failed: {reason}",
            }

        # Calculate discount through promotion
        discount_amount = self.discount_service.calculate_discount(
            coupon.promotion_id, order_items, customer_id
        )

        if discount_amount <= 0:
            return {
                "coupon_code": coupon_code,
                "coupon_id": coupon.id,
                "success": False,
                "error": "No discount applicable",
                "discount_amount": 0.0,
            }

        # Create coupon usage record
        coupon_usage = CouponUsage(
            coupon_id=coupon.id,
            customer_id=customer_id,
            order_id=order.id,
            discount_amount=discount_amount,
            metadata={
                "idempotency_key": idempotency_key,
                "order_items": order_items,
                "applied_method": "idempotent_service",
            },
            created_at=datetime.utcnow(),
        )

        self.db.add(coupon_usage)
        self.db.flush()

        # Update coupon usage count
        coupon.current_uses = (coupon.current_uses or 0) + 1

        # Also create promotion usage record
        promotion_usage = PromotionUsage(
            promotion_id=coupon.promotion_id,
            customer_id=customer_id,
            order_id=order.id,
            discount_amount=discount_amount,
            final_order_amount=order.total_amount - discount_amount,
            metadata={
                "idempotency_key": idempotency_key,
                "coupon_code": coupon_code,
                "applied_method": "idempotent_service_coupon",
            },
            created_at=datetime.utcnow(),
        )

        self.db.add(promotion_usage)

        return {
            "coupon_code": coupon_code,
            "coupon_id": coupon.id,
            "promotion_id": coupon.promotion_id,
            "success": True,
            "already_applied": False,
            "discount_amount": float(discount_amount),
            "usage_id": coupon_usage.id,
        }

    def _update_order_totals(self, order: Order, total_discount: float):
        """Update order totals with applied discounts"""

        # Update discount amount
        order.discount_amount = (order.discount_amount or 0.0) + total_discount

        # Update final amount
        order.final_amount = order.total_amount - order.discount_amount

        # Ensure final amount doesn't go below zero
        if order.final_amount < 0:
            order.final_amount = 0.0

        order.updated_at = datetime.utcnow()

    def _invalidate_related_caches(
        self,
        order_id: int,
        customer_id: int,
        promotion_ids: List[int] = None,
        coupon_codes: List[str] = None,
    ):
        """Invalidate caches related to the discount application"""

        # Invalidate customer-specific caches
        self.cache.invalidate_customer_cache(customer_id)

        # Invalidate promotion-specific caches
        if promotion_ids:
            for promotion_id in promotion_ids:
                self.cache.invalidate_promotion_cache(promotion_id)

        # Invalidate coupon-specific caches
        if coupon_codes:
            for coupon_code in coupon_codes:
                self.cache.invalidate_coupon_cache(coupon_code)

        # Invalidate order-specific caches
        order_cache_patterns = [f"order:{order_id}:*", f"order_discount:{order_id}:*"]

        for pattern in order_cache_patterns:
            self.cache.delete_pattern(pattern)

    def rollback_discount_application(
        self, order_id: int, idempotency_key: str, reason: str = "Manual rollback"
    ) -> Dict[str, Any]:
        """Rollback a discount application"""

        try:
            # Find all usage records for this order with the idempotency key
            promotion_usages = (
                self.db.query(PromotionUsage)
                .filter(
                    PromotionUsage.order_id == order_id,
                    PromotionUsage.metadata["idempotency_key"].astext
                    == idempotency_key,
                )
                .all()
            )

            coupon_usages = (
                self.db.query(CouponUsage)
                .filter(
                    CouponUsage.order_id == order_id,
                    CouponUsage.metadata["idempotency_key"].astext == idempotency_key,
                )
                .all()
            )

            total_rollback_amount = 0.0
            rollback_details = {"promotions_rolled_back": [], "coupons_rolled_back": []}

            # Rollback promotion usages
            for usage in promotion_usages:
                promotion = (
                    self.db.query(Promotion)
                    .filter(Promotion.id == usage.promotion_id)
                    .first()
                )

                if promotion:
                    promotion.current_uses = max(0, (promotion.current_uses or 0) - 1)

                total_rollback_amount += float(usage.discount_amount)
                rollback_details["promotions_rolled_back"].append(
                    {
                        "promotion_id": usage.promotion_id,
                        "discount_amount": float(usage.discount_amount),
                    }
                )

                self.db.delete(usage)

            # Rollback coupon usages
            for usage in coupon_usages:
                coupon = (
                    self.db.query(Coupon).filter(Coupon.id == usage.coupon_id).first()
                )

                if coupon:
                    coupon.current_uses = max(0, (coupon.current_uses or 0) - 1)

                total_rollback_amount += float(usage.discount_amount)
                rollback_details["coupons_rolled_back"].append(
                    {
                        "coupon_id": usage.coupon_id,
                        "discount_amount": float(usage.discount_amount),
                    }
                )

                self.db.delete(usage)

            # Update order totals
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.discount_amount = max(
                    0.0, (order.discount_amount or 0.0) - total_rollback_amount
                )
                order.final_amount = order.total_amount - order.discount_amount
                order.updated_at = datetime.utcnow()

            self.db.commit()

            # Invalidate cache
            cache_key = f"discount_application:{idempotency_key}"
            self.cache.delete(cache_key)

            result = {
                "success": True,
                "order_id": order_id,
                "idempotency_key": idempotency_key,
                "total_rollback_amount": total_rollback_amount,
                "rollback_details": rollback_details,
                "reason": reason,
                "rolled_back_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Successfully rolled back discount application for order {order_id}"
            )
            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error rolling back discount application: {e}")

            return {
                "success": False,
                "error": str(e),
                "order_id": order_id,
                "idempotency_key": idempotency_key,
            }

    def get_application_status(self, idempotency_key: str) -> Dict[str, Any]:
        """Get status of a discount application by idempotency key"""

        # Check cache first
        cache_key = f"discount_application:{idempotency_key}"
        cached_result = self.cache.get(cache_key)

        if cached_result:
            return {"found": True, "source": "cache", "result": cached_result}

        # Check database
        promotion_usages = (
            self.db.query(PromotionUsage)
            .filter(
                PromotionUsage.metadata["idempotency_key"].astext == idempotency_key
            )
            .all()
        )

        coupon_usages = (
            self.db.query(CouponUsage)
            .filter(CouponUsage.metadata["idempotency_key"].astext == idempotency_key)
            .all()
        )

        if promotion_usages or coupon_usages:
            # Reconstruct result from database
            total_discount = sum(
                float(u.discount_amount) for u in promotion_usages + coupon_usages
            )

            result = {
                "found": True,
                "source": "database",
                "idempotency_key": idempotency_key,
                "total_discount": total_discount,
                "promotions_applied": len(promotion_usages),
                "coupons_applied": len(coupon_usages),
                "last_applied": max(
                    (u.created_at for u in promotion_usages + coupon_usages),
                    default=datetime.utcnow(),
                ).isoformat(),
            }

            return result

        return {"found": False, "idempotency_key": idempotency_key}
