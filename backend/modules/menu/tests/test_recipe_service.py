# backend/modules/menu/tests/test_recipe_service.py

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models.recipe_models import (
    Recipe,
    RecipeIngredient,
    RecipeStatus,
    RecipeComplexity,
    UnitType,
)
from ..services.recipe_service import RecipeService
from ..schemas.recipe_schemas import (
    RecipeCreate,
    RecipeUpdate,
    RecipeIngredientCreate,
    RecipeSearchParams,
    RecipeCloneRequest,
)
from core.menu_models import MenuItem, MenuCategory
from core.inventory_models import Inventory


class TestRecipeService:

    @pytest.fixture
    def recipe_service(self, db_session: Session):
        return RecipeService(db_session)

    @pytest.fixture
    def sample_category(self, db_session: Session):
        category = MenuCategory(
            name="Main Dishes",
            description="Main course items",
            display_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        return category

    @pytest.fixture
    def sample_menu_item(self, db_session: Session, sample_category):
        item = MenuItem(
            name="Grilled Chicken",
            description="Delicious grilled chicken breast",
            price=15.99,
            category_id=sample_category.id,
            is_active=True,
            is_available=True,
        )
        db_session.add(item)
        db_session.commit()
        return item

    @pytest.fixture
    def sample_inventory_items(self, db_session: Session):
        items = [
            Inventory(
                item_name="Chicken Breast",
                quantity=100,
                unit="piece",
                threshold=20,
                cost_per_unit=3.50,
                is_active=True,
            ),
            Inventory(
                item_name="Olive Oil",
                quantity=50,
                unit="liter",
                threshold=10,
                cost_per_unit=8.00,
                is_active=True,
            ),
            Inventory(
                item_name="Salt",
                quantity=25,
                unit="kg",
                threshold=5,
                cost_per_unit=1.50,
                is_active=True,
            ),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()
        return items

    def test_create_recipe(
        self, recipe_service, sample_menu_item, sample_inventory_items, db_session
    ):
        """Test creating a new recipe"""
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Grilled Chicken Recipe",
            yield_quantity=1,
            yield_unit="portion",
            prep_time_minutes=15,
            cook_time_minutes=20,
            complexity=RecipeComplexity.MODERATE,
            instructions=[
                "Season chicken",
                "Grill for 20 minutes",
                "Rest for 5 minutes",
            ],
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                    preparation="trimmed and pounded",
                ),
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[1].id,
                    quantity=0.02,
                    unit=UnitType.LITER,
                    preparation="for brushing",
                ),
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[2].id,
                    quantity=0.005,
                    unit=UnitType.KILOGRAM,
                    preparation="for seasoning",
                ),
            ],
        )

        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        assert recipe.id is not None
        assert recipe.menu_item_id == sample_menu_item.id
        assert recipe.name == "Grilled Chicken Recipe"
        assert recipe.total_time_minutes == 35  # prep + cook
        assert len(recipe.ingredients) == 3
        assert recipe.total_cost == pytest.approx(
            3.67, rel=0.01
        )  # 3.50 + 0.16 + 0.0075
        assert recipe.food_cost_percentage == pytest.approx(
            22.95, rel=0.1
        )  # 3.67 / 15.99 * 100

    def test_create_recipe_duplicate(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test creating duplicate recipe for same menu item"""
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="First Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )

        # Create first recipe
        recipe_service.create_recipe(recipe_data, user_id=1)

        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            recipe_service.create_recipe(recipe_data, user_id=1)

        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)

    def test_update_recipe(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test updating recipe details"""
        # Create recipe
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Original Recipe",
            status=RecipeStatus.DRAFT,
            prep_time_minutes=10,
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        # Update recipe
        update_data = RecipeUpdate(
            name="Updated Recipe",
            status=RecipeStatus.ACTIVE,
            prep_time_minutes=15,
            cook_time_minutes=25,
        )

        updated_recipe = recipe_service.update_recipe(recipe.id, update_data, user_id=1)

        assert updated_recipe.name == "Updated Recipe"
        assert updated_recipe.status == RecipeStatus.ACTIVE
        assert updated_recipe.prep_time_minutes == 15
        assert updated_recipe.cook_time_minutes == 25
        assert updated_recipe.total_time_minutes == 40
        assert updated_recipe.version == 2  # Version incremented

    def test_update_recipe_ingredients(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test updating recipe ingredients"""
        # Create recipe with initial ingredients
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Test Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)
        initial_cost = recipe.total_cost

        # Update ingredients
        new_ingredients = [
            RecipeIngredientCreate(
                inventory_id=sample_inventory_items[0].id,
                quantity=2,  # Double the quantity
                unit=UnitType.PIECE,
            ),
            RecipeIngredientCreate(
                inventory_id=sample_inventory_items[1].id,
                quantity=0.05,
                unit=UnitType.LITER,
            ),
        ]

        updated_recipe = recipe_service.update_recipe_ingredients(
            recipe.id, new_ingredients, user_id=1
        )

        assert len(updated_recipe.ingredients) == 2
        assert updated_recipe.total_cost > initial_cost
        assert updated_recipe.version == 2

    def test_search_recipes(
        self, recipe_service, sample_menu_item, sample_inventory_items, db_session
    ):
        """Test searching recipes with filters"""
        # Create multiple recipes
        recipes_data = [
            RecipeCreate(
                menu_item_id=sample_menu_item.id,
                name="Simple Recipe",
                status=RecipeStatus.ACTIVE,
                complexity=RecipeComplexity.SIMPLE,
                ingredients=[
                    RecipeIngredientCreate(
                        inventory_id=sample_inventory_items[0].id,
                        quantity=1,
                        unit=UnitType.PIECE,
                    )
                ],
            )
        ]

        # Create another menu item for second recipe
        item2 = MenuItem(
            name="Pasta",
            price=12.99,
            category_id=sample_menu_item.category_id,
            is_active=True,
        )
        db_session.add(item2)
        db_session.commit()

        recipes_data.append(
            RecipeCreate(
                menu_item_id=item2.id,
                name="Complex Recipe",
                status=RecipeStatus.DRAFT,
                complexity=RecipeComplexity.COMPLEX,
                ingredients=[
                    RecipeIngredientCreate(
                        inventory_id=sample_inventory_items[1].id,
                        quantity=0.1,
                        unit=UnitType.LITER,
                    )
                ],
            )
        )

        for recipe_data in recipes_data:
            recipe_service.create_recipe(recipe_data, user_id=1)

        # Test search by status
        params = RecipeSearchParams(status=RecipeStatus.ACTIVE)
        results, total = recipe_service.search_recipes(params)
        assert total == 1
        assert results[0].name == "Simple Recipe"

        # Test search by complexity
        params = RecipeSearchParams(complexity=RecipeComplexity.COMPLEX)
        results, total = recipe_service.search_recipes(params)
        assert total == 1
        assert results[0].name == "Complex Recipe"

        # Test search by ingredient
        params = RecipeSearchParams(ingredient_id=sample_inventory_items[0].id)
        results, total = recipe_service.search_recipes(params)
        assert total == 1

    def test_calculate_recipe_cost(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test calculating recipe cost analysis"""
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Cost Test Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=2,
                    unit=UnitType.PIECE,
                ),
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[1].id,
                    quantity=0.1,
                    unit=UnitType.LITER,
                ),
            ],
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        cost_analysis = recipe_service.calculate_recipe_cost(recipe.id)

        assert cost_analysis.recipe_id == recipe.id
        assert cost_analysis.total_ingredient_cost == pytest.approx(
            7.8, rel=0.01
        )  # 7.00 + 0.80
        assert cost_analysis.total_cost == cost_analysis.total_ingredient_cost
        assert cost_analysis.food_cost_percentage == pytest.approx(48.78, rel=0.1)
        assert cost_analysis.profit_margin == pytest.approx(51.22, rel=0.1)
        assert len(cost_analysis.ingredient_costs) == 2
        assert len(cost_analysis.cost_optimization_suggestions) > 0  # High food cost

    def test_validate_recipe(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test recipe validation"""
        # Create incomplete recipe
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Incomplete Recipe",
            ingredients=[],  # No ingredients
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        validation = recipe_service.validate_recipe(recipe.id)

        assert not validation.is_valid
        assert not validation.has_ingredients
        assert "Recipe has no ingredients" in validation.validation_errors
        assert not validation.instructions_complete

    def test_get_compliance_report(
        self, recipe_service, sample_category, sample_inventory_items, db_session
    ):
        """Test recipe compliance report"""
        # Create menu items with and without recipes
        items = []
        for i in range(3):
            item = MenuItem(
                name=f"Item {i}",
                price=10.00 + i,
                category_id=sample_category.id,
                is_active=True,
            )
            db_session.add(item)
            items.append(item)
        db_session.commit()

        # Create recipe for first item only
        recipe_data = RecipeCreate(
            menu_item_id=items[0].id,
            name="Recipe 1",
            status=RecipeStatus.ACTIVE,
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe_service.create_recipe(recipe_data, user_id=1)

        # Get compliance report
        report = recipe_service.get_compliance_report()

        assert report.total_menu_items >= 3
        assert report.items_without_recipes >= 2
        assert report.compliance_percentage < 50
        assert len(report.missing_recipes) >= 2
        assert any(item.menu_item_id == items[1].id for item in report.missing_recipes)

    def test_clone_recipe(
        self, recipe_service, sample_menu_item, sample_inventory_items, db_session
    ):
        """Test cloning a recipe"""
        # Create source recipe
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Original Recipe",
            yield_quantity=1,
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        source_recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        # Create target menu item
        target_item = MenuItem(
            name="New Dish",
            price=18.99,
            category_id=sample_menu_item.category_id,
            is_active=True,
        )
        db_session.add(target_item)
        db_session.commit()

        # Clone recipe with portion adjustment
        clone_request = RecipeCloneRequest(
            source_recipe_id=source_recipe.id,
            target_menu_item_id=target_item.id,
            name="Cloned Recipe",
            adjust_portions=2.0,  # Double the portions
        )

        cloned_recipe = recipe_service.clone_recipe(clone_request, user_id=1)

        assert cloned_recipe.menu_item_id == target_item.id
        assert cloned_recipe.name == "Cloned Recipe"
        assert cloned_recipe.yield_quantity == 2.0
        assert cloned_recipe.status == RecipeStatus.DRAFT
        assert len(cloned_recipe.ingredients) == 1
        assert cloned_recipe.ingredients[0].quantity == 2.0  # Doubled

    def test_recipe_history(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test recipe history tracking"""
        # Create recipe
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="History Test Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        # Make some changes
        update_data = RecipeUpdate(name="Updated Name")
        recipe_service.update_recipe(recipe.id, update_data, user_id=1)

        # Update ingredients
        new_ingredients = [
            RecipeIngredientCreate(
                inventory_id=sample_inventory_items[0].id,
                quantity=2,
                unit=UnitType.PIECE,
            )
        ]
        recipe_service.update_recipe_ingredients(recipe.id, new_ingredients, user_id=1)

        # Get history
        history = recipe_service.get_recipe_history(recipe.id)

        assert len(history) >= 3  # Created, updated, ingredients changed
        assert history[0].change_type == "ingredients_changed"  # Most recent first
        assert history[-1].change_type == "created"  # Oldest last

    def test_duplicate_ingredients_prevention(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test that duplicate ingredients are prevented"""
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Duplicate Test Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                ),
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,  # Duplicate
                    quantity=2,
                    unit=UnitType.PIECE,
                ),
            ],
        )

        with pytest.raises(HTTPException) as exc_info:
            recipe_service.create_recipe(recipe_data, user_id=1)

        assert exc_info.value.status_code == 400
        assert "Duplicate ingredients found" in str(exc_info.value.detail)

    def test_sub_recipe_cost_propagation(
        self, recipe_service, sample_category, sample_inventory_items, db_session
    ):
        """Test that sub-recipe costs propagate correctly"""
        # Create sauce recipe (sub-recipe)
        sauce_item = MenuItem(
            name="House Sauce",
            price=5.00,
            category_id=sample_category.id,
            is_active=True,
        )
        db_session.add(sauce_item)
        db_session.commit()

        sauce_recipe_data = RecipeCreate(
            menu_item_id=sauce_item.id,
            name="House Sauce Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[1].id,  # Olive oil
                    quantity=0.1,
                    unit=UnitType.LITER,
                ),
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[2].id,  # Salt
                    quantity=0.01,
                    unit=UnitType.KILOGRAM,
                ),
            ],
        )
        sauce_recipe = recipe_service.create_recipe(sauce_recipe_data, user_id=1)

        # Create main dish using sauce as sub-recipe
        main_item = MenuItem(
            name="Pasta with House Sauce",
            price=18.00,
            category_id=sample_category.id,
            is_active=True,
        )
        db_session.add(main_item)
        db_session.commit()

        main_recipe_data = RecipeCreate(
            menu_item_id=main_item.id,
            name="Pasta Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[
                        0
                    ].id,  # Using chicken as pasta for test
                    quantity=0.2,
                    unit=UnitType.KILOGRAM,
                )
            ],
            sub_recipes=[
                RecipeSubRecipeCreate(
                    sub_recipe_id=sauce_recipe.id,
                    quantity=2.0,  # 2 portions of sauce
                    unit="portion",
                )
            ],
        )
        main_recipe = recipe_service.create_recipe(main_recipe_data, user_id=1)

        # Calculate costs
        cost_analysis = recipe_service.calculate_recipe_cost(main_recipe.id)

        # Verify sub-recipe cost is included
        sauce_cost = 0.8 + 0.015  # 0.1L oil @ 8.00 + 0.01kg salt @ 1.50
        expected_sub_recipe_cost = sauce_cost * 2  # 2 portions

        assert cost_analysis.total_sub_recipe_cost == pytest.approx(
            expected_sub_recipe_cost, rel=0.01
        )
        assert len(cost_analysis.sub_recipe_costs) == 1
        assert cost_analysis.sub_recipe_costs[0]["quantity"] == 2.0

    def test_circular_reference_prevention(
        self, recipe_service, sample_category, sample_inventory_items, db_session
    ):
        """Test that circular references in sub-recipes are prevented"""
        # Create recipe A
        item_a = MenuItem(
            name="Recipe A", price=10.00, category_id=sample_category.id, is_active=True
        )
        db_session.add(item_a)
        db_session.commit()

        recipe_a_data = RecipeCreate(
            menu_item_id=item_a.id,
            name="Recipe A",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe_a = recipe_service.create_recipe(recipe_a_data, user_id=1)

        # Create recipe B that uses A as sub-recipe
        item_b = MenuItem(
            name="Recipe B", price=15.00, category_id=sample_category.id, is_active=True
        )
        db_session.add(item_b)
        db_session.commit()

        recipe_b_data = RecipeCreate(
            menu_item_id=item_b.id,
            name="Recipe B",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[1].id,
                    quantity=0.1,
                    unit=UnitType.LITER,
                )
            ],
            sub_recipes=[
                RecipeSubRecipeCreate(sub_recipe_id=recipe_a.id, quantity=1.0)
            ],
        )
        recipe_b = recipe_service.create_recipe(recipe_b_data, user_id=1)

        # Try to update recipe A to use recipe B as sub-recipe (circular)
        # This would need to be done through a different method since we can't
        # add sub-recipes to existing recipes in current implementation
        # Let's test the _would_create_circular_reference method directly

        assert (
            recipe_service._would_create_circular_reference(recipe_a.id, recipe_b.id)
            == True
        )
        assert (
            recipe_service._would_create_circular_reference(recipe_b.id, recipe_a.id)
            == False
        )

    def test_cost_caching(
        self, recipe_service, sample_menu_item, sample_inventory_items
    ):
        """Test that cost calculations are cached"""
        recipe_data = RecipeCreate(
            menu_item_id=sample_menu_item.id,
            name="Cache Test Recipe",
            ingredients=[
                RecipeIngredientCreate(
                    inventory_id=sample_inventory_items[0].id,
                    quantity=1,
                    unit=UnitType.PIECE,
                )
            ],
        )
        recipe = recipe_service.create_recipe(recipe_data, user_id=1)

        # First calculation - not cached
        cost1 = recipe_service.calculate_recipe_cost(recipe.id)

        # Second calculation - should be cached
        cost2 = recipe_service.calculate_recipe_cost(recipe.id)

        assert cost1.total_cost == cost2.total_cost

        # Verify cache is used (check cache directly)
        cache_key = recipe_service._get_cache_key(recipe.id, "cost")
        assert cache_key in recipe_service._cost_cache

        # Force recalculation without cache
        cost3 = recipe_service.calculate_recipe_cost(recipe.id, use_cache=False)
        assert cost3.total_cost == cost1.total_cost
