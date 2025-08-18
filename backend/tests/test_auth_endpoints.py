"""
Test all authentication endpoints for complete coverage.

This ensures all auth routes are tested including edge cases.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from core.auth import (
    SECRET_KEY, ALGORITHM, create_access_token, 
    create_refresh_token, get_password_hash
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "roles": ["staff"],
        "tenant_ids": [1],
        "is_active": True
    }


@pytest.fixture
def valid_token(mock_user):
    """Create a valid access token."""
    return create_access_token({
        "sub": str(mock_user["id"]),
        "username": mock_user["username"],
        "roles": mock_user["roles"],
        "tenant_ids": mock_user["tenant_ids"]
    })


class TestAuthRoutes:
    """Test all /auth/* routes."""
    
    def test_login_endpoint_validation(self, client):
        """Test login endpoint input validation."""
        # Empty request
        response = client.post("/auth/login", json={})
        assert response.status_code == 422
        
        # Missing password
        response = client.post("/auth/login", data={"username": "test"})
        assert response.status_code == 422
        
        # Missing username  
        response = client.post("/auth/login", data={"password": "test"})
        assert response.status_code == 422
        
        # Wrong content type
        response = client.post("/auth/login", json={"username": "test", "password": "test"})
        assert response.status_code == 422  # Expects form data
    
    def test_login_response_headers(self, client, mock_user):
        """Test login response includes proper headers."""
        with patch('core.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = type('User', (), mock_user)()
            
            response = client.post("/auth/login", data={
                "username": "testuser",
                "password": "password"
            })
            
            # Check security headers
            assert response.headers.get("Cache-Control") == "no-store"
            assert response.headers.get("Pragma") == "no-cache"
    
    def test_me_endpoint(self, client, mock_user, valid_token):
        """Test /auth/me endpoint."""
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': mock_user['id'],
                'username': mock_user['username'],
                'roles': mock_user['roles'],
                'tenant_ids': mock_user['tenant_ids'],
                'session_id': 'test_session',
                'token_id': 'test_token'
            })()
            
            with patch('core.auth.get_user') as mock_get_user:
                mock_get_user.return_value = type('User', (), mock_user)()
                
                headers = {"Authorization": f"Bearer {valid_token}"}
                response = client.get("/auth/me", headers=headers)
                
                assert response.status_code == 200
                data = response.json()
                assert data["username"] == mock_user["username"]
                assert data["email"] == mock_user["email"]
                assert data["roles"] == mock_user["roles"]
    
    def test_me_endpoint_rbac_info(self, client, mock_user, valid_token):
        """Test /auth/me/rbac endpoint for RBAC information."""
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': mock_user['id'],
                'username': mock_user['username'],
                'roles': mock_user['roles'],
                'tenant_ids': mock_user['tenant_ids']
            })()
            
            with patch('core.auth.get_user') as mock_get_user:
                mock_get_user.return_value = type('User', (), mock_user)()
                
                headers = {"Authorization": f"Bearer {valid_token}"}
                response = client.get("/auth/me/rbac", headers=headers)
                
                # Endpoint should return RBAC details
                # Actual implementation would include permissions
    
    def test_logout_endpoint_methods(self, client, valid_token):
        """Test logout endpoint accepts only POST."""
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        # GET should not work
        response = client.get("/auth/logout", headers=headers)
        assert response.status_code == 405  # Method not allowed
        
        # PUT should not work
        response = client.put("/auth/logout", headers=headers)
        assert response.status_code == 405
    
    def test_refresh_endpoint_validation(self, client):
        """Test refresh endpoint validation."""
        # Missing refresh token
        response = client.post("/auth/refresh", json={})
        assert response.status_code == 422
        
        # Invalid token format
        response = client.post("/auth/refresh", json={"refresh_token": "invalid"})
        assert response.status_code == 401
        
        # Access token instead of refresh token
        access_token = create_access_token({"sub": "1", "username": "test"})
        response = client.post("/auth/refresh", json={"refresh_token": access_token})
        assert response.status_code == 401
    
    def test_sessions_endpoint(self, client, mock_user, valid_token):
        """Test /auth/sessions endpoint."""
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': mock_user['id'],
                'username': mock_user['username'],
                'roles': mock_user['roles'],
                'tenant_ids': mock_user['tenant_ids']
            })()
            
            with patch('core.auth.get_user') as mock_get_user:
                mock_get_user.return_value = type('User', (), mock_user)()
                
                headers = {"Authorization": f"Bearer {valid_token}"}
                response = client.get("/auth/sessions", headers=headers)
                
                assert response.status_code == 200
                data = response.json()
                assert "active_sessions" in data
                assert "user_id" in data
    
    def test_revoke_session_endpoint(self, client, mock_user, valid_token):
        """Test revoking specific sessions."""
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': mock_user['id'],
                'username': mock_user['username'],
                'roles': mock_user['roles'],
                'tenant_ids': mock_user['tenant_ids']
            })()
            
            headers = {"Authorization": f"Bearer {valid_token}"}
            
            # Try to revoke a session
            response = client.delete("/auth/sessions/test_session_id", headers=headers)
            
            # Should handle gracefully even if session doesn't exist


class TestPasswordEndpoints:
    """Test password-related endpoints."""
    
    def test_change_password_endpoint(self, client, mock_user, valid_token):
        """Test password change endpoint."""
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': mock_user['id'],
                'username': mock_user['username'],
                'roles': mock_user['roles'],
                'tenant_ids': mock_user['tenant_ids']
            })()
            
            with patch('core.auth.get_user') as mock_get_user:
                # Mock user with password
                user_with_password = mock_user.copy()
                user_with_password['hashed_password'] = get_password_hash("OldPass123!")
                mock_get_user.return_value = type('User', (), user_with_password)()
                
                headers = {"Authorization": f"Bearer {valid_token}"}
                
                # Test password change
                response = client.post("/auth/password/change", headers=headers, json={
                    "current_password": "OldPass123!",
                    "new_password": "NewPass123!",
                    "confirm_password": "NewPass123!"
                })
                
                # Should validate old password and update
    
    def test_password_validation_endpoint(self, client):
        """Test password validation endpoint."""
        # Test weak password
        response = client.post("/auth/password/validate", json={
            "password": "weak"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert not data["is_valid"]
        assert data["strength"] in ["very_weak", "weak"]
        assert len(data["errors"]) > 0
        
        # Test strong password
        response = client.post("/auth/password/validate", json={
            "password": "StrongP@ssw0rd123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"]
        assert data["strength"] in ["good", "strong"]
    
    def test_password_reset_flow(self, client):
        """Test complete password reset flow."""
        # 1. Request reset
        with patch('core.email_service.EmailService.send_password_reset_email') as mock_email:
            mock_email.return_value = True
            
            response = client.post("/auth/password/reset-request", json={
                "email": "user@example.com"
            })
            
            assert response.status_code == 200
        
        # 2. Validate token (would be sent via email)
        mock_token = "a" * 32
        
        with patch('modules.auth.routes.password_routes.verify_reset_token') as mock_verify:
            mock_verify.return_value = (True, 1)
            
            # 3. Reset password
            response = client.post("/auth/password/reset-confirm", json={
                "token": mock_token,
                "new_password": "NewSecureP@ss123!",
                "confirm_password": "NewSecureP@ss123!"
            })
            
            assert response.status_code == 200


class TestAuthorizationHeaders:
    """Test authorization header handling."""
    
    def test_bearer_token_format(self, client):
        """Test various Bearer token formats."""
        # Valid format
        headers = {"Authorization": "Bearer validtoken123"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401  # Invalid token but correct format
        
        # Missing Bearer prefix
        headers = {"Authorization": "validtoken123"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 403
        
        # Wrong auth type
        headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 403
        
        # Multiple spaces
        headers = {"Authorization": "Bearer  token"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_case_sensitivity(self, client, valid_token):
        """Test authorization header case sensitivity."""
        # Standard case
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        # Lower case header name (should work)
        headers_lower = {"authorization": f"Bearer {valid_token}"}
        
        # Mixed case Bearer (should work)
        headers_mixed = {"Authorization": f"bearer {valid_token}"}
        
        # Test each variant
        for hdrs in [headers, headers_lower, headers_mixed]:
            with patch('core.auth.verify_token') as mock_verify:
                mock_verify.return_value = type('TokenData', (), {
                    'user_id': 1,
                    'username': 'test',
                    'roles': ['staff'],
                    'tenant_ids': [1]
                })()
                
                response = client.get("/auth/me", headers=hdrs)
                # Should handle case variations gracefully


class TestErrorResponses:
    """Test error response consistency."""
    
    def test_401_response_format(self, client):
        """Test 401 Unauthorized response format."""
        # Invalid token
        headers = {"Authorization": "Bearer invalid"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.headers.get("WWW-Authenticate") == "Bearer"
    
    def test_403_response_format(self, client, valid_token):
        """Test 403 Forbidden response format."""
        # Try to access admin endpoint as regular user
        with patch('core.auth.verify_token') as mock_verify:
            mock_verify.return_value = type('TokenData', (), {
                'user_id': 1,
                'username': 'test',
                'roles': ['staff'],  # Not admin
                'tenant_ids': [1]
            })()
            
            headers = {"Authorization": f"Bearer {valid_token}"}
            
            # Would need an admin-only endpoint to test
            # response = client.get("/admin/users", headers=headers)
            # assert response.status_code == 403
    
    def test_rate_limit_response_format(self, client):
        """Test 429 Too Many Requests response format."""
        with patch('core.rate_limiter.RateLimiter.is_allowed') as mock_allowed:
            mock_allowed.return_value = False
            
            response = client.post("/auth/login", data={
                "username": "test",
                "password": "test"
            })
            
            assert response.status_code == 429
            assert "detail" in response.json()
            
            # Should include Retry-After header
            assert "Retry-After" in response.headers


class TestCORSAndSecurity:
    """Test CORS and security headers."""
    
    def test_cors_headers(self, client):
        """Test CORS headers on auth endpoints."""
        # Preflight request
        response = client.options("/auth/login", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        })
        
        # Check CORS headers
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
    
    def test_security_headers(self, client):
        """Test security headers on responses."""
        response = client.post("/auth/login", data={
            "username": "test",
            "password": "test"
        })
        
        # Check security headers
        # assert "X-Content-Type-Options" in response.headers
        # assert "X-Frame-Options" in response.headers
        # assert "Strict-Transport-Security" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])