# backend/modules/analytics/utils/performance_monitor.py

import time
import logging
from typing import Dict, Any, Callable
from functools import wraps
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log performance metrics for AI insights generation"""

    @staticmethod
    def monitor_query(query_name: str):
        """Decorator to monitor database query performance"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                if execution_time > 1.0:  # Log slow queries (>1 second)
                    logger.warning(
                        f"Slow query detected: {query_name} took {execution_time:.2f} seconds"
                    )
                else:
                    logger.debug(
                        f"Query {query_name} completed in {execution_time:.3f} seconds"
                    )

                return result

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                if execution_time > 1.0:  # Log slow queries (>1 second)
                    logger.warning(
                        f"Slow query detected: {query_name} took {execution_time:.2f} seconds"
                    )
                else:
                    logger.debug(
                        f"Query {query_name} completed in {execution_time:.3f} seconds"
                    )

                return result

            return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper

        return decorator

    @staticmethod
    def log_insight_metrics(
        insight_type: str,
        date_range_days: int,
        record_count: int,
        execution_time: float,
        cache_hit: bool = False,
    ):
        """Log detailed metrics for insights generation"""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "insight_type": insight_type,
            "date_range_days": date_range_days,
            "record_count": record_count,
            "execution_time_seconds": execution_time,
            "cache_hit": cache_hit,
            "records_per_second": (
                record_count / execution_time if execution_time > 0 else 0
            ),
        }

        # Log as structured data for monitoring systems
        logger.info(f"AI_INSIGHTS_METRICS: {metrics}")

        # Alert on performance issues
        if execution_time > 5.0 and not cache_hit:
            logger.warning(
                f"Performance issue: {insight_type} took {execution_time:.2f}s for {record_count} records"
            )

    @staticmethod
    def get_query_optimization_hints(
        query_type: str, execution_time: float, record_count: int
    ) -> Dict[str, Any]:
        """Provide optimization hints based on query performance"""
        hints = {
            "query_type": query_type,
            "execution_time": execution_time,
            "record_count": record_count,
            "recommendations": [],
        }

        # Check if query is slow
        if execution_time > 2.0:
            if record_count > 10000:
                hints["recommendations"].append(
                    "Consider using materialized views for large datasets"
                )
                hints["recommendations"].append(
                    "Implement pagination or date-based partitioning"
                )

            if "peak_time" in query_type:
                hints["recommendations"].append(
                    "Ensure index exists on (order_date, status)"
                )
                hints["recommendations"].append("Consider pre-aggregating hourly data")

            if "product_trend" in query_type:
                hints["recommendations"].append(
                    "Ensure composite index on (product_id, order_date)"
                )

            if "customer_pattern" in query_type:
                hints["recommendations"].append(
                    "Ensure index on (customer_id, order_date)"
                )
                hints["recommendations"].append("Consider caching customer segments")

        return hints


# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "peak_time_analysis": {
        "warning_seconds": 2.0,
        "critical_seconds": 5.0,
        "max_records": 100000,
    },
    "product_trend_analysis": {
        "warning_seconds": 3.0,
        "critical_seconds": 8.0,
        "max_records": 50000,
    },
    "customer_pattern_analysis": {
        "warning_seconds": 4.0,
        "critical_seconds": 10.0,
        "max_records": 200000,
    },
    "anomaly_detection": {
        "warning_seconds": 2.0,
        "critical_seconds": 5.0,
        "max_records": 50000,
    },
}


def check_performance_threshold(
    analysis_type: str, execution_time: float, record_count: int
) -> str:
    """Check if performance is within acceptable thresholds"""
    thresholds = PERFORMANCE_THRESHOLDS.get(analysis_type, {})

    if not thresholds:
        return "ok"

    if execution_time > thresholds.get("critical_seconds", 10.0):
        return "critical"
    elif execution_time > thresholds.get("warning_seconds", 5.0):
        return "warning"
    elif record_count > thresholds.get("max_records", 100000):
        return "warning"

    return "ok"


# Export utilities
__all__ = [
    "PerformanceMonitor",
    "PERFORMANCE_THRESHOLDS",
    "check_performance_threshold",
]
