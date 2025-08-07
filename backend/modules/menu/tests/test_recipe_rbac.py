# backend/modules/menu/tests/test_recipe_rbac.py

"""
Comprehensive RBAC (Role-Based Access Control) tests for recipe management endpoints.
Tests permission enforcement for different user roles and unauthorized access scenarios.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from main import app
from core.auth import User
from modules.menu.models.recipe_models import Recipe, RecipeStatus
from modules.menu.schemas.recipe_schemas import RecipeCreate, RecipeUpdate, BulkRecipeUpdate


class TestRecipeRBAC:
    """Test suite for RBAC enforcement on recipe management endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def admin_user(self):
        """Create admin user with all permissions"""
        return User(
            id=1,
            email="admin@test.com",
            name="Admin User",
            role="admin",
            permissions=["menu:create", "menu:read", "menu:update", "menu:delete", 
                        "admin:recipes", "manager:recipes"]
        )

    @pytest.fixture
    def manager_user(self):
        """Create manager user with manager permissions"""
        return User(
            id=2,
            email="manager@test.com",
            name="Manager User",
            role="manager",
            permissions=["menu:create", "menu:read", "menu:update", "menu:delete", 
                        "manager:recipes"]
        )

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
                    "inventory_id": 1,
                    "quantity": 2.0,
                    "unit": "kg"
                }
            ]
        }

    # Test Basic CRUD Permissions

    def test_create_recipe_with_permission(self, client, chef_user, mock_db):
        """Test that users with menu:create permission can create recipes"""
        with patch('core.auth.get_current_user', return_value=chef_user):
            with patch('core.database.get_db', return_value=mock_db):
                # Mock the service response
                mock_recipe = Recipe(
                    id=1,
                    menu_item_id=1,
                    name="Test Recipe",
                    status=RecipeStatus.ACTIVE,
                    created_by=chef_user.id
                )
                
                with patch('modules.menu.services.recipe_service.RecipeService.create_recipe', 
                          return_value=mock_recipe):
                    response = client.post(
                        "/recipes/",
                        json=self.sample_recipe_data(),
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_201_CREATED

    def test_create_recipe_without_permission(self, client, waiter_user):
        """Test that users without menu:create permission cannot create recipes"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            response = client.post(
                "/recipes/",
                json=self.sample_recipe_data(),
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_recipe_with_permission(self, client, waiter_user, mock_db):
        """Test that users with menu:read permission can read recipes"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1, name="Test Recipe")
                
                with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                          return_value=mock_recipe):
                    response = client.get(
                        "/recipes/1",
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

    def test_read_recipe_without_permission(self, client, unauthorized_user):
        """Test that users without menu:read permission cannot read recipes"""
        with patch('core.auth.get_current_user', return_value=unauthorized_user):
            response = client.get(
                "/recipes/1",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_recipe_with_permission(self, client, chef_user, mock_db):
        """Test that users with menu:update permission can update recipes"""
        with patch('core.auth.get_current_user', return_value=chef_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1, name="Updated Recipe")
                
                with patch('modules.menu.services.recipe_service.RecipeService.update_recipe',
                          return_value=mock_recipe):
                    response = client.put(
                        "/recipes/1",
                        json={"name": "Updated Recipe"},
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

    def test_update_recipe_without_permission(self, client, waiter_user):
        """Test that users without menu:update permission cannot update recipes"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            response = client.put(
                "/recipes/1",
                json={"name": "Updated Recipe"},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_recipe_with_permission(self, client, chef_user, mock_db):
        """Test that users with menu:delete permission can delete recipes"""
        with patch('core.auth.get_current_user', return_value=chef_user):
            with patch('core.database.get_db', return_value=mock_db):
                with patch('modules.menu.services.recipe_service.RecipeService.delete_recipe',
                          return_value=True):
                    response = client.delete(
                        "/recipes/1",
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_recipe_without_permission(self, client, waiter_user):
        """Test that users without menu:delete permission cannot delete recipes"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            response = client.delete(
                "/recipes/1",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Admin-Only Endpoints

    def test_recalculate_costs_admin_only(self, client, admin_user, manager_user, mock_db):
        """Test that only admin users can recalculate all costs"""
        # Test with admin user - should succeed
        with patch('core.auth.get_current_user', return_value=admin_user):
            with patch('core.database.get_db', return_value=mock_db):
                with patch('modules.menu.services.recipe_service.RecipeService.recalculate_all_recipe_costs',
                          return_value={"updated": 10, "failed": 0}):
                    response = client.post(
                        "/recipes/recalculate-costs",
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

        # Test with manager user - should fail
        with patch('core.auth.get_current_user', return_value=manager_user):
            response = client.post(
                "/recipes/recalculate-costs",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Manager-Only Endpoints

    def test_bulk_update_manager_only(self, client, manager_user, chef_user, mock_db):
        """Test that only manager/admin users can perform bulk updates"""
        bulk_data = {
            "recipe_ids": [1, 2, 3],
            "updates": {"status": "inactive"}
        }

        # Test with manager user - should succeed
        with patch('core.auth.get_current_user', return_value=manager_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1, status=RecipeStatus.ACTIVE)
                with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                          return_value=mock_recipe):
                    with patch('modules.menu.services.recipe_service.RecipeService.update_recipe',
                              return_value=mock_recipe):
                        response = client.put(
                            "/recipes/bulk/update",
                            json=bulk_data,
                            headers={"Authorization": "Bearer fake-token"}
                        )
                        
                        assert response.status_code == status.HTTP_200_OK

        # Test with chef user - should fail
        with patch('core.auth.get_current_user', return_value=chef_user):
            response = client.put(
                "/recipes/bulk/update",
                json=bulk_data,
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_activate_manager_only(self, client, manager_user, chef_user, mock_db):
        """Test that only manager/admin users can perform bulk activation"""
        # Test with manager user - should succeed
        with patch('core.auth.get_current_user', return_value=manager_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1, status=RecipeStatus.INACTIVE)
                with patch('modules.menu.services.recipe_service.RecipeService.update_recipe',
                          return_value=mock_recipe):
                    response = client.put(
                        "/recipes/bulk/activate",
                        json=[1, 2, 3],
                        params={"active": True},
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

        # Test with chef user - should fail
        with patch('core.auth.get_current_user', return_value=chef_user):
            response = client.put(
                "/recipes/bulk/activate",
                json=[1, 2, 3],
                params={"active": True},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_approve_recipe_manager_only(self, client, manager_user, chef_user, mock_db):
        """Test that only manager/admin users can approve recipes"""
        # Test with manager user - should succeed
        with patch('core.auth.get_current_user', return_value=manager_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1, status=RecipeStatus.DRAFT)
                with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                          return_value=mock_recipe):
                    with patch('modules.menu.services.recipe_service.RecipeService.update_recipe',
                              return_value=mock_recipe):
                        # Mock the database operations in the endpoint
                        mock_db.commit = Mock()
                        
                        response = client.post(
                            "/recipes/1/approve",
                            headers={"Authorization": "Bearer fake-token"}
                        )
                        
                        assert response.status_code == status.HTTP_200_OK

        # Test with chef user - should fail
        with patch('core.auth.get_current_user', return_value=chef_user):
            response = client.post(
                "/recipes/1/approve",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Public Endpoints (No Auth Required)

    def test_public_nutrition_endpoint(self, client, mock_db):
        """Test that public nutrition endpoint doesn't require authentication"""
        with patch('core.database.get_db', return_value=mock_db):
            mock_recipe = Recipe(
                id=1, 
                status=RecipeStatus.ACTIVE,
                allergen_notes="Contains nuts"
            )
            
            with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                      return_value=mock_recipe):
                # No authorization header
                response = client.get("/recipes/public/1/nutrition")
                
                # Should still return 200 OK
                assert response.status_code == status.HTTP_200_OK

    # Test Sub-Recipe Management Permissions

    def test_update_sub_recipes_with_permission(self, client, chef_user, mock_db):
        """Test that users with menu:update can manage sub-recipes"""
        sub_recipes = [
            {"sub_recipe_id": 2, "quantity": 1.0}
        ]

        with patch('core.auth.get_current_user', return_value=chef_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1)
                with patch('modules.menu.services.recipe_service.RecipeService.update_recipe_sub_recipes',
                          return_value=mock_recipe):
                    response = client.put(
                        "/recipes/1/sub-recipes",
                        json=sub_recipes,
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

    def test_update_sub_recipes_without_permission(self, client, waiter_user):
        """Test that users without menu:update cannot manage sub-recipes"""
        sub_recipes = [
            {"sub_recipe_id": 2, "quantity": 1.0}
        ]

        with patch('core.auth.get_current_user', return_value=waiter_user):
            response = client.put(
                "/recipes/1/sub-recipes",
                json=sub_recipes,
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Dry Run with Permissions

    def test_dry_run_respects_permissions(self, client, chef_user, waiter_user, mock_db):
        """Test that dry run operations still enforce permissions"""
        sub_recipes = [
            {"sub_recipe_id": 2, "quantity": 1.0}
        ]

        # Chef with update permission - dry run should work
        with patch('core.auth.get_current_user', return_value=chef_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_recipe = Recipe(id=1)
                with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                          return_value=mock_recipe):
                    response = client.put(
                        "/recipes/1/sub-recipes",
                        json=sub_recipes,
                        params={"dry_run": True},
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    assert response.json()["dry_run"] is True

        # Waiter without update permission - dry run should still fail
        with patch('core.auth.get_current_user', return_value=waiter_user):
            response = client.put(
                "/recipes/1/sub-recipes",
                json=sub_recipes,
                params={"dry_run": True},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Search/List Permissions

    def test_search_recipes_with_permission(self, client, waiter_user, mock_db):
        """Test that users with menu:read can search recipes"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            with patch('core.database.get_db', return_value=mock_db):
                with patch('modules.menu.services.recipe_service.RecipeService.search_recipes',
                          return_value=([], 0)):
                    response = client.get(
                        "/recipes/",
                        params={"query": "test"},
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

    def test_search_recipes_without_permission(self, client, unauthorized_user):
        """Test that users without menu:read cannot search recipes"""
        with patch('core.auth.get_current_user', return_value=unauthorized_user):
            response = client.get(
                "/recipes/",
                params={"query": "test"},
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test Compliance Report Permissions

    def test_compliance_report_with_permission(self, client, waiter_user, mock_db):
        """Test that users with menu:read can view compliance reports"""
        with patch('core.auth.get_current_user', return_value=waiter_user):
            with patch('core.database.get_db', return_value=mock_db):
                mock_report = {
                    "total_menu_items": 10,
                    "items_with_recipes": 8,
                    "items_without_recipes": 2,
                    "compliance_percentage": 80.0
                }
                
                with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_compliance_report',
                          return_value=mock_report):
                    response = client.get(
                        "/recipes/compliance/report",
                        headers={"Authorization": "Bearer fake-token"}
                    )
                    
                    assert response.status_code == status.HTTP_200_OK

    # Test Unauthorized Access

    def test_no_authentication_header(self, client):
        """Test that requests without authentication header are rejected"""
        response = client.get("/recipes/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_authentication_token(self, client):
        """Test that requests with invalid token are rejected"""
        with patch('core.auth.get_current_user', side_effect=Exception("Invalid token")):
            response = client.get(
                "/recipes/1",
                headers={"Authorization": "Bearer invalid-token"}
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test Cross-Permission Scenarios

    def test_chef_cannot_access_manager_endpoints(self, client, chef_user):
        """Test that chef users cannot access manager-only endpoints"""
        manager_endpoints = [
            ("/recipes/bulk/update", "put", {"recipe_ids": [1], "updates": {}}),
            ("/recipes/bulk/activate", "put", [1, 2, 3]),
            ("/recipes/1/approve", "post", None)
        ]

        for endpoint, method, json_data in manager_endpoints:
            with patch('core.auth.get_current_user', return_value=chef_user):
                if method == "put":
                    response = client.put(
                        endpoint,
                        json=json_data,
                        headers={"Authorization": "Bearer fake-token"}
                    )
                elif method == "post":
                    response = client.post(
                        endpoint,
                        headers={"Authorization": "Bearer fake-token"}
                    )
                
                assert response.status_code == status.HTTP_403_FORBIDDEN, \
                    f"Chef should not access {endpoint}"

    def test_admin_can_access_all_endpoints(self, client, admin_user, mock_db):
        """Test that admin users can access all recipe endpoints"""
        endpoints_to_test = [
            # Regular endpoints
            ("/recipes/1", "get"),
            # Manager endpoints
            ("/recipes/1/approve", "post"),
            # Admin endpoints
            ("/recipes/recalculate-costs", "post")
        ]

        for endpoint, method in endpoints_to_test:
            with patch('core.auth.get_current_user', return_value=admin_user):
                with patch('core.database.get_db', return_value=mock_db):
                    # Mock appropriate service methods
                    mock_recipe = Recipe(id=1, status=RecipeStatus.ACTIVE)
                    
                    with patch('modules.menu.services.recipe_service.RecipeService.get_recipe_by_id',
                              return_value=mock_recipe):
                        with patch('modules.menu.services.recipe_service.RecipeService.update_recipe',
                                  return_value=mock_recipe):
                            with patch('modules.menu.services.recipe_service.RecipeService.recalculate_all_recipe_costs',
                                      return_value={"updated": 1}):
                                if method == "get":
                                    response = client.get(
                                        endpoint,
                                        headers={"Authorization": "Bearer fake-token"}
                                    )
                                elif method == "post":
                                    response = client.post(
                                        endpoint,
                                        headers={"Authorization": "Bearer fake-token"}
                                    )
                                
                                assert response.status_code in [200, 201, 204], \
                                    f"Admin should access {endpoint}"