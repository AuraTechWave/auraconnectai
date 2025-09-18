"""
Enhanced cache monitoring and management endpoints.

Provides additional API endpoints for:
- Compression statistics
- Multi-level cache metrics
- Pattern analysis
- Preloading management
- Performance analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.auth import get_current_user, require_admin
from core.enhanced_redis_cache import enhanced_cache, get_cache_performance_report
from core.memory_cache import memory_cache
from core.cache_preloader import cache_preloader, pattern_analyzer
from core.cache_versioning import CacheVersion, cache_version_manager

router = APIRouter(prefix="/cache/v2", tags=["Enhanced Cache Management"])


@router.get("/performance")
async def get_enhanced_performance_metrics(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive cache performance metrics."""
    try:
        return await get_cache_performance_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/compression/stats")
async def get_compression_statistics(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache compression statistics."""
    try:
        stats = await enhanced_cache.get_stats()
        return {
            "compression": stats.get("compression", {}),
            "recommendations": {
                "current_threshold": enhanced_cache.compression_threshold,
                "suggested_threshold": 512 if stats.get("compression", {}).get("compression_ratio", "0%").replace("%", "") < "20" else enhanced_cache.compression_threshold,
                "potential_savings": "Enable compression for more data types" if stats.get("compression", {}).get("compressed_count", 0) < stats.get("compression", {}).get("uncompressed_count", 0) else "Compression is well utilized"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get compression stats: {str(e)}")


@router.get("/memory/stats")
async def get_memory_cache_statistics(
    namespace: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get local memory cache statistics."""
    try:
        stats = await memory_cache.get_stats()
        
        if namespace and namespace in stats["namespaces"]:
            return {
                "namespace": namespace,
                "stats": stats["namespaces"][namespace],
                "global_stats": stats["global_stats"]
            }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get memory cache stats: {str(e)}")


@router.post("/memory/clear")
async def clear_memory_cache(
    namespace: Optional[str] = Query(None, description="Specific namespace to clear"),
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Clear memory cache (admin only)."""
    try:
        if namespace:
            await memory_cache.clear_namespace(namespace)
            message = f"Cleared memory cache for namespace: {namespace}"
        else:
            await memory_cache.clear_all()
            message = "Cleared all memory cache"
        
        return {
            "success": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear memory cache: {str(e)}")


@router.get("/patterns/analysis")
async def get_cache_pattern_analysis(
    limit: int = Query(20, description="Number of patterns to return"),
    min_priority: int = Query(5, description="Minimum priority threshold"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache access pattern analysis."""
    try:
        patterns = pattern_analyzer.analyze_patterns()
        
        # Filter by priority
        filtered_patterns = [
            {
                "key": p.key,
                "namespace": p.namespace,
                "pattern_type": p.pattern_type.value,
                "access_count": p.access_count,
                "avg_latency_ms": p.avg_latency_ms,
                "peak_hours": p.peak_hours,
                "predictability_score": p.predictability_score,
                "preload_priority": p.preload_priority
            }
            for p in patterns
            if p.preload_priority >= min_priority
        ][:limit]
        
        return {
            "total_patterns": len(patterns),
            "filtered_count": len(filtered_patterns),
            "patterns": filtered_patterns,
            "analysis_period_days": pattern_analyzer.history_days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pattern analysis: {str(e)}")


@router.get("/preloader/stats")
async def get_preloader_statistics(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache preloader statistics."""
    try:
        return await cache_preloader.get_preload_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preloader stats: {str(e)}")


@router.post("/preloader/run")
async def trigger_cache_preload(
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Manually trigger cache preloading cycle (admin only)."""
    try:
        await cache_preloader.run_preload_cycle()
        return {
            "success": True,
            "message": "Preload cycle completed",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run preload cycle: {str(e)}")


@router.put("/preloader/config")
async def update_preloader_configuration(
    max_concurrent_preloads: Optional[int] = None,
    preload_threshold_priority: Optional[int] = None,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Update cache preloader configuration (admin only)."""
    try:
        if max_concurrent_preloads is not None:
            cache_preloader.max_concurrent_preloads = max_concurrent_preloads
        
        if preload_threshold_priority is not None:
            cache_preloader.preload_threshold_priority = preload_threshold_priority
        
        return {
            "success": True,
            "configuration": {
                "max_concurrent_preloads": cache_preloader.max_concurrent_preloads,
                "preload_threshold_priority": cache_preloader.preload_threshold_priority
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.get("/versions")
async def get_cache_versions(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cache versioning information."""
    try:
        return {
            "current_version": cache_version_manager.current_version.value,
            "available_versions": [v.value for v in CacheVersion],
            "migration_paths": [
                {
                    "from": k[0].value,
                    "to": k[1].value,
                    "migrator": v.__class__.__name__
                }
                for k, v in cache_version_manager.migrators.items()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get version info: {str(e)}")


@router.post("/compress/{key}")
async def compress_cache_entry(
    key: str,
    namespace: str = Query("default", description="Cache namespace"),
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Manually compress a cache entry (admin only)."""
    try:
        # Get the value
        value = await enhanced_cache.get(key, namespace)
        if value is None:
            raise HTTPException(status_code=404, detail="Cache entry not found")
        
        # Re-cache with compression
        success = await enhanced_cache.set(
            key,
            value,
            namespace=namespace,
            compress=True
        )
        
        return {
            "success": success,
            "key": key,
            "namespace": namespace,
            "message": "Entry compressed and re-cached" if success else "Failed to compress",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compress entry: {str(e)}")


@router.get("/multi-level/flow")
async def get_cache_flow_visualization(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get multi-level cache flow statistics."""
    try:
        memory_stats = await memory_cache.get_stats()
        redis_stats = await enhanced_cache.get_stats()
        
        # Calculate flow metrics
        l1_requests = memory_stats["global_stats"]["l1_hits"] + memory_stats["global_stats"]["l1_misses"]
        l2_requests = memory_stats["global_stats"]["l2_hits"] + memory_stats["global_stats"]["l2_misses"]
        
        flow = {
            "level_1_memory": {
                "requests": l1_requests,
                "hits": memory_stats["global_stats"]["l1_hits"],
                "hit_rate": memory_stats["global_stats"]["l1_hit_rate"],
                "size": memory_stats["totals"]["total_entries"],
                "memory_mb": memory_stats["totals"]["total_memory_mb"]
            },
            "level_2_redis": {
                "requests": l2_requests,
                "hits": memory_stats["global_stats"]["l2_hits"],
                "hit_rate": memory_stats["global_stats"]["l2_hit_rate"],
                "compressed_entries": redis_stats["compression"]["compressed_count"],
                "mb_saved": redis_stats["compression"]["mb_saved"]
            },
            "overall": {
                "total_requests": l1_requests,
                "served_from_memory": memory_stats["global_stats"]["l1_hits"],
                "served_from_redis": memory_stats["global_stats"]["l2_hits"],
                "cache_misses": memory_stats["global_stats"]["l2_misses"],
                "overall_hit_rate": memory_stats["global_stats"]["overall_hit_rate"]
            }
        }
        
        return flow
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache flow: {str(e)}")


# Export router
__all__ = ["router"]