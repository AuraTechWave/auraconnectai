# backend/modules/menu/services/recipe_service_optimized.py

"""
Optimized Recipe Service with enhanced caching and pagination support.
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, text
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from math import ceil
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from ..models.recipe_models import Recipe, RecipeIngredient, RecipeStatus
from ..schemas.recipe_schemas import (
    RecipeCostAnalysis, RecipeComplianceReport, 
    MenuItemRecipeStatus
)
from ..utils.pagination_utils import PaginatedResponse
from .recipe_cache_service import get_recipe_cache_service
from .recipe_service import RecipeService
from core.menu_models import MenuItem
from core.inventory_models import Inventory
from fastapi import HTTPException, status
from ..utils.performance_utils import ParallelExecutor, timing_logger
from ..exceptions.recipe_exceptions import RecipePerformanceError, RecipeErrorCode

logger = logging.getLogger(__name__)


class OptimizedRecipeService(RecipeService):
    """
    Enhanced Recipe Service with performance optimizations.
    Extends the base RecipeService with caching and pagination.
    """
    
    def __init__(self, db: Session, cache_service=None):
        super().__init__(db)
        self.cache_service = cache_service or get_recipe_cache_service()
    
    @timing_logger("calculate_recipe_cost", warning_threshold_ms=300, error_threshold_ms=1000)
    def calculate_recipe_cost(self, recipe_id: int, use_cache: bool = True) -> RecipeCostAnalysis:
        """
        Calculate recipe cost with enhanced caching.
        
        Args:
            recipe_id: ID of the recipe
            use_cache: Whether to use cached results
            
        Returns:
            RecipeCostAnalysis with detailed cost breakdown
        """
        # Try cache first
        if use_cache:
            cached_result = self.cache_service.get('cost_analysis', recipe_id)
            if cached_result:
                return RecipeCostAnalysis(**cached_result)
        
        # Fetch recipe with optimized query
        recipe = self.db.query(Recipe).options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.inventory_item),
            joinedload(Recipe.sub_recipes).joinedload(RecipeIngredient.sub_recipe)
        ).filter(Recipe.id == recipe_id).first()
        
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipe not found"
            )
        
        # Calculate costs
        ingredient_costs = []
        total_ingredient_cost = 0.0
        
        for ingredient in recipe.ingredients:
            unit_cost = ingredient.inventory_item.unit_cost or 0.0
            total_cost = unit_cost * ingredient.quantity
            
            ingredient_costs.append({
                "inventory_id": ingredient.inventory_id,
                "name": ingredient.inventory_item.name,
                "quantity": ingredient.quantity,
                "unit": ingredient.unit,
                "unit_cost": unit_cost,
                "total_cost": total_cost
            })
            total_ingredient_cost += total_cost
        
        # Calculate sub-recipe costs
        sub_recipe_costs = []
        total_sub_recipe_cost = 0.0
        
        for sub_recipe_link in recipe.sub_recipes:
            # Recursive calculation with caching
            sub_cost_analysis = self.calculate_recipe_cost(
                sub_recipe_link.sub_recipe_id, 
                use_cache=True
            )
            
            sub_total = sub_cost_analysis.total_cost * sub_recipe_link.quantity
            sub_recipe_costs.append({
                "sub_recipe_id": sub_recipe_link.sub_recipe_id,
                "name": sub_recipe_link.sub_recipe.name,
                "quantity": sub_recipe_link.quantity,
                "unit_cost": sub_cost_analysis.total_cost,
                "total_cost": sub_total
            })
            total_sub_recipe_cost += sub_total
        
        # Build response
        total_cost = total_ingredient_cost + total_sub_recipe_cost
        cost_per_serving = total_cost / max(recipe.yield_quantity, 1)
        
        # Calculate margins if menu item has price
        suggested_price = None
        profit_margin = None
        markup_percentage = None
        
        if recipe.menu_item and recipe.menu_item.price:
            menu_price = float(recipe.menu_item.price)
            suggested_price = menu_price
            profit_margin = menu_price - cost_per_serving
            if cost_per_serving > 0:
                markup_percentage = (profit_margin / cost_per_serving) * 100
        
        result = RecipeCostAnalysis(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            total_cost=total_cost,
            cost_per_serving=cost_per_serving,
            yield_quantity=recipe.yield_quantity,
            ingredient_costs=ingredient_costs,
            sub_recipe_costs=sub_recipe_costs,
            total_ingredient_cost=total_ingredient_cost,
            total_sub_recipe_cost=total_sub_recipe_cost,
            last_calculated=datetime.utcnow(),
            currency="USD",
            suggested_price=suggested_price,
            profit_margin=profit_margin,
            markup_percentage=markup_percentage
        )
        
        # Cache the result
        self.cache_service.set('cost_analysis', result.dict(), recipe_id)
        
        return result
    
    @timing_logger("compliance_report", warning_threshold_ms=500, error_threshold_ms=2000)
    def get_recipe_compliance_report(
        self, 
        use_cache: bool = True,
        page: int = 1,
        page_size: int = 50,
        category_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated compliance report with caching.
        
        Args:
            use_cache: Whether to use cached results
            page: Page number (1-based)
            page_size: Items per page
            category_filter: Optional category filter
            
        Returns:
            Paginated compliance report
        """
        cache_key_suffix = f"{page}:{page_size}:{category_filter or 'all'}"
        
        # Try cache first
        if use_cache:
            cached_result = self.cache_service.get('compliance_report', cache_key_suffix)
            if cached_result:
                return cached_result
        
        # Build query with filters
        query = self.db.query(MenuItem).filter(
            MenuItem.is_active == True,
            MenuItem.deleted_at.is_(None)
        )
        
        if category_filter:
            query = query.filter(MenuItem.category == category_filter)
        
        # Get total count
        total_items = query.count()
        
        # Calculate pagination
        total_pages = ceil(total_items / page_size)
        offset = (page - 1) * page_size
        
        # Get paginated items
        menu_items = query.offset(offset).limit(page_size).options(
            joinedload(MenuItem.recipe)
        ).all()
        
        # Process items
        items_with_recipes = 0
        missing_recipes = []
        draft_recipes = []
        inactive_recipes = []
        
        for item in menu_items:
            if item.recipe:
                items_with_recipes += 1
                if item.recipe.status == RecipeStatus.DRAFT:
                    draft_recipes.append(MenuItemRecipeStatus(
                        menu_item_id=item.id,
                        menu_item_name=item.name,
                        category=item.category,
                        recipe_status="draft",
                        recipe_id=item.recipe.id
                    ))
                elif not item.recipe.is_active:
                    inactive_recipes.append(MenuItemRecipeStatus(
                        menu_item_id=item.id,
                        menu_item_name=item.name,
                        category=item.category,
                        recipe_status="inactive",
                        recipe_id=item.recipe.id
                    ))
            else:
                missing_recipes.append(MenuItemRecipeStatus(
                    menu_item_id=item.id,
                    menu_item_name=item.name,
                    category=item.category,
                    recipe_status="missing"
                ))
        
        # Calculate compliance percentage
        compliance_percentage = (items_with_recipes / len(menu_items) * 100) if menu_items else 0
        
        result = {
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "summary": {
                "total_menu_items": total_items,
                "items_with_recipes": items_with_recipes,
                "items_without_recipes": len(missing_recipes),
                "compliance_percentage": compliance_percentage,
                "draft_recipes_count": len(draft_recipes),
                "inactive_recipes_count": len(inactive_recipes)
            },
            "data": {
                "missing_recipes": missing_recipes,
                "draft_recipes": draft_recipes,
                "inactive_recipes": inactive_recipes
            },
            "filters": {
                "category": category_filter
            },
            "generated_at": datetime.utcnow()
        }
        
        # Cache the result
        self.cache_service.set('compliance_report', result, cache_key_suffix, ttl=600)
        
        return result
    
    @timing_logger("bulk_cost_recalculation", warning_threshold_ms=5000, error_threshold_ms=30000)
    async def recalculate_all_recipe_costs_optimized(
        self, 
        user_id: int,
        batch_size: int = 100,
        use_background_task: bool = True
    ) -> Dict[str, Any]:
        """
        Optimized bulk cost recalculation with batching and optional background processing.
        Uses ParallelExecutor for CPU-bound operations.
        
        Args:
            user_id: ID of the user triggering recalculation
            batch_size: Number of recipes to process per batch
            use_background_task: Whether to use background task
            
        Returns:
            Task info or immediate result
        """
        if use_background_task:
            # Import here to avoid circular imports
            from ..tasks.recipe_cost_tasks import bulk_recalculate_costs_async
            
            # Schedule background task
            task = bulk_recalculate_costs_async.delay(
                recipe_ids=None,
                user_id=user_id,
                batch_size=batch_size
            )
            
            return {
                "task_id": task.id,
                "status": "scheduled",
                "message": "Bulk cost recalculation scheduled",
                "check_status_url": f"/api/v1/recipes/tasks/{task.id}"
            }
        else:
            # Perform synchronous calculation with parallelization
            recipes = self.db.query(Recipe).filter(
                Recipe.deleted_at.is_(None),
                Recipe.is_active == True
            ).all()
            
            total_recipes = len(recipes)
            updated_count = 0
            failed_count = 0
            
            # Use ParallelExecutor for CPU-bound cost calculations
            with ParallelExecutor(max_workers=4, chunk_size=batch_size) as executor:
                # Define function to calculate cost for a recipe
                def calculate_cost_for_recipe(recipe):
                    try:
                        self.calculate_recipe_cost(recipe.id, use_cache=False)
                        return True
                    except Exception as e:
                        logger.error(f"Error calculating cost for recipe {recipe.id}: {str(e)}")
                        return False
                
                # Process recipes in parallel
                results = executor.parallel_map(
                    calculate_cost_for_recipe,
                    recipes,
                    timeout=300  # 5 minute timeout for all operations
                )
                
                # Count successes and failures
                for result in results:
                    if isinstance(result, bool) and result:
                        updated_count += 1
                    else:
                        failed_count += 1
            
            # Check if operation took too long
            if updated_count + failed_count < total_recipes:
                raise RecipePerformanceError(
                    error_code=RecipeErrorCode.OPERATION_TIMEOUT,
                    message="Bulk recalculation timed out",
                    operation="bulk_cost_recalculation",
                    threshold_ms=300000  # 5 minutes
                )
            
            # Invalidate compliance cache
            self.cache_service.invalidate_compliance_cache()
            
            return {
                "total_recipes": total_recipes,
                "updated": updated_count,
                "failed": failed_count,
                "timestamp": datetime.utcnow()
            }
    
    @timing_logger("warm_cache", warning_threshold_ms=2000)
    def warm_cache(self, recipe_ids: Optional[List[int]] = None):
        """
        Pre-warm cache for frequently accessed recipes using parallel processing.
        
        Args:
            recipe_ids: List of recipe IDs to warm (None for top recipes)
        """
        if not recipe_ids:
            # Get top 100 most active recipes
            top_recipes = self.db.query(Recipe.id).filter(
                Recipe.deleted_at.is_(None),
                Recipe.is_active == True
            ).order_by(Recipe.updated_at.desc()).limit(100).all()
            
            recipe_ids = [r[0] for r in top_recipes]
        
        # Warm cache using ParallelExecutor
        with ParallelExecutor(max_workers=4, chunk_size=25) as executor:
            def warm_single_recipe(recipe_id):
                try:
                    self.calculate_recipe_cost(recipe_id, use_cache=False)
                    return True
                except Exception as e:
                    logger.warning(f"Cache warming error for recipe {recipe_id}: {e}")
                    return False
            
            # Process all recipes in parallel
            results = executor.parallel_map(
                warm_single_recipe,
                recipe_ids,
                timeout=60  # 1 minute timeout
            )
            
            # Log statistics
            success_count = sum(1 for r in results if r is True)
            logger.info(
                f"Cache warming completed: {success_count}/{len(recipe_ids)} recipes warmed successfully"
            )
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.cache_service.get_cache_stats()