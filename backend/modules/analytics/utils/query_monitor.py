# backend/modules/analytics/utils/query_monitor.py

"""
Query performance monitoring utilities for analytics operations.

Provides decorators and utilities to monitor database query performance,
track slow queries, and generate performance reports.
"""

import time
import functools
import logging
from typing import Callable, Any, Dict, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """Monitor and track database query performance"""
    
    def __init__(self):
        self.query_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "slow_queries": [],
            "last_executed": None
        })
        self.slow_query_threshold = 1.0  # seconds
        self.enabled = True
        self._lock = asyncio.Lock()
    
    async def record_query(
        self,
        query_name: str,
        execution_time: float,
        query_details: Optional[Dict[str, Any]] = None
    ):
        """Record query execution statistics"""
        if not self.enabled:
            return
            
        async with self._lock:
            stats = self.query_stats[query_name]
            stats["count"] += 1
            stats["total_time"] += execution_time
            stats["min_time"] = min(stats["min_time"], execution_time)
            stats["max_time"] = max(stats["max_time"], execution_time)
            stats["last_executed"] = datetime.utcnow()
            
            # Track slow queries
            if execution_time > self.slow_query_threshold:
                slow_query_info = {
                    "execution_time": execution_time,
                    "timestamp": datetime.utcnow(),
                    "details": query_details or {}
                }
                stats["slow_queries"].append(slow_query_info)
                
                # Keep only last 100 slow queries
                if len(stats["slow_queries"]) > 100:
                    stats["slow_queries"] = stats["slow_queries"][-100:]
                
                logger.warning(
                    f"Slow query detected: {query_name} took {execution_time:.2f}s"
                )
    
    def get_statistics(self, query_name: Optional[str] = None) -> Dict[str, Any]:
        """Get query performance statistics"""
        if query_name:
            stats = self.query_stats.get(query_name)
            if not stats:
                return {}
            
            avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            return {
                "query_name": query_name,
                "execution_count": stats["count"],
                "total_time": stats["total_time"],
                "average_time": avg_time,
                "min_time": stats["min_time"] if stats["min_time"] != float('inf') else 0,
                "max_time": stats["max_time"],
                "slow_query_count": len(stats["slow_queries"]),
                "last_executed": stats["last_executed"]
            }
        
        # Return all statistics
        all_stats = []
        for name, stats in self.query_stats.items():
            avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            all_stats.append({
                "query_name": name,
                "execution_count": stats["count"],
                "average_time": avg_time,
                "slow_query_count": len(stats["slow_queries"])
            })
        
        return {
            "total_queries": sum(s["execution_count"] for s in all_stats),
            "queries": sorted(all_stats, key=lambda x: x["average_time"], reverse=True)
        }
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the slowest queries across all monitored queries"""
        all_slow_queries = []
        
        for query_name, stats in self.query_stats.items():
            for slow_query in stats["slow_queries"]:
                all_slow_queries.append({
                    "query_name": query_name,
                    "execution_time": slow_query["execution_time"],
                    "timestamp": slow_query["timestamp"],
                    **slow_query["details"]
                })
        
        # Sort by execution time and return top N
        return sorted(
            all_slow_queries,
            key=lambda x: x["execution_time"],
            reverse=True
        )[:limit]
    
    def reset_statistics(self, query_name: Optional[str] = None):
        """Reset query statistics"""
        if query_name:
            if query_name in self.query_stats:
                del self.query_stats[query_name]
        else:
            self.query_stats.clear()


# Global monitor instance
query_monitor = QueryPerformanceMonitor()


def monitor_query_performance(query_name: Optional[str] = None):
    """
    Decorator to monitor query performance.
    
    Usage:
        @monitor_query_performance("get_sales_summary")
        async def get_sales_summary(self, filters):
            # Query implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = None
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                execution_time = time.time() - start_time
                
                # Determine query name
                name = query_name or f"{func.__module__}.{func.__name__}"
                
                # Extract query details from arguments if possible
                details = {}
                if args and hasattr(args[0], '__class__'):
                    details["class"] = args[0].__class__.__name__
                if "filters" in kwargs:
                    details["filters"] = str(kwargs["filters"])
                if error:
                    details["error"] = str(error)
                
                # Record the query performance
                await query_monitor.record_query(name, execution_time, details)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = None
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                execution_time = time.time() - start_time
                
                # Determine query name
                name = query_name or f"{func.__module__}.{func.__name__}"
                
                # Extract query details
                details = {}
                if args and hasattr(args[0], '__class__'):
                    details["class"] = args[0].__class__.__name__
                if error:
                    details["error"] = str(error)
                
                # Record synchronously (create async task)
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    query_monitor.record_query(name, execution_time, details)
                )
                loop.close()
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def setup_sqlalchemy_query_logging(engine: Engine, slow_query_threshold: float = 0.5):
    """
    Set up SQLAlchemy event listeners to log slow queries.
    
    Args:
        engine: SQLAlchemy engine instance
        slow_query_threshold: Threshold in seconds for slow query logging
    """
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())
        
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        
        if total_time > slow_query_threshold:
            # Log slow query
            logger.warning(
                f"Slow SQL query detected ({total_time:.2f}s):\n"
                f"Statement: {statement[:200]}...\n"
                f"Parameters: {parameters}"
            )
            
            # Also record in our monitor
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                query_monitor.record_query(
                    "raw_sql_query",
                    total_time,
                    {
                        "statement": statement[:500],
                        "parameter_count": len(parameters) if parameters else 0
                    }
                )
            )
            loop.close()


class QueryOptimizationHints:
    """Provides optimization hints based on query performance"""
    
    @staticmethod
    def analyze_query_performance(stats: Dict[str, Any]) -> List[str]:
        """Analyze query statistics and provide optimization hints"""
        hints = []
        
        if not stats:
            return hints
        
        # Check average execution time
        avg_time = stats.get("average_time", 0)
        if avg_time > 2.0:
            hints.append(
                f"Query '{stats.get('query_name')}' has high average execution time "
                f"({avg_time:.2f}s). Consider adding indexes or optimizing the query."
            )
        
        # Check for high execution count
        exec_count = stats.get("execution_count", 0)
        if exec_count > 1000 and avg_time > 0.1:
            hints.append(
                f"Query '{stats.get('query_name')}' is executed frequently "
                f"({exec_count} times) with noticeable latency. "
                "Consider implementing caching."
            )
        
        # Check for slow query spikes
        slow_count = stats.get("slow_query_count", 0)
        if slow_count > 10:
            hints.append(
                f"Query '{stats.get('query_name')}' has {slow_count} slow executions. "
                "This might indicate missing indexes or lock contention."
            )
        
        # Check min/max time variance
        min_time = stats.get("min_time", 0)
        max_time = stats.get("max_time", 0)
        if max_time > 0 and max_time > min_time * 10:
            hints.append(
                f"Query '{stats.get('query_name')}' has high execution time variance "
                f"(min: {min_time:.2f}s, max: {max_time:.2f}s). "
                "This might indicate cache misses or data-dependent performance."
            )
        
        return hints
    
    @staticmethod
    def generate_optimization_report() -> Dict[str, Any]:
        """Generate a comprehensive optimization report"""
        all_stats = query_monitor.get_statistics()
        slow_queries = query_monitor.get_slow_queries(20)
        
        # Analyze each query
        optimization_hints = []
        for query_stats in all_stats.get("queries", []):
            query_name = query_stats["query_name"]
            detailed_stats = query_monitor.get_statistics(query_name)
            hints = QueryOptimizationHints.analyze_query_performance(detailed_stats)
            if hints:
                optimization_hints.extend(hints)
        
        return {
            "summary": {
                "total_queries_monitored": len(all_stats.get("queries", [])),
                "total_executions": all_stats.get("total_queries", 0),
                "slow_queries_detected": len(slow_queries),
                "optimization_hints_count": len(optimization_hints)
            },
            "top_slow_queries": slow_queries[:10],
            "optimization_hints": optimization_hints,
            "detailed_statistics": all_stats
        }


# Export commonly used functions
__all__ = [
    "query_monitor",
    "monitor_query_performance",
    "setup_sqlalchemy_query_logging",
    "QueryOptimizationHints"
]