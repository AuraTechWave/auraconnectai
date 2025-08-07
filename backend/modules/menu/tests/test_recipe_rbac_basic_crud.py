# backend/modules/menu/tests/test_recipe_rbac_basic_crud.py

"""
RBAC tests for basic CRUD operations on recipe management endpoints.
Tests permission enforcement for create, read, update, and delete operations.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from datetime import datetime

from main import app
from core.auth import User
from modules.menu.models.recipe_models import Recipe, RecipeStatus
from modules.menu.schemas.recipe_schemas import RecipeCreate, RecipeUpdate


class TestRecipeBasicCRUD:
    """Test suite for basic CRUD operations with RBAC enforcement"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def chef_user(self):
        """Create chef user with basic menu permissions"""
        return User(
            id=3,
            email="chef@test.com",
            name="Chef User",
            role="chef",
            permissions=["menu:create", "menu:read", "menu:update"]
        )

    @pytest.fixture
    def waiter_user(self):
        """Create waiter user with read-only permissions"""
        return User(
            id=4,
            email="waiter@test.com",
            name="Waiter User",
            role="waiter",
            permissions=["menu:read"]
        )

    @pytest.fixture
    def unauthorized_user(self):
        """Create user with no recipe permissions"""
        return User(
            id=5,
            email="unauthorized@test.com",
            name="Unauthorized User",
            role="cashier",
            permissions=["orders:read"]  # No menu permissions
        )

    @pytest.fixture
    def sample_recipe_data(self):
        """Sample recipe creation data"""
        return {
            "menu_item_id": 1,
            "name": "Test Recipe",
            "yield_quantity": 1.0,
            "status": "active",
            "ingredients": [
                {
                    "ingredient_id": 1,
                    "quantity": 0.5,
                    "unit": "kg"
                }
            ]
        }

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_create_recipe_with_permission(self, mock_auth, mock_session, client, chef_user, mock_db):
        """Test that users with menu:create permission can create recipes"""
        mock_auth.return_value = chef_user
        mock_session.return_value = mock_db
        
        # Mock the recipe service
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.create_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE
            )
            
            response = client.post(
                "/api/v1/recipes",
                json=self.sample_recipe_data(),
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["name"] == "Test Recipe"
            mock_service.create_recipe.assert_called_once()

    @patch('core.auth.get_current_user')
    def test_create_recipe_without_permission(self, mock_auth, client, waiter_user):
        """Test that users without menu:create permission cannot create recipes"""
        mock_auth.return_value = waiter_user
        
        response = client.post(
            "/api/v1/recipes",
            json=self.sample_recipe_data(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_read_recipe_with_permission(self, mock_auth, mock_session, client, waiter_user, mock_db):
        """Test that users with menu:read permission can read recipes"""
        mock_auth.return_value = waiter_user
        mock_session.return_value = mock_db
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_recipe_by_id.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE
            )
            
            response = client.get(
                "/api/v1/recipes/1",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["name"] == "Test Recipe"

    @patch('core.auth.get_current_user')
    def test_read_recipe_without_permission(self, mock_auth, client, unauthorized_user):
        """Test that users without menu:read permission cannot read recipes"""
        mock_auth.return_value = unauthorized_user
        
        response = client.get(
            "/api/v1/recipes/1",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_update_recipe_with_permission(self, mock_auth, mock_session, client, chef_user, mock_db):
        """Test that users with menu:update permission can update recipes"""
        mock_auth.return_value = chef_user
        mock_session.return_value = mock_db
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.update_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Updated Recipe",
                yield_quantity=2.0,
                status=RecipeStatus.ACTIVE
            )
            
            update_data = {"name": "Updated Recipe", "yield_quantity": 2.0}
            response = client.put(
                "/api/v1/recipes/1",
                json=update_data,
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["name"] == "Updated Recipe"

    @patch('core.auth.get_current_user')
    def test_update_recipe_without_permission(self, mock_auth, client, waiter_user):
        """Test that users without menu:update permission cannot update recipes"""
        mock_auth.return_value = waiter_user
        
        update_data = {"name": "Updated Recipe"}
        response = client.put(
            "/api/v1/recipes/1",
            json=update_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_delete_recipe_with_permission(self, mock_auth, mock_session, client, chef_user, mock_db):
        """Test that users with menu:delete permission can delete recipes"""
        mock_auth.return_value = chef_user
        mock_session.return_value = mock_db
        
        # Note: Chef doesn't have delete permission by default
        chef_user.permissions.append("menu:delete")
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.delete_recipe.return_value = True
            
            response = client.delete(
                "/api/v1/recipes/1",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK

    @patch('core.auth.get_current_user')
    def test_delete_recipe_without_permission(self, mock_auth, client, waiter_user):
        """Test that users without menu:delete permission cannot delete recipes"""
        mock_auth.return_value = waiter_user
        
        response = client.delete(
            "/api/v1/recipes/1",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_search_recipes_with_permission(self, mock_auth, mock_session, client, waiter_user, mock_db):
        """Test that users with menu:read permission can search recipes"""
        mock_auth.return_value = waiter_user
        mock_session.return_value = mock_db
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.search_recipes.return_value = ([], 0)
            
            response = client.get(
                "/api/v1/recipes/search?query=test",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK

    @patch('core.auth.get_current_user')
    def test_search_recipes_without_permission(self, mock_auth, client, unauthorized_user):
        """Test that users without menu:read permission cannot search recipes"""
        mock_auth.return_value = unauthorized_user
        
        response = client.get(
            "/api/v1/recipes/search?query=test",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('core.db.SessionLocal')
    @patch('core.auth.get_current_user')
    def test_dry_run_respects_permissions(self, mock_auth, mock_session, client, chef_user, waiter_user, mock_db):
        """Test that dry run operations respect the same permissions as actual operations"""
        # Test with permission
        mock_auth.return_value = chef_user
        mock_session.return_value = mock_db
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.create_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE
            )
            
            response = client.post(
                "/api/v1/recipes?dry_run=true",
                json=self.sample_recipe_data(),
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            
        # Test without permission
        mock_auth.return_value = waiter_user
        
        response = client.post(
            "/api/v1/recipes?dry_run=true",
            json=self.sample_recipe_data(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN