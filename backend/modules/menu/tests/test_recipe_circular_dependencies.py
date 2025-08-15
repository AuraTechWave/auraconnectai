# backend/modules/menu/tests/test_recipe_circular_dependencies.py

"""
Comprehensive tests for recipe circular dependency validation.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from modules.menu.models.recipe_models import Recipe, RecipeSubRecipe, RecipeStatus
from modules.menu.services.recipe_service import RecipeService
from modules.menu.services.recipe_circular_validation import (
    RecipeCircularValidator,
    CircularDependencyError,
)
from modules.menu.schemas.recipe_schemas import RecipeCreate, RecipeSubRecipeCreate
from core.menu_models import MenuItem, MenuCategory
from core.inventory_models import Inventory, InventoryCategory
from core.staff_models import StaffMember


class TestRecipeCircularDependencies:
    """Test cases for circular dependency validation in recipes"""

    @pytest.fixture
    def setup_test_data(self, db: Session):
        """Set up test data"""
        # Create staff member
        staff = StaffMember(
            name="Test Chef",
            email="chef@test.com",
            phone="1234567890",
            role="chef",
            is_active=True,
        )
        db.add(staff)

        # Create menu category
        category = MenuCategory(name="Test Category", description="Test")
        db.add(category)
        db.commit()

        # Create inventory category
        inv_category = InventoryCategory(
            name="Ingredients", description="Test ingredients"
        )
        db.add(inv_category)
        db.commit()

        # Create inventory items
        flour = Inventory(
            name="Flour",
            category_id=inv_category.id,
            quantity=100,
            unit="kg",
            cost_per_unit=2.0,
            minimum_quantity=10,
        )
        butter = Inventory(
            name="Butter",
            category_id=inv_category.id,
            quantity=50,
            unit="kg",
            cost_per_unit=5.0,
            minimum_quantity=5,
        )
        sugar = Inventory(
            name="Sugar",
            category_id=inv_category.id,
            quantity=75,
            unit="kg",
            cost_per_unit=3.0,
            minimum_quantity=10,
        )
        db.add_all([flour, butter, sugar])
        db.commit()

        # Create menu items
        menu_items = []
        for i in range(6):
            item = MenuItem(
                name=f"Test Item {i}",
                description=f"Test menu item {i}",
                price=10.0 + i,
                category_id=category.id,
                is_available=True,
            )
            db.add(item)
            menu_items.append(item)

        db.commit()

        return {
            "staff": staff,
            "category": category,
            "inventory": {"flour": flour, "butter": butter, "sugar": sugar},
            "menu_items": menu_items,
        }

    def test_self_reference_prevention(self, db: Session, setup_test_data):
        """Test that a recipe cannot reference itself"""
        data = setup_test_data
        service = RecipeService(db)

        # Create a recipe
        recipe_data = RecipeCreate(
            menu_item_id=data["menu_items"][0].id,
            name="Base Recipe",
            yield_quantity=1,
            status=RecipeStatus.ACTIVE,
            ingredients=[],
        )
        recipe = service.create_recipe(recipe_data, data["staff"].id)

        # Try to add itself as a sub-recipe
        validator = RecipeCircularValidator(db)

        with pytest.raises(CircularDependencyError) as exc_info:
            validator.validate_no_circular_reference(recipe.id, recipe.id)

        assert "cannot reference itself" in str(exc_info.value)

    def test_simple_circular_dependency(self, db: Session, setup_test_data):
        """Test detection of simple A -> B -> A circular dependency"""
        data = setup_test_data
        service = RecipeService(db)

        # Create Recipe A
        recipe_a_data = RecipeCreate(
            menu_item_id=data["menu_items"][0].id,
            name="Recipe A",
            yield_quantity=1,
            status=RecipeStatus.ACTIVE,
            ingredients=[
                {
                    "inventory_id": data["inventory"]["flour"].id,
                    "quantity": 1.0,
                    "unit": "kg",
                }
            ],
        )
        recipe_a = service.create_recipe(recipe_a_data, data["staff"].id)

        # Create Recipe B with A as sub-recipe
        recipe_b_data = RecipeCreate(
            menu_item_id=data["menu_items"][1].id,
            name="Recipe B",
            yield_quantity=1,
            status=RecipeStatus.ACTIVE,
            ingredients=[
                {
                    "inventory_id": data["inventory"]["butter"].id,
                    "quantity": 0.5,
                    "unit": "kg",
                }
            ],
            sub_recipes=[{"sub_recipe_id": recipe_a.id, "quantity": 1.0}],
        )
        recipe_b = service.create_recipe(recipe_b_data, data["staff"].id)

        # Try to add B as sub-recipe to A (creating A -> B -> A cycle)
        with pytest.raises(HTTPException) as exc_info:
            service.add_sub_recipe(
                recipe_a.id,
                RecipeSubRecipeCreate(sub_recipe_id=recipe_b.id, quantity=1.0),
                data["staff"].id,
            )

        assert "circular dependency" in str(exc_info.value.detail).lower()

    def test_complex_circular_dependency(self, db: Session, setup_test_data):
        """Test detection of complex circular dependency A -> B -> C -> A"""
        data = setup_test_data
        service = RecipeService(db)

        # Create Recipe A
        recipe_a = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][0].id,
                name="Recipe A",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["flour"].id,
                        "quantity": 1.0,
                        "unit": "kg",
                    }
                ],
            ),
            data["staff"].id,
        )

        # Create Recipe B with A as sub-recipe
        recipe_b = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][1].id,
                name="Recipe B",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["butter"].id,
                        "quantity": 0.5,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": recipe_a.id, "quantity": 1.0}],
            ),
            data["staff"].id,
        )

        # Create Recipe C with B as sub-recipe
        recipe_c = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][2].id,
                name="Recipe C",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["sugar"].id,
                        "quantity": 0.3,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": recipe_b.id, "quantity": 1.0}],
            ),
            data["staff"].id,
        )

        # Try to add C as sub-recipe to A (creating A -> B -> C -> A cycle)
        validator = RecipeCircularValidator(db)

        with pytest.raises(CircularDependencyError) as exc_info:
            validator.validate_no_circular_reference(recipe_a.id, recipe_c.id)

        # Check that the error includes the cycle path
        assert recipe_a.id in exc_info.value.cycle_path
        assert recipe_c.id in exc_info.value.cycle_path

    def test_valid_shared_sub_recipe(self, db: Session, setup_test_data):
        """Test that multiple recipes can share the same sub-recipe without issues"""
        data = setup_test_data
        service = RecipeService(db)

        # Create a base sauce recipe
        sauce_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][0].id,
                name="Base Sauce",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["butter"].id,
                        "quantity": 0.2,
                        "unit": "kg",
                    }
                ],
            ),
            data["staff"].id,
        )

        # Create Recipe A using the sauce
        recipe_a = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][1].id,
                name="Dish A",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["flour"].id,
                        "quantity": 0.5,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": sauce_recipe.id, "quantity": 0.5}],
            ),
            data["staff"].id,
        )

        # Create Recipe B also using the sauce - this should be allowed
        recipe_b = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][2].id,
                name="Dish B",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["sugar"].id,
                        "quantity": 0.3,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": sauce_recipe.id, "quantity": 0.7}],
            ),
            data["staff"].id,
        )

        # Both recipes should exist and share the sauce
        assert recipe_a.id != recipe_b.id
        assert len(recipe_a.sub_recipes) == 1
        assert len(recipe_b.sub_recipes) == 1
        assert recipe_a.sub_recipes[0].sub_recipe_id == sauce_recipe.id
        assert recipe_b.sub_recipes[0].sub_recipe_id == sauce_recipe.id

    def test_update_sub_recipes_with_circular_check(self, db: Session, setup_test_data):
        """Test updating sub-recipes with circular dependency prevention"""
        data = setup_test_data
        service = RecipeService(db)

        # Create recipes
        recipes = []
        for i in range(3):
            recipe = service.create_recipe(
                RecipeCreate(
                    menu_item_id=data["menu_items"][i].id,
                    name=f"Recipe {i}",
                    yield_quantity=1,
                    status=RecipeStatus.ACTIVE,
                    ingredients=[
                        {
                            "inventory_id": data["inventory"]["flour"].id,
                            "quantity": 0.5,
                            "unit": "kg",
                        }
                    ],
                ),
                data["staff"].id,
            )
            recipes.append(recipe)

        # Set up initial relationship: Recipe 0 -> Recipe 1
        service.update_recipe_sub_recipes(
            recipes[0].id,
            [RecipeSubRecipeCreate(sub_recipe_id=recipes[1].id, quantity=1.0)],
            data["staff"].id,
        )

        # Try to update Recipe 1 to include Recipe 0 (would create cycle)
        with pytest.raises(HTTPException) as exc_info:
            service.update_recipe_sub_recipes(
                recipes[1].id,
                [RecipeSubRecipeCreate(sub_recipe_id=recipes[0].id, quantity=1.0)],
                data["staff"].id,
            )

        assert "circular" in str(exc_info.value.detail).lower()

    def test_hierarchy_validation(self, db: Session, setup_test_data):
        """Test full hierarchy validation"""
        data = setup_test_data
        service = RecipeService(db)

        # Create a complex hierarchy
        # Level 0: Base ingredients
        base_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][0].id,
                name="Base Recipe",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["flour"].id,
                        "quantity": 1.0,
                        "unit": "kg",
                    }
                ],
            ),
            data["staff"].id,
        )

        # Level 1: Uses base
        level1_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][1].id,
                name="Level 1 Recipe",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["butter"].id,
                        "quantity": 0.5,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": base_recipe.id, "quantity": 2.0}],
            ),
            data["staff"].id,
        )

        # Level 2: Uses level 1
        level2_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][2].id,
                name="Level 2 Recipe",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["sugar"].id,
                        "quantity": 0.3,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": level1_recipe.id, "quantity": 1.5}],
            ),
            data["staff"].id,
        )

        # Validate hierarchy
        validation = service.validate_recipe_hierarchy(level2_recipe.id)

        assert validation["is_valid"] is True
        assert validation["depth"] == 2  # 0-indexed, so 2 levels below
        assert validation["total_sub_recipes"] == 2  # level1 and base
        assert len(validation["cycles"]) == 0

    def test_dependencies_analysis(self, db: Session, setup_test_data):
        """Test getting recipe dependencies and dependents"""
        data = setup_test_data
        service = RecipeService(db)

        # Create recipes with relationships
        sauce = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][0].id,
                name="Sauce",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["butter"].id,
                        "quantity": 0.2,
                        "unit": "kg",
                    }
                ],
            ),
            data["staff"].id,
        )

        pasta = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][1].id,
                name="Pasta",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["flour"].id,
                        "quantity": 0.5,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[{"sub_recipe_id": sauce.id, "quantity": 0.3}],
            ),
            data["staff"].id,
        )

        dish = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][2].id,
                name="Complete Dish",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["sugar"].id,
                        "quantity": 0.1,
                        "unit": "kg",
                    }
                ],
                sub_recipes=[
                    {"sub_recipe_id": pasta.id, "quantity": 1.0},
                    {
                        "sub_recipe_id": sauce.id,
                        "quantity": 0.2,
                    },  # Also uses sauce directly
                ],
            ),
            data["staff"].id,
        )

        # Analyze dependencies
        sauce_analysis = service.get_recipe_dependencies_analysis(sauce.id)
        pasta_analysis = service.get_recipe_dependencies_analysis(pasta.id)
        dish_analysis = service.get_recipe_dependencies_analysis(dish.id)

        # Sauce has no dependencies but is used by pasta and dish
        assert sauce_analysis["total_dependencies"] == 0
        assert sauce_analysis["total_dependents"] == 2

        # Pasta depends on sauce and is used by dish
        assert pasta_analysis["total_dependencies"] == 1
        assert pasta_analysis["total_dependents"] == 1

        # Dish depends on both pasta and sauce
        assert dish_analysis["total_dependencies"] == 2
        assert dish_analysis["total_dependents"] == 0

    def test_batch_sub_recipe_validation(self, db: Session, setup_test_data):
        """Test validating multiple sub-recipes at once"""
        data = setup_test_data
        service = RecipeService(db)

        # Create recipes
        recipes = []
        for i in range(4):
            recipe = service.create_recipe(
                RecipeCreate(
                    menu_item_id=data["menu_items"][i].id,
                    name=f"Recipe {i}",
                    yield_quantity=1,
                    status=RecipeStatus.ACTIVE,
                    ingredients=[
                        {
                            "inventory_id": data["inventory"]["flour"].id,
                            "quantity": 0.5,
                            "unit": "kg",
                        }
                    ],
                ),
                data["staff"].id,
            )
            recipes.append(recipe)

        # Try to add multiple sub-recipes including a duplicate
        with pytest.raises(HTTPException) as exc_info:
            service.update_recipe_sub_recipes(
                recipes[0].id,
                [
                    RecipeSubRecipeCreate(sub_recipe_id=recipes[1].id, quantity=1.0),
                    RecipeSubRecipeCreate(sub_recipe_id=recipes[2].id, quantity=1.0),
                    RecipeSubRecipeCreate(
                        sub_recipe_id=recipes[1].id, quantity=2.0
                    ),  # Duplicate
                ],
                data["staff"].id,
            )

        assert "duplicate" in str(exc_info.value.detail).lower()

    def test_cost_recalculation_with_circular_prevention(
        self, db: Session, setup_test_data
    ):
        """Test that costs are properly calculated even with circular dependency checks"""
        data = setup_test_data
        service = RecipeService(db)

        # Create base recipe with known cost
        base_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][0].id,
                name="Base Recipe",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["flour"].id,
                        "quantity": 1.0,  # 1kg at 2.0 per kg = 2.0
                        "unit": "kg",
                    },
                    {
                        "inventory_id": data["inventory"]["butter"].id,
                        "quantity": 0.5,  # 0.5kg at 5.0 per kg = 2.5
                        "unit": "kg",
                    },
                ],
            ),
            data["staff"].id,
        )

        # Base recipe cost should be 2.0 + 2.5 = 4.5
        assert base_recipe.total_cost == 4.5

        # Create recipe using base as sub-recipe
        complex_recipe = service.create_recipe(
            RecipeCreate(
                menu_item_id=data["menu_items"][1].id,
                name="Complex Recipe",
                yield_quantity=1,
                status=RecipeStatus.ACTIVE,
                ingredients=[
                    {
                        "inventory_id": data["inventory"]["sugar"].id,
                        "quantity": 1.0,  # 1kg at 3.0 per kg = 3.0
                        "unit": "kg",
                    }
                ],
                sub_recipes=[
                    {
                        "sub_recipe_id": base_recipe.id,
                        "quantity": 2.0,  # 2x base recipe = 2 * 4.5 = 9.0
                    }
                ],
            ),
            data["staff"].id,
        )

        # Complex recipe cost should be 3.0 + 9.0 = 12.0
        assert complex_recipe.total_cost == 12.0

        # Verify circular dependency still prevented
        with pytest.raises(HTTPException) as exc_info:
            service.add_sub_recipe(
                base_recipe.id,
                RecipeSubRecipeCreate(sub_recipe_id=complex_recipe.id, quantity=1.0),
                data["staff"].id,
            )

        assert "circular" in str(exc_info.value.detail).lower()
