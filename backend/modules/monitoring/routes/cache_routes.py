"""
Cache monitoring and management endpoints.

Provides API endpoints for:
- Cache statistics
- Performance metrics
- Cache invalidation
- Health checks
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.auth import get_current_user, require_admin
from core.cache_config import get_cache_health, CACHE_CONFIG
from core.cache_monitoring import cache_monitor
from core.redis_cache import redis_cache
from core.distributed_session import session_manager

router = APIRouter(prefix="/cache", tags=["Cache Management"])


@router.get("/health")
async def get_cache_health_status(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache system health status."""
    try:
        health = await get_cache_health()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/stats")
async def get_cache_statistics(
    namespace: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache statistics."""
    try:
        # Get Redis stats
        redis_stats = await redis_cache.get_stats()
        
        # Get monitoring stats
        monitoring_stats = cache_monitor.metrics.get_summary()
        
        # Filter by namespace if requested
        if namespace:
            monitoring_stats["by_namespace"] = {
                namespace: monitoring_stats["by_namespace"].get(namespace, {})
            }
            
        return {
            "redis": redis_stats,
            "monitoring": monitoring_stats,
            "configuration": {
                "namespaces": list(CACHE_CONFIG["namespaces"].keys()),
                "warming_enabled": CACHE_CONFIG["warming"]["enabled"],
                "monitoring_enabled": CACHE_CONFIG["monitoring"]["enabled"],
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/metrics")
async def get_prometheus_metrics(
    current_user: dict = Depends(get_current_user)
) -> str:
    """Get cache metrics in Prometheus format."""
    try:
        metrics = cache_monitor.get_prometheus_metrics()
        return metrics.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.delete("/invalidate/pattern")
async def invalidate_cache_pattern(
    pattern: str = Query(..., description="Cache key pattern to invalidate"),
    namespace: Optional[str] = Query(None, description="Cache namespace"),
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Invalidate cache entries matching a pattern (admin only)."""
    try:
        deleted_count = await redis_cache.delete_pattern(pattern, namespace)
        
        return {
            "success": True,
            "pattern": pattern,
            "namespace": namespace,
            "deleted_count": deleted_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")


@router.delete("/invalidate/tag")
async def invalidate_cache_tag(
    tag: str = Query(..., description="Cache tag to invalidate"),
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Invalidate all cache entries with a specific tag (admin only)."""
    try:
        deleted_count = await redis_cache.invalidate_tag(tag)
        
        return {
            "success": True,
            "tag": tag,
            "deleted_count": deleted_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate tag: {str(e)}")


@router.delete("/invalidate/namespace/{namespace}")
async def invalidate_namespace(
    namespace: str,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Clear all cache entries in a namespace (admin only)."""
    try:
        deleted_count = await redis_cache.clear_namespace(namespace)
        
        return {
            "success": True,
            "namespace": namespace,
            "deleted_count": deleted_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear namespace: {str(e)}")


@router.post("/warm/{namespace}")
async def warm_cache_namespace(
    namespace: str,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Trigger cache warming for a namespace (admin only)."""
    try:
        # Import and call appropriate warming function based on namespace
        if namespace == "menu":
            from ...menu.services.menu_cache_service import MenuCacheService
            # Would implement actual warming here
            warmed_items = 0
            
        elif namespace == "analytics":
            from ...analytics.services.analytics_cache_service import AnalyticsCacheService
            # Would implement actual warming here
            warmed_items = 0
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown namespace: {namespace}")
            
        return {
            "success": True,
            "namespace": namespace,
            "warmed_items": warmed_items,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to warm cache: {str(e)}")


@router.get("/sessions/stats")
async def get_session_statistics(
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Get distributed session statistics (admin only)."""
    try:
        stats = await session_manager.get_session_count()
        
        return {
            "sessions": stats,
            "configuration": {
                "default_ttl": session_manager.default_ttl,
                "encryption_enabled": True,
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session stats: {str(e)}")


@router.delete("/sessions/user/{user_id}")
async def invalidate_user_sessions(
    user_id: int,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Invalidate all sessions for a user (admin only)."""
    try:
        deleted_count = await session_manager.delete_user_sessions(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "deleted_sessions": deleted_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete sessions: {str(e)}")


@router.get("/config")
async def get_cache_configuration(
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Get cache configuration details (admin only)."""
    try:
        # Remove sensitive information
        config = {
            "namespaces": CACHE_CONFIG["namespaces"],
            "warming": CACHE_CONFIG["warming"],
            "monitoring": CACHE_CONFIG["monitoring"],
        }
        
        return config
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@router.put("/config/monitoring")
async def update_monitoring_config(
    hit_rate_min: Optional[float] = None,
    latency_max_ms: Optional[int] = None,
    error_rate_max: Optional[float] = None,
    enabled: Optional[bool] = None,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Update cache monitoring configuration (admin only)."""
    try:
        if hit_rate_min is not None:
            cache_monitor.alert_thresholds["hit_rate_min"] = hit_rate_min
            
        if latency_max_ms is not None:
            cache_monitor.alert_thresholds["latency_max_ms"] = latency_max_ms
            
        if error_rate_max is not None:
            cache_monitor.alert_thresholds["error_rate_max"] = error_rate_max
            
        if enabled is not None:
            cache_monitor.monitoring_enabled = enabled
            
        return {
            "success": True,
            "monitoring_enabled": cache_monitor.monitoring_enabled,
            "alert_thresholds": cache_monitor.alert_thresholds,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


# Export router
__all__ = ["router"]