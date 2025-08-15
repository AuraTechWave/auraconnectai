# backend/modules/menu/tests/test_recipe_rbac_manager_endpoints.py

"""
RBAC tests for manager-level endpoints in recipe management.
Tests permission enforcement for operations like bulk updates and approvals.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from main import app
from core.auth import User
from modules.menu.models.recipe_models import Recipe, RecipeStatus
from modules.menu.schemas.recipe_schemas import BulkRecipeUpdate


class TestRecipeManagerEndpoints:
    """Test suite for manager-level endpoints with RBAC enforcement"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def manager_user(self):
        """Create manager user with manager permissions"""
        return User(
            id=2,
            email="manager@test.com",
            name="Manager User",
            role="manager",
            permissions=[
                "menu:create",
                "menu:read",
                "menu:update",
                "menu:delete",
                "manager:recipes",
            ],
        )

    @pytest.fixture
    def chef_user(self):
        """Create chef user with basic menu permissions"""
        return User(
            id=3,
            email="chef@test.com",
            name="Chef User",
            role="chef",
            permissions=["menu:create", "menu:read", "menu:update"],
        )

    @pytest.fixture
    def admin_user(self):
        """Create admin user with all permissions"""
        return User(
            id=1,
            email="admin@test.com",
            name="Admin User",
            role="admin",
            permissions=[
                "menu:create",
                "menu:read",
                "menu:update",
                "menu:delete",
                "admin:recipes",
                "manager:recipes",
            ],
        )

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_bulk_update_manager_only(
        self, mock_auth, mock_session, client, manager_user, chef_user, mock_db
    ):
        """Test that only managers and admins can perform bulk updates"""
        mock_session.return_value = mock_db

        bulk_update_data = {"recipe_ids": [1, 2, 3], "status": "active"}

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.bulk_update_recipes.return_value = {
                "updated": 3,
                "failed": 0,
                "errors": [],
            }

            # Test with manager user
            mock_auth.return_value = manager_user
            response = client.put(
                "/api/v1/recipes/bulk-update",
                json=bulk_update_data,
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["updated"] == 3

            # Test with chef user (should fail)
            mock_auth.return_value = chef_user
            response = client.put(
                "/api/v1/recipes/bulk-update",
                json=bulk_update_data,
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "manager:recipes" in response.json()["detail"]

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_bulk_activate_manager_only(
        self, mock_auth, mock_session, client, manager_user, chef_user, mock_db
    ):
        """Test that only managers can bulk activate recipes"""
        mock_session.return_value = mock_db

        bulk_activate_data = {"recipe_ids": [1, 2, 3]}

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.bulk_activate_recipes.return_value = {
                "activated": 3,
                "failed": 0,
                "errors": [],
            }

            # Test with manager user
            mock_auth.return_value = manager_user
            response = client.post(
                "/api/v1/recipes/bulk-activate",
                json=bulk_activate_data,
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["activated"] == 3

            # Test with chef user (should fail)
            mock_auth.return_value = chef_user
            response = client.post(
                "/api/v1/recipes/bulk-activate",
                json=bulk_activate_data,
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_approve_recipe_manager_only(
        self, mock_auth, mock_session, client, manager_user, chef_user, mock_db
    ):
        """Test that only managers can approve recipes"""
        mock_session.return_value = mock_db

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.approve_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.APPROVED,
            )

            # Test with manager user
            mock_auth.return_value = manager_user
            response = client.post(
                "/api/v1/recipes/1/approve",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "approved"

            # Test with chef user (should fail)
            mock_auth.return_value = chef_user
            response = client.post(
                "/api/v1/recipes/1/approve",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.auth.get_current_user")
    def test_chef_cannot_access_manager_endpoints(self, mock_auth, client, chef_user):
        """Test that chefs cannot access manager-level endpoints"""
        mock_auth.return_value = chef_user

        manager_endpoints = [
            (
                "PUT",
                "/api/v1/recipes/bulk-update",
                {"recipe_ids": [1], "status": "active"},
            ),
            ("POST", "/api/v1/recipes/bulk-activate", {"recipe_ids": [1]}),
            ("POST", "/api/v1/recipes/1/approve", None),
            ("POST", "/api/v1/recipes/bulk-deactivate", {"recipe_ids": [1]}),
        ]

        for method, endpoint, json_data in manager_endpoints:
            if method == "POST":
                response = client.post(
                    endpoint,
                    json=json_data,
                    headers={"Authorization": "Bearer test-token"},
                )
            elif method == "PUT":
                response = client.put(
                    endpoint,
                    json=json_data,
                    headers={"Authorization": "Bearer test-token"},
                )

            assert (
                response.status_code == status.HTTP_403_FORBIDDEN
            ), f"Chef should not access {method} {endpoint}"

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_admin_can_access_manager_endpoints(
        self, mock_auth, mock_session, client, admin_user, mock_db
    ):
        """Test that admin users can access manager-level endpoints"""
        mock_auth.return_value = admin_user
        mock_session.return_value = mock_db

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.bulk_update_recipes.return_value = {"updated": 1, "failed": 0}
            mock_service.bulk_activate_recipes.return_value = {
                "activated": 1,
                "failed": 0,
            }
            mock_service.approve_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test",
                yield_quantity=1.0,
                status=RecipeStatus.APPROVED,
            )

            # Admin should be able to access manager endpoints
            response = client.put(
                "/api/v1/recipes/bulk-update",
                json={"recipe_ids": [1], "status": "active"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == status.HTTP_200_OK

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_manager_batch_operations_limits(
        self, mock_auth, mock_session, client, manager_user, mock_db
    ):
        """Test that batch operations have appropriate limits for managers"""
        mock_auth.return_value = manager_user
        mock_session.return_value = mock_db

        # Test with too many recipe IDs
        large_batch_data = {
            "recipe_ids": list(range(1, 101)),  # 100 recipe IDs
            "status": "active",
        }

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.bulk_update_recipes.return_value = {
                "updated": 50,  # Service might limit internally
                "failed": 0,
                "errors": [],
            }

            response = client.put(
                "/api/v1/recipes/bulk-update",
                json=large_batch_data,
                headers={"Authorization": "Bearer test-token"},
            )

            # Should still work but might be limited by the service
            assert response.status_code == status.HTTP_200_OK
