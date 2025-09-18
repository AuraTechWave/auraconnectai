"""
Cache performance monitoring and metrics collection.

Provides:
- Real-time cache performance metrics
- Hit/miss ratio tracking
- Latency measurements
- Memory usage monitoring
- Prometheus metrics export
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from functools import wraps
import statistics

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from .redis_cache import redis_cache

logger = logging.getLogger(__name__)


# Prometheus metrics
cache_hits = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['namespace', 'operation']
)
cache_misses = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['namespace', 'operation']
)
cache_errors = Counter(
    'cache_errors_total',
    'Total number of cache errors',
    ['namespace', 'operation', 'error_type']
)
cache_operation_duration = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration',
    ['namespace', 'operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)
cache_memory_usage = Gauge(
    'cache_memory_usage_bytes',
    'Current cache memory usage',
    ['namespace']
)
cache_key_count = Gauge(
    'cache_key_count',
    'Number of keys in cache',
    ['namespace']
)
cache_evictions = Counter(
    'cache_evictions_total',
    'Total number of cache evictions',
    ['namespace', 'reason']
)


class CacheMetrics:
    """Collects and tracks cache performance metrics."""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        
        # Track recent operations for moving averages
        self.operation_times: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self.hit_rates: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        
        # Cumulative statistics
        self.total_operations = 0
        self.total_hits = 0
        self.total_misses = 0
        self.total_errors = 0
        
        # Per-namespace statistics
        self.namespace_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "hits": 0,
                "misses": 0,
                "errors": 0,
                "total_time": 0,
                "operations": 0,
            }
        )
        
        # Track slow operations
        self.slow_operations: List[Dict[str, Any]] = []
        self.slow_threshold = 0.1  # 100ms
        
    def record_hit(self, namespace: str, duration: float):
        """Record a cache hit."""
        self.total_operations += 1
        self.total_hits += 1
        
        self.namespace_stats[namespace]["hits"] += 1
        self.namespace_stats[namespace]["operations"] += 1
        self.namespace_stats[namespace]["total_time"] += duration
        
        self.operation_times[namespace].append(duration)
        self.hit_rates[namespace].append(1)  # 1 for hit
        
        # Update Prometheus metrics
        cache_hits.labels(namespace=namespace, operation="get").inc()
        cache_operation_duration.labels(
            namespace=namespace,
            operation="get"
        ).observe(duration)
        
        # Track slow operations
        if duration > self.slow_threshold:
            self.slow_operations.append({
                "type": "hit",
                "namespace": namespace,
                "duration": duration,
                "timestamp": datetime.utcnow()
            })
            
    def record_miss(self, namespace: str, duration: float):
        """Record a cache miss."""
        self.total_operations += 1
        self.total_misses += 1
        
        self.namespace_stats[namespace]["misses"] += 1
        self.namespace_stats[namespace]["operations"] += 1
        self.namespace_stats[namespace]["total_time"] += duration
        
        self.operation_times[namespace].append(duration)
        self.hit_rates[namespace].append(0)  # 0 for miss
        
        # Update Prometheus metrics
        cache_misses.labels(namespace=namespace, operation="get").inc()
        cache_operation_duration.labels(
            namespace=namespace,
            operation="get"
        ).observe(duration)
        
    def record_error(
        self,
        namespace: str,
        operation: str,
        error_type: str,
        duration: float
    ):
        """Record a cache error."""
        self.total_errors += 1
        
        self.namespace_stats[namespace]["errors"] += 1
        self.namespace_stats[namespace]["operations"] += 1
        self.namespace_stats[namespace]["total_time"] += duration
        
        # Update Prometheus metrics
        cache_errors.labels(
            namespace=namespace,
            operation=operation,
            error_type=error_type
        ).inc()
        
    def get_hit_rate(self, namespace: Optional[str] = None) -> float:
        """Get hit rate for a namespace or overall."""
        if namespace:
            hits = self.namespace_stats[namespace]["hits"]
            total = self.namespace_stats[namespace]["operations"]
        else:
            hits = self.total_hits
            total = self.total_operations
            
        return (hits / total * 100) if total > 0 else 0
        
    def get_average_latency(self, namespace: Optional[str] = None) -> float:
        """Get average operation latency."""
        if namespace and namespace in self.operation_times:
            times = self.operation_times[namespace]
            return statistics.mean(times) if times else 0
        elif not namespace:
            all_times = []
            for times in self.operation_times.values():
                all_times.extend(times)
            return statistics.mean(all_times) if all_times else 0
        return 0
        
    def get_p95_latency(self, namespace: Optional[str] = None) -> float:
        """Get 95th percentile latency."""
        if namespace and namespace in self.operation_times:
            times = list(self.operation_times[namespace])
            if len(times) >= 20:  # Need enough samples
                return statistics.quantiles(times, n=20)[18]  # 95th percentile
        return 0
        
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            "overall": {
                "total_operations": self.total_operations,
                "total_hits": self.total_hits,
                "total_misses": self.total_misses,
                "total_errors": self.total_errors,
                "hit_rate": self.get_hit_rate(),
                "average_latency_ms": self.get_average_latency() * 1000,
            },
            "by_namespace": {
                ns: {
                    "hits": stats["hits"],
                    "misses": stats["misses"],
                    "errors": stats["errors"],
                    "hit_rate": self.get_hit_rate(ns),
                    "average_latency_ms": self.get_average_latency(ns) * 1000,
                    "p95_latency_ms": self.get_p95_latency(ns) * 1000,
                }
                for ns, stats in self.namespace_stats.items()
            },
            "slow_operations": self.slow_operations[-10:],  # Last 10 slow ops
            "timestamp": datetime.utcnow().isoformat()
        }


class CacheMonitor:
    """Monitors cache performance and provides insights."""
    
    def __init__(self):
        self.metrics = CacheMetrics()
        self.monitoring_enabled = True
        self.alert_thresholds = {
            "hit_rate_min": 80.0,  # Alert if hit rate drops below 80%
            "latency_max_ms": 100,  # Alert if latency exceeds 100ms
            "error_rate_max": 5.0,  # Alert if error rate exceeds 5%
        }
        self.alert_callbacks: List[Callable] = []
        
    @asynccontextmanager
    async def monitor_operation(
        self,
        namespace: str,
        operation: str = "get"
    ):
        """Context manager to monitor a cache operation."""
        start_time = time.time()
        error_occurred = False
        error_type = None
        
        try:
            yield
        except Exception as e:
            error_occurred = True
            error_type = type(e).__name__
            raise
        finally:
            if self.monitoring_enabled:
                duration = time.time() - start_time
                
                if error_occurred:
                    self.metrics.record_error(
                        namespace,
                        operation,
                        error_type,
                        duration
                    )
                    
    def record_cache_result(
        self,
        namespace: str,
        hit: bool,
        duration: float
    ):
        """Record the result of a cache operation."""
        if not self.monitoring_enabled:
            return
            
        if hit:
            self.metrics.record_hit(namespace, duration)
        else:
            self.metrics.record_miss(namespace, duration)
            
        # Check thresholds
        self._check_alerts(namespace)
        
    def _check_alerts(self, namespace: str):
        """Check if any alert thresholds are exceeded."""
        hit_rate = self.metrics.get_hit_rate(namespace)
        if hit_rate < self.alert_thresholds["hit_rate_min"]:
            self._trigger_alert({
                "type": "low_hit_rate",
                "namespace": namespace,
                "value": hit_rate,
                "threshold": self.alert_thresholds["hit_rate_min"]
            })
            
        avg_latency_ms = self.metrics.get_average_latency(namespace) * 1000
        if avg_latency_ms > self.alert_thresholds["latency_max_ms"]:
            self._trigger_alert({
                "type": "high_latency",
                "namespace": namespace,
                "value": avg_latency_ms,
                "threshold": self.alert_thresholds["latency_max_ms"]
            })
            
    def _trigger_alert(self, alert_data: Dict[str, Any]):
        """Trigger alert callbacks."""
        logger.warning(f"Cache alert: {alert_data}")
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(alert_data))
                else:
                    callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
                
    def add_alert_callback(self, callback: Callable):
        """Add a callback to be called when alerts are triggered."""
        self.alert_callbacks.append(callback)
        
    async def collect_redis_metrics(self):
        """Collect metrics from Redis."""
        if not redis_cache.redis_client:
            return
            
        try:
            info = await redis_cache.redis_client.info()
            
            # Update Prometheus metrics
            cache_memory_usage.labels(namespace="redis").set(
                info.get("used_memory", 0)
            )
            
            # Get key count per namespace
            for namespace in self.metrics.namespace_stats.keys():
                pattern = f"{redis_cache.key_prefix}:{namespace}:*"
                cursor = 0
                key_count = 0
                
                while True:
                    cursor, keys = await redis_cache.redis_client.scan(
                        cursor,
                        match=pattern,
                        count=1000
                    )
                    key_count += len(keys)
                    
                    if cursor == 0:
                        break
                        
                cache_key_count.labels(namespace=namespace).set(key_count)
                
        except Exception as e:
            logger.error(f"Error collecting Redis metrics: {e}")
            
    def get_prometheus_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest()
        
    async def start_background_collection(self, interval: int = 60):
        """Start background metrics collection."""
        while True:
            try:
                await self.collect_redis_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background metrics collection: {e}")
                await asyncio.sleep(interval)


# Global cache monitor instance
cache_monitor = CacheMonitor()


def monitored_cache_operation(namespace: str = "default"):
    """Decorator to monitor cache operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            hit = False
            
            try:
                result = await func(*args, **kwargs)
                hit = result is not None
                return result
            finally:
                duration = time.time() - start_time
                cache_monitor.record_cache_result(namespace, hit, duration)
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            hit = False
            
            try:
                result = func(*args, **kwargs)
                hit = result is not None
                return result
            finally:
                duration = time.time() - start_time
                cache_monitor.record_cache_result(namespace, hit, duration)
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


# Export public interface
__all__ = [
    "cache_monitor",
    "monitored_cache_operation",
    "CacheMonitor",
    "CacheMetrics"
]