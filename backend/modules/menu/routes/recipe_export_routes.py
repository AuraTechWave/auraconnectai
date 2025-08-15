# backend/modules/menu/routes/recipe_export_routes.py

"""
Export routes for recipe management with full compliance dumps.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import logging

from ....core.database import get_db
from ....core.auth import get_current_user
from ..services.recipe_export_service import RecipeExportService
from ..exceptions.recipe_exceptions import RecipeExportError
from ..utils.performance_utils import timing_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/menu/recipes/export", tags=["recipe-export"])


@router.get("/compliance")
@timing_logger("export_compliance_endpoint", warning_threshold_ms=3000)
async def export_compliance_report(
    format: str = Query("json", regex="^(json|csv)$", description="Export format"),
    include_costs: bool = Query(True, description="Include cost analysis"),
    include_nutritional: bool = Query(False, description="Include nutritional data"),
    category: Optional[str] = Query(None, description="Filter by menu category"),
    max_items: int = Query(
        5000, ge=100, le=10000, description="Maximum items to export"
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Export comprehensive compliance report with full data dump.

    This endpoint provides a complete export of menu items and their recipe compliance status,
    including detailed information about missing recipes, draft recipes, and cost analysis.

    **Export Formats:**
    - **JSON**: Structured format with summary, compliance issues, and detailed data
    - **CSV**: Flattened format suitable for spreadsheet analysis

    **Performance Note:** Large exports may take several seconds. Consider using pagination
    for very large datasets or increase the timeout on your client.

    **Access Control:** Requires admin or manager role.
    """
    # Check permissions
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions to export compliance data"
        )

    try:
        export_service = RecipeExportService(db)
        result = export_service.export_compliance_report(
            format=format,
            include_costs=include_costs,
            include_nutritional=include_nutritional,
            category_filter=category,
            max_items=max_items,
        )

        # Set appropriate headers based on format
        if format == "csv":
            headers = {
                "Content-Disposition": f"attachment; filename=recipe_compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
                "Content-Type": "text/csv",
            }
        else:
            headers = {
                "Content-Disposition": f"attachment; filename=recipe_compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                "Content-Type": "application/json",
            }

        return Response(
            content=result["data"], headers=headers, media_type=headers["Content-Type"]
        )

    except RecipeExportError as e:
        logger.error(f"Export error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/recipes")
@timing_logger("export_recipes_endpoint")
async def export_recipe_details(
    recipe_ids: List[int] = Query(..., description="List of recipe IDs to export"),
    format: str = Query("json", regex="^(json|csv)$", description="Export format"),
    include_history: bool = Query(False, description="Include version history"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Export detailed recipe information for specific recipes.

    This endpoint exports comprehensive recipe data including:
    - Recipe metadata and configuration
    - Complete ingredient lists with quantities
    - Sub-recipe dependencies
    - Cost analysis breakdown
    - Version information

    **Use Cases:**
    - Backup specific recipes
    - Share recipes between locations
    - Generate recipe cards for kitchen staff
    - Cost analysis reports

    **Access Control:** Requires authentication.
    """
    if len(recipe_ids) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 recipes can be exported at once"
        )

    try:
        export_service = RecipeExportService(db)
        result = export_service.export_recipe_details(
            recipe_ids=recipe_ids, format=format, include_history=include_history
        )

        # Set appropriate headers
        if format == "csv":
            headers = {
                "Content-Disposition": f"attachment; filename=recipes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
                "Content-Type": "text/csv",
            }
        else:
            headers = {
                "Content-Disposition": f"attachment; filename=recipes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                "Content-Type": "application/json",
            }

        return Response(
            content=result["data"], headers=headers, media_type=headers["Content-Type"]
        )

    except Exception as e:
        logger.error(f"Recipe export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/summary")
async def get_export_summary(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """
    Get a summary of available export data without performing the actual export.

    This endpoint provides a quick overview of:
    - Total menu items available for export
    - Compliance statistics
    - Available categories
    - Estimated export sizes

    Use this to preview what will be included in exports.
    """
    from sqlalchemy import func
    from core.menu_models import MenuItem
    from ..models.recipe_models import Recipe

    # Get statistics
    total_menu_items = (
        db.query(MenuItem)
        .filter(MenuItem.is_active == True, MenuItem.deleted_at.is_(None))
        .count()
    )

    items_with_recipes = (
        db.query(MenuItem)
        .join(Recipe)
        .filter(
            MenuItem.is_active == True,
            MenuItem.deleted_at.is_(None),
            Recipe.deleted_at.is_(None),
        )
        .count()
    )

    # Get categories
    categories = (
        db.query(MenuItem.category, func.count(MenuItem.id))
        .filter(MenuItem.is_active == True, MenuItem.deleted_at.is_(None))
        .group_by(MenuItem.category)
        .all()
    )

    return {
        "summary": {
            "total_menu_items": total_menu_items,
            "items_with_recipes": items_with_recipes,
            "items_without_recipes": total_menu_items - items_with_recipes,
            "compliance_percentage": (
                (items_with_recipes / total_menu_items * 100)
                if total_menu_items > 0
                else 0
            ),
        },
        "categories": [{"name": cat[0], "count": cat[1]} for cat in categories],
        "export_info": {
            "max_items_per_export": 10000,
            "available_formats": ["json", "csv"],
            "estimated_json_size_mb": round(
                total_menu_items * 0.005, 2
            ),  # ~5KB per item
            "estimated_csv_size_mb": round(
                total_menu_items * 0.002, 2
            ),  # ~2KB per item
        },
    }
