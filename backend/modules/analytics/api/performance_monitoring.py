# backend/modules/analytics/api/performance_monitoring.py

"""
API endpoints for query performance monitoring and optimization insights.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from ..utils.query_monitor import query_monitor, QueryOptimizationHints
from ..utils.cache_manager import analytics_cache
from ..services.materialized_view_queries import MaterializedViewQueries

router = APIRouter(
    prefix="/analytics/performance",
    tags=["Analytics Performance"],
    responses={404: {"description": "Not found"}},
)


@router.get("/query-stats")
async def get_query_statistics(
    query_name: Optional[str] = Query(None, description="Specific query name to get stats for"),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get query performance statistics.
    
    Returns execution counts, average times, and slow query information.
    Requires admin or manager role.
    """
    # Check permissions (assuming admin/manager check)
    if not current_user.is_admin and current_user.role != "manager":
        raise HTTPException(
            status_code=403, 
            detail="Only admins and managers can view performance statistics"
        )
    
    if query_name:
        stats = query_monitor.get_statistics(query_name)
        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No statistics found for query: {query_name}"
            )
        return stats
    
    return query_monitor.get_statistics()


@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=100, description="Number of slow queries to return"),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get the slowest queries recorded.
    
    Returns detailed information about queries that exceeded the slow query threshold.
    """
    if not current_user.is_admin and current_user.role != "manager":
        raise HTTPException(
            status_code=403, 
            detail="Only admins and managers can view performance statistics"
        )
    
    slow_queries = query_monitor.get_slow_queries(limit)
    
    return {
        "slow_query_threshold": query_monitor.slow_query_threshold,
        "slow_queries": slow_queries,
        "count": len(slow_queries),
    }


@router.get("/optimization-report")
async def get_optimization_report(
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate a comprehensive query optimization report.
    
    Analyzes query performance and provides optimization recommendations.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Only admins can view optimization reports"
        )
    
    report = QueryOptimizationHints.generate_optimization_report()
    
    # Add cache statistics
    report["cache_statistics"] = analytics_cache.get_cache_stats()
    
    # Add timestamp
    report["generated_at"] = datetime.utcnow()
    
    return report


@router.get("/cache-stats")
async def get_cache_statistics(
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get analytics cache statistics.
    
    Returns hit rates, miss counts, and cache effectiveness metrics.
    """
    if not current_user.is_admin and current_user.role != "manager":
        raise HTTPException(
            status_code=403, 
            detail="Only admins and managers can view cache statistics"
        )
    
    return analytics_cache.get_cache_stats()


@router.post("/cache/invalidate")
async def invalidate_cache(
    namespace: str = Query(..., description="Cache namespace to invalidate"),
    pattern: Optional[str] = Query(None, description="Optional pattern within namespace"),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Invalidate analytics cache entries.
    
    Useful for forcing fresh data after significant changes.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Only admins can invalidate cache"
        )
    
    try:
        if pattern:
            await analytics_cache.invalidate_pattern(f"{namespace}:{pattern}")
        else:
            await analytics_cache.invalidate_namespace(namespace)
        
        return {
            "status": "success",
            "message": f"Cache invalidated for namespace: {namespace}",
            "pattern": pattern,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.get("/materialized-views/status")
async def get_materialized_view_status(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get status of materialized views.
    
    Shows size, last refresh time, and other metadata.
    """
    if not current_user.is_admin and current_user.role != "manager":
        raise HTTPException(
            status_code=403, 
            detail="Only admins and managers can view materialized view status"
        )
    
    try:
        return MaterializedViewQueries.get_materialized_view_stats(db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get materialized view stats: {str(e)}"
        )


@router.post("/materialized-views/refresh")
async def refresh_materialized_views(
    view_name: Optional[str] = Query(None, description="Specific view to refresh, or all if not specified"),
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Manually refresh materialized views.
    
    Can refresh a specific view or all analytics views.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Only admins can refresh materialized views"
        )
    
    try:
        success = MaterializedViewQueries.refresh_materialized_views(db, view_name)
        
        if success:
            return {
                "status": "success",
                "message": f"Refreshed {'all materialized views' if not view_name else view_name}",
                "timestamp": datetime.utcnow(),
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to refresh materialized views"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing materialized views: {str(e)}"
        )


@router.post("/monitoring/reset")
async def reset_monitoring_stats(
    query_name: Optional[str] = Query(None, description="Reset stats for specific query or all"),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Reset query monitoring statistics.
    
    Useful for starting fresh measurements after optimizations.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Only admins can reset monitoring statistics"
        )
    
    query_monitor.reset_statistics(query_name)
    
    return {
        "status": "success",
        "message": f"Reset statistics for {'all queries' if not query_name else query_name}",
        "timestamp": datetime.utcnow(),
    }


@router.get("/health-check")
async def performance_health_check(
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Perform a comprehensive performance health check.
    
    Checks query performance, cache effectiveness, and database health.
    """
    if not current_user.is_admin and current_user.role != "manager":
        raise HTTPException(
            status_code=403, 
            detail="Only admins and managers can run health checks"
        )
    
    # Get overall statistics
    query_stats = query_monitor.get_statistics()
    cache_stats = analytics_cache.get_cache_stats()
    
    # Determine health status
    issues = []
    
    # Check for slow queries
    slow_queries = query_monitor.get_slow_queries(5)
    if slow_queries:
        issues.append({
            "type": "slow_queries",
            "severity": "warning",
            "message": f"{len(slow_queries)} slow queries detected",
            "details": [q["query_name"] for q in slow_queries[:3]]
        })
    
    # Check cache hit rate
    hit_rate = float(cache_stats["hit_rate"].rstrip('%'))
    if hit_rate < 50:
        issues.append({
            "type": "low_cache_hit_rate",
            "severity": "warning",
            "message": f"Cache hit rate is low: {hit_rate}%",
        })
    
    # Check for queries with high average time
    if "queries" in query_stats:
        high_avg_queries = [
            q for q in query_stats["queries"] 
            if q["average_time"] > 1.0
        ]
        if high_avg_queries:
            issues.append({
                "type": "high_average_query_time",
                "severity": "warning",
                "message": f"{len(high_avg_queries)} queries have high average execution time",
                "details": high_avg_queries[:3]
            })
    
    health_status = "healthy" if not issues else ("degraded" if len(issues) < 3 else "unhealthy")
    
    return {
        "status": health_status,
        "timestamp": datetime.utcnow(),
        "metrics": {
            "total_queries_monitored": len(query_stats.get("queries", [])),
            "cache_hit_rate": cache_stats["hit_rate"],
            "slow_query_count": len(slow_queries),
        },
        "issues": issues,
        "recommendations": [
            "Review and optimize slow queries",
            "Consider increasing cache TTL for frequently accessed data",
            "Ensure materialized views are refreshed regularly",
        ] if issues else []
    }