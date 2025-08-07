# backend/modules/menu/services/recipe_service_enhanced.py

"""
Enhanced recipe service methods for updating sub-recipes with circular dependency validation.
"""

from typing import List
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import HTTPException, status

from ..models.recipe_models import Recipe, RecipeSubRecipe
from ..schemas.recipe_schemas import RecipeSubRecipeCreate
from .recipe_circular_validation import RecipeCircularValidator, CircularDependencyError


def update_recipe_sub_recipes(
    db: Session,
    recipe_id: int, 
    sub_recipes: List[RecipeSubRecipeCreate], 
    user_id: int,
    recipe_service_instance=None
) -> Recipe:
    """
    Update recipe sub-recipes with circular dependency validation.
    This replaces all existing sub-recipes.
    
    Args:
        db: Database session
        recipe_id: The recipe to update
        sub_recipes: List of new sub-recipes
        user_id: User making the update
        recipe_service_instance: Optional RecipeService instance for history tracking
        
    Returns:
        Updated recipe
        
    Raises:
        HTTPException: For various validation errors
    """
    # Get the recipe
    recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.deleted_at.is_(None)
    ).first()
    
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    
    # Initialize validator
    validator = RecipeCircularValidator(db)
    
    # Prepare sub-recipe data for validation
    sub_recipe_data = [
        {'sub_recipe_id': sub.sub_recipe_id, 'quantity': sub.quantity}
        for sub in sub_recipes
    ]
    
    # Validate all sub-recipes
    try:
        validator.validate_batch_sub_recipes(recipe_id, sub_recipe_data)
    except CircularDependencyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Get existing sub-recipes for comparison
    existing_sub_recipes = db.query(RecipeSubRecipe).filter(
        RecipeSubRecipe.parent_recipe_id == recipe_id
    ).all()
    
    # Delete existing sub-recipes
    db.query(RecipeSubRecipe).filter(
        RecipeSubRecipe.parent_recipe_id == recipe_id
    ).delete()
    
    # Add new sub-recipes and calculate total cost
    total_sub_recipe_cost = 0.0
    new_sub_recipe_links = []
    
    for sub_data in sub_recipes:
        # Get the sub-recipe
        sub_recipe = db.query(Recipe).filter(
            Recipe.id == sub_data.sub_recipe_id
        ).first()
        
        # Create the link
        sub_recipe_link = RecipeSubRecipe(
            parent_recipe_id=recipe_id,
            created_by=user_id,
            **sub_data.dict()
        )
        db.add(sub_recipe_link)
        new_sub_recipe_links.append(sub_recipe_link)
        
        # Add to total cost
        if sub_recipe.total_cost:
            total_sub_recipe_cost += sub_recipe.total_cost * sub_data.quantity
    
    # Update recipe total cost
    # Get ingredient cost
    ingredient_cost = sum(
        ing.total_cost or 0 
        for ing in recipe.ingredients 
        if ing.is_active
    )
    
    recipe.total_cost = ingredient_cost + total_sub_recipe_cost
    recipe.last_cost_update = datetime.utcnow()
    
    # Update food cost percentage
    if hasattr(recipe, 'menu_item') and recipe.menu_item and recipe.menu_item.price:
        recipe.food_cost_percentage = (recipe.total_cost / recipe.menu_item.price) * 100
    
    # Increment version
    recipe.version += 1
    
    # Create history entry if service instance provided
    if recipe_service_instance and hasattr(recipe_service_instance, '_create_history_entry'):
        # Build change summary
        old_sub_ids = {sub.sub_recipe_id for sub in existing_sub_recipes}
        new_sub_ids = {sub.sub_recipe_id for sub in sub_recipes}
        
        added = new_sub_ids - old_sub_ids
        removed = old_sub_ids - new_sub_ids
        
        change_parts = []
        if added:
            change_parts.append(f"Added sub-recipes: {list(added)}")
        if removed:
            change_parts.append(f"Removed sub-recipes: {list(removed)}")
        if not added and not removed and existing_sub_recipes:
            change_parts.append("Updated sub-recipe quantities")
        
        change_summary = "; ".join(change_parts) if change_parts else "Sub-recipes updated"
        
        recipe_service_instance._create_history_entry(
            recipe,
            "sub_recipes_updated",
            change_summary,
            user_id
        )
    
    db.commit()
    db.refresh(recipe)
    
    # Clear validator cache
    validator.clear_cache()
    
    return recipe


def add_single_sub_recipe(
    db: Session,
    recipe_id: int,
    sub_recipe_data: RecipeSubRecipeCreate,
    user_id: int
) -> RecipeSubRecipe:
    """
    Add a single sub-recipe to an existing recipe with validation.
    
    Args:
        db: Database session
        recipe_id: The parent recipe ID
        sub_recipe_data: Sub-recipe to add
        user_id: User making the addition
        
    Returns:
        Created RecipeSubRecipe link
        
    Raises:
        HTTPException: For validation errors
    """
    # Check parent recipe exists
    parent_recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.deleted_at.is_(None)
    ).first()
    
    if not parent_recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent recipe not found"
        )
    
    # Check sub-recipe exists
    sub_recipe = db.query(Recipe).filter(
        Recipe.id == sub_recipe_data.sub_recipe_id,
        Recipe.deleted_at.is_(None)
    ).first()
    
    if not sub_recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sub-recipe {sub_recipe_data.sub_recipe_id} not found"
        )
    
    # Check if already exists
    existing = db.query(RecipeSubRecipe).filter(
        RecipeSubRecipe.parent_recipe_id == recipe_id,
        RecipeSubRecipe.sub_recipe_id == sub_recipe_data.sub_recipe_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This sub-recipe is already linked to the parent recipe"
        )
    
    # Validate circular dependency
    validator = RecipeCircularValidator(db)
    
    try:
        validator.validate_no_circular_reference(
            recipe_id,
            sub_recipe_data.sub_recipe_id
        )
    except CircularDependencyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Create the link
    sub_recipe_link = RecipeSubRecipe(
        parent_recipe_id=recipe_id,
        created_by=user_id,
        **sub_recipe_data.dict()
    )
    db.add(sub_recipe_link)
    
    # Update parent recipe cost
    if sub_recipe.total_cost:
        parent_recipe.total_cost = (parent_recipe.total_cost or 0) + (
            sub_recipe.total_cost * sub_recipe_data.quantity
        )
        parent_recipe.last_cost_update = datetime.utcnow()
    
    # Update version
    parent_recipe.version += 1
    
    db.commit()
    db.refresh(sub_recipe_link)
    
    return sub_recipe_link


def remove_sub_recipe(
    db: Session,
    recipe_id: int,
    sub_recipe_id: int,
    user_id: int
) -> None:
    """
    Remove a sub-recipe link from a recipe.
    
    Args:
        db: Database session
        recipe_id: The parent recipe ID
        sub_recipe_id: The sub-recipe to remove
        user_id: User making the removal
        
    Raises:
        HTTPException: If link not found
    """
    # Find the link
    link = db.query(RecipeSubRecipe).filter(
        RecipeSubRecipe.parent_recipe_id == recipe_id,
        RecipeSubRecipe.sub_recipe_id == sub_recipe_id
    ).first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sub-recipe link not found"
        )
    
    # Get recipes for cost update
    parent_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    sub_recipe = db.query(Recipe).filter(Recipe.id == sub_recipe_id).first()
    
    # Remove the link
    db.delete(link)
    
    # Update parent recipe cost
    if parent_recipe and sub_recipe and sub_recipe.total_cost:
        parent_recipe.total_cost = (parent_recipe.total_cost or 0) - (
            sub_recipe.total_cost * link.quantity
        )
        parent_recipe.last_cost_update = datetime.utcnow()
        parent_recipe.version += 1
    
    db.commit()


def validate_recipe_hierarchy(db: Session, recipe_id: int) -> dict:
    """
    Validate and analyze a recipe's entire hierarchy.
    
    Args:
        db: Database session
        recipe_id: Recipe to analyze
        
    Returns:
        Dictionary with validation results
    """
    validator = RecipeCircularValidator(db)
    return validator.validate_recipe_hierarchy(recipe_id)


def get_recipe_dependencies(db: Session, recipe_id: int) -> dict:
    """
    Get all dependencies and dependents of a recipe.
    
    Args:
        db: Database session
        recipe_id: Recipe to analyze
        
    Returns:
        Dictionary with dependencies and dependents
    """
    validator = RecipeCircularValidator(db)
    
    dependencies = validator.get_all_dependencies(recipe_id)
    dependents = validator.get_all_dependents(recipe_id)
    
    # Get recipe names
    all_ids = dependencies.union(dependents).union({recipe_id})
    recipes = db.query(Recipe).filter(Recipe.id.in_(all_ids)).all()
    recipe_map = {r.id: r.name for r in recipes}
    
    return {
        'recipe_id': recipe_id,
        'recipe_name': recipe_map.get(recipe_id, f"Recipe#{recipe_id}"),
        'dependencies': [
            {'id': dep_id, 'name': recipe_map.get(dep_id, f"Recipe#{dep_id}")}
            for dep_id in dependencies
        ],
        'dependents': [
            {'id': dep_id, 'name': recipe_map.get(dep_id, f"Recipe#{dep_id}")}
            for dep_id in dependents
        ],
        'total_dependencies': len(dependencies),
        'total_dependents': len(dependents)
    }