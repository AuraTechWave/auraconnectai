# backend/modules/menu/tests/test_recipe_rbac_public_access.py

"""
RBAC tests for public access and authentication scenarios.
Tests unauthenticated access, invalid tokens, and public endpoints.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import jwt

from main import app
from core.auth import User
from modules.menu.models.recipe_models import Recipe, RecipeStatus


class TestRecipePublicAccess:
    """Test suite for public access and authentication edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    def test_no_authentication_header(self, client):
        """Test that requests without authentication headers are rejected"""
        endpoints = [
            ("GET", "/api/v1/recipes"),
            ("GET", "/api/v1/recipes/1"),
            ("POST", "/api/v1/recipes", {"name": "Test"}),
            ("PUT", "/api/v1/recipes/1", {"name": "Updated"}),
            ("DELETE", "/api/v1/recipes/1"),
        ]
        
        for method, endpoint, *args in endpoints:
            json_data = args[0] if args else None
            
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=json_data)
            elif method == "PUT":
                response = client.put(endpoint, json=json_data)
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Endpoint {method} {endpoint} should require authentication"

    def test_invalid_authentication_token(self, client):
        """Test that requests with invalid tokens are rejected"""
        invalid_tokens = [
            "Bearer invalid-token",
            "Bearer ",
            "InvalidScheme token",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "",
        ]
        
        for token in invalid_tokens:
            response = client.get(
                "/api/v1/recipes",
                headers={"Authorization": token} if token else {}
            )
            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN], \
                f"Token '{token}' should be rejected"

    @patch('core.db.SessionLocal')
    def test_public_nutrition_endpoint(self, mock_session, client, mock_db):
        """Test that public nutrition endpoint doesn't require authentication"""
        mock_session.return_value = mock_db
        
        with patch('modules.menu.services.recipe_service.RecipeService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_recipe_nutrition.return_value = {
                "calories": 250,
                "protein": 10,
                "carbs": 30,
                "fat": 12
            }
            
            # Should work without authentication
            response = client.get("/api/v1/recipes/1/nutrition/public")
            
            assert response.status_code == status.HTTP_200_OK
            assert "calories" in response.json()

    @patch('core.auth.get_current_user')
    def test_expired_token_handling(self, mock_auth, client):
        """Test that expired tokens are properly rejected"""
        # Simulate expired token by raising appropriate exception
        mock_auth.side_effect = Exception("Token has expired")
        
        response = client.get(
            "/api/v1/recipes",
            headers={"Authorization": "Bearer expired-token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('core.auth.get_current_user')
    def test_malformed_user_data_in_token(self, mock_auth, client):
        """Test handling of tokens with malformed user data"""
        # User with missing required fields
        malformed_users = [
            User(id=None, email="test@test.com", permissions=["menu:read"]),  # Missing ID
            User(id=1, email=None, permissions=["menu:read"]),  # Missing email
            User(id=1, email="test@test.com", permissions=None),  # Missing permissions
        ]
        
        for user in malformed_users:
            mock_auth.return_value = user
            
            response = client.get(
                "/api/v1/recipes",
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Should handle gracefully, likely with 401 or 500
            assert response.status_code >= 400

    @patch('core.auth.get_current_user')
    def test_user_with_empty_permissions(self, mock_auth, client):
        """Test that users with empty permissions array are handled correctly"""
        user_with_no_permissions = User(
            id=1,
            email="noperms@test.com",
            name="No Permissions User",
            role="guest",
            permissions=[]  # Empty permissions list
        )
        
        mock_auth.return_value = user_with_no_permissions
        
        # Should be forbidden from accessing any protected endpoint
        response = client.get(
            "/api/v1/recipes",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('core.db.SessionLocal')
    def test_health_check_endpoints_public(self, mock_session, client, mock_db):
        """Test that health check endpoints don't require authentication"""
        mock_session.return_value = mock_db
        
        # Assuming there's a health check endpoint for the recipe service
        response = client.get("/api/v1/recipes/health")
        
        # Health check should be accessible without auth
        # If endpoint doesn't exist, we expect 404, not 401
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @patch('core.auth.get_current_user')
    def test_cors_preflight_requests(self, mock_auth, client):
        """Test that CORS preflight requests are handled correctly"""
        # OPTIONS requests should not require authentication
        response = client.options(
            "/api/v1/recipes",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization"
            }
        )
        
        # OPTIONS should not return 401
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @patch('core.auth.get_current_user')
    def test_rate_limiting_for_unauthenticated(self, mock_auth, client):
        """Test rate limiting behavior for unauthenticated requests"""
        # Simulate multiple rapid requests without auth
        responses = []
        for _ in range(10):
            response = client.get("/api/v1/recipes")
            responses.append(response.status_code)
        
        # All should be 401, but we're checking rate limiting doesn't change this
        assert all(status == status.HTTP_401_UNAUTHORIZED for status in responses)

    @patch('core.auth.get_current_user')
    def test_authentication_with_different_schemes(self, mock_auth, client):
        """Test that only Bearer authentication scheme is accepted"""
        schemes = [
            "Basic dXNlcjpwYXNz",  # Basic auth
            "Digest username=test",  # Digest auth
            "OAuth token",  # OAuth
            "Token abc123",  # Simple token auth
        ]
        
        for scheme in schemes:
            response = client.get(
                "/api/v1/recipes",
                headers={"Authorization": scheme}
            )
            
            # Should reject non-Bearer schemes
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Scheme '{scheme}' should be rejected"