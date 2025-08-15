# backend/modules/menu/services/recipe_export_service.py

"""
Recipe Export Service for generating comprehensive reports.
Supports CSV and JSON exports with full compliance data.
"""

import csv
import json
import io
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
import logging

from ..models.recipe_models import Recipe, RecipeIngredient, RecipeStatus
from ..schemas.recipe_schemas import RecipeCostAnalysis
from .recipe_service_optimized import OptimizedRecipeService
from core.menu_models import MenuItem
from core.inventory_models import Inventory
from ..utils.performance_utils import timing_logger, ParallelExecutor
from ..exceptions.recipe_exceptions import RecipeExportError, RecipeErrorCode

logger = logging.getLogger(__name__)


class RecipeExportService:
    """Service for exporting recipe and compliance data"""

    def __init__(
        self, db: Session, recipe_service: Optional[OptimizedRecipeService] = None
    ):
        self.db = db
        self.recipe_service = recipe_service or OptimizedRecipeService(db)

    @timing_logger("export_compliance_report", warning_threshold_ms=3000)
    def export_compliance_report(
        self,
        format: str = "json",
        include_costs: bool = True,
        include_nutritional: bool = False,
        category_filter: Optional[str] = None,
        max_items: int = 10000,
    ) -> Dict[str, Any]:
        """
        Export comprehensive compliance report with full data dump.

        Args:
            format: Export format ('json' or 'csv')
            include_costs: Include cost analysis in export
            include_nutritional: Include nutritional data
            category_filter: Filter by menu category
            max_items: Maximum items to export

        Returns:
            Export data with metadata
        """
        if format not in ["json", "csv"]:
            raise RecipeExportError(
                error_code=RecipeErrorCode.INVALID_EXPORT_FORMAT,
                message=f"Invalid export format: {format}",
                format=format,
            )

        # Get all menu items with recipes
        query = (
            self.db.query(MenuItem)
            .options(
                joinedload(MenuItem.recipe)
                .joinedload(Recipe.ingredients)
                .joinedload(RecipeIngredient.inventory_item)
            )
            .filter(MenuItem.is_active == True, MenuItem.deleted_at.is_(None))
        )

        if category_filter:
            query = query.filter(MenuItem.category == category_filter)

        menu_items = query.limit(max_items).all()

        # Check export size
        if len(menu_items) == max_items:
            logger.warning(f"Export limited to {max_items} items")

        # Build comprehensive data
        export_data = []
        missing_recipes = []
        draft_recipes = []
        inactive_recipes = []
        cost_errors = []

        # Process items in parallel for performance
        with ParallelExecutor(max_workers=4, chunk_size=100) as executor:

            def process_menu_item(item):
                item_data = {
                    "menu_item_id": item.id,
                    "menu_item_name": item.name,
                    "category": item.category,
                    "price": float(item.price) if item.price else None,
                    "is_active": item.is_active,
                    "created_at": (
                        item.created_at.isoformat() if item.created_at else None
                    ),
                    "updated_at": (
                        item.updated_at.isoformat() if item.updated_at else None
                    ),
                }

                if item.recipe:
                    recipe = item.recipe
                    item_data.update(
                        {
                            "recipe_id": recipe.id,
                            "recipe_name": recipe.name,
                            "recipe_status": recipe.status.value,
                            "recipe_active": recipe.is_active,
                            "yield_quantity": recipe.yield_quantity,
                            "yield_unit": recipe.yield_unit,
                            "prep_time_minutes": recipe.prep_time_minutes,
                            "cook_time_minutes": recipe.cook_time_minutes,
                            "total_time_minutes": recipe.total_time_minutes,
                            "difficulty_level": recipe.difficulty_level,
                            "cuisine_type": recipe.cuisine_type,
                            "dietary_flags": recipe.dietary_flags,
                            "allergen_info": recipe.allergen_info,
                            "storage_instructions": recipe.storage_instructions,
                            "recipe_version": recipe.version,
                            "recipe_created_at": (
                                recipe.created_at.isoformat()
                                if recipe.created_at
                                else None
                            ),
                            "recipe_updated_at": (
                                recipe.updated_at.isoformat()
                                if recipe.updated_at
                                else None
                            ),
                        }
                    )

                    # Include ingredient details
                    ingredients = []
                    for ing in recipe.ingredients:
                        ingredients.append(
                            {
                                "ingredient_name": (
                                    ing.inventory_item.name
                                    if ing.inventory_item
                                    else "Unknown"
                                ),
                                "quantity": ing.quantity,
                                "unit": ing.unit,
                                "notes": ing.notes,
                            }
                        )
                    item_data["ingredients"] = ingredients
                    item_data["ingredient_count"] = len(ingredients)

                    # Include cost analysis if requested
                    if include_costs:
                        try:
                            cost_analysis = self.recipe_service.calculate_recipe_cost(
                                recipe.id, use_cache=True
                            )
                            item_data.update(
                                {
                                    "total_cost": cost_analysis.total_cost,
                                    "cost_per_serving": cost_analysis.cost_per_serving,
                                    "profit_margin": cost_analysis.profit_margin,
                                    "markup_percentage": cost_analysis.markup_percentage,
                                    "cost_calculated_at": cost_analysis.last_calculated.isoformat(),
                                }
                            )
                        except Exception as e:
                            logger.error(
                                f"Cost calculation failed for recipe {recipe.id}: {e}"
                            )
                            item_data["cost_error"] = str(e)
                            cost_errors.append(item.id)

                    # Include nutritional data if requested
                    if include_nutritional and hasattr(recipe, "nutritional_info"):
                        item_data["nutritional_info"] = recipe.nutritional_info

                    # Categorize compliance issues
                    if recipe.status == RecipeStatus.DRAFT:
                        draft_recipes.append(item.id)
                        item_data["compliance_issue"] = "draft_recipe"
                    elif not recipe.is_active:
                        inactive_recipes.append(item.id)
                        item_data["compliance_issue"] = "inactive_recipe"
                    else:
                        item_data["compliance_issue"] = None
                else:
                    # No recipe
                    item_data.update(
                        {
                            "recipe_id": None,
                            "recipe_name": None,
                            "recipe_status": "missing",
                            "compliance_issue": "missing_recipe",
                        }
                    )
                    missing_recipes.append(item.id)

                return item_data

            # Process all items in parallel
            results = executor.parallel_map(process_menu_item, menu_items)
            export_data = [r for r in results if not isinstance(r, Exception)]

        # Generate export based on format
        if format == "json":
            output = self._generate_json_export(
                export_data,
                missing_recipes,
                draft_recipes,
                inactive_recipes,
                cost_errors,
            )
        else:  # csv
            output = self._generate_csv_export(export_data)

        return {
            "format": format,
            "data": output,
            "metadata": {
                "total_items": len(export_data),
                "missing_recipes": len(missing_recipes),
                "draft_recipes": len(draft_recipes),
                "inactive_recipes": len(inactive_recipes),
                "cost_errors": len(cost_errors) if include_costs else None,
                "export_timestamp": datetime.utcnow().isoformat(),
                "filters": {
                    "category": category_filter,
                    "include_costs": include_costs,
                    "include_nutritional": include_nutritional,
                },
            },
        }

    def _generate_json_export(
        self,
        data: List[Dict[str, Any]],
        missing_recipes: List[int],
        draft_recipes: List[int],
        inactive_recipes: List[int],
        cost_errors: List[int],
    ) -> str:
        """Generate JSON export with full structure"""
        export = {
            "export_info": {
                "generated_at": datetime.utcnow().isoformat(),
                "total_items": len(data),
                "format": "json",
                "version": "1.0",
            },
            "summary": {
                "compliance": {
                    "total_menu_items": len(data),
                    "items_with_recipes": len(data) - len(missing_recipes),
                    "missing_recipes": len(missing_recipes),
                    "draft_recipes": len(draft_recipes),
                    "inactive_recipes": len(inactive_recipes),
                    "compliance_percentage": (
                        ((len(data) - len(missing_recipes)) / len(data) * 100)
                        if data
                        else 0
                    ),
                },
                "cost_analysis": {
                    "items_with_costs": len([d for d in data if "total_cost" in d]),
                    "cost_calculation_errors": len(cost_errors),
                },
            },
            "compliance_issues": {
                "missing_recipe_ids": missing_recipes,
                "draft_recipe_ids": draft_recipes,
                "inactive_recipe_ids": inactive_recipes,
                "cost_error_ids": cost_errors,
            },
            "data": data,
        }

        return json.dumps(export, indent=2, default=str)

    def _generate_csv_export(self, data: List[Dict[str, Any]]) -> str:
        """Generate CSV export with flattened structure"""
        if not data:
            return ""

        # Flatten nested data for CSV
        flattened_data = []
        for item in data:
            flat_item = {
                "menu_item_id": item.get("menu_item_id"),
                "menu_item_name": item.get("menu_item_name"),
                "category": item.get("category"),
                "price": item.get("price"),
                "recipe_id": item.get("recipe_id"),
                "recipe_name": item.get("recipe_name"),
                "recipe_status": item.get("recipe_status"),
                "compliance_issue": item.get("compliance_issue"),
                "ingredient_count": item.get("ingredient_count", 0),
                "total_cost": item.get("total_cost"),
                "cost_per_serving": item.get("cost_per_serving"),
                "profit_margin": item.get("profit_margin"),
                "markup_percentage": item.get("markup_percentage"),
                "yield_quantity": item.get("yield_quantity"),
                "prep_time_minutes": item.get("prep_time_minutes"),
                "cook_time_minutes": item.get("cook_time_minutes"),
                "difficulty_level": item.get("difficulty_level"),
                "cuisine_type": item.get("cuisine_type"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }

            # Add ingredient summary
            if "ingredients" in item and item["ingredients"]:
                ingredients_summary = "; ".join(
                    [
                        f"{ing['ingredient_name']} ({ing['quantity']} {ing['unit']})"
                        for ing in item["ingredients"][:5]  # Limit to first 5
                    ]
                )
                if len(item["ingredients"]) > 5:
                    ingredients_summary += (
                        f"... and {len(item['ingredients']) - 5} more"
                    )
                flat_item["ingredients_summary"] = ingredients_summary

            flattened_data.append(flat_item)

        # Generate CSV
        output = io.StringIO()
        if flattened_data:
            writer = csv.DictWriter(output, fieldnames=flattened_data[0].keys())
            writer.writeheader()
            writer.writerows(flattened_data)

        return output.getvalue()

    @timing_logger("export_recipe_details")
    def export_recipe_details(
        self, recipe_ids: List[int], format: str = "json", include_history: bool = False
    ) -> Dict[str, Any]:
        """
        Export detailed recipe information for specific recipes.

        Args:
            recipe_ids: List of recipe IDs to export
            format: Export format
            include_history: Include version history

        Returns:
            Detailed recipe export
        """
        recipes = (
            self.db.query(Recipe)
            .options(
                joinedload(Recipe.ingredients).joinedload(
                    RecipeIngredient.inventory_item
                ),
                joinedload(Recipe.sub_recipes).joinedload(RecipeIngredient.sub_recipe),
                joinedload(Recipe.menu_item),
            )
            .filter(Recipe.id.in_(recipe_ids))
            .all()
        )

        recipe_data = []
        for recipe in recipes:
            data = {
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "menu_item": (
                    {"id": recipe.menu_item.id, "name": recipe.menu_item.name}
                    if recipe.menu_item
                    else None
                ),
                "status": recipe.status.value,
                "is_active": recipe.is_active,
                "yield_quantity": recipe.yield_quantity,
                "yield_unit": recipe.yield_unit,
                "prep_time_minutes": recipe.prep_time_minutes,
                "cook_time_minutes": recipe.cook_time_minutes,
                "total_time_minutes": recipe.total_time_minutes,
                "difficulty_level": recipe.difficulty_level,
                "cuisine_type": recipe.cuisine_type,
                "dietary_flags": recipe.dietary_flags,
                "allergen_info": recipe.allergen_info,
                "instructions": recipe.instructions,
                "notes": recipe.notes,
                "storage_instructions": recipe.storage_instructions,
                "version": recipe.version,
                "created_at": (
                    recipe.created_at.isoformat() if recipe.created_at else None
                ),
                "updated_at": (
                    recipe.updated_at.isoformat() if recipe.updated_at else None
                ),
                "ingredients": [
                    {
                        "id": ing.id,
                        "inventory_item": (
                            {
                                "id": ing.inventory_item.id,
                                "name": ing.inventory_item.name,
                                "unit_cost": ing.inventory_item.unit_cost,
                            }
                            if ing.inventory_item
                            else None
                        ),
                        "quantity": ing.quantity,
                        "unit": ing.unit,
                        "notes": ing.notes,
                        "is_optional": ing.is_optional,
                    }
                    for ing in recipe.ingredients
                ],
                "sub_recipes": [
                    {
                        "id": sub.sub_recipe_id,
                        "name": sub.sub_recipe.name,
                        "quantity": sub.quantity,
                    }
                    for sub in recipe.sub_recipes
                ],
            }

            # Add cost analysis
            try:
                cost_analysis = self.recipe_service.calculate_recipe_cost(
                    recipe.id, use_cache=True
                )
                data["cost_analysis"] = {
                    "total_cost": cost_analysis.total_cost,
                    "cost_per_serving": cost_analysis.cost_per_serving,
                    "ingredient_costs": cost_analysis.ingredient_costs,
                    "sub_recipe_costs": cost_analysis.sub_recipe_costs,
                }
            except Exception as e:
                data["cost_analysis"] = {"error": str(e)}

            recipe_data.append(data)

        if format == "json":
            return {
                "format": "json",
                "data": json.dumps(recipe_data, indent=2, default=str),
                "metadata": {
                    "recipe_count": len(recipe_data),
                    "export_timestamp": datetime.utcnow().isoformat(),
                },
            }
        else:
            # CSV format - simplified version
            output = io.StringIO()
            if recipe_data:
                # Flatten for CSV
                csv_data = []
                for recipe in recipe_data:
                    csv_data.append(
                        {
                            "recipe_id": recipe["id"],
                            "recipe_name": recipe["name"],
                            "menu_item": (
                                recipe["menu_item"]["name"]
                                if recipe["menu_item"]
                                else None
                            ),
                            "status": recipe["status"],
                            "ingredient_count": len(recipe["ingredients"]),
                            "total_cost": recipe.get("cost_analysis", {}).get(
                                "total_cost"
                            ),
                            "cost_per_serving": recipe.get("cost_analysis", {}).get(
                                "cost_per_serving"
                            ),
                        }
                    )

                writer = csv.DictWriter(output, fieldnames=csv_data[0].keys())
                writer.writeheader()
                writer.writerows(csv_data)

            return {
                "format": "csv",
                "data": output.getvalue(),
                "metadata": {
                    "recipe_count": len(recipe_data),
                    "export_timestamp": datetime.utcnow().isoformat(),
                },
            }
