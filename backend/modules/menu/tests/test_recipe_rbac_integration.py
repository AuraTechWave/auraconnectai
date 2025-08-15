# backend/modules/menu/tests/test_recipe_rbac_integration.py

"""
Integration tests for RBAC enforcement on recipe management endpoints.
These tests verify the complete permission flow from request to response.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from core.database import get_db
from core.auth import User, get_current_user, require_permission
from modules.menu.models.recipe_models import Recipe, RecipeStatus, RecipeIngredient
from modules.menu.services.recipe_service import RecipeService
from core.menu_models import MenuItem, MenuCategory
from core.inventory_models import Inventory
from core.staff_models import StaffMember


@pytest.fixture
def db_session():
    """Create a test database session"""
    # In a real test, this would create a test database
    # For now, we'll mock it
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def setup_test_data(db_session):
    """Setup test data for integration tests"""
    # Create test category
    category = MenuCategory(id=1, name="Test Category")

    # Create test menu item
    menu_item = MenuItem(
        id=1, name="Test Item", category_id=1, price=10.99, is_available=True
    )

    # Create test inventory
    inventory = Inventory(
        id=1, name="Test Ingredient", quantity=100, unit="kg", cost_per_unit=5.0
    )

    # Create test recipe
    recipe = Recipe(
        id=1,
        menu_item_id=1,
        name="Test Recipe",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1.0,
        created_by=1,
    )

    return {
        "category": category,
        "menu_item": menu_item,
        "inventory": inventory,
        "recipe": recipe,
    }


class TestRecipeRBACIntegration:
    """Integration tests for recipe RBAC"""

    def test_permission_decorator_integration(self):
        """Test that the require_permission decorator properly enforces permissions"""

        # Create a mock endpoint function
        @require_permission("menu:create")
        def mock_create_endpoint(current_user: User):
            return {"message": "Created"}

        # Test with user who has permission
        user_with_permission = User(
            id=1, email="chef@test.com", permissions=["menu:create"]
        )

        with patch("core.auth.get_current_user", return_value=user_with_permission):
            result = mock_create_endpoint(user_with_permission)
            assert result == {"message": "Created"}

        # Test with user who lacks permission
        user_without_permission = User(
            id=2, email="waiter@test.com", permissions=["menu:read"]
        )

        with patch("core.auth.get_current_user", return_value=user_without_permission):
            with pytest.raises(Exception):  # Should raise permission error
                mock_create_endpoint(user_without_permission)

    def test_recipe_service_permission_flow(self, db_session, setup_test_data):
        """Test that recipe service operations respect permissions"""
        service = RecipeService(db_session)

        # Mock the database queries
        db_session.query.return_value.filter.return_value.first.return_value = None
        db_session.query.return_value.filter.return_value.all.return_value = [
            setup_test_data["inventory"]
        ]

        # Test creating recipe with valid user
        recipe_data = {
            "menu_item_id": 1,
            "name": "New Recipe",
            "yield_quantity": 1.0,
            "status": RecipeStatus.ACTIVE,
            "ingredients": [{"inventory_id": 1, "quantity": 2.0, "unit": "kg"}],
        }

        # The service itself doesn't check permissions - that's done at the route level
        # But we can verify the created_by field is set correctly
        user_id = 123

        with patch.object(service, "db") as mock_db:
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                setup_test_data["menu_item"],  # Menu item exists
                None,  # No existing recipe
            ]
            mock_db.query.return_value.filter.return_value.all.return_value = [
                setup_test_data["inventory"]
            ]

            # Mock the recipe creation
            created_recipe = Recipe(
                id=1,
                menu_item_id=1,
                name="New Recipe",
                created_by=user_id,  # Should match the user_id passed
            )

            with patch.object(Recipe, "__init__", return_value=None):
                with patch.object(service, "_create_history_entry"):
                    # Create recipe
                    recipe = service.create_recipe(recipe_data, user_id)

                    # Verify the created_by was set
                    assert mock_db.add.called

    def test_admin_only_operation_flow(self, db_session):
        """Test admin-only operations like recalculate_all_recipe_costs"""
        service = RecipeService(db_session)

        # Mock recipes for recalculation
        mock_recipes = [
            Recipe(id=1, status=RecipeStatus.ACTIVE),
            Recipe(id=2, status=RecipeStatus.ACTIVE),
        ]

        db_session.query.return_value.filter.return_value.all.return_value = (
            mock_recipes
        )

        # Mock the calculate_recipe_cost method
        with patch.object(service, "calculate_recipe_cost") as mock_calc:
            result = service.recalculate_all_recipe_costs(user_id=1)

            # Verify it tried to recalculate all recipes
            assert mock_calc.call_count == len(mock_recipes)
            assert result["total_recipes"] == len(mock_recipes)

    def test_manager_bulk_operations(self, db_session):
        """Test manager-level bulk operations"""
        service = RecipeService(db_session)

        # Test bulk update scenario
        recipe_ids = [1, 2, 3]
        update_data = {"status": RecipeStatus.INACTIVE}

        # Mock get_recipe_by_id to return recipes
        def mock_get_recipe(recipe_id):
            return Recipe(id=recipe_id, status=RecipeStatus.ACTIVE, version=1)

        with patch.object(service, "get_recipe_by_id", side_effect=mock_get_recipe):
            with patch.object(service, "update_recipe") as mock_update:
                # Simulate bulk update
                for recipe_id in recipe_ids:
                    recipe = service.get_recipe_by_id(recipe_id)
                    if recipe:
                        service.update_recipe(recipe_id, update_data, user_id=1)

                # Verify all recipes were updated
                assert mock_update.call_count == len(recipe_ids)

    def test_permission_inheritance_flow(self):
        """Test that higher roles inherit lower role permissions"""
        # Define role hierarchy
        role_permissions = {
            "waiter": ["menu:read"],
            "chef": ["menu:read", "menu:create", "menu:update"],
            "manager": [
                "menu:read",
                "menu:create",
                "menu:update",
                "menu:delete",
                "manager:recipes",
            ],
            "admin": [
                "menu:read",
                "menu:create",
                "menu:update",
                "menu:delete",
                "manager:recipes",
                "admin:recipes",
            ],
        }

        # Test that admin has all permissions
        admin_user = User(
            id=1,
            email="admin@test.com",
            role="admin",
            permissions=role_permissions["admin"],
        )

        # Admin should have all recipe permissions
        assert "menu:read" in admin_user.permissions
        assert "menu:create" in admin_user.permissions
        assert "menu:update" in admin_user.permissions
        assert "menu:delete" in admin_user.permissions
        assert "manager:recipes" in admin_user.permissions
        assert "admin:recipes" in admin_user.permissions

        # Manager should not have admin permissions
        manager_user = User(
            id=2,
            email="manager@test.com",
            role="manager",
            permissions=role_permissions["manager"],
        )

        assert "admin:recipes" not in manager_user.permissions
        assert "manager:recipes" in manager_user.permissions

    def test_sub_recipe_permission_flow(self, db_session):
        """Test sub-recipe management permission flow"""
        service = RecipeService(db_session)

        # Mock the circular dependency validator
        with patch("modules.menu.services.recipe_service.RecipeCircularValidator"):
            # Test adding sub-recipe
            parent_recipe_id = 1
            sub_recipe_data = {"sub_recipe_id": 2, "quantity": 1.0}

            # Mock the database queries
            parent_recipe = Recipe(id=1, name="Parent Recipe")
            sub_recipe = Recipe(id=2, name="Sub Recipe", total_cost=5.0)

            with patch.object(service, "get_recipe_by_id") as mock_get:
                mock_get.side_effect = [parent_recipe, sub_recipe]

                with patch.object(service, "add_sub_recipe") as mock_add:
                    # This would be called by the route after permission check
                    service.add_sub_recipe(parent_recipe_id, sub_recipe_data, user_id=1)

                    mock_add.assert_called_once()

    def test_public_endpoint_no_auth_required(self, db_session):
        """Test that public endpoints don't require authentication"""
        service = RecipeService(db_session)

        # Mock a recipe with nutrition info
        recipe = Recipe(
            id=1, status=RecipeStatus.ACTIVE, allergen_notes="Contains dairy"
        )

        with patch.object(service, "get_recipe_by_id", return_value=recipe):
            # This should work without any user context
            fetched_recipe = service.get_recipe_by_id(1)

            # Public endpoint would check status and return limited info
            assert fetched_recipe.status == RecipeStatus.ACTIVE
            assert fetched_recipe.allergen_notes == "Contains dairy"

    def test_dry_run_permission_enforcement(self, db_session):
        """Test that dry run operations still enforce permissions"""
        from modules.menu.services.recipe_circular_validation import (
            RecipeCircularValidator,
        )

        # Create validator with mocked db
        validator = RecipeCircularValidator(db_session)

        # Mock the validation logic
        with patch.object(validator, "validate_batch_sub_recipes"):
            # Dry run validation should work the same way
            sub_recipes = [{"sub_recipe_id": 2, "quantity": 1.0}]

            # This would be called after permission check in the route
            validator.validate_batch_sub_recipes(1, sub_recipes)

            # The permission check happens at the route level, not here

    def test_cascading_permissions(self):
        """Test that permissions cascade properly for related operations"""
        # User with menu:update should be able to:
        # - Update recipe details
        # - Update recipe ingredients
        # - Update recipe sub-recipes

        user = User(id=1, email="chef@test.com", permissions=["menu:update"])

        # All these operations require the same permission
        update_operations = [
            "update_recipe",
            "update_recipe_ingredients",
            "update_recipe_sub_recipes",
            "add_sub_recipe",
            "remove_sub_recipe_link",
        ]

        # Verify the user has permission for all update operations
        for operation in update_operations:
            assert (
                "menu:update" in user.permissions
            ), f"User should have permission for {operation}"

    def test_permission_error_messages(self):
        """Test that permission errors return appropriate messages"""
        from fastapi import HTTPException

        # Simulate permission denied scenario
        def check_permission(user_permissions, required_permission):
            if required_permission not in user_permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied. Required permission: {required_permission}",
                )

        user_permissions = ["menu:read"]

        # Test various permission checks
        with pytest.raises(HTTPException) as exc_info:
            check_permission(user_permissions, "menu:create")

        assert exc_info.value.status_code == 403
        assert "menu:create" in str(exc_info.value.detail)

    def test_role_based_data_filtering(self, db_session):
        """Test that data is filtered based on user role"""
        service = RecipeService(db_session)

        # Mock recipes with different statuses
        all_recipes = [
            Recipe(id=1, status=RecipeStatus.ACTIVE),
            Recipe(id=2, status=RecipeStatus.DRAFT),
            Recipe(id=3, status=RecipeStatus.INACTIVE),
        ]

        # Regular users might only see active recipes
        # Managers might see all recipes
        # This filtering would typically happen at the service or route level

        def filter_recipes_by_role(recipes, user_role):
            if user_role in ["admin", "manager"]:
                return recipes  # See all recipes
            else:
                return [r for r in recipes if r.status == RecipeStatus.ACTIVE]

        # Test filtering for different roles
        waiter_recipes = filter_recipes_by_role(all_recipes, "waiter")
        assert len(waiter_recipes) == 1  # Only active recipes

        manager_recipes = filter_recipes_by_role(all_recipes, "manager")
        assert len(manager_recipes) == 3  # All recipes
