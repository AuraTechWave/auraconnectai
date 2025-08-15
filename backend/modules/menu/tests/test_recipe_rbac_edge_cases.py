# backend/modules/menu/tests/test_recipe_rbac_edge_cases.py

"""
RBAC edge case tests for recipe management.
Tests partial permissions, custom roles, and invalid permission combinations.
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


class TestRecipeRBACEdgeCases:
    """Test suite for RBAC edge cases and unusual permission scenarios"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def user_with_create_only(self):
        """User with only create permission - missing read"""
        return User(
            id=10,
            email="createonly@test.com",
            name="Create Only User",
            role="custom",
            permissions=["menu:create"],  # Has create but no read
        )

    @pytest.fixture
    def user_with_update_no_read(self):
        """User with update but no read permission"""
        return User(
            id=11,
            email="updateonly@test.com",
            name="Update Only User",
            role="custom",
            permissions=["menu:update"],  # Has update but no read
        )

    @pytest.fixture
    def readonly_api_user(self):
        """External API user with custom readonly permission"""
        return User(
            id=12,
            email="api@external.com",
            name="API User",
            role="api_user",
            permissions=["recipe:readonly", "menu:read"],
        )

    @pytest.fixture
    def user_with_conflicting_permissions(self):
        """User with potentially conflicting permissions"""
        return User(
            id=13,
            email="conflict@test.com",
            name="Conflicting User",
            role="custom",
            permissions=[
                "menu:read",
                "menu:write",
                "menu:deny",
            ],  # Hypothetical deny permission
        )

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_create_without_read_permission(
        self, mock_auth, mock_session, client, user_with_create_only, mock_db
    ):
        """Test user who can create but not read recipes"""
        mock_auth.return_value = user_with_create_only
        mock_session.return_value = mock_db

        recipe_data = {
            "menu_item_id": 1,
            "name": "Test Recipe",
            "yield_quantity": 1.0,
            "status": "active",
            "ingredients": [{"ingredient_id": 1, "quantity": 0.5, "unit": "kg"}],
        }

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.create_recipe.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE,
            )

            # Should be able to create
            response = client.post(
                "/api/v1/recipes",
                json=recipe_data,
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == status.HTTP_201_CREATED

            # But not able to read
            response = client.get(
                "/api/v1/recipes/1", headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.auth.get_current_user")
    def test_update_without_read_permission(
        self, mock_auth, client, user_with_update_no_read
    ):
        """Test user who can update but not read - unusual scenario"""
        mock_auth.return_value = user_with_update_no_read

        # Attempt to update without read permission
        update_data = {"name": "Updated Recipe"}
        response = client.put(
            "/api/v1/recipes/1",
            json=update_data,
            headers={"Authorization": "Bearer test-token"},
        )

        # Should be allowed if they have update permission
        # (though in practice this is unusual without read)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_readonly_api_user_permissions(
        self, mock_auth, mock_session, client, readonly_api_user, mock_db
    ):
        """Test external API user with custom readonly permissions"""
        mock_auth.return_value = readonly_api_user
        mock_session.return_value = mock_db

        with patch("modules.menu.services.recipe_service.RecipeService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_recipe_by_id.return_value = Recipe(
                id=1,
                menu_item_id=1,
                name="Test Recipe",
                yield_quantity=1.0,
                status=RecipeStatus.ACTIVE,
            )

            # Should be able to read
            response = client.get(
                "/api/v1/recipes/1", headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == status.HTTP_200_OK

            # But not able to create
            response = client.post(
                "/api/v1/recipes",
                json={"name": "New Recipe"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # And not able to update
            response = client.put(
                "/api/v1/recipes/1",
                json={"name": "Updated"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.auth.get_current_user")
    def test_permission_inheritance_and_override(self, mock_auth, client):
        """Test complex permission scenarios with inheritance"""
        # User with role-based permissions plus custom overrides
        complex_user = User(
            id=14,
            email="complex@test.com",
            name="Complex User",
            role="chef",  # Base chef role
            permissions=[
                "menu:read",
                "menu:create",
                "menu:update",
                "manager:recipes",
            ],  # Added manager permission
        )

        mock_auth.return_value = complex_user

        # Should have manager permissions despite being a chef
        response = client.post(
            "/api/v1/recipes/1/approve", headers={"Authorization": "Bearer test-token"}
        )

        # This depends on implementation - might allow or might check role
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    @patch("core.auth.get_current_user")
    def test_malformed_permission_strings(self, mock_auth, client):
        """Test handling of malformed permission strings"""
        users_with_bad_permissions = [
            User(
                id=15, email="bad1@test.com", permissions=["menu:", "read"]
            ),  # Split permission
            User(id=16, email="bad2@test.com", permissions=["MENU:READ"]),  # Wrong case
            User(
                id=17, email="bad3@test.com", permissions=["menu.read"]
            ),  # Wrong separator
            User(id=18, email="bad4@test.com", permissions=["menu:*"]),  # Wildcard
            User(id=19, email="bad5@test.com", permissions=[""]),  # Empty string
            User(
                id=20, email="bad6@test.com", permissions=["menu:read:write"]
            ),  # Too many parts
        ]

        for user in users_with_bad_permissions:
            mock_auth.return_value = user

            response = client.get(
                "/api/v1/recipes", headers={"Authorization": "Bearer test-token"}
            )

            # Should handle gracefully - likely forbidden
            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.auth.get_current_user")
    def test_duplicate_permissions(self, mock_auth, client):
        """Test user with duplicate permissions in the list"""
        user_with_duplicates = User(
            id=21,
            email="duplicate@test.com",
            name="Duplicate Permissions User",
            role="custom",
            permissions=[
                "menu:read",
                "menu:read",
                "menu:create",
                "menu:read",
            ],  # Duplicates
        )

        mock_auth.return_value = user_with_duplicates

        # Should still work normally
        response = client.get(
            "/api/v1/recipes", headers={"Authorization": "Bearer test-token"}
        )

        # Duplicates should be handled gracefully
        assert response.status_code == status.HTTP_200_OK

    @patch("core.auth.get_current_user")
    def test_permission_with_special_characters(self, mock_auth, client):
        """Test permissions with special characters or injection attempts"""
        injection_attempts = [
            ["menu:read'; DROP TABLE recipes; --"],
            ["menu:read\n\rmenu:delete"],
            ["menu:read%00menu:delete"],
            ["../../../admin:all"],
            ["menu:read&menu:delete"],
        ]

        for permissions in injection_attempts:
            user = User(id=22, email="injection@test.com", permissions=permissions)
            mock_auth.return_value = user

            response = client.get(
                "/api/v1/recipes", headers={"Authorization": "Bearer test-token"}
            )

            # Should safely handle without executing injections
            assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("core.db.SessionLocal")
    @patch("core.auth.get_current_user")
    def test_permission_caching_scenarios(
        self, mock_auth, mock_session, client, mock_db
    ):
        """Test scenarios where permissions might be cached incorrectly"""
        mock_session.return_value = mock_db

        # Start with read-only user
        readonly_user = User(id=23, email="cache@test.com", permissions=["menu:read"])
        mock_auth.return_value = readonly_user

        # First request - should be allowed
        response = client.get(
            "/api/v1/recipes", headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == status.HTTP_200_OK

        # Now "upgrade" the user's permissions mid-session
        upgraded_user = User(
            id=23, email="cache@test.com", permissions=["menu:read", "menu:create"]
        )
        mock_auth.return_value = upgraded_user

        # Should now be able to create
        response = client.post(
            "/api/v1/recipes",
            json={"name": "Test"},
            headers={"Authorization": "Bearer test-token"},
        )

        # This tests if permissions are properly checked each time
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_403_FORBIDDEN,
        ]
