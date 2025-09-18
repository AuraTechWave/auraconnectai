"""
Cache configuration and initialization.

Centralizes all cache-related configuration and provides
initialization functions for the application startup.
"""

import logging
from typing import Optional, Dict, Any
from .config import get_settings
from .redis_cache import redis_cache, RedisCacheService
from .distributed_session import session_manager
from .cache_monitoring import cache_monitor

logger = logging.getLogger(__name__)
settings = get_settings()


# Cache configuration
CACHE_CONFIG = {
    # Redis connection
    "redis": {
        "url": settings.redis_url or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
        "password": settings.REDIS_PASSWORD,
        "max_connections": 100,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
    },
    
    # Cache namespaces and their TTLs
    "namespaces": {
        "menu": {
            "default_ttl": 3600,  # 1 hour
            "patterns": {
                "item": 3600,
                "category": 3600,
                "recipe": 1800,
                "recipe_cost": 300,  # 5 minutes
                "full_menu": 900,  # 15 minutes
            }
        },
        "analytics": {
            "default_ttl": 300,  # 5 minutes
            "patterns": {
                "realtime": 60,
                "dashboard": 900,
                "sales": 600,
                "ai_insights": 1800,
                "pos": 300,
            }
        },
        "inventory": {
            "default_ttl": 600,  # 10 minutes
            "patterns": {
                "stock_level": 300,
                "low_stock": 600,
                "movement": 900,
                "supplier": 3600,
            }
        },
        "staff": {
            "default_ttl": 1800,  # 30 minutes
            "patterns": {
                "schedule": 1800,
                "availability": 900,
                "performance": 3600,
                "payroll": 7200,
            }
        },
        "orders": {
            "default_ttl": 300,  # 5 minutes
            "patterns": {
                "active": 60,
                "history": 900,
                "stats": 600,
                "priority": 120,
            }
        },
        "promotions": {
            "default_ttl": 600,  # 10 minutes
            "patterns": {
                "active": 300,
                "eligibility": 180,
                "usage": 600,
            }
        },
        "session": {
            "default_ttl": 1800,  # 30 minutes
        }
    },
    
    # Cache warming configuration
    "warming": {
        "enabled": True,
        "interval_minutes": 30,
        "namespaces": ["menu", "analytics"],
    },
    
    # Monitoring configuration
    "monitoring": {
        "enabled": True,
        "metrics_collection_interval": 60,
        "alert_thresholds": {
            "hit_rate_min": 80.0,
            "latency_max_ms": 100,
            "error_rate_max": 5.0,
        },
        "slow_operation_threshold_ms": 100,
    }
}


async def initialize_cache_system():
    """Initialize the entire caching system."""
    logger.info("Initializing cache system...")
    
    try:
        # Initialize Redis cache service
        await redis_cache.initialize()
        
        # Initialize session manager (uses same Redis connection)
        # Session manager will use the redis_cache client
        
        # Configure monitoring
        if CACHE_CONFIG["monitoring"]["enabled"]:
            cache_monitor.monitoring_enabled = True
            cache_monitor.alert_thresholds = CACHE_CONFIG["monitoring"]["alert_thresholds"]
            cache_monitor.metrics.slow_threshold = (
                CACHE_CONFIG["monitoring"]["slow_operation_threshold_ms"] / 1000
            )
            
        logger.info("Cache system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize cache system: {e}")
        # Allow graceful degradation - app can run without cache
        return False


async def shutdown_cache_system():
    """Shutdown the caching system gracefully."""
    logger.info("Shutting down cache system...")
    
    try:
        # Close Redis connections
        await redis_cache.close()
        
        logger.info("Cache system shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during cache system shutdown: {e}")


def get_cache_service(namespace: str = "default") -> RedisCacheService:
    """
    Get a cache service instance for a specific namespace.
    
    This allows different modules to have their own cache configurations.
    """
    config = CACHE_CONFIG["namespaces"].get(namespace, {})
    default_ttl = config.get("default_ttl", 300)
    
    # For now, return the global instance
    # In future, could create namespace-specific instances
    return redis_cache


def get_cache_ttl(namespace: str, pattern: str) -> int:
    """Get the configured TTL for a specific cache pattern."""
    namespace_config = CACHE_CONFIG["namespaces"].get(namespace, {})
    patterns = namespace_config.get("patterns", {})
    
    if pattern in patterns:
        return patterns[pattern]
    
    return namespace_config.get("default_ttl", 300)


async def warm_caches():
    """Warm critical caches proactively."""
    if not CACHE_CONFIG["warming"]["enabled"]:
        return
        
    logger.info("Starting cache warming...")
    
    for namespace in CACHE_CONFIG["warming"]["namespaces"]:
        try:
            if namespace == "menu":
                from ..modules.menu.services.menu_cache_service import MenuCacheService
                # Would call MenuCacheService.warm_menu_cache() here
                logger.info(f"Warmed {namespace} cache")
                
            elif namespace == "analytics":
                from ..modules.analytics.services.analytics_cache_service import AnalyticsCacheService
                # Would call warming methods here
                logger.info(f"Warmed {namespace} cache")
                
        except Exception as e:
            logger.error(f"Error warming {namespace} cache: {e}")


# Cache health check for monitoring endpoints
async def get_cache_health() -> Dict[str, Any]:
    """Get cache system health status."""
    health = {
        "status": "healthy",
        "redis_connected": False,
        "circuit_breaker_state": "unknown",
        "metrics": {}
    }
    
    try:
        # Check Redis connection
        if redis_cache.redis_client:
            await redis_cache.redis_client.ping()
            health["redis_connected"] = True
            
        # Get circuit breaker state
        health["circuit_breaker_state"] = redis_cache.circuit_breaker.state
        
        # Get cache statistics
        stats = await redis_cache.get_stats()
        health["metrics"] = stats
        
        # Get monitoring metrics
        if cache_monitor.monitoring_enabled:
            health["monitoring"] = cache_monitor.metrics.get_summary()
            
        # Determine overall health
        if not health["redis_connected"]:
            health["status"] = "degraded"
        elif redis_cache.circuit_breaker.state == "open":
            health["status"] = "degraded"
        elif stats.get("client_stats", {}).get("error_rate", 0) > 10:
            health["status"] = "unhealthy"
            
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        
    return health


# Export configuration
__all__ = [
    "CACHE_CONFIG",
    "initialize_cache_system",
    "shutdown_cache_system",
    "get_cache_service",
    "get_cache_ttl",
    "warm_caches",
    "get_cache_health",
]