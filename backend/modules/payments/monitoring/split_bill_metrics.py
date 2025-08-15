# backend/modules/payments/monitoring/split_bill_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
from typing import Optional, Dict, Any

# Split Bill Metrics

# Counters
split_bill_created_total = Counter(
    "split_bill_created_total",
    "Total number of split bills created",
    ["split_method", "status"],
)

split_bill_participant_status_total = Counter(
    "split_bill_participant_status_total",
    "Total participant status changes",
    ["status", "split_method"],
)

split_bill_payment_total = Counter(
    "split_bill_payment_total", "Total split bill payments", ["status", "split_method"]
)

split_bill_cancelled_total = Counter(
    "split_bill_cancelled_total", "Total split bills cancelled", ["split_method"]
)

split_bill_expired_total = Counter(
    "split_bill_expired_total", "Total split bills expired", ["split_method"]
)

# Histograms
split_bill_payment_duration_seconds = Histogram(
    "split_bill_payment_duration_seconds",
    "Time from split creation to payment completion",
    ["split_method"],
    buckets=(
        300,
        600,
        1800,
        3600,
        7200,
        14400,
        28800,
        86400,
    ),  # 5m, 10m, 30m, 1h, 2h, 4h, 8h, 24h
)

split_bill_amount_histogram = Histogram(
    "split_bill_amount_histogram",
    "Distribution of split bill amounts",
    ["split_method", "currency"],
    buckets=(10, 25, 50, 100, 200, 500, 1000, 2000, 5000),
)

split_bill_participant_count_histogram = Histogram(
    "split_bill_participant_count_histogram",
    "Distribution of participant counts",
    ["split_method"],
    buckets=(2, 3, 4, 5, 6, 8, 10, 15, 20),
)

tip_distribution_processing_seconds = Histogram(
    "tip_distribution_processing_seconds",
    "Time to process tip distributions",
    ["distribution_method"],
)

# Gauges
split_bill_active_count = Gauge(
    "split_bill_active_count", "Current number of active split bills", ["split_method"]
)

split_bill_pending_payments = Gauge(
    "split_bill_pending_payments", "Current number of pending participant payments"
)

split_bill_completion_rate = Gauge(
    "split_bill_completion_rate",
    "Rate of split bill completion (last hour)",
    ["split_method"],
)

tip_distribution_pending_count = Gauge(
    "tip_distribution_pending_count", "Current number of pending tip distributions"
)


class SplitBillMetrics:
    """Helper class for recording split bill metrics"""

    @staticmethod
    def record_split_created(split_method: str, status: str = "pending"):
        """Record a new split bill creation"""
        split_bill_created_total.labels(split_method=split_method, status=status).inc()

    @staticmethod
    def record_participant_status_change(status: str, split_method: str):
        """Record participant status change"""
        split_bill_participant_status_total.labels(
            status=status, split_method=split_method
        ).inc()

    @staticmethod
    def record_split_payment(status: str, split_method: str):
        """Record a split bill payment attempt"""
        split_bill_payment_total.labels(status=status, split_method=split_method).inc()

    @staticmethod
    def record_split_cancelled(split_method: str):
        """Record split bill cancellation"""
        split_bill_cancelled_total.labels(split_method=split_method).inc()

    @staticmethod
    def record_split_expired(split_method: str):
        """Record split bill expiration"""
        split_bill_expired_total.labels(split_method=split_method).inc()

    @staticmethod
    def record_payment_duration(split_method: str, duration_seconds: float):
        """Record time from split creation to payment"""
        split_bill_payment_duration_seconds.labels(split_method=split_method).observe(
            duration_seconds
        )

    @staticmethod
    def record_split_amount(split_method: str, amount: float, currency: str = "USD"):
        """Record split bill amount"""
        split_bill_amount_histogram.labels(
            split_method=split_method, currency=currency
        ).observe(amount)

    @staticmethod
    def record_participant_count(split_method: str, count: int):
        """Record number of participants"""
        split_bill_participant_count_histogram.labels(
            split_method=split_method
        ).observe(count)

    @staticmethod
    def record_tip_distribution_processing(
        distribution_method: str, processing_time: float
    ):
        """Record tip distribution processing time"""
        tip_distribution_processing_seconds.labels(
            distribution_method=distribution_method
        ).observe(processing_time)

    @staticmethod
    def set_active_splits(split_method: str, count: int):
        """Set current number of active splits"""
        split_bill_active_count.labels(split_method=split_method).set(count)

    @staticmethod
    def set_pending_payments(count: int):
        """Set current number of pending payments"""
        split_bill_pending_payments.set(count)

    @staticmethod
    def set_completion_rate(split_method: str, rate: float):
        """Set split bill completion rate"""
        split_bill_completion_rate.labels(split_method=split_method).set(rate)

    @staticmethod
    def set_pending_tip_distributions(count: int):
        """Set current number of pending tip distributions"""
        tip_distribution_pending_count.set(count)


# Decorators for automatic metric tracking


def track_split_creation(func):
    """Decorator to track split bill creation metrics"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)

            # Extract split details from result
            if hasattr(result, "split_method"):
                SplitBillMetrics.record_split_created(
                    split_method=result.split_method.value, status=result.status.value
                )

                if hasattr(result, "total_amount"):
                    SplitBillMetrics.record_split_amount(
                        split_method=result.split_method.value,
                        amount=float(result.total_amount),
                    )

                if hasattr(result, "participants"):
                    SplitBillMetrics.record_participant_count(
                        split_method=result.split_method.value,
                        count=len(result.participants),
                    )

            return result

        except Exception as e:
            # Record failed creation
            split_bill_created_total.labels(
                split_method="unknown", status="failed"
            ).inc()
            raise

    return wrapper


def track_payment_processing(func):
    """Decorator to track split bill payment processing"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)

            # Extract payment details
            split_method = kwargs.get("split_method", "unknown")

            SplitBillMetrics.record_split_payment(
                status="completed", split_method=split_method
            )

            # Record payment duration if split creation time is available
            if "created_at" in kwargs:
                duration = time.time() - kwargs["created_at"].timestamp()
                SplitBillMetrics.record_payment_duration(
                    split_method=split_method, duration_seconds=duration
                )

            return result

        except Exception as e:
            SplitBillMetrics.record_split_payment(
                status="failed", split_method=kwargs.get("split_method", "unknown")
            )
            raise

    return wrapper


def track_tip_distribution(func):
    """Decorator to track tip distribution processing"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)

            # Record processing time
            processing_time = time.time() - start_time
            distribution_method = kwargs.get("distribution_method", "unknown")

            SplitBillMetrics.record_tip_distribution_processing(
                distribution_method=distribution_method, processing_time=processing_time
            )

            return result

        except Exception as e:
            raise

    return wrapper


# Background task to update gauge metrics
async def update_split_bill_gauges(db):
    """Update gauge metrics for split bills (run periodically)"""
    from sqlalchemy import select, func, and_
    from datetime import datetime, timedelta
    from ..models.split_bill_models import (
        BillSplit,
        SplitParticipant,
        SplitStatus,
        ParticipantStatus,
        TipDistribution,
    )

    try:
        # Count active splits by method
        active_splits = await db.execute(
            select(BillSplit.split_method, func.count(BillSplit.id))
            .where(BillSplit.status == SplitStatus.ACTIVE)
            .group_by(BillSplit.split_method)
        )

        for method, count in active_splits:
            SplitBillMetrics.set_active_splits(method.value, count)

        # Count pending payments
        pending_payments = await db.execute(
            select(func.count(SplitParticipant.id)).where(
                and_(
                    SplitParticipant.status.in_(
                        [ParticipantStatus.PENDING, ParticipantStatus.ACCEPTED]
                    ),
                    SplitParticipant.paid_amount < SplitParticipant.total_amount,
                )
            )
        )

        SplitBillMetrics.set_pending_payments(pending_payments.scalar() or 0)

        # Calculate completion rate (last hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        completion_stats = await db.execute(
            select(
                BillSplit.split_method,
                func.count(BillSplit.id).filter(
                    BillSplit.status == SplitStatus.COMPLETED
                ),
                func.count(BillSplit.id),
            )
            .where(BillSplit.created_at >= one_hour_ago)
            .group_by(BillSplit.split_method)
        )

        for method, completed, total in completion_stats:
            rate = (completed / total) if total > 0 else 0
            SplitBillMetrics.set_completion_rate(method.value, rate)

        # Count pending tip distributions
        pending_tips = await db.execute(
            select(func.count(TipDistribution.id)).where(
                TipDistribution.is_distributed == False
            )
        )

        SplitBillMetrics.set_pending_tip_distributions(pending_tips.scalar() or 0)

    except Exception as e:
        print(f"Error updating split bill gauges: {e}")
