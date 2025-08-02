# backend/modules/menu/routes/recipe_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from core.database import get_db
from core.auth import require_permission, User
from ..services.recipe_service import RecipeService
from ..schemas.recipe_schemas import (
    RecipeCreate, RecipeUpdate, RecipeResponse,
    RecipeIngredientCreate, RecipeIngredientUpdate, RecipeIngredientResponse,
    RecipeSearchParams, RecipeCostAnalysis, RecipeValidation,
    RecipeComplianceReport, MenuItemRecipeStatus,
    RecipeCloneRequest, RecipeHistoryResponse,
    RecipeNutritionCreate, RecipeNutritionUpdate, RecipeNutritionResponse,
    BulkRecipeUpdate
)

router = APIRouter(prefix="/recipes", tags=["Recipe Management"])


def get_recipe_service(db: Session = Depends(get_db)) -> RecipeService:
    """Dependency to get recipe service instance"""
    return RecipeService(db)


# Recipe CRUD Operations
@router.post("/", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe_data: RecipeCreate,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:create"))
):
    """Create a new recipe for a menu item"""
    recipe = recipe_service.create_recipe(recipe_data, current_user.id)
    return recipe


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get a recipe by ID"""
    recipe = recipe_service.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    return recipe


@router.get("/menu-item/{menu_item_id}", response_model=RecipeResponse)
async def get_recipe_by_menu_item(
    menu_item_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get recipe for a specific menu item"""
    recipe = recipe_service.get_recipe_by_menu_item(menu_item_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found for this menu item"
        )
    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdate,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Update recipe details"""
    recipe = recipe_service.update_recipe(recipe_id, recipe_data, current_user.id)
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:delete"))
):
    """Delete a recipe"""
    recipe_service.delete_recipe(recipe_id, current_user.id)


# Recipe Search and Listing
@router.get("/", response_model=dict)
async def search_recipes(
    query: Optional[str] = Query(None, description="Search query"),
    menu_item_id: Optional[int] = Query(None, description="Filter by menu item"),
    status: Optional[str] = Query(None, description="Filter by status"),
    complexity: Optional[str] = Query(None, description="Filter by complexity"),
    min_cost: Optional[float] = Query(None, ge=0, description="Minimum cost"),
    max_cost: Optional[float] = Query(None, ge=0, description="Maximum cost"),
    ingredient_id: Optional[int] = Query(None, description="Find recipes using specific ingredient"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", pattern=r'^(asc|desc)$'),
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Search and list recipes with filters"""
    params = RecipeSearchParams(
        query=query,
        menu_item_id=menu_item_id,
        status=status,
        complexity=complexity,
        min_cost=min_cost,
        max_cost=max_cost,
        ingredient_id=ingredient_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    recipes, total = recipe_service.search_recipes(params)
    
    return {
        "recipes": recipes,
        "total": total,
        "page": (offset // limit) + 1,
        "pages": (total + limit - 1) // limit if limit > 0 else 0
    }


# Recipe Ingredients Management
@router.put("/{recipe_id}/ingredients", response_model=RecipeResponse)
async def update_recipe_ingredients(
    recipe_id: int,
    ingredients: List[RecipeIngredientCreate],
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Update recipe ingredients (replaces all ingredients)"""
    recipe = recipe_service.update_recipe_ingredients(recipe_id, ingredients, current_user.id)
    return recipe


@router.post("/{recipe_id}/ingredients", response_model=RecipeIngredientResponse)
async def add_recipe_ingredient(
    recipe_id: int,
    ingredient: RecipeIngredientCreate,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Add a single ingredient to a recipe"""
    # Get current recipe
    recipe = recipe_service.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    
    # Add to existing ingredients
    current_ingredients = [
        RecipeIngredientCreate(
            inventory_id=ing.inventory_id,
            quantity=ing.quantity,
            unit=ing.unit,
            custom_unit=ing.custom_unit,
            preparation=ing.preparation,
            is_optional=ing.is_optional,
            notes=ing.notes,
            display_order=ing.display_order
        )
        for ing in recipe.ingredients
    ]
    current_ingredients.append(ingredient)
    
    # Update all ingredients
    updated_recipe = recipe_service.update_recipe_ingredients(recipe_id, current_ingredients, current_user.id)
    
    # Return the newly added ingredient
    return updated_recipe.ingredients[-1]


@router.delete("/{recipe_id}/ingredients/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recipe_ingredient(
    recipe_id: int,
    inventory_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Remove an ingredient from a recipe"""
    # Get current recipe
    recipe = recipe_service.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    
    # Filter out the ingredient to remove
    remaining_ingredients = [
        RecipeIngredientCreate(
            inventory_id=ing.inventory_id,
            quantity=ing.quantity,
            unit=ing.unit,
            custom_unit=ing.custom_unit,
            preparation=ing.preparation,
            is_optional=ing.is_optional,
            notes=ing.notes,
            display_order=ing.display_order
        )
        for ing in recipe.ingredients
        if ing.inventory_id != inventory_id
    ]
    
    if len(remaining_ingredients) == len(recipe.ingredients):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found in recipe"
        )
    
    # Update with remaining ingredients
    recipe_service.update_recipe_ingredients(recipe_id, remaining_ingredients, current_user.id)


# Recipe Cost Analysis
@router.get("/{recipe_id}/cost-analysis", response_model=RecipeCostAnalysis)
async def get_recipe_cost_analysis(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get detailed cost analysis for a recipe"""
    return recipe_service.calculate_recipe_cost(recipe_id)


@router.post("/recalculate-costs")
async def recalculate_all_costs(
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Recalculate costs for all recipes (admin only)"""
    # Additional permission check for admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can recalculate all recipe costs"
        )
    
    result = recipe_service.recalculate_all_recipe_costs(current_user.id)
    return result


# Recipe Validation
@router.get("/{recipe_id}/validate", response_model=RecipeValidation)
async def validate_recipe(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Validate a recipe for completeness and accuracy"""
    return recipe_service.validate_recipe(recipe_id)


# Recipe Compliance
@router.get("/compliance/report", response_model=RecipeComplianceReport)
async def get_compliance_report(
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get compliance report showing menu items without recipes"""
    return recipe_service.get_recipe_compliance_report()


@router.get("/compliance/missing", response_model=List[MenuItemRecipeStatus])
async def get_menu_items_without_recipes(
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get list of menu items that don't have recipes"""
    report = recipe_service.get_recipe_compliance_report()
    return report.missing_recipes


# Recipe Cloning
@router.post("/clone", response_model=RecipeResponse)
async def clone_recipe(
    clone_request: RecipeCloneRequest,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:create"))
):
    """Clone a recipe to another menu item"""
    recipe = recipe_service.clone_recipe(clone_request, current_user.id)
    return recipe


# Recipe History
@router.get("/{recipe_id}/history", response_model=List[RecipeHistoryResponse])
async def get_recipe_history(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get version history for a recipe"""
    return recipe_service.get_recipe_history(recipe_id)


# Bulk Operations
@router.put("/bulk/update", response_model=dict)
async def bulk_update_recipes(
    bulk_data: BulkRecipeUpdate,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Bulk update multiple recipes"""
    updated_count = 0
    errors = []
    
    for recipe_id in bulk_data.recipe_ids:
        try:
            recipe_service.update_recipe(recipe_id, bulk_data.updates, current_user.id)
            updated_count += 1
        except HTTPException as e:
            errors.append({
                "recipe_id": recipe_id,
                "error": e.detail
            })
    
    return {
        "updated": updated_count,
        "failed": len(errors),
        "errors": errors
    }


@router.put("/bulk/activate", response_model=dict)
async def bulk_activate_recipes(
    recipe_ids: List[int],
    active: bool = True,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Bulk activate or deactivate recipes"""
    updated_count = 0
    errors = []
    
    status = "active" if active else "inactive"
    update_data = RecipeUpdate(status=status)
    
    for recipe_id in recipe_ids:
        try:
            recipe_service.update_recipe(recipe_id, update_data, current_user.id)
            updated_count += 1
        except HTTPException as e:
            errors.append({
                "recipe_id": recipe_id,
                "error": e.detail
            })
    
    return {
        "updated": updated_count,
        "failed": len(errors),
        "errors": errors,
        "action": "activated" if active else "deactivated"
    }


# Public Endpoints (for customer-facing apps)
@router.get("/public/{recipe_id}/nutrition", response_model=dict)
async def get_public_recipe_nutrition(
    recipe_id: int,
    recipe_service: RecipeService = Depends(get_recipe_service)
):
    """Get nutritional information for a recipe (public)"""
    recipe = recipe_service.get_recipe_by_id(recipe_id)
    if not recipe or recipe.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    
    # Return basic nutrition info if available
    if hasattr(recipe, 'nutrition') and recipe.nutrition:
        return {
            "calories": recipe.nutrition.calories,
            "protein": recipe.nutrition.protein,
            "carbohydrates": recipe.nutrition.total_carbohydrates,
            "fat": recipe.nutrition.total_fat,
            "allergens": recipe.allergen_notes
        }
    
    return {
        "message": "Nutritional information not available",
        "allergens": recipe.allergen_notes
    }


# Admin endpoints
@router.post("/{recipe_id}/approve")
async def approve_recipe(
    recipe_id: int,
    notes: Optional[str] = None,
    recipe_service: RecipeService = Depends(get_recipe_service),
    current_user: User = Depends(require_permission("menu:approve"))
):
    """Approve a recipe (manager/admin only)"""
    recipe = recipe_service.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    
    # Update recipe
    update_data = RecipeUpdate(status="active")
    recipe = recipe_service.update_recipe(recipe_id, update_data, current_user.id)
    
    # Update approval fields
    db = next(get_db())
    recipe.approved_by = current_user.id
    recipe.approved_at = datetime.utcnow()
    db.commit()
    
    return {
        "message": "Recipe approved successfully",
        "recipe_id": recipe.id,
        "approved_by": current_user.id,
        "approved_at": recipe.approved_at
    }