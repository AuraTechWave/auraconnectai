# backend/modules/payments/services/reconciliation_service.py

import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload

from ..models.payment_models import Payment, PaymentStatus, PaymentGateway, Refund, RefundStatus
from ..models.split_bill_models import SplitBillPayment, SplitBillPaymentStatus
from ...orders.models.order_models import Order, OrderStatus

logger = logging.getLogger(__name__)


class PaymentReconciliationService:
    """
    Service for payment reconciliation and reporting
    """

    async def generate_daily_reconciliation_report(
        self,
        db: AsyncSession,
        report_date: date,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate daily payment reconciliation report
        
        Args:
            db: Database session
            report_date: Date for the report
            restaurant_id: Optional restaurant filter
            location_id: Optional location filter
            
        Returns:
            Reconciliation report data
        """
        start_datetime = datetime.combine(report_date, datetime.min.time())
        end_datetime = datetime.combine(report_date, datetime.max.time())
        
        # Build base query
        query = select(Payment).where(
            and_(
                Payment.created_at >= start_datetime,
                Payment.created_at <= end_datetime,
            )
        )
        
        if restaurant_id:
            query = query.join(Order).where(Order.restaurant_id == restaurant_id)
        if location_id:
            query = query.join(Order).where(Order.location_id == location_id)
            
        result = await db.execute(query.options(selectinload(Payment.order)))
        payments = result.scalars().all()
        
        # Calculate totals by gateway
        gateway_totals = {}
        for gateway in PaymentGateway:
            gateway_payments = [p for p in payments if p.gateway == gateway]
            gateway_totals[gateway.value] = {
                "count": len(gateway_payments),
                "gross_amount": sum(p.amount for p in gateway_payments),
                "fees": sum(p.gateway_fee or Decimal(0) for p in gateway_payments),
                "net_amount": sum(p.net_amount or p.amount for p in gateway_payments),
                "successful": len([p for p in gateway_payments if p.status == PaymentStatus.COMPLETED]),
                "failed": len([p for p in gateway_payments if p.status == PaymentStatus.FAILED]),
                "pending": len([p for p in gateway_payments if p.status == PaymentStatus.PROCESSING]),
            }
        
        # Calculate refunds
        refund_query = select(Refund).where(
            and_(
                Refund.created_at >= start_datetime,
                Refund.created_at <= end_datetime,
            )
        )
        
        refund_result = await db.execute(refund_query)
        refunds = refund_result.scalars().all()
        
        refund_totals = {
            "count": len(refunds),
            "total_amount": sum(r.amount for r in refunds),
            "completed": len([r for r in refunds if r.status == RefundStatus.COMPLETED]),
            "pending": len([r for r in refunds if r.status == RefundStatus.PROCESSING]),
            "failed": len([r for r in refunds if r.status == RefundStatus.FAILED]),
        }
        
        # Calculate overall totals
        total_gross = sum(p.amount for p in payments)
        total_fees = sum(p.gateway_fee or Decimal(0) for p in payments)
        total_net = sum(p.net_amount or p.amount for p in payments)
        
        # Calculate discrepancies
        discrepancies = await self._find_discrepancies(db, payments)
        
        return {
            "report_date": report_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_transactions": len(payments),
                "total_gross_amount": float(total_gross),
                "total_fees": float(total_fees),
                "total_net_amount": float(total_net),
                "total_refunds": float(refund_totals["total_amount"]),
                "net_after_refunds": float(total_net - refund_totals["total_amount"]),
            },
            "by_gateway": gateway_totals,
            "refunds": refund_totals,
            "discrepancies": discrepancies,
            "hourly_breakdown": await self._get_hourly_breakdown(payments),
            "payment_methods": await self._get_payment_method_breakdown(payments),
        }
    
    async def _find_discrepancies(
        self, db: AsyncSession, payments: List[Payment]
    ) -> List[Dict[str, Any]]:
        """
        Find payment discrepancies
        
        Args:
            db: Database session
            payments: List of payments to check
            
        Returns:
            List of discrepancies
        """
        discrepancies = []
        
        for payment in payments:
            # Check order total vs payment amount
            if payment.order:
                expected_amount = payment.order.total_amount
                if abs(payment.amount - expected_amount) > Decimal("0.01"):
                    discrepancies.append({
                        "type": "amount_mismatch",
                        "payment_id": payment.id,
                        "order_id": payment.order_id,
                        "expected": float(expected_amount),
                        "actual": float(payment.amount),
                        "difference": float(payment.amount - expected_amount),
                    })
            
            # Check for duplicate payments
            duplicate_query = select(Payment).where(
                and_(
                    Payment.order_id == payment.order_id,
                    Payment.id != payment.id,
                    Payment.status == PaymentStatus.COMPLETED,
                    Payment.amount == payment.amount,
                )
            )
            duplicate_result = await db.execute(duplicate_query)
            duplicates = duplicate_result.scalars().all()
            
            if duplicates:
                discrepancies.append({
                    "type": "potential_duplicate",
                    "payment_id": payment.id,
                    "order_id": payment.order_id,
                    "duplicate_payment_ids": [d.id for d in duplicates],
                    "amount": float(payment.amount),
                })
        
        return discrepancies
    
    async def _get_hourly_breakdown(
        self, payments: List[Payment]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get hourly breakdown of payments
        
        Args:
            payments: List of payments
            
        Returns:
            Hourly breakdown data
        """
        hourly_data = {}
        
        for hour in range(24):
            hour_payments = [
                p for p in payments 
                if p.created_at.hour == hour
            ]
            
            if hour_payments:
                hourly_data[hour] = {
                    "count": len(hour_payments),
                    "total_amount": float(sum(p.amount for p in hour_payments)),
                    "average_amount": float(
                        sum(p.amount for p in hour_payments) / len(hour_payments)
                    ),
                }
        
        return hourly_data
    
    async def _get_payment_method_breakdown(
        self, payments: List[Payment]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get payment method breakdown
        
        Args:
            payments: List of payments
            
        Returns:
            Payment method breakdown
        """
        method_data = {}
        
        for payment in payments:
            method = payment.payment_method or "unknown"
            
            if method not in method_data:
                method_data[method] = {
                    "count": 0,
                    "total_amount": Decimal(0),
                    "successful": 0,
                    "failed": 0,
                }
            
            method_data[method]["count"] += 1
            method_data[method]["total_amount"] += payment.amount
            
            if payment.status == PaymentStatus.COMPLETED:
                method_data[method]["successful"] += 1
            elif payment.status == PaymentStatus.FAILED:
                method_data[method]["failed"] += 1
        
        # Convert Decimal to float for JSON serialization
        for method in method_data:
            method_data[method]["total_amount"] = float(
                method_data[method]["total_amount"]
            )
            method_data[method]["average_amount"] = (
                method_data[method]["total_amount"] / method_data[method]["count"]
            )
        
        return method_data
    
    async def generate_gateway_settlement_report(
        self,
        db: AsyncSession,
        gateway: PaymentGateway,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate settlement report for a specific gateway
        
        Args:
            db: Database session
            gateway: Payment gateway
            start_date: Start date
            end_date: End date
            
        Returns:
            Settlement report data
        """
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get payments
        payment_query = select(Payment).where(
            and_(
                Payment.gateway == gateway,
                Payment.created_at >= start_datetime,
                Payment.created_at <= end_datetime,
                Payment.status == PaymentStatus.COMPLETED,
            )
        )
        
        payment_result = await db.execute(payment_query)
        payments = payment_result.scalars().all()
        
        # Get refunds
        refund_query = select(Refund).where(
            and_(
                Refund.created_at >= start_datetime,
                Refund.created_at <= end_datetime,
            )
        ).join(Payment).where(Payment.gateway == gateway)
        
        refund_result = await db.execute(refund_query)
        refunds = refund_result.scalars().all()
        
        # Calculate daily totals
        daily_totals = {}
        current_date = start_date
        
        while current_date <= end_date:
            day_payments = [
                p for p in payments 
                if p.created_at.date() == current_date
            ]
            day_refunds = [
                r for r in refunds 
                if r.created_at.date() == current_date
            ]
            
            daily_totals[current_date.isoformat()] = {
                "payments": {
                    "count": len(day_payments),
                    "gross_amount": float(sum(p.amount for p in day_payments)),
                    "fees": float(sum(p.gateway_fee or Decimal(0) for p in day_payments)),
                    "net_amount": float(sum(p.net_amount or p.amount for p in day_payments)),
                },
                "refunds": {
                    "count": len(day_refunds),
                    "amount": float(sum(r.amount for r in day_refunds)),
                },
                "net_settlement": float(
                    sum(p.net_amount or p.amount for p in day_payments) -
                    sum(r.amount for r in day_refunds)
                ),
            }
            
            current_date += timedelta(days=1)
        
        # Calculate totals
        total_payments = sum(p.amount for p in payments)
        total_fees = sum(p.gateway_fee or Decimal(0) for p in payments)
        total_net = sum(p.net_amount or p.amount for p in payments)
        total_refunds = sum(r.amount for r in refunds)
        
        return {
            "gateway": gateway.value,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_payments": len(payments),
                "total_refunds": len(refunds),
                "gross_amount": float(total_payments),
                "total_fees": float(total_fees),
                "net_amount": float(total_net),
                "refund_amount": float(total_refunds),
                "net_settlement": float(total_net - total_refunds),
                "average_fee_rate": float(
                    (total_fees / total_payments * 100) if total_payments else 0
                ),
            },
            "daily_breakdown": daily_totals,
            "payment_ids": [p.id for p in payments],
            "refund_ids": [r.id for r in refunds],
        }
    
    async def generate_financial_summary(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        restaurant_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive financial summary
        
        Args:
            db: Database session
            start_date: Start date
            end_date: End date
            restaurant_id: Optional restaurant filter
            
        Returns:
            Financial summary data
        """
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Build query
        query = select(
            func.count(Payment.id).label("total_transactions"),
            func.sum(Payment.amount).label("gross_revenue"),
            func.sum(Payment.gateway_fee).label("total_fees"),
            func.sum(
                case(
                    (Payment.net_amount.is_not(None), Payment.net_amount),
                    else_=Payment.amount
                )
            ).label("net_revenue"),
            func.avg(Payment.amount).label("average_transaction"),
            Payment.gateway,
        ).where(
            and_(
                Payment.created_at >= start_datetime,
                Payment.created_at <= end_datetime,
                Payment.status == PaymentStatus.COMPLETED,
            )
        ).group_by(Payment.gateway)
        
        if restaurant_id:
            query = query.join(Order).where(Order.restaurant_id == restaurant_id)
        
        result = await db.execute(query)
        gateway_stats = result.all()
        
        # Get refund statistics
        refund_query = select(
            func.count(Refund.id).label("total_refunds"),
            func.sum(Refund.amount).label("refund_amount"),
        ).where(
            and_(
                Refund.created_at >= start_datetime,
                Refund.created_at <= end_datetime,
                Refund.status == RefundStatus.COMPLETED,
            )
        )
        
        refund_result = await db.execute(refund_query)
        refund_stats = refund_result.first()
        
        # Format results
        gateway_breakdown = []
        total_transactions = 0
        total_gross = Decimal(0)
        total_fees = Decimal(0)
        total_net = Decimal(0)
        
        for stat in gateway_stats:
            gateway_breakdown.append({
                "gateway": stat.gateway.value,
                "transactions": stat.total_transactions,
                "gross_revenue": float(stat.gross_revenue or 0),
                "fees": float(stat.total_fees or 0),
                "net_revenue": float(stat.net_revenue or 0),
                "average_transaction": float(stat.average_transaction or 0),
            })
            
            total_transactions += stat.total_transactions
            total_gross += stat.gross_revenue or Decimal(0)
            total_fees += stat.total_fees or Decimal(0)
            total_net += stat.net_revenue or Decimal(0)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days + 1,
            },
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_transactions": total_transactions,
                "gross_revenue": float(total_gross),
                "total_fees": float(total_fees),
                "net_revenue": float(total_net),
                "total_refunds": refund_stats.total_refunds if refund_stats else 0,
                "refund_amount": float(refund_stats.refund_amount or 0) if refund_stats else 0,
                "final_revenue": float(total_net - (refund_stats.refund_amount or 0)) if refund_stats else float(total_net),
                "average_transaction": float(total_gross / total_transactions) if total_transactions else 0,
                "average_daily_revenue": float(total_net / ((end_date - start_date).days + 1)),
            },
            "by_gateway": gateway_breakdown,
            "trends": await self._calculate_trends(db, start_date, end_date, restaurant_id),
        }
    
    async def _calculate_trends(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        restaurant_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate payment trends
        
        Args:
            db: Database session
            start_date: Start date
            end_date: End date
            restaurant_id: Optional restaurant filter
            
        Returns:
            Trend data
        """
        # Calculate previous period for comparison
        period_days = (end_date - start_date).days + 1
        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date - timedelta(days=1)
        
        # Current period query
        current_query = select(
            func.count(Payment.id),
            func.sum(Payment.amount),
        ).where(
            and_(
                Payment.created_at >= datetime.combine(start_date, datetime.min.time()),
                Payment.created_at <= datetime.combine(end_date, datetime.max.time()),
                Payment.status == PaymentStatus.COMPLETED,
            )
        )
        
        # Previous period query
        prev_query = select(
            func.count(Payment.id),
            func.sum(Payment.amount),
        ).where(
            and_(
                Payment.created_at >= datetime.combine(prev_start, datetime.min.time()),
                Payment.created_at <= datetime.combine(prev_end, datetime.max.time()),
                Payment.status == PaymentStatus.COMPLETED,
            )
        )
        
        if restaurant_id:
            current_query = current_query.join(Order).where(Order.restaurant_id == restaurant_id)
            prev_query = prev_query.join(Order).where(Order.restaurant_id == restaurant_id)
        
        current_result = await db.execute(current_query)
        current_data = current_result.first()
        
        prev_result = await db.execute(prev_query)
        prev_data = prev_result.first()
        
        # Calculate growth rates
        transaction_growth = 0
        revenue_growth = 0
        
        if prev_data and prev_data[0]:
            transaction_growth = ((current_data[0] - prev_data[0]) / prev_data[0]) * 100
        
        if prev_data and prev_data[1]:
            revenue_growth = ((current_data[1] - prev_data[1]) / prev_data[1]) * 100
        
        return {
            "transaction_growth": float(transaction_growth),
            "revenue_growth": float(revenue_growth),
            "current_period": {
                "transactions": current_data[0] if current_data else 0,
                "revenue": float(current_data[1] or 0) if current_data else 0,
            },
            "previous_period": {
                "transactions": prev_data[0] if prev_data else 0,
                "revenue": float(prev_data[1] or 0) if prev_data else 0,
            },
        }


# Create singleton instance
payment_reconciliation_service = PaymentReconciliationService()