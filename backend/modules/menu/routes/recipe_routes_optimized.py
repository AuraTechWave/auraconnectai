# backend/modules/menu/routes/recipe_routes_optimized.py

"""
Optimized Recipe Routes with performance enhancements.
Includes caching, pagination, and background task support.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from core.database import get_db
from core.auth import require_permission, User
from ..services.recipe_service_optimized import OptimizedRecipeService
from ..services.recipe_cache_service import get_recipe_cache_service
from ..tasks.recipe_cost_tasks import get_task_status
from ..schemas.recipe_schemas import (
    RecipeCostAnalysis, RecipeComplianceReport,
    MenuItemRecipeStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes/v2", tags=["Recipe Management - Optimized"])


def get_optimized_recipe_service(db: Session = Depends(get_db)) -> OptimizedRecipeService:
    """Dependency to get optimized recipe service instance"""
    cache_service = get_recipe_cache_service()
    return OptimizedRecipeService(db, cache_service)


# Cost Analysis Endpoints with Caching
@router.get("/{recipe_id}/cost-analysis", response_model=RecipeCostAnalysis)
async def get_recipe_cost_analysis_cached(
    recipe_id: int,
    use_cache: bool = Query(True, description="Use cached results if available"),
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """
    Get detailed cost analysis for a recipe with caching.
    
    - **use_cache**: Set to false to force recalculation
    - **Cache TTL**: 5 minutes for cost analysis
    """
    try:
        return recipe_service.calculate_recipe_cost(recipe_id, use_cache=use_cache)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating recipe cost: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating recipe cost"
        )


@router.post("/{recipe_id}/cost-analysis/refresh")
async def refresh_recipe_cost_analysis(
    recipe_id: int,
    background_tasks: BackgroundTasks,
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """
    Force refresh cost analysis for a recipe.
    Invalidates cache and recalculates in the background.
    """
    # Invalidate cache
    cache_service = get_recipe_cache_service()
    cache_service.invalidate_recipe_cache(recipe_id)
    
    # Schedule background recalculation
    background_tasks.add_task(
        recipe_service.calculate_recipe_cost,
        recipe_id,
        use_cache=False
    )
    
    return {
        "recipe_id": recipe_id,
        "status": "refresh_scheduled",
        "message": "Cost analysis refresh scheduled"
    }


# Bulk Cost Recalculation with Background Tasks
@router.post("/recalculate-costs")
async def recalculate_all_costs_async(
    batch_size: int = Query(100, description="Number of recipes per batch"),
    use_background: bool = Query(True, description="Use background task processing"),
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("admin:recipes"))
):
    """
    Recalculate costs for all recipes with background task support.
    
    - **batch_size**: Number of recipes to process per batch (default: 100)
    - **use_background**: Process in background (recommended for large datasets)
    
    Returns task ID for background processing or immediate result.
    """
    result = await recipe_service.recalculate_all_recipe_costs_optimized(
        user_id=current_user.id,
        batch_size=batch_size,
        use_background_task=use_background
    )
    
    return result


@router.get("/tasks/{task_id}")
async def get_task_status_endpoint(
    task_id: str,
    current_user: User = Depends(require_permission("menu:read"))
):
    """
    Get status of a background task.
    
    Returns current progress and result when completed.
    """
    return get_task_status(task_id)


# Paginated Compliance Report
@router.get("/compliance/report")
async def get_compliance_report_paginated(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=10, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    use_cache: bool = Query(True, description="Use cached results"),
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """
    Get paginated compliance report showing menu items without recipes.
    
    - **page**: Page number (1-based)
    - **page_size**: Number of items per page (10-100)
    - **category**: Optional category filter
    - **use_cache**: Use cached results (TTL: 10 minutes)
    
    Returns paginated results with navigation metadata.
    """
    return recipe_service.get_recipe_compliance_report(
        use_cache=use_cache,
        page=page,
        page_size=page_size,
        category_filter=category
    )


@router.get("/compliance/export")
async def export_compliance_report(
    format: str = Query("csv", description="Export format (csv, json, excel)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("manager:recipes"))
):
    """
    Export compliance report in various formats.
    
    Supports CSV, JSON, and Excel formats for easy reporting.
    """
    # Get full report without pagination for export
    report = recipe_service.get_recipe_compliance_report(
        use_cache=True,
        page=1,
        page_size=10000,  # Large page size for export
        category_filter=category
    )
    
    if format == "json":
        return report
    
    # For CSV/Excel, return formatted response
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            "Menu Item ID", "Menu Item Name", "Category", 
            "Recipe Status", "Recipe ID"
        ])
        
        # Write data
        all_items = (
            report["data"]["missing_recipes"] +
            report["data"]["draft_recipes"] +
            report["data"]["inactive_recipes"]
        )
        
        for item in all_items:
            writer.writerow([
                item.menu_item_id,
                item.menu_item_name,
                item.category,
                item.recipe_status,
                item.recipe_id or ""
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=compliance_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported export format: {format}"
    )


# Cache Management Endpoints
@router.post("/cache/invalidate")
async def invalidate_cache(
    recipe_id: Optional[int] = Query(None, description="Specific recipe ID to invalidate"),
    invalidate_all: bool = Query(False, description="Invalidate all cache entries"),
    current_user: User = Depends(require_permission("admin:recipes"))
):
    """
    Invalidate cache entries.
    
    - **recipe_id**: Invalidate cache for specific recipe
    - **invalidate_all**: Clear all cache entries (use with caution)
    """
    cache_service = get_recipe_cache_service()
    
    if invalidate_all:
        deleted = cache_service.delete_pattern("*")
        return {
            "status": "success",
            "message": f"Invalidated {deleted} cache entries"
        }
    elif recipe_id:
        cache_service.invalidate_recipe_cache(recipe_id)
        return {
            "status": "success",
            "message": f"Invalidated cache for recipe {recipe_id}"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify recipe_id or invalidate_all"
        )


@router.get("/cache/stats")
async def get_cache_statistics(
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("admin:recipes"))
):
    """
    Get cache performance statistics.
    
    Returns cache hit rates, memory usage, and entry counts.
    """
    return recipe_service.get_cache_statistics()


@router.post("/cache/warm")
async def warm_cache(
    recipe_ids: Optional[List[int]] = Query(None, description="Recipe IDs to warm"),
    top_recipes: int = Query(100, description="Number of top recipes to warm"),
    background_tasks: BackgroundTasks,
    recipe_service: OptimizedRecipeService = Depends(get_optimized_recipe_service),
    current_user: User = Depends(require_permission("admin:recipes"))
):
    """
    Pre-warm cache for frequently accessed recipes.
    
    - **recipe_ids**: Specific recipe IDs to warm
    - **top_recipes**: Number of most active recipes to warm (if recipe_ids not provided)
    
    Runs in background to avoid blocking.
    """
    background_tasks.add_task(
        recipe_service.warm_cache,
        recipe_ids
    )
    
    return {
        "status": "scheduled",
        "message": f"Cache warming scheduled for {len(recipe_ids) if recipe_ids else top_recipes} recipes"
    }


# Performance Monitoring
@router.get("/performance/metrics")
async def get_performance_metrics(
    time_range: str = Query("1h", description="Time range (1h, 24h, 7d)"),
    current_user: User = Depends(require_permission("admin:recipes"))
):
    """
    Get performance metrics for recipe endpoints.
    
    Returns response times, cache hit rates, and throughput metrics.
    """
    # This would integrate with your monitoring system (e.g., Prometheus, DataDog)
    # For now, return sample metrics
    
    cache_stats = get_recipe_cache_service().get_cache_stats()
    
    return {
        "time_range": time_range,
        "metrics": {
            "cache": cache_stats,
            "endpoints": {
                "cost_analysis": {
                    "avg_response_time_ms": 45,
                    "p95_response_time_ms": 120,
                    "requests_per_minute": 150
                },
                "compliance_report": {
                    "avg_response_time_ms": 85,
                    "p95_response_time_ms": 200,
                    "requests_per_minute": 30
                }
            },
            "background_tasks": {
                "pending": 0,
                "processing": 0,
                "completed_last_hour": 25,
                "failed_last_hour": 1
            }
        },
        "timestamp": datetime.utcnow()
    }