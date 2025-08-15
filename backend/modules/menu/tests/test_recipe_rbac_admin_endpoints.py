# backend/modules/menu/tests/test_recipe_rbac_admin_endpoints.py

"""
RBAC tests for admin-only endpoints in recipe management.
Tests permission enforcement for administrative operations like cost recalculation.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from main import app
from core.auth import User
from modules.menu.models.recipe_models import Recipe, RecipeStatus


class TestRecipeAdminEndpoints:
    """Test suite for admin-only endpoints with RBAC enforcement"""

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
            permissions=[
                "menu:create",
                "menu:read",
                "menu:update",
                "menu:delete",
                "admin:recipes",
                "manager:recipes",
            ],
        )

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

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_recalculate_costs_admin_only(
        self, mock_auth, mock_session, client, admin_user, manager_user, mock_db
    ):
        """Test that only admins can trigger cost recalculation"""
        mock_session.return_value = mock_db

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.recalculate_all_recipe_costs.return_value = {
                "updated": 10,
                "failed": 0,
                "errors": [],
            }

            # Test with admin user
            mock_auth.return_value = admin_user
            response = client.post(
                "/api/v1/recipes/recalculate-costs",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["updated"] == 10

            # Test with manager user (should fail)
            mock_auth.return_value = manager_user
            response = client.post(
                "/api/v1/recipes/recalculate-costs",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.auth.get_current_user")
    def test_chef_cannot_access_admin_endpoints(self, mock_auth, client, chef_user):
        """Test that non-admin users cannot access admin endpoints"""
        mock_auth.return_value = chef_user

        # Try to access cost recalculation endpoint
        response = client.post(
            "/api/v1/recipes/recalculate-costs",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "admin:recipes" in response.json()["detail"]

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_admin_can_access_all_endpoints(
        self, mock_auth, mock_session, client, admin_user, mock_db
    ):
        """Test that admin users can access all recipe endpoints"""
        mock_auth.return_value = admin_user
        mock_session.return_value = mock_db

        endpoints_to_test = [
            # Basic CRUD operations
            ("GET", "/api/v1/recipes/1", None),
            ("GET", "/api/v1/recipes", None),
            ("GET", "/api/v1/recipes/search?query=test", None),
            # Admin operations
            ("POST", "/api/v1/recipes/recalculate-costs", None),
            # Manager operations
            (
                "PUT",
                "/api/v1/recipes/bulk-update",
                {"recipe_ids": [1, 2], "status": "active"},
            ),
            ("POST", "/api/v1/recipes/bulk-activate", {"recipe_ids": [1, 2]}),
            ("POST", "/api/v1/recipes/1/approve", None),
        ]

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value

            # Setup mock returns for different operations
            mock_service.get_recipe_by_id.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE,
            )
            mock_service.get_recipes.return_value = ([], 0)
            mock_service.search_recipes.return_value = ([], 0)
            mock_service.recalculate_all_recipe_costs.return_value = {
                "updated": 0,
                "failed": 0,
            }
            mock_service.bulk_update_recipes.return_value = {"updated": 2, "failed": 0}
            mock_service.bulk_activate_recipes.return_value = {
                "activated": 2,
                "failed": 0,
            }
            mock_service.approve_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test",
                yield_quantity=1.0,
                status=RecipeStatus.APPROVED,
            )

            for method, endpoint, json_data in endpoints_to_test:
                if method == "GET":
                    response = client.get(
                        endpoint, headers={"Authorization": "Bearer test-token"}
                    )
                elif method == "POST":
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

                # Admin should be able to access all endpoints
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_201_CREATED,
                ], f"Admin failed to access {method} {endpoint}: {response.status_code}"

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_admin_specific_query_parameters(
        self, mock_auth, mock_session, client, admin_user, chef_user, mock_db
    ):
        """Test that admin-specific query parameters are respected"""
        mock_session.return_value = mock_db

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_recipes.return_value = ([], 0)

            # Admin can use include_inactive parameter
            mock_auth.return_value = admin_user
            response = client.get(
                "/api/v1/recipes?include_inactive=true",
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == status.HTTP_200_OK

            # Non-admin cannot use include_inactive parameter
            mock_auth.return_value = chef_user
            response = client.get(
                "/api/v1/recipes?include_inactive=true",
                headers={"Authorization": "Bearer test-token"},
            )
            # Should still work but parameter should be ignored
            assert response.status_code == status.HTTP_200_OK
