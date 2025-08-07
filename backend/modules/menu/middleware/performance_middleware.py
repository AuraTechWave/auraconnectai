# backend/modules/menu/middleware/performance_middleware.py

"""
Performance monitoring middleware for recipe endpoints.
Tracks response times, cache hits, and throughput.
"""

import time
import logging
from typing import Callable, Dict, Any
from datetime import datetime
from collections import defaultdict, deque
from threading import Lock
import asyncio

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Thread-safe metrics collector"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.lock = Lock()
        self.response_times = defaultdict(lambda: deque(maxlen=window_size))
        self.cache_hits = defaultdict(int)
        self.cache_misses = defaultdict(int)
        self.request_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.start_time = datetime.utcnow()
    
    def record_request(self, endpoint: str, response_time: float, cache_hit: bool = None, error: bool = False):
        """Record metrics for a request"""
        with self.lock:
            self.response_times[endpoint].append(response_time)
            self.request_counts[endpoint] += 1
            
            if error:
                self.error_counts[endpoint] += 1
            
            if cache_hit is not None:
                if cache_hit:
                    self.cache_hits[endpoint] += 1
                else:
                    self.cache_misses[endpoint] += 1
    
    def get_metrics(self, endpoint: str = None) -> Dict[str, Any]:
        """Get metrics for an endpoint or all endpoints"""
        with self.lock:
            if endpoint:
                return self._calculate_endpoint_metrics(endpoint)
            
            # Calculate metrics for all endpoints
            metrics = {
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
                "endpoints": {}
            }
            
            for ep in self.request_counts.keys():
                metrics["endpoints"][ep] = self._calculate_endpoint_metrics(ep)
            
            return metrics
    
    def _calculate_endpoint_metrics(self, endpoint: str) -> Dict[str, Any]:
        """Calculate metrics for a specific endpoint"""
        response_times = list(self.response_times[endpoint])
        
        if not response_times:
            return {
                "request_count": 0,
                "error_count": 0,
                "avg_response_time_ms": 0,
                "p50_response_time_ms": 0,
                "p95_response_time_ms": 0,
                "p99_response_time_ms": 0,
                "cache_hit_rate": 0
            }
        
        response_times.sort()
        count = len(response_times)
        
        # Calculate percentiles
        p50_idx = int(count * 0.5)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        
        total_cache_requests = self.cache_hits[endpoint] + self.cache_misses[endpoint]
        cache_hit_rate = (self.cache_hits[endpoint] / total_cache_requests * 100) if total_cache_requests > 0 else 0
        
        return {
            "request_count": self.request_counts[endpoint],
            "error_count": self.error_counts[endpoint],
            "error_rate": (self.error_counts[endpoint] / self.request_counts[endpoint] * 100) if self.request_counts[endpoint] > 0 else 0,
            "avg_response_time_ms": sum(response_times) / count * 1000,
            "p50_response_time_ms": response_times[p50_idx] * 1000,
            "p95_response_time_ms": response_times[p95_idx] * 1000,
            "p99_response_time_ms": response_times[p99_idx] * 1000,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.cache_hits[endpoint],
            "cache_misses": self.cache_misses[endpoint]
        }


# Global metrics instance
_metrics = PerformanceMetrics()


class RecipePerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track performance metrics for recipe endpoints.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.tracked_prefixes = [
            "/api/v1/menu/recipes",
            "/api/v1/menu/recipes/v2"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track metrics"""
        # Check if this is a tracked endpoint
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in self.tracked_prefixes):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Extract endpoint info
        endpoint = self._normalize_endpoint(path)
        
        # Process request
        error_occurred = False
        cache_hit = None
        
        try:
            response = await call_next(request)
            
            # Check for cache hit header
            if "X-Cache-Hit" in response.headers:
                cache_hit = response.headers["X-Cache-Hit"].lower() == "true"
            
            # Check for errors
            if response.status_code >= 400:
                error_occurred = True
            
            return response
            
        except Exception as e:
            error_occurred = True
            raise
        
        finally:
            # Record metrics
            response_time = time.time() - start_time
            _metrics.record_request(
                endpoint=endpoint,
                response_time=response_time,
                cache_hit=cache_hit,
                error=error_occurred
            )
            
            # Log slow requests
            if response_time > 1.0:  # 1 second threshold
                logger.warning(
                    f"Slow request detected: {endpoint} took {response_time:.2f}s"
                )
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics grouping"""
        # Remove numeric IDs from paths
        import re
        
        # Replace numeric IDs with placeholder
        normalized = re.sub(r'/\d+', '/{id}', path)
        
        # Remove query parameters
        normalized = normalized.split('?')[0]
        
        return normalized


def get_performance_metrics(endpoint: str = None) -> Dict[str, Any]:
    """Get current performance metrics"""
    return _metrics.get_metrics(endpoint)


def reset_performance_metrics():
    """Reset all metrics (useful for testing)"""
    global _metrics
    _metrics = PerformanceMetrics()