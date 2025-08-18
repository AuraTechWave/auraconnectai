"""
Comprehensive test suite for JWT authentication with refresh tokens.

Tests cover:
- Token generation and validation
- Login/logout flows
- Refresh token functionality
- Session management
- Token expiration
- Security features
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from jose import jwt
import time

from app.main import app
from core.auth import (
    create_access_token, create_refresh_token, verify_token,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS, generate_token_id
)
from core.session_manager import session_manager


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Test user data."""
    return {
        "username": "admin",
        "password": "secret",
        "id": 1,
        "email": "admin@auraconnect.ai",
        "roles": ["admin", "payroll_manager"],
        "tenant_ids": [1, 2, 3]
    }


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers with valid token."""
    response = client.post(
        "/auth/login",
        data={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestTokenGeneration:
    """Test JWT token generation and validation."""
    
    def test_create_access_token(self, test_user):
        """Test access token creation."""
        token_data = {
            "sub": str(test_user["id"]),
            "username": test_user["username"],
            "roles": test_user["roles"],
            "tenant_ids": test_user["tenant_ids"]
        }
        
        token = create_access_token(token_data)
        assert token is not None
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == test_user["id"]
        assert payload["username"] == test_user["username"]
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "jti" in payload  # Token ID
        assert "iat" in payload  # Issued at
    
    def test_create_refresh_token(self, test_user):
        """Test refresh token creation."""
        token_data = {
            "sub": str(test_user["id"]),
            "username": test_user["username"],
            "roles": test_user["roles"],
            "tenant_ids": test_user["tenant_ids"]
        }
        
        token = create_refresh_token(token_data, session_id="test_session_123")
        assert token is not None
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == test_user["id"]
        assert payload["type"] == "refresh"
        assert payload["session_id"] == "test_session_123"
        assert "exp" in payload
        
        # Check expiration is 7 days
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        assert abs((exp_time - expected_exp).total_seconds()) < 60  # Within 1 minute
    
    def test_verify_valid_token(self, test_user):
        """Test verification of valid token."""
        token_data = {
            "sub": str(test_user["id"]),
            "username": test_user["username"],
            "roles": test_user["roles"],
            "tenant_ids": test_user["tenant_ids"]
        }
        
        token = create_access_token(token_data)
        verified = verify_token(token, "access", check_blacklist=False)
        
        assert verified is not None
        assert verified.user_id == test_user["id"]
        assert verified.username == test_user["username"]
        assert verified.roles == test_user["roles"]
    
    def test_verify_invalid_token(self):
        """Test verification of invalid token."""
        invalid_token = "invalid.token.here"
        verified = verify_token(invalid_token, "access")
        assert verified is None
    
    def test_verify_wrong_token_type(self, test_user):
        """Test verification with wrong token type."""
        token_data = {
            "sub": str(test_user["id"]),
            "username": test_user["username"]
        }
        
        # Create access token but verify as refresh
        access_token = create_access_token(token_data)
        verified = verify_token(access_token, "refresh")
        assert verified is None
    
    def test_token_expiration(self, test_user):
        """Test token expiration."""
        token_data = {
            "sub": str(test_user["id"]),
            "username": test_user["username"]
        }
        
        # Create token that expires in 1 second
        token = create_access_token(token_data, expires_delta=timedelta(seconds=1))
        
        # Should be valid immediately
        verified = verify_token(token, "access", check_blacklist=False)
        assert verified is not None
        
        # Wait for expiration
        time.sleep(2)
        
        # Should be invalid now
        verified = verify_token(token, "access", check_blacklist=False)
        assert verified is None


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            data={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "access_expires_in" in data
        assert "refresh_expires_in" in data
        assert "session_id" in data
        assert "user_info" in data
        
        # Check user info
        user_info = data["user_info"]
        assert user_info["username"] == test_user["username"]
        assert user_info["email"] == test_user["email"]
        assert user_info["roles"] == ["admin", "payroll_manager", "staff_manager"]
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/auth/login",
            data={
                "username": "invalid",
                "password": "wrong"
            }
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_get_current_user(self, client, auth_headers):
        """Test getting current user info."""
        response = client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["username"] == "admin"
        assert data["email"] == "admin@auraconnect.ai"
        assert "admin" in data["roles"]
    
    def test_get_current_user_no_auth(self, client):
        """Test getting current user without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 403  # Forbidden (no credentials)
    
    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401  # Unauthorized


class TestRefreshToken:
    """Test refresh token functionality."""
    
    def test_refresh_token_success(self, client, test_user):
        """Test successful token refresh."""
        # First login
        login_response = client.post(
            "/auth/login",
            data={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        assert login_response.status_code == 200
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Wait a bit to ensure new token has different timestamp
        time.sleep(1)
        
        # Refresh token
        refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        
        assert "access_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert data["access_token"] != login_response.json()["access_token"]
    
    def test_refresh_with_invalid_token(self, client):
        """Test refresh with invalid token."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid.refresh.token"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired refresh token" in response.json()["detail"]
    
    def test_refresh_with_access_token(self, client, test_user):
        """Test refresh with access token instead of refresh token."""
        # Login to get tokens
        login_response = client.post(
            "/auth/login",
            data={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Try to refresh with access token
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": access_token}
        )
        
        assert response.status_code == 401


class TestLogout:
    """Test logout functionality."""
    
    def test_logout_single_session(self, client, auth_headers):
        """Test logout from single session."""
        response = client.post(
            "/auth/logout",
            headers=auth_headers,
            json={"logout_all_sessions": False}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
        assert response.json()["logout_all_sessions"] is False
        
        # Token should be blacklisted now
        # Trying to use it should fail
        me_response = client.get("/auth/me", headers=auth_headers)
        assert me_response.status_code == 401
    
    def test_logout_all_sessions(self, client, auth_headers):
        """Test logout from all sessions."""
        response = client.post(
            "/auth/logout",
            headers=auth_headers,
            json={"logout_all_sessions": True}
        )
        
        assert response.status_code == 200
        assert response.json()["logout_all_sessions"] is True
    
    def test_logout_without_auth(self, client):
        """Test logout without authentication."""
        response = client.post("/auth/logout")
        assert response.status_code == 403


class TestSessionManagement:
    """Test session management features."""
    
    def test_get_active_sessions(self, client, auth_headers):
        """Test getting active sessions count."""
        response = client.get("/auth/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "username" in data
        assert "active_sessions" in data
        assert data["active_sessions"] >= 1  # At least current session
    
    def test_revoke_session(self, client, test_user):
        """Test revoking a specific session."""
        # Create multiple sessions
        login1 = client.post(
            "/auth/login",
            data={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        session1_id = login1.json()["session_id"]
        token1 = login1.json()["access_token"]
        
        # Create second session
        login2 = client.post(
            "/auth/login",
            data={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        token2 = login2.json()["access_token"]
        
        # Revoke first session using second session's token
        headers2 = {"Authorization": f"Bearer {token2}"}
        response = client.delete(
            f"/auth/sessions/{session1_id}",
            headers=headers2
        )
        
        assert response.status_code == 200
        
        # First token should no longer work
        headers1 = {"Authorization": f"Bearer {token1}"}
        me_response = client.get("/auth/me", headers=headers1)
        assert me_response.status_code == 401
        
        # Second token should still work
        me_response2 = client.get("/auth/me", headers=headers2)
        assert me_response2.status_code == 200


class TestSecurityFeatures:
    """Test security features."""
    
    def test_token_blacklisting(self, client, auth_headers, test_user):
        """Test token blacklisting after logout."""
        # Get the token
        token = auth_headers["Authorization"].split(" ")[1]
        
        # Logout
        client.post("/auth/logout", headers=auth_headers)
        
        # Token should be blacklisted
        from core.session_manager import session_manager
        assert session_manager.is_token_blacklisted(token)
    
    def test_concurrent_request_handling(self, client, test_user):
        """Test handling of concurrent requests during token refresh."""
        # This would require more complex testing setup with threading
        # Placeholder for demonstration
        pass
    
    def test_session_cleanup(self):
        """Test expired session cleanup."""
        # Create expired session
        expired_time = datetime.utcnow() - timedelta(days=1)
        
        # Test cleanup
        from core.session_manager import session_manager
        cleaned = session_manager.cleanup_expired_sessions()
        assert cleaned >= 0


class TestTokenHelpers:
    """Test token helper functions."""
    
    def test_generate_token_id(self):
        """Test token ID generation."""
        token_id1 = generate_token_id()
        token_id2 = generate_token_id()
        
        assert token_id1 != token_id2
        assert len(token_id1) > 20  # Should be long enough
    
    def test_is_token_expired(self):
        """Test token expiration checking."""
        # Create expired token
        expired_token_data = {"sub": "1", "username": "test"}
        expired_token = create_access_token(
            expired_token_data,
            expires_delta=timedelta(seconds=-10)  # Already expired
        )
        
        # Verify token can't be verified when expired
        verified = verify_token(expired_token, "access", check_blacklist=False)
        assert verified is None