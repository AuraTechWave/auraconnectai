"""
Cache Monitoring and Metrics

Monitor cache performance and provide metrics for optimization.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
from threading import Lock

from .cache_manager import cache_manager
from .redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class CacheMetric:
    """Individual cache metric"""

    timestamp: float
    operation: str  # get, set, delete, miss, hit
    cache_type: str
    key: str
    duration_ms: float
    size_bytes: Optional[int] = None
    success: bool = True


@dataclass
class CacheMetrics:
    """Aggregated cache metrics"""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_sets: int = 0
    cache_deletes: int = 0
    total_errors: int = 0
    avg_response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    hit_rate_percent: float = 0.0

    def calculate_hit_rate(self):
        """Calculate cache hit rate"""
        total = self.cache_hits + self.cache_misses
        if total > 0:
            self.hit_rate_percent = (self.cache_hits / total) * 100


class CacheMonitor:
    """
    Monitor cache performance and collect metrics
    """

    def __init__(self, max_metrics: int = 10000):
        """
        Initialize cache monitor

        Args:
            max_metrics: Maximum number of metrics to keep in memory
        """
        self.metrics: deque = deque(maxlen=max_metrics)
        self.aggregated_metrics: Dict[str, CacheMetrics] = defaultdict(CacheMetrics)
        self.metric_lock = Lock()
        self.start_time = time.time()

        # Performance thresholds
        self.thresholds = {
            "hit_rate_min": 80.0,  # Minimum acceptable hit rate
            "response_time_max_ms": 50.0,  # Maximum acceptable response time
            "error_rate_max": 5.0,  # Maximum error rate percentage
        }

    def record_metric(self, metric: CacheMetric):
        """Record a cache operation metric"""
        with self.metric_lock:
            self.metrics.append(metric)

            # Update aggregated metrics
            agg = self.aggregated_metrics[metric.cache_type]
            agg.total_requests += 1

            if metric.operation == "hit":
                agg.cache_hits += 1
            elif metric.operation == "miss":
                agg.cache_misses += 1
            elif metric.operation == "set":
                agg.cache_sets += 1
            elif metric.operation == "delete":
                agg.cache_deletes += 1

            if not metric.success:
                agg.total_errors += 1

            # Update average response time (running average)
            agg.avg_response_time_ms = (
                agg.avg_response_time_ms * (agg.total_requests - 1) + metric.duration_ms
            ) / agg.total_requests

    def get_metrics(
        self, cache_type: Optional[str] = None, last_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get cache metrics

        Args:
            cache_type: Optional filter by cache type
            last_minutes: Optional filter by time window

        Returns:
            Metrics dictionary
        """
        with self.metric_lock:
            # Filter metrics by time if requested
            if last_minutes:
                cutoff_time = time.time() - (last_minutes * 60)
                filtered_metrics = [
                    m for m in self.metrics if m.timestamp >= cutoff_time
                ]
            else:
                filtered_metrics = list(self.metrics)

            # Filter by cache type if requested
            if cache_type:
                filtered_metrics = [
                    m for m in filtered_metrics if m.cache_type == cache_type
                ]

            # Calculate metrics
            if not filtered_metrics:
                return {"message": "No metrics available"}

            metrics = CacheMetrics()
            response_times = []

            for metric in filtered_metrics:
                metrics.total_requests += 1
                response_times.append(metric.duration_ms)

                if metric.operation == "hit":
                    metrics.cache_hits += 1
                elif metric.operation == "miss":
                    metrics.cache_misses += 1
                elif metric.operation == "set":
                    metrics.cache_sets += 1
                elif metric.operation == "delete":
                    metrics.cache_deletes += 1

                if not metric.success:
                    metrics.total_errors += 1

            # Calculate aggregates
            metrics.calculate_hit_rate()
            if response_times:
                metrics.avg_response_time_ms = sum(response_times) / len(response_times)

            # Get memory usage from Redis
            try:
                client = RedisClient.get_client()
                info = client.info("memory")
                metrics.memory_usage_mb = info.get("used_memory", 0) / (1024 * 1024)
            except Exception as e:
                logger.error(f"Failed to get Redis memory info: {e}")

            return {
                "cache_type": cache_type,
                "time_window": (
                    f"Last {last_minutes} minutes" if last_minutes else "All time"
                ),
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "cache_hits": metrics.cache_hits,
                    "cache_misses": metrics.cache_misses,
                    "cache_sets": metrics.cache_sets,
                    "cache_deletes": metrics.cache_deletes,
                    "total_errors": metrics.total_errors,
                    "hit_rate_percent": round(metrics.hit_rate_percent, 2),
                    "avg_response_time_ms": round(metrics.avg_response_time_ms, 2),
                    "memory_usage_mb": round(metrics.memory_usage_mb, 2),
                    "error_rate_percent": round(
                        (
                            (metrics.total_errors / metrics.total_requests * 100)
                            if metrics.total_requests > 0
                            else 0
                        ),
                        2,
                    ),
                },
            }

    def get_top_keys(
        self, limit: int = 10, cache_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently accessed cache keys

        Args:
            limit: Number of top keys to return
            cache_type: Optional filter by cache type

        Returns:
            List of top keys with access counts
        """
        key_counts = defaultdict(int)
        key_types = {}

        with self.metric_lock:
            for metric in self.metrics:
                if cache_type and metric.cache_type != cache_type:
                    continue

                key_counts[metric.key] += 1
                key_types[metric.key] = metric.cache_type

        # Sort by count and get top keys
        top_keys = sorted(key_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return [
            {
                "key": key,
                "cache_type": key_types[key],
                "access_count": count,
                "percentage": round(
                    (count / sum(key_counts.values()) * 100) if key_counts else 0, 2
                ),
            }
            for key, count in top_keys
        ]

    def get_slow_operations(
        self, threshold_ms: float = 100, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get slowest cache operations

        Args:
            threshold_ms: Minimum duration to consider slow
            limit: Number of operations to return

        Returns:
            List of slow operations
        """
        slow_ops = []

        with self.metric_lock:
            for metric in self.metrics:
                if metric.duration_ms >= threshold_ms:
                    slow_ops.append(
                        {
                            "timestamp": datetime.fromtimestamp(
                                metric.timestamp
                            ).isoformat(),
                            "operation": metric.operation,
                            "cache_type": metric.cache_type,
                            "key": metric.key,
                            "duration_ms": round(metric.duration_ms, 2),
                            "success": metric.success,
                        }
                    )

        # Sort by duration and return top ones
        slow_ops.sort(key=lambda x: x["duration_ms"], reverse=True)
        return slow_ops[:limit]

    def check_health(self) -> Dict[str, Any]:
        """
        Check cache health against thresholds

        Returns:
            Health status and recommendations
        """
        health = {"status": "healthy", "issues": [], "recommendations": []}

        # Get current metrics
        metrics = self.get_metrics(last_minutes=5)["metrics"]

        # Check hit rate
        if metrics["hit_rate_percent"] < self.thresholds["hit_rate_min"]:
            health["status"] = "degraded"
            health["issues"].append(
                f"Low cache hit rate: {metrics['hit_rate_percent']}% "
                f"(threshold: {self.thresholds['hit_rate_min']}%)"
            )
            health["recommendations"].append(
                "Consider warming cache or increasing TTL for frequently accessed data"
            )

        # Check response time
        if metrics["avg_response_time_ms"] > self.thresholds["response_time_max_ms"]:
            health["status"] = "degraded"
            health["issues"].append(
                f"High average response time: {metrics['avg_response_time_ms']}ms "
                f"(threshold: {self.thresholds['response_time_max_ms']}ms)"
            )
            health["recommendations"].append(
                "Consider optimizing cache key structure or upgrading Redis instance"
            )

        # Check error rate
        if metrics["error_rate_percent"] > self.thresholds["error_rate_max"]:
            health["status"] = "unhealthy"
            health["issues"].append(
                f"High error rate: {metrics['error_rate_percent']}% "
                f"(threshold: {self.thresholds['error_rate_max']}%)"
            )
            health["recommendations"].append("Check Redis connection and server health")

        # Check Redis connection
        try:
            client = RedisClient.get_client()
            if not client.ping():
                health["status"] = "unhealthy"
                health["issues"].append("Redis connection failed")
                health["recommendations"].append(
                    "Check Redis server status and network connectivity"
                )
        except Exception as e:
            health["status"] = "unhealthy"
            health["issues"].append(f"Redis connection error: {str(e)}")

        # Add metrics to health report
        health["metrics"] = metrics

        return health

    def get_cache_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive cache report

        Returns:
            Complete cache performance report
        """
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2),
            "health": self.check_health(),
            "current_metrics": self.get_metrics(last_minutes=5),
            "hourly_metrics": self.get_metrics(last_minutes=60),
            "daily_metrics": self.get_metrics(last_minutes=1440),
            "top_keys": self.get_top_keys(limit=20),
            "slow_operations": self.get_slow_operations(threshold_ms=50, limit=20),
            "cache_types": {},
        }

        # Add per-cache-type metrics
        for cache_type in ["menu", "permissions", "settings", "analytics", "api"]:
            report["cache_types"][cache_type] = self.get_metrics(
                cache_type=cache_type, last_minutes=60
            )

        return report

    def reset_metrics(self):
        """Reset all collected metrics"""
        with self.metric_lock:
            self.metrics.clear()
            self.aggregated_metrics.clear()
            logger.info("Cache metrics reset")


# Global cache monitor instance
cache_monitor = CacheMonitor()


def monitor_cache_operation(cache_type: str, operation: str):
    """
    Decorator to monitor cache operations

    Args:
        cache_type: Type of cache
        operation: Operation type (get, set, delete)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            result = None

            try:
                result = func(*args, **kwargs)

                # Determine if it's a hit or miss for get operations
                if operation == "get" and result is None:
                    op_type = "miss"
                elif operation == "get":
                    op_type = "hit"
                else:
                    op_type = operation

            except Exception as e:
                success = False
                op_type = operation
                logger.error(f"Cache operation failed: {e}")
                raise
            finally:
                # Record metric
                duration_ms = (time.time() - start_time) * 1000

                # Extract key from arguments
                key = args[0] if args else kwargs.get("key", "unknown")

                metric = CacheMetric(
                    timestamp=time.time(),
                    operation=op_type,
                    cache_type=cache_type,
                    key=str(key),
                    duration_ms=duration_ms,
                    success=success,
                )

                cache_monitor.record_metric(metric)

            return result

        return wrapper

    return decorator
