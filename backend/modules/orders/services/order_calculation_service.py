# backend/modules/orders/services/order_calculation_service.py

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
import logging

from ..models.order_models import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderCalculationService:
    """Service for calculating order totals, taxes, and final amounts"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_order_totals(
        self,
        order: Order,
        tax_rate: float = 0.08,  # Default 8% tax rate
        calculate_discounts: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculate all order totals including subtotal, tax, discounts, and final amount

        Args:
            order: Order to calculate totals for
            tax_rate: Tax rate to apply (as decimal, e.g., 0.08 for 8%)
            calculate_discounts: Whether to recalculate discounts

        Returns:
            Dictionary with calculated totals
        """
        try:
            # Calculate subtotal from order items
            subtotal = Decimal("0.00")
            for item in order.order_items:
                item_total = Decimal(str(item.price)) * item.quantity
                subtotal += item_total

            # Get existing discount amount or default to 0
            discount_amount = Decimal(str(order.discount_amount or 0))

            # Calculate taxable amount (subtotal minus discount)
            taxable_amount = max(subtotal - discount_amount, Decimal("0.00"))

            # Calculate tax
            tax_amount = (taxable_amount * Decimal(str(tax_rate))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Calculate total amount (subtotal + tax)
            total_amount = subtotal + tax_amount

            # Calculate final amount (total - discount)
            final_amount = max(total_amount - discount_amount, Decimal("0.00"))

            # Update order fields
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.total_amount = total_amount
            order.final_amount = final_amount

            # If discount amount wasn't already set, ensure it's 0
            if order.discount_amount is None:
                order.discount_amount = Decimal("0.00")

            calculation_result = {
                "subtotal": float(subtotal),
                "discount_amount": float(discount_amount),
                "tax_amount": float(tax_amount),
                "total_amount": float(total_amount),
                "final_amount": float(final_amount),
                "tax_rate": tax_rate,
                "savings": float(discount_amount),
                "items_count": len(order.order_items),
                "total_quantity": sum(item.quantity for item in order.order_items),
            }

            logger.info(
                f"Calculated order totals for order {order.id}: "
                f"Subtotal: ${subtotal}, Tax: ${tax_amount}, "
                f"Discount: ${discount_amount}, Final: ${final_amount}"
            )

            return calculation_result

        except Exception as e:
            logger.error(
                f"Error calculating order totals for order {order.id}: {str(e)}"
            )
            raise

    def update_order_totals(self, order: Order, commit: bool = True) -> Dict[str, Any]:
        """
        Update order totals and save to database

        Args:
            order: Order to update
            commit: Whether to commit the transaction

        Returns:
            Dictionary with calculated totals
        """
        try:
            result = self.calculate_order_totals(order)

            if commit:
                self.db.commit()
                self.db.refresh(order)

            return result

        except Exception as e:
            if commit:
                self.db.rollback()
            logger.error(f"Error updating order totals for order {order.id}: {str(e)}")
            raise

    def recalculate_with_discount(
        self, order: Order, discount_amount: float, tax_rate: float = 0.08
    ) -> Dict[str, Any]:
        """
        Recalculate order totals with a specific discount amount

        Args:
            order: Order to recalculate
            discount_amount: Discount amount to apply
            tax_rate: Tax rate to apply

        Returns:
            Dictionary with recalculated totals
        """
        try:
            # Set the discount amount
            order.discount_amount = Decimal(str(discount_amount))

            # Recalculate totals
            result = self.calculate_order_totals(order, tax_rate)

            return result

        except Exception as e:
            logger.error(f"Error recalculating order with discount: {str(e)}")
            raise

    def get_order_summary(self, order: Order) -> Dict[str, Any]:
        """
        Get a comprehensive summary of order calculations

        Args:
            order: Order to summarize

        Returns:
            Dictionary with order summary
        """
        try:
            # Get items breakdown
            items_breakdown = []
            for item in order.order_items:
                item_total = float(item.price) * item.quantity
                items_breakdown.append(
                    {
                        "menu_item_id": item.menu_item_id,
                        "quantity": item.quantity,
                        "unit_price": float(item.price),
                        "total_price": item_total,
                        "notes": item.notes,
                    }
                )

            # Get promotion and coupon details
            promotions = order.promotions_applied or []
            coupons = order.coupons_used or []

            # Calculate savings percentage
            savings_percentage = 0.0
            if order.total_amount and order.total_amount > 0:
                savings_percentage = (
                    float(order.discount_amount or 0) / float(order.total_amount)
                ) * 100

            summary = {
                "order_id": order.id,
                "calculation_summary": {
                    "subtotal": float(order.subtotal or 0),
                    "discount_amount": float(order.discount_amount or 0),
                    "tax_amount": float(order.tax_amount or 0),
                    "total_amount": float(order.total_amount or 0),
                    "final_amount": float(order.final_amount or 0),
                },
                "savings_info": {
                    "total_savings": float(order.discount_amount or 0),
                    "savings_percentage": round(savings_percentage, 2),
                    "promotions_count": len(promotions),
                    "coupons_count": len(coupons),
                },
                "items_breakdown": items_breakdown,
                "promotions_applied": promotions,
                "coupons_used": coupons,
                "referral_info": (
                    {
                        "referral_code_used": order.referral_code_used,
                        "is_qualifying": order.is_referral_qualifying,
                    }
                    if order.referral_code_used
                    else None
                ),
            }

            return summary

        except Exception as e:
            logger.error(f"Error getting order summary for order {order.id}: {str(e)}")
            raise

    def validate_order_amounts(self, order: Order) -> Dict[str, Any]:
        """
        Validate that order amounts are calculated correctly

        Args:
            order: Order to validate

        Returns:
            Dictionary with validation results
        """
        try:
            # Recalculate totals
            calculated = self.calculate_order_totals(order)

            # Compare with stored values
            validation_results = {
                "is_valid": True,
                "discrepancies": [],
                "calculated_totals": calculated,
                "stored_totals": {
                    "subtotal": float(order.subtotal or 0),
                    "discount_amount": float(order.discount_amount or 0),
                    "tax_amount": float(order.tax_amount or 0),
                    "total_amount": float(order.total_amount or 0),
                    "final_amount": float(order.final_amount or 0),
                },
            }

            # Check for discrepancies (allow for small floating point differences)
            tolerance = 0.01

            if abs(calculated["subtotal"] - float(order.subtotal or 0)) > tolerance:
                validation_results["discrepancies"].append("subtotal")
                validation_results["is_valid"] = False

            if abs(calculated["tax_amount"] - float(order.tax_amount or 0)) > tolerance:
                validation_results["discrepancies"].append("tax_amount")
                validation_results["is_valid"] = False

            if (
                abs(calculated["final_amount"] - float(order.final_amount or 0))
                > tolerance
            ):
                validation_results["discrepancies"].append("final_amount")
                validation_results["is_valid"] = False

            return validation_results

        except Exception as e:
            logger.error(
                f"Error validating order amounts for order {order.id}: {str(e)}"
            )
            return {
                "is_valid": False,
                "error": str(e),
                "discrepancies": ["validation_error"],
            }
