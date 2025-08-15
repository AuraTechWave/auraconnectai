# backend/modules/payments/services/payment_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional
import time
from functools import wraps
import asyncio
from datetime import datetime

from ..models.payment_models import PaymentGateway, PaymentStatus, RefundStatus


# Payment counters
payment_created_total = Counter(
    "payment_created_total", "Total number of payments created", ["gateway", "status"]
)

payment_completed_total = Counter(
    "payment_completed_total",
    "Total number of payments completed successfully",
    ["gateway", "payment_method"],
)

payment_failed_total = Counter(
    "payment_failed_total", "Total number of failed payments", ["gateway", "error_code"]
)

payment_action_required_total = Counter(
    "payment_action_required_total",
    "Total number of payments requiring user action",
    ["gateway", "action_type"],
)

# Refund counters
refund_created_total = Counter(
    "refund_created_total",
    "Total number of refunds created",
    ["gateway", "type"],  # type: full/partial
)

refund_completed_total = Counter(
    "refund_completed_total", "Total number of refunds completed", ["gateway"]
)

refund_failed_total = Counter(
    "refund_failed_total", "Total number of failed refunds", ["gateway", "error_code"]
)

# Webhook counters
webhook_received_total = Counter(
    "webhook_received_total",
    "Total number of webhooks received",
    ["gateway", "event_type"],
)

webhook_processed_total = Counter(
    "webhook_processed_total",
    "Total number of webhooks processed successfully",
    ["gateway", "event_type"],
)

webhook_failed_total = Counter(
    "webhook_failed_total",
    "Total number of failed webhook processing",
    ["gateway", "event_type", "error"],
)

# Amount metrics
payment_amount_total = Counter(
    "payment_amount_total", "Total payment amount in cents", ["gateway", "currency"]
)

refund_amount_total = Counter(
    "refund_amount_total", "Total refund amount in cents", ["gateway", "currency"]
)

fee_amount_total = Counter(
    "fee_amount_total", "Total processing fees in cents", ["gateway", "currency"]
)

# Latency histograms
gateway_request_duration = Histogram(
    "gateway_request_duration_seconds",
    "Gateway API request duration",
    ["gateway", "operation"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

payment_processing_duration = Histogram(
    "payment_processing_duration_seconds",
    "Total payment processing duration",
    ["gateway"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

webhook_processing_duration = Histogram(
    "webhook_processing_duration_seconds",
    "Webhook processing duration",
    ["gateway", "event_type"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Gauges
active_payment_actions = Gauge(
    "active_payment_actions", "Number of payments requiring action", ["gateway"]
)

payment_gateway_available = Gauge(
    "payment_gateway_available",
    "Payment gateway availability (1=available, 0=unavailable)",
    ["gateway"],
)

# Info metrics
payment_gateway_info = Info(
    "payment_gateway_info", "Payment gateway configuration info"
)


class PaymentMetrics:
    """Helper class for recording payment metrics"""

    @staticmethod
    def record_payment_created(gateway: PaymentGateway, status: PaymentStatus):
        """Record payment creation"""
        payment_created_total.labels(gateway=gateway.value, status=status.value).inc()

    @staticmethod
    def record_payment_completed(
        gateway: PaymentGateway,
        payment_method: str,
        amount: float,
        currency: str,
        fee: Optional[float] = None,
    ):
        """Record successful payment completion"""
        payment_completed_total.labels(
            gateway=gateway.value, payment_method=payment_method
        ).inc()

        # Record amount in cents
        amount_cents = int(amount * 100)
        payment_amount_total.labels(gateway=gateway.value, currency=currency).inc(
            amount_cents
        )

        # Record fee if available
        if fee:
            fee_cents = int(fee * 100)
            fee_amount_total.labels(gateway=gateway.value, currency=currency).inc(
                fee_cents
            )

    @staticmethod
    def record_payment_failed(
        gateway: PaymentGateway, error_code: Optional[str] = None
    ):
        """Record payment failure"""
        payment_failed_total.labels(
            gateway=gateway.value, error_code=error_code or "unknown"
        ).inc()

    @staticmethod
    def record_payment_action_required(gateway: PaymentGateway, action_type: str):
        """Record payment requiring action"""
        payment_action_required_total.labels(
            gateway=gateway.value, action_type=action_type
        ).inc()

    @staticmethod
    def record_refund_created(
        gateway: PaymentGateway, amount: float, original_amount: float, currency: str
    ):
        """Record refund creation"""
        refund_type = "full" if amount >= original_amount else "partial"

        refund_created_total.labels(gateway=gateway.value, type=refund_type).inc()

        # Record amount in cents
        amount_cents = int(amount * 100)
        refund_amount_total.labels(gateway=gateway.value, currency=currency).inc(
            amount_cents
        )

    @staticmethod
    def record_refund_completed(gateway: PaymentGateway):
        """Record successful refund"""
        refund_completed_total.labels(gateway=gateway.value).inc()

    @staticmethod
    def record_refund_failed(gateway: PaymentGateway, error_code: Optional[str] = None):
        """Record refund failure"""
        refund_failed_total.labels(
            gateway=gateway.value, error_code=error_code or "unknown"
        ).inc()

    @staticmethod
    def record_webhook_received(gateway: PaymentGateway, event_type: str):
        """Record webhook receipt"""
        webhook_received_total.labels(
            gateway=gateway.value, event_type=event_type
        ).inc()

    @staticmethod
    def record_webhook_processed(
        gateway: PaymentGateway, event_type: str, duration: float
    ):
        """Record successful webhook processing"""
        webhook_processed_total.labels(
            gateway=gateway.value, event_type=event_type
        ).inc()

        webhook_processing_duration.labels(
            gateway=gateway.value, event_type=event_type
        ).observe(duration)

    @staticmethod
    def record_webhook_failed(gateway: PaymentGateway, event_type: str, error: str):
        """Record webhook processing failure"""
        webhook_failed_total.labels(
            gateway=gateway.value,
            event_type=event_type,
            error=error[:50],  # Limit error label length
        ).inc()

    @staticmethod
    def update_active_actions(gateway: PaymentGateway, count: int):
        """Update count of active payment actions"""
        active_payment_actions.labels(gateway=gateway.value).set(count)

    @staticmethod
    def update_gateway_availability(gateway: PaymentGateway, available: bool):
        """Update gateway availability status"""
        payment_gateway_available.labels(gateway=gateway.value).set(
            1 if available else 0
        )

    @staticmethod
    def update_gateway_info(info: dict):
        """Update gateway configuration info"""
        payment_gateway_info.info(info)


def track_gateway_request(gateway: str, operation: str):
    """
    Decorator to track gateway API request duration

    Usage:
        @track_gateway_request('stripe', 'create_payment')
        async def create_payment():
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                gateway_request_duration.labels(
                    gateway=gateway, operation=operation
                ).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                gateway_request_duration.labels(
                    gateway=gateway, operation=operation
                ).observe(duration)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_payment_processing(gateway: str):
    """
    Decorator to track total payment processing duration

    Usage:
        @track_payment_processing('stripe')
        async def process_payment():
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                payment_processing_duration.labels(gateway=gateway).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                payment_processing_duration.labels(gateway=gateway).observe(duration)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Background task to update gateway metrics
async def update_payment_metrics(ctx: dict) -> dict:
    """
    Periodic task to update payment metrics

    This runs every minute to update gauges
    """
    from core.database import get_db
    from sqlalchemy import select, func, and_
    from ..models.payment_models import Payment, PaymentGatewayConfig

    try:
        async for db in get_db():
            try:
                # Count active payment actions by gateway
                result = await db.execute(
                    select(Payment.gateway, func.count(Payment.id).label("count"))
                    .where(Payment.status == PaymentStatus.REQUIRES_ACTION)
                    .group_by(Payment.gateway)
                )

                for row in result:
                    PaymentMetrics.update_active_actions(row.gateway, row.count)

                # Check gateway availability
                result = await db.execute(
                    select(PaymentGatewayConfig).where(
                        PaymentGatewayConfig.is_active == True
                    )
                )

                active_gateways = {config.gateway for config in result.scalars()}

                for gateway in PaymentGateway:
                    available = gateway in active_gateways
                    PaymentMetrics.update_gateway_availability(gateway, available)

            finally:
                await db.close()

        return {"status": "success", "updated_at": datetime.utcnow().isoformat()}

    except Exception as e:
        return {"status": "error", "error": str(e)}
