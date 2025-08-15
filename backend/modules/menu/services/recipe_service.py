# backend/modules/menu/services/recipe_service.py

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import json
from functools import lru_cache
import hashlib

from ..models.recipe_models import (
    Recipe,
    RecipeIngredient,
    RecipeSubRecipe,
    RecipeHistory,
    RecipeNutrition,
    RecipeStatus,
    RecipeComplexity,
    UnitType,
)
from .recipe_circular_validation import RecipeCircularValidator, CircularDependencyError
from .recipe_service_enhanced import (
    update_recipe_sub_recipes as enhanced_update_sub_recipes,
    add_single_sub_recipe,
    remove_sub_recipe,
    validate_recipe_hierarchy as enhanced_validate_hierarchy,
    get_recipe_dependencies,
)
from ..schemas.recipe_schemas import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeSubRecipeCreate,
    RecipeSearchParams,
    RecipeCostAnalysis,
    RecipeValidation,
    RecipeComplianceReport,
    MenuItemRecipeStatus,
    RecipeCloneRequest,
    RecipeHistoryResponse,
)
from core.menu_models import MenuItem, MenuItemInventory
from core.inventory_models import Inventory
from fastapi import HTTPException, status


class RecipeService:
    def __init__(self, db: Session):
        self.db = db
        self._cost_cache = {}  # Cache for cost calculations
        self._compliance_cache = None  # Cache for compliance report
        self._compliance_cache_time = None

    def create_recipe(self, recipe_data: RecipeCreate, user_id: int) -> Recipe:
        """Create a new recipe for a menu item"""
        # Check if menu item exists
        menu_item = (
            self.db.query(MenuItem)
            .filter(MenuItem.id == recipe_data.menu_item_id)
            .first()
        )

        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found"
            )

        # Check if recipe already exists for this menu item
        existing_recipe = (
            self.db.query(Recipe)
            .filter(
                Recipe.menu_item_id == recipe_data.menu_item_id,
                Recipe.deleted_at.is_(None),
            )
            .first()
        )

        if existing_recipe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipe already exists for this menu item",
            )

        # Validate all ingredients exist and check for duplicates
        ingredient_ids = [ing.inventory_id for ing in recipe_data.ingredients]

        # Check for duplicate ingredients
        if len(ingredient_ids) != len(set(ingredient_ids)):
            duplicates = [id for id in ingredient_ids if ingredient_ids.count(id) > 1]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate ingredients found: {duplicates}",
            )

        inventory_items = (
            self.db.query(Inventory).filter(Inventory.id.in_(ingredient_ids)).all()
        )

        if len(inventory_items) != len(ingredient_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more inventory items not found",
            )

        # Create recipe
        recipe_dict = recipe_data.dict(exclude={"ingredients", "sub_recipes"})
        recipe_dict["created_by"] = user_id
        recipe = Recipe(**recipe_dict)

        # Calculate total time if not provided
        if recipe.total_time_minutes is None:
            prep_time = recipe.prep_time_minutes or 0
            cook_time = recipe.cook_time_minutes or 0
            recipe.total_time_minutes = prep_time + cook_time

        self.db.add(recipe)
        self.db.flush()

        # Add ingredients
        total_cost = 0.0
        for ing_data in recipe_data.ingredients:
            ingredient = RecipeIngredient(
                recipe_id=recipe.id, created_by=user_id, **ing_data.dict()
            )

            # Get current cost from inventory
            inv_item = next(i for i in inventory_items if i.id == ing_data.inventory_id)
            if inv_item.cost_per_unit:
                ingredient.unit_cost = inv_item.cost_per_unit
                ingredient.total_cost = ing_data.quantity * inv_item.cost_per_unit
                total_cost += ingredient.total_cost

            self.db.add(ingredient)

        # Add sub-recipes if any
        if recipe_data.sub_recipes:
            # Check for duplicate sub-recipes
            sub_recipe_ids = [sub.sub_recipe_id for sub in recipe_data.sub_recipes]
            if len(sub_recipe_ids) != len(set(sub_recipe_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate sub-recipes found",
                )

            for sub_data in recipe_data.sub_recipes:
                # Validate sub-recipe exists
                sub_recipe = (
                    self.db.query(Recipe)
                    .filter(Recipe.id == sub_data.sub_recipe_id)
                    .first()
                )

                if not sub_recipe:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sub-recipe {sub_data.sub_recipe_id} not found",
                    )

                # Prevent circular references
                if self._would_create_circular_reference(
                    recipe.id, sub_data.sub_recipe_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Circular reference detected: sub-recipe {sub_data.sub_recipe_id} would create a loop",
                    )

                sub_recipe_link = RecipeSubRecipe(
                    parent_recipe_id=recipe.id, created_by=user_id, **sub_data.dict()
                )
                self.db.add(sub_recipe_link)

                # Add sub-recipe cost
                if sub_recipe.total_cost:
                    total_cost += sub_recipe.total_cost * sub_data.quantity

        # Update recipe cost
        recipe.total_cost = total_cost
        recipe.last_cost_update = datetime.utcnow()

        # Calculate food cost percentage
        if menu_item.price and menu_item.price > 0:
            recipe.food_cost_percentage = (total_cost / menu_item.price) * 100

        # Create history entry
        self._create_history_entry(recipe, "created", "Recipe created", user_id)

        self.db.commit()
        self.db.refresh(recipe)

        return recipe

    def get_recipe_by_id(self, recipe_id: int) -> Optional[Recipe]:
        """Get recipe by ID with all details"""
        recipe = (
            self.db.query(Recipe)
            .options(
                joinedload(Recipe.menu_item),
                selectinload(Recipe.ingredients).joinedload(
                    RecipeIngredient.inventory_item
                ),
                selectinload(Recipe.sub_recipes).joinedload(RecipeSubRecipe.sub_recipe),
                selectinload(Recipe.history),
            )
            .filter(Recipe.id == recipe_id, Recipe.deleted_at.is_(None))
            .first()
        )

        return recipe

    def get_recipe_by_menu_item(self, menu_item_id: int) -> Optional[Recipe]:
        """Get recipe for a specific menu item"""
        recipe = (
            self.db.query(Recipe)
            .options(
                selectinload(Recipe.ingredients).joinedload(
                    RecipeIngredient.inventory_item
                ),
                selectinload(Recipe.sub_recipes).joinedload(RecipeSubRecipe.sub_recipe),
            )
            .filter(Recipe.menu_item_id == menu_item_id, Recipe.deleted_at.is_(None))
            .first()
        )

        return recipe

    def update_recipe(
        self, recipe_id: int, recipe_data: RecipeUpdate, user_id: int
    ) -> Recipe:
        """Update recipe details"""
        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        # Track changes for history
        changes = []

        # Update recipe fields
        for field, value in recipe_data.dict(exclude_unset=True).items():
            if hasattr(recipe, field) and getattr(recipe, field) != value:
                changes.append(f"{field}: {getattr(recipe, field)} → {value}")
                setattr(recipe, field, value)

        # Recalculate total time if needed
        if (
            recipe_data.prep_time_minutes is not None
            or recipe_data.cook_time_minutes is not None
        ):
            prep_time = recipe.prep_time_minutes or 0
            cook_time = recipe.cook_time_minutes or 0
            recipe.total_time_minutes = prep_time + cook_time

        # Increment version if significant changes
        if changes:
            recipe.version += 1
            self._create_history_entry(
                recipe,
                "updated",
                f"Updated fields: {', '.join(changes[:5])}"
                + ("..." if len(changes) > 5 else ""),
                user_id,
            )

        self.db.commit()
        self.db.refresh(recipe)

        return recipe

    def update_recipe_ingredients(
        self, recipe_id: int, ingredients: List[RecipeIngredientCreate], user_id: int
    ) -> Recipe:
        """Update recipe ingredients (replaces all)"""
        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        # Validate all new ingredients exist and check for duplicates
        ingredient_ids = [ing.inventory_id for ing in ingredients]

        # Check for duplicate ingredients
        if len(ingredient_ids) != len(set(ingredient_ids)):
            duplicates = [id for id in ingredient_ids if ingredient_ids.count(id) > 1]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate ingredients found: {duplicates}",
            )

        inventory_items = (
            self.db.query(Inventory).filter(Inventory.id.in_(ingredient_ids)).all()
        )

        if len(inventory_items) != len(ingredient_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more inventory items not found",
            )

        # Delete existing ingredients
        self.db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).delete()

        # Add new ingredients
        total_cost = 0.0
        for ing_data in ingredients:
            ingredient = RecipeIngredient(
                recipe_id=recipe_id, created_by=user_id, **ing_data.dict()
            )

            # Get current cost from inventory
            inv_item = next(i for i in inventory_items if i.id == ing_data.inventory_id)
            if inv_item.cost_per_unit:
                ingredient.unit_cost = inv_item.cost_per_unit
                ingredient.total_cost = ing_data.quantity * inv_item.cost_per_unit
                total_cost += ingredient.total_cost

            self.db.add(ingredient)

        # Update recipe cost
        recipe.total_cost = total_cost
        recipe.last_cost_update = datetime.utcnow()
        recipe.version += 1

        # Recalculate food cost percentage
        menu_item = recipe.menu_item
        if menu_item.price and menu_item.price > 0:
            recipe.food_cost_percentage = (total_cost / menu_item.price) * 100

        # Create history entry
        self._create_history_entry(
            recipe,
            "ingredients_changed",
            f"Updated ingredients list ({len(ingredients)} ingredients)",
            user_id,
        )

        self.db.commit()
        self.db.refresh(recipe)

        return recipe

    def delete_recipe(self, recipe_id: int, user_id: int) -> bool:
        """Soft delete a recipe"""
        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        recipe.deleted_at = datetime.utcnow()
        recipe.is_active = False

        self._create_history_entry(recipe, "deleted", "Recipe deleted", user_id)

        self.db.commit()
        return True

    def search_recipes(self, params: RecipeSearchParams) -> Tuple[List[Recipe], int]:
        """Search recipes with filters"""
        query = (
            self.db.query(Recipe)
            .options(joinedload(Recipe.menu_item), selectinload(Recipe.ingredients))
            .filter(Recipe.deleted_at.is_(None))
        )

        # Apply filters
        if params.query:
            search_term = f"%{params.query}%"
            query = query.filter(
                or_(Recipe.name.ilike(search_term), Recipe.notes.ilike(search_term))
            )

        if params.menu_item_id:
            query = query.filter(Recipe.menu_item_id == params.menu_item_id)

        if params.status:
            query = query.filter(Recipe.status == params.status)

        if params.complexity:
            query = query.filter(Recipe.complexity == params.complexity)

        if params.min_cost is not None:
            query = query.filter(Recipe.total_cost >= params.min_cost)

        if params.max_cost is not None:
            query = query.filter(Recipe.total_cost <= params.max_cost)

        if params.ingredient_id:
            query = query.join(RecipeIngredient).filter(
                RecipeIngredient.inventory_id == params.ingredient_id
            )

        # Get total count
        total = query.count()

        # Apply sorting
        if params.sort_by == "name":
            order_by = Recipe.name
        elif params.sort_by == "cost":
            order_by = Recipe.total_cost
        elif params.sort_by == "created_at":
            order_by = Recipe.created_at
        else:
            order_by = Recipe.name

        if params.sort_order == "desc":
            order_by = order_by.desc()

        query = query.order_by(order_by)

        # Apply pagination
        recipes = query.offset(params.offset).limit(params.limit).all()

        return recipes, total

    def calculate_recipe_cost(
        self, recipe_id: int, use_cache: bool = True
    ) -> RecipeCostAnalysis:
        """Calculate detailed cost analysis for a recipe with caching"""
        # Check cache first
        cache_key = self._get_cache_key(recipe_id, "cost")
        if use_cache and cache_key in self._cost_cache:
            cached_data, cached_time = self._cost_cache[cache_key]
            # Cache valid for 5 minutes
            if datetime.utcnow() - cached_time < timedelta(minutes=5):
                return cached_data

        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        # Calculate ingredient costs
        ingredient_costs = []
        total_ingredient_cost = 0.0

        for ingredient in recipe.ingredients:
            inv_item = ingredient.inventory_item
            cost = 0.0

            if inv_item.cost_per_unit:
                cost = ingredient.quantity * inv_item.cost_per_unit

            ingredient_costs.append(
                {
                    "inventory_id": inv_item.id,
                    "name": inv_item.item_name,
                    "quantity": ingredient.quantity,
                    "unit": ingredient.unit,
                    "unit_cost": inv_item.cost_per_unit,
                    "total_cost": cost,
                }
            )

            total_ingredient_cost += cost

        # Calculate sub-recipe costs
        sub_recipe_costs = []
        total_sub_recipe_cost = 0.0

        for sub_link in recipe.sub_recipes:
            sub_recipe = sub_link.sub_recipe
            cost = 0.0

            if sub_recipe.total_cost:
                cost = sub_recipe.total_cost * sub_link.quantity

            sub_recipe_costs.append(
                {
                    "sub_recipe_id": sub_recipe.id,
                    "name": sub_recipe.name,
                    "quantity": sub_link.quantity,
                    "unit_cost": sub_recipe.total_cost,
                    "total_cost": cost,
                }
            )

            total_sub_recipe_cost += cost

        # Total cost
        total_cost = total_ingredient_cost + total_sub_recipe_cost

        # Calculate margins
        menu_item = recipe.menu_item
        food_cost_percentage = 0.0
        profit_margin = 0.0
        profit_amount = 0.0

        if menu_item.price and menu_item.price > 0:
            food_cost_percentage = (total_cost / menu_item.price) * 100
            profit_margin = ((menu_item.price - total_cost) / menu_item.price) * 100
            profit_amount = menu_item.price - total_cost

        # Cost optimization suggestions
        suggestions = []

        if food_cost_percentage > 35:
            suggestions.append(
                "Food cost percentage is high. Consider reviewing portion sizes or ingredient choices."
            )

        # Find most expensive ingredients
        expensive_ingredients = sorted(
            ingredient_costs, key=lambda x: x["total_cost"], reverse=True
        )[:3]
        if expensive_ingredients:
            suggestions.append(
                f"Most expensive ingredients: {', '.join([i['name'] for i in expensive_ingredients])}. "
                "Consider alternatives or negotiate better prices."
            )

        # Update recipe cost
        recipe.total_cost = total_cost
        recipe.food_cost_percentage = food_cost_percentage
        recipe.last_cost_update = datetime.utcnow()
        self.db.commit()

        result = RecipeCostAnalysis(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            menu_item_id=menu_item.id,
            menu_item_name=menu_item.name,
            menu_item_price=menu_item.price,
            total_ingredient_cost=total_ingredient_cost,
            total_sub_recipe_cost=total_sub_recipe_cost,
            total_cost=total_cost,
            food_cost_percentage=food_cost_percentage,
            profit_margin=profit_margin,
            profit_amount=profit_amount,
            ingredient_costs=ingredient_costs,
            sub_recipe_costs=sub_recipe_costs,
            cost_optimization_suggestions=suggestions,
        )

        # Cache the result
        self._cost_cache[cache_key] = (result, datetime.utcnow())

        return result

    def validate_recipe(self, recipe_id: int) -> RecipeValidation:
        """Validate a recipe for completeness and accuracy"""
        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        errors = []
        warnings = []

        # Check ingredients
        has_ingredients = len(recipe.ingredients) > 0
        if not has_ingredients:
            errors.append("Recipe has no ingredients")

        # Check ingredient availability
        all_ingredients_available = True
        for ingredient in recipe.ingredients:
            if not ingredient.inventory_item.is_active:
                all_ingredients_available = False
                errors.append(
                    f"Ingredient '{ingredient.inventory_item.item_name}' is not active"
                )
            elif ingredient.inventory_item.quantity <= 0:
                warnings.append(
                    f"Ingredient '{ingredient.inventory_item.item_name}' is out of stock"
                )

        # Check cost calculation
        cost_calculated = recipe.total_cost is not None and recipe.total_cost > 0
        if not cost_calculated:
            warnings.append("Recipe cost has not been calculated")

        # Check food cost percentage
        within_target_cost = True
        if recipe.food_cost_percentage:
            if recipe.food_cost_percentage > 35:
                within_target_cost = False
                warnings.append(
                    f"Food cost percentage ({recipe.food_cost_percentage:.1f}%) exceeds target of 35%"
                )

        # Check instructions
        instructions_complete = recipe.instructions and len(recipe.instructions) > 0
        if not instructions_complete:
            warnings.append("Recipe has no preparation instructions")

        # Overall validation
        is_valid = len(errors) == 0

        return RecipeValidation(
            recipe_id=recipe.id,
            is_valid=is_valid,
            validation_errors=errors,
            warnings=warnings,
            has_ingredients=has_ingredients,
            all_ingredients_available=all_ingredients_available,
            cost_calculated=cost_calculated,
            within_target_cost=within_target_cost,
            instructions_complete=instructions_complete,
        )

    def get_recipe_compliance_report(
        self, use_cache: bool = True
    ) -> RecipeComplianceReport:
        """Get report on menu items without recipes with caching"""
        # Check cache first
        if use_cache and self._compliance_cache and self._compliance_cache_time:
            # Cache valid for 10 minutes
            if datetime.utcnow() - self._compliance_cache_time < timedelta(minutes=10):
                return self._compliance_cache

        # Get all active menu items
        menu_items = (
            self.db.query(MenuItem)
            .filter(MenuItem.is_active == True, MenuItem.deleted_at.is_(None))
            .all()
        )

        total_items = len(menu_items)
        items_with_recipes = 0
        missing_recipes = []
        draft_recipes = []
        inactive_recipes = []
        compliance_by_category = {}

        for item in menu_items:
            recipe = (
                self.db.query(Recipe)
                .filter(Recipe.menu_item_id == item.id, Recipe.deleted_at.is_(None))
                .first()
            )

            # Track by category
            category_name = item.category.name if item.category else "Uncategorized"
            if category_name not in compliance_by_category:
                compliance_by_category[category_name] = {
                    "total": 0,
                    "with_recipes": 0,
                    "without_recipes": 0,
                    "draft": 0,
                    "inactive": 0,
                }

            compliance_by_category[category_name]["total"] += 1

            if recipe:
                items_with_recipes += 1
                compliance_by_category[category_name]["with_recipes"] += 1

                status_info = MenuItemRecipeStatus(
                    menu_item_id=item.id,
                    menu_item_name=item.name,
                    has_recipe=True,
                    recipe_id=recipe.id,
                    recipe_status=recipe.status,
                    last_updated=recipe.updated_at,
                )

                if recipe.status == RecipeStatus.DRAFT:
                    draft_recipes.append(status_info)
                    compliance_by_category[category_name]["draft"] += 1
                elif recipe.status == RecipeStatus.INACTIVE:
                    inactive_recipes.append(status_info)
                    compliance_by_category[category_name]["inactive"] += 1
            else:
                missing_recipes.append(
                    MenuItemRecipeStatus(
                        menu_item_id=item.id, menu_item_name=item.name, has_recipe=False
                    )
                )
                compliance_by_category[category_name]["without_recipes"] += 1

        # Calculate compliance percentage
        compliance_percentage = (
            (items_with_recipes / total_items * 100) if total_items > 0 else 0
        )

        # Calculate percentages by category
        for category in compliance_by_category.values():
            if category["total"] > 0:
                category["compliance_percentage"] = (
                    category["with_recipes"] / category["total"]
                ) * 100
            else:
                category["compliance_percentage"] = 0

        result = RecipeComplianceReport(
            total_menu_items=total_items,
            items_with_recipes=items_with_recipes,
            items_without_recipes=len(missing_recipes),
            compliance_percentage=compliance_percentage,
            missing_recipes=missing_recipes,
            draft_recipes=draft_recipes,
            inactive_recipes=inactive_recipes,
            compliance_by_category=compliance_by_category,
            cached=use_cache and self._compliance_cache is not None,
            generated_at=(
                self._compliance_cache_time
                if use_cache and self._compliance_cache
                else datetime.utcnow()
            ),
        )

        # Cache the result
        self._compliance_cache = result
        self._compliance_cache_time = datetime.utcnow()

        return result

    def clone_recipe(self, clone_request: RecipeCloneRequest, user_id: int) -> Recipe:
        """Clone a recipe to another menu item"""
        # Get source recipe
        source_recipe = self.get_recipe_by_id(clone_request.source_recipe_id)
        if not source_recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Source recipe not found"
            )

        # Check target menu item
        target_item = (
            self.db.query(MenuItem)
            .filter(MenuItem.id == clone_request.target_menu_item_id)
            .first()
        )

        if not target_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target menu item not found",
            )

        # Check if target already has recipe
        existing = (
            self.db.query(Recipe)
            .filter(
                Recipe.menu_item_id == clone_request.target_menu_item_id,
                Recipe.deleted_at.is_(None),
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target menu item already has a recipe",
            )

        # Create new recipe
        new_recipe = Recipe(
            menu_item_id=clone_request.target_menu_item_id,
            name=clone_request.name or f"{source_recipe.name} (Copy)",
            status=RecipeStatus.DRAFT,
            yield_quantity=source_recipe.yield_quantity,
            yield_unit=source_recipe.yield_unit,
            portion_size=source_recipe.portion_size,
            portion_unit=source_recipe.portion_unit,
            prep_time_minutes=source_recipe.prep_time_minutes,
            cook_time_minutes=source_recipe.cook_time_minutes,
            total_time_minutes=source_recipe.total_time_minutes,
            complexity=source_recipe.complexity,
            instructions=source_recipe.instructions,
            notes=source_recipe.notes,
            allergen_notes=source_recipe.allergen_notes,
            quality_standards=source_recipe.quality_standards,
            plating_instructions=source_recipe.plating_instructions,
            created_by=user_id,
        )

        # Apply portion adjustment if requested
        adjust_factor = clone_request.adjust_portions or 1.0
        if adjust_factor != 1.0:
            new_recipe.yield_quantity *= adjust_factor

        self.db.add(new_recipe)
        self.db.flush()

        # Clone ingredients
        total_cost = 0.0
        for ingredient in source_recipe.ingredients:
            new_ingredient = RecipeIngredient(
                recipe_id=new_recipe.id,
                inventory_id=ingredient.inventory_id,
                quantity=ingredient.quantity * adjust_factor,
                unit=ingredient.unit,
                custom_unit=ingredient.custom_unit,
                preparation=ingredient.preparation,
                is_optional=ingredient.is_optional,
                notes=ingredient.notes,
                display_order=ingredient.display_order,
                unit_cost=ingredient.unit_cost,
                total_cost=(
                    ingredient.total_cost * adjust_factor
                    if ingredient.total_cost
                    else None
                ),
                created_by=user_id,
            )
            self.db.add(new_ingredient)

            if new_ingredient.total_cost:
                total_cost += new_ingredient.total_cost

        # Clone sub-recipes
        for sub_link in source_recipe.sub_recipes:
            new_sub_link = RecipeSubRecipe(
                parent_recipe_id=new_recipe.id,
                sub_recipe_id=sub_link.sub_recipe_id,
                quantity=sub_link.quantity * adjust_factor,
                unit=sub_link.unit,
                display_order=sub_link.display_order,
                notes=sub_link.notes,
                created_by=user_id,
            )
            self.db.add(new_sub_link)

            if sub_link.sub_recipe.total_cost:
                total_cost += sub_link.sub_recipe.total_cost * new_sub_link.quantity

        # Update cost
        new_recipe.total_cost = total_cost
        new_recipe.last_cost_update = datetime.utcnow()

        # Calculate food cost percentage
        if target_item.price and target_item.price > 0:
            new_recipe.food_cost_percentage = (total_cost / target_item.price) * 100

        # Create history entry
        self._create_history_entry(
            new_recipe,
            "cloned",
            f"Cloned from recipe {source_recipe.id} ({source_recipe.name})",
            user_id,
        )

        self.db.commit()
        self.db.refresh(new_recipe)

        return new_recipe

    def get_recipe_history(self, recipe_id: int) -> List[RecipeHistoryResponse]:
        """Get version history for a recipe"""
        history = (
            self.db.query(RecipeHistory)
            .filter(RecipeHistory.recipe_id == recipe_id)
            .order_by(RecipeHistory.created_at.desc())
            .all()
        )

        return history

    def recalculate_all_recipe_costs(self, user_id: int) -> Dict[str, Any]:
        """Recalculate costs for all recipes (useful after inventory price updates)"""
        recipes = (
            self.db.query(Recipe)
            .filter(Recipe.deleted_at.is_(None), Recipe.is_active == True)
            .all()
        )

        updated_count = 0
        total_recipes = len(recipes)

        for recipe in recipes:
            try:
                self.calculate_recipe_cost(
                    recipe.id, use_cache=False
                )  # Force recalculation
                updated_count += 1
            except Exception as e:
                # Log error but continue
                print(f"Error updating recipe {recipe.id}: {str(e)}")

        return {
            "total_recipes": total_recipes,
            "updated": updated_count,
            "failed": total_recipes - updated_count,
            "timestamp": datetime.utcnow(),
        }

    def _create_history_entry(
        self, recipe: Recipe, change_type: str, change_summary: str, user_id: int
    ):
        """Create a history entry for recipe changes"""
        # Prepare recipe snapshot
        recipe_snapshot = {
            "id": recipe.id,
            "name": recipe.name,
            "status": recipe.status,
            "version": recipe.version,
            "yield_quantity": recipe.yield_quantity,
            "yield_unit": recipe.yield_unit,
            "portion_size": recipe.portion_size,
            "portion_unit": recipe.portion_unit,
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "total_time_minutes": recipe.total_time_minutes,
            "complexity": recipe.complexity,
            "instructions": recipe.instructions,
            "notes": recipe.notes,
            "allergen_notes": recipe.allergen_notes,
            "total_cost": recipe.total_cost,
            "food_cost_percentage": recipe.food_cost_percentage,
        }

        # Prepare ingredients snapshot
        ingredients_snapshot = []
        for ing in recipe.ingredients:
            ingredients_snapshot.append(
                {
                    "inventory_id": ing.inventory_id,
                    "inventory_name": (
                        ing.inventory_item.item_name if ing.inventory_item else None
                    ),
                    "quantity": ing.quantity,
                    "unit": ing.unit,
                    "custom_unit": ing.custom_unit,
                    "preparation": ing.preparation,
                    "is_optional": ing.is_optional,
                    "unit_cost": ing.unit_cost,
                    "total_cost": ing.total_cost,
                }
            )

        history = RecipeHistory(
            recipe_id=recipe.id,
            version=recipe.version,
            change_type=change_type,
            change_summary=change_summary,
            recipe_snapshot=recipe_snapshot,
            ingredients_snapshot=ingredients_snapshot,
            total_cost=recipe.total_cost,
            food_cost_percentage=recipe.food_cost_percentage,
            changed_by=user_id,
        )

        self.db.add(history)

    def _would_create_circular_reference(
        self, parent_id: int, potential_sub_id: int
    ) -> bool:
        """Check if adding a sub-recipe would create a circular reference"""
        # Try to get Redis client if available
        redis_client = None
        try:
            from core.redis_client import get_redis_client

            redis_client = get_redis_client()
        except:
            pass  # Redis not configured, will use local cache only

        validator = RecipeCircularValidator(self.db, redis_client)
        try:
            validator.validate_no_circular_reference(parent_id, potential_sub_id)
            return False
        except CircularDependencyError:
            return True

    def _get_cache_key(self, recipe_id: int, operation: str) -> str:
        """Generate cache key for recipe operations"""
        return f"{operation}:{recipe_id}"

    def _invalidate_cost_cache(self, recipe_id: int):
        """Invalidate cost cache for a recipe and its parents"""
        # Remove direct cache
        cache_key = self._get_cache_key(recipe_id, "cost")
        if cache_key in self._cost_cache:
            del self._cost_cache[cache_key]

        # Find and invalidate parent recipes
        parent_links = (
            self.db.query(RecipeSubRecipe)
            .filter(RecipeSubRecipe.sub_recipe_id == recipe_id)
            .all()
        )

        for link in parent_links:
            self._invalidate_cost_cache(link.parent_recipe_id)

    def update_recipe_sub_recipes(
        self, recipe_id: int, sub_recipes: List[RecipeSubRecipeCreate], user_id: int
    ) -> Recipe:
        """Update recipe sub-recipes with enhanced circular dependency validation"""
        return enhanced_update_sub_recipes(
            self.db, recipe_id, sub_recipes, user_id, recipe_service_instance=self
        )

    def add_sub_recipe(
        self, recipe_id: int, sub_recipe_data: RecipeSubRecipeCreate, user_id: int
    ) -> RecipeSubRecipe:
        """Add a single sub-recipe with validation"""
        return add_single_sub_recipe(self.db, recipe_id, sub_recipe_data, user_id)

    def remove_sub_recipe_link(
        self, recipe_id: int, sub_recipe_id: int, user_id: int
    ) -> None:
        """Remove a sub-recipe from a recipe"""
        remove_sub_recipe(self.db, recipe_id, sub_recipe_id, user_id)

    def validate_recipe_hierarchy(self, recipe_id: int) -> dict:
        """Validate and analyze a recipe's entire hierarchy"""
        return enhanced_validate_hierarchy(self.db, recipe_id)

    def get_recipe_dependencies_analysis(self, recipe_id: int) -> dict:
        """Get all dependencies and dependents of a recipe"""
        return get_recipe_dependencies(self.db, recipe_id)
