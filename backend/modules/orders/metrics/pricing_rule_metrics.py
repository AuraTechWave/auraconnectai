# backend/modules/orders/metrics/pricing_rule_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from functools import wraps
from typing import Dict, Any

# Counters
pricing_rules_evaluated = Counter(
    "pricing_rules_evaluated_total",
    "Total number of pricing rules evaluated",
    ["restaurant_id", "rule_type"],
)

pricing_rules_applied = Counter(
    "pricing_rules_applied_total",
    "Total number of pricing rules successfully applied",
    ["restaurant_id", "rule_type", "rule_id"],
)

pricing_rules_skipped = Counter(
    "pricing_rules_skipped_total",
    "Total number of pricing rules skipped",
    ["restaurant_id", "skip_reason"],
)

pricing_conflicts_resolved = Counter(
    "pricing_conflicts_resolved_total",
    "Total number of pricing rule conflicts resolved",
    ["restaurant_id", "resolution_method"],
)

pricing_rule_errors = Counter(
    "pricing_rule_errors_total",
    "Total number of errors in pricing rule evaluation",
    ["restaurant_id", "error_type"],
)

promo_codes_used = Counter(
    "promo_codes_used_total",
    "Total number of promo codes used",
    ["restaurant_id", "promo_code"],
)

# Histograms
discount_amount_histogram = Histogram(
    "pricing_discount_amount_dollars",
    "Distribution of discount amounts in dollars",
    ["restaurant_id", "rule_type"],
    buckets=(0.5, 1, 2, 5, 10, 20, 50, 100),
)

rule_evaluation_duration = Histogram(
    "pricing_rule_evaluation_duration_seconds",
    "Time taken to evaluate pricing rules",
    ["restaurant_id"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

rules_per_order_histogram = Histogram(
    "pricing_rules_per_order",
    "Number of rules applied per order",
    ["restaurant_id"],
    buckets=(0, 1, 2, 3, 5, 10),
)

# Gauges
active_pricing_rules = Gauge(
    "active_pricing_rules_total",
    "Current number of active pricing rules",
    ["restaurant_id", "rule_type"],
)

total_discount_today = Gauge(
    "pricing_total_discount_today_dollars",
    "Total discount amount given today in dollars",
    ["restaurant_id"],
)

# Summary
rule_stacking_summary = Summary(
    "pricing_rule_stacking", "Summary of rule stacking occurrences", ["restaurant_id"]
)


class PricingRuleMetricsCollector:
    """Collector for pricing rule metrics"""

    def __init__(self):
        self.batch_metrics: Dict[str, Any] = {}

    def record_rule_evaluated(self, restaurant_id: int, rule_type: str):
        """Record that a rule was evaluated"""
        pricing_rules_evaluated.labels(
            restaurant_id=str(restaurant_id), rule_type=rule_type
        ).inc()

    def record_rule_applied(
        self, restaurant_id: int, rule_type: str, rule_id: str, discount_amount: float
    ):
        """Record that a rule was successfully applied"""
        pricing_rules_applied.labels(
            restaurant_id=str(restaurant_id), rule_type=rule_type, rule_id=rule_id
        ).inc()

        discount_amount_histogram.labels(
            restaurant_id=str(restaurant_id), rule_type=rule_type
        ).observe(discount_amount)

    def record_rule_skipped(self, restaurant_id: int, skip_reason: str):
        """Record that a rule was skipped"""
        pricing_rules_skipped.labels(
            restaurant_id=str(restaurant_id), skip_reason=skip_reason
        ).inc()

    def record_conflict_resolved(self, restaurant_id: int, resolution_method: str):
        """Record that a conflict was resolved"""
        pricing_conflicts_resolved.labels(
            restaurant_id=str(restaurant_id), resolution_method=resolution_method
        ).inc()

    def record_evaluation_time(self, restaurant_id: int, duration: float):
        """Record rule evaluation duration"""
        rule_evaluation_duration.labels(restaurant_id=str(restaurant_id)).observe(
            duration
        )

    def record_rules_per_order(self, restaurant_id: int, rule_count: int):
        """Record number of rules applied to an order"""
        rules_per_order_histogram.labels(restaurant_id=str(restaurant_id)).observe(
            rule_count
        )

    def record_error(self, restaurant_id: int, error_type: str):
        """Record an error in rule evaluation"""
        pricing_rule_errors.labels(
            restaurant_id=str(restaurant_id), error_type=error_type
        ).inc()

    def record_promo_code_used(self, restaurant_id: int, promo_code: str):
        """Record promo code usage"""
        promo_codes_used.labels(
            restaurant_id=str(restaurant_id), promo_code=promo_code
        ).inc()

    def record_stacking(self, restaurant_id: int, stack_count: int):
        """Record rule stacking"""
        rule_stacking_summary.labels(restaurant_id=str(restaurant_id)).observe(
            stack_count
        )

    def update_active_rules_gauge(
        self, restaurant_id: int, rule_counts: Dict[str, int]
    ):
        """Update the active rules gauge"""
        for rule_type, count in rule_counts.items():
            active_pricing_rules.labels(
                restaurant_id=str(restaurant_id), rule_type=rule_type
            ).set(count)

    def update_daily_discount_gauge(self, restaurant_id: int, total_discount: float):
        """Update today's total discount gauge"""
        total_discount_today.labels(restaurant_id=str(restaurant_id)).set(
            total_discount
        )


# Decorator for timing rule evaluation
def track_rule_evaluation(restaurant_id: int):
    """Decorator to track rule evaluation time"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                collector = PricingRuleMetricsCollector()
                collector.record_evaluation_time(restaurant_id, duration)

                return result
            except Exception as e:
                collector = PricingRuleMetricsCollector()
                collector.record_error(restaurant_id, type(e).__name__)
                raise

        return wrapper

    return decorator


# Create singleton collector
pricing_metrics_collector = PricingRuleMetricsCollector()


# Export all metrics for registration
__all__ = [
    "pricing_rules_evaluated",
    "pricing_rules_applied",
    "pricing_rules_skipped",
    "pricing_conflicts_resolved",
    "pricing_rule_errors",
    "promo_codes_used",
    "discount_amount_histogram",
    "rule_evaluation_duration",
    "rules_per_order_histogram",
    "active_pricing_rules",
    "total_discount_today",
    "rule_stacking_summary",
    "pricing_metrics_collector",
    "track_rule_evaluation",
]
