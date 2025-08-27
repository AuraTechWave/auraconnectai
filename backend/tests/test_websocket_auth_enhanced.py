"""
Enhanced tests for WebSocket authentication security features.

Tests all security requirements from PR #195 review.
"""

import pytest
import asyncio
import json
import time
import os
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from fastapi import WebSocket
from fastapi.testclient import TestClient
from jose import jwt

from core.websocket_auth import (
    authenticate_websocket,
    get_websocket_user,
    WebSocketAuthError,
    check_auth_rate_limit,
    auth_attempts,
    AuthenticatedWebSocket,
    validate_tenant_access,
    AUTH_MESSAGE_TIMEOUT,
    MAX_AUTH_MESSAGE_SIZE,
)
from core.auth import create_access_token, SECRET_KEY, ALGORITHM, User


class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.messages = []
        self.client = Mock(host="127.0.0.1")
        
    async def accept(self):
        self.accepted = True
        
    async def close(self, code=1008, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        
    async awful receive_text(self):
        if self.messages:
            return self.messages.pop(0)
        raise asyncio.TimeoutError()
        
    async def send_text(self, data):
        pass
        
    async def send_json(self, data):
        pass
        
    def add_message(self, message):
        """Add a message to be received"""
        self.messages.append(message)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket"""
    return MockWebSocket()


@pytest.fixture
def valid_token():
    """Create a valid JWT token"""
    token_data = {
        "sub": "1",
        "username": "testuser",
        "roles": ["admin"],
        "tenant_ids": [1, 2],
    }
    return create_access_token(token_data)


@pytest.fixture
def expired_token():
    """Create an expired JWT token"""
    token_data = {
        "sub": "1",
        "username": "testuser",
        "roles": ["admin"],
        "tenant_ids": [1, 2],
    }
    # Create token that expired 1 hour ago
    return create_access_token(
        token_data,
        expires_delta=timedelta(hours=-1)
    )


@pytest.fixture
def malformed_tokens():
    """Collection of malformed tokens for testing"""
    return {
        "invalid_signature": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.invalid",
        "missing_claims": jwt.encode({"foo": "bar"}, SECRET_KEY, algorithm=ALGORITHM),
        "wrong_issuer": jwt.encode({
            "sub": "1",
            "username": "test",
            "iss": "wrong-issuer",
            "aud": "auraconnect-ws",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()
        }, SECRET_KEY, algorithm=ALGORITHM),
        "wrong_audience": jwt.encode({
            "sub": "1",
            "username": "test",
            "iss": "auraconnect-api",
            "aud": "wrong-audience",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()
        }, SECRET_KEY, algorithm=ALGORITHM),
        "none_algorithm": "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJ0ZXN0In0.",
        "empty_string": "",
        "not_a_token": "definitely-not-a-jwt",
    }


class TestProductionSecurity:
    """Test production security features"""
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    async def test_query_param_rejected_in_production(self, mock_websocket, valid_token):
        """Test that query parameters are rejected in production"""
        # Reload module to pick up env change
        import core.websocket_auth
        core.websocket_auth.IS_PRODUCTION = True
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(
                mock_websocket,
                token=valid_token,
                use_query_param=True
            )
        assert "Authentication method not allowed" in str(exc.value)
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    async def test_query_param_allowed_in_development(self, mock_websocket, valid_token):
        """Test that query parameters are allowed in development"""
        # Reload module to pick up env change
        import core.websocket_auth
        core.websocket_auth.IS_PRODUCTION = False
        
        with patch("core.websocket_auth.verify_token") as mock_verify:
            mock_verify.return_value = Mock(
                user_id=1,
                username="testuser",
                roles=["admin"],
                tenant_ids=[1]
            )
            
            result = await authenticate_websocket(
                mock_websocket,
                token=valid_token,
                use_query_param=True
            )
            assert result.user_id == 1


class TestRateLimiting:
    """Test rate limiting for authentication attempts"""
    
    def test_rate_limit_check(self):
        """Test rate limit checking logic"""
        # Clear previous attempts
        auth_attempts.clear()
        
        # First 3 attempts should pass
        for i in range(3):
            assert check_auth_rate_limit("192.168.1.1") is True
            
        # 4th attempt should fail
        assert check_auth_rate_limit("192.168.1.1") is False
        
        # Different IP should pass
        assert check_auth_rate_limit("192.168.1.2") is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_window_reset(self):
        """Test that rate limit resets after time window"""
        auth_attempts.clear()
        
        # Use up rate limit
        for i in range(3):
            check_auth_rate_limit("192.168.1.3")
            
        assert check_auth_rate_limit("192.168.1.3") is False
        
        # Simulate time passing (61 seconds)
        auth_attempts["192.168.1.3"]["last_attempt"] = time.time() - 61
        
        # Should be allowed again
        assert check_auth_rate_limit("192.168.1.3") is True
    
    @pytest.mark.asyncio
    async def test_auth_rate_limit_enforcement(self, mock_websocket):
        """Test that rate limits are enforced during authentication"""
        auth_attempts.clear()
        
        # Use up rate limit for test IP
        auth_attempts["127.0.0.1"] = {
            "count": 3,
            "last_attempt": time.time()
        }
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(mock_websocket)
        assert "rate limit exceeded" in str(exc.value).lower()


class TestFirstMessageAuth:
    """Test first message authentication flow"""
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    async def test_first_message_auth_timeout(self, mock_websocket):
        """Test timeout for first message authentication"""
        import core.websocket_auth
        core.websocket_auth.IS_PRODUCTION = True
        
        # Don't add any messages to simulate timeout
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(mock_websocket)
        assert "Authentication timeout" in str(exc.value)
        assert mock_websocket.accepted  # Should accept temporarily
    
    @pytest.mark.asyncio
    async def test_first_message_size_limit(self, mock_websocket):
        """Test message size limit for authentication"""
        # Create oversized auth message
        large_token = "x" * MAX_AUTH_MESSAGE_SIZE
        auth_message = json.dumps({
            "type": "auth",
            "token": large_token
        })
        mock_websocket.add_message(auth_message)
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(mock_websocket, use_query_param=False)
        assert "Auth message too large" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_first_message_invalid_format(self, mock_websocket):
        """Test various invalid first message formats"""
        invalid_messages = [
            "not json",  # Not JSON
            json.dumps(["not", "object"]),  # Not object
            json.dumps({"type": "subscribe"}),  # Wrong type
            json.dumps({"type": "auth"}),  # Missing token
            json.dumps({"type": "auth", "token": 123}),  # Token not string
        ]
        
        for msg in invalid_messages:
            mock_ws = MockWebSocket()
            mock_ws.add_message(msg)
            
            with pytest.raises(WebSocketAuthError):
                await authenticate_websocket(mock_ws, use_query_param=False)


class TestEnhancedJWTValidation:
    """Test enhanced JWT validation features"""
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, mock_websocket, expired_token):
        """Test that expired tokens are rejected"""
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(mock_websocket, token=expired_token)
        assert "Invalid or expired token" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_malformed_tokens_rejected(self, mock_websocket, malformed_tokens):
        """Test that various malformed tokens are rejected"""
        for token_type, token in malformed_tokens.items():
            mock_ws = MockWebSocket()
            with pytest.raises(WebSocketAuthError) as exc:
                await authenticate_websocket(mock_ws, token=token)
            assert "Invalid or expired token" in str(exc.value) or \
                   "Token validation failed" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_issuer_audience_validation(self, mock_websocket):
        """Test JWT issuer and audience validation"""
        # Token with correct issuer/audience should pass
        good_token = jwt.encode({
            "sub": "1",
            "username": "test",
            "roles": ["admin"],
            "tenant_ids": [1],
            "type": "access",
            "iss": os.getenv("JWT_ISSUER", "auraconnect-api"),
            "aud": os.getenv("JWT_AUDIENCE", "auraconnect-ws"),
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            "iat": datetime.utcnow().timestamp()
        }, SECRET_KEY, algorithm=ALGORITHM)
        
        with patch("core.websocket_auth.get_user") as mock_get_user:
            mock_get_user.return_value = User(
                id=1,
                username="test",
                email="test@example.com",
                roles=["admin"],
                tenant_ids=[1],
                is_active=True
            )
            
            user = await get_websocket_user(mock_websocket, token=good_token)
            assert user.username == "test"


class TestTenantValidation:
    """Test tenant access validation"""
    
    def test_admin_bypasses_tenant_check(self):
        """Test that admins can access any tenant"""
        admin_user = User(
            id=1,
            username="admin",
            email="admin@example.com",
            roles=["admin"],
            tenant_ids=[1],
            is_active=True
        )
        
        # Admin should access tenant not in their list
        assert validate_tenant_access(admin_user, 999) is True
    
    def test_regular_user_tenant_check(self):
        """Test tenant validation for regular users"""
        regular_user = User(
            id=2,
            username="user",
            email="user@example.com",
            roles=["staff"],
            tenant_ids=[1, 2, 3],
            is_active=True
        )
        
        # Should access assigned tenants
        assert validate_tenant_access(regular_user, 1) is True
        assert validate_tenant_access(regular_user, 2) is True
        assert validate_tenant_access(regular_user, 3) is True
        
        # Should not access unassigned tenant
        assert validate_tenant_access(regular_user, 4) is False


class TestAuthenticatedWebSocket:
    """Test AuthenticatedWebSocket wrapper class"""
    
    @pytest.mark.asyncio
    async def test_token_expiration_checking(self, mock_websocket):
        """Test that expired tokens close the connection"""
        user = User(
            id=1,
            username="test",
            email="test@example.com",
            roles=["admin"],
            tenant_ids=[1],
            is_active=True
        )
        
        # Create wrapper with expired token
        past_timestamp = (datetime.utcnow() - timedelta(hours=1)).timestamp()
        auth_ws = AuthenticatedWebSocket(
            mock_websocket,
            user,
            ["admin"],
            token_exp=past_timestamp
        )
        
        # Should close connection on any operation
        with pytest.raises(WebSocketAuthError):
            await auth_ws.send_text("test")
        
        assert mock_websocket.closed
        assert mock_websocket.close_code == 1008
    
    def test_permission_checking(self):
        """Test permission checking in AuthenticatedWebSocket"""
        user = User(
            id=1,
            username="test",
            email="test@example.com",
            roles=["manager"],
            tenant_ids=[1],
            is_active=True
        )
        
        auth_ws = AuthenticatedWebSocket(
            MockWebSocket(),
            user,
            ["analytics.view_dashboard", "analytics.view_sales_reports"]
        )
        
        assert auth_ws.has_permission("analytics.view_dashboard") is True
        assert auth_ws.has_permission("analytics.admin_analytics") is False
        assert auth_ws.has_permission("unknown.permission") is False
    
    def test_data_sanitization(self):
        """Test sensitive data sanitization for logging"""
        user = User(
            id=1,
            username="test",
            email="test@example.com",
            roles=["admin"],
            tenant_ids=[1],
            is_active=True
        )
        
        auth_ws = AuthenticatedWebSocket(MockWebSocket(), user, ["admin"])
        
        # Test sanitization
        sensitive_data = {
            "token": "secret-token",
            "password": "secret-pass",
            "data": {
                "api_key": "secret-key",
                "normal": "visible"
            }
        }
        
        sanitized = auth_ws._sanitize_for_logging(sensitive_data)
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["data"]["api_key"] == "[REDACTED]"
        assert sanitized["data"]["normal"] == "visible"


class TestErrorHandling:
    """Test error handling and messages"""
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    async def test_generic_error_messages_in_production(self, mock_websocket):
        """Test that production uses generic error messages"""
        import core.websocket_auth
        core.websocket_auth.IS_PRODUCTION = True
        
        # Test various error conditions
        with pytest.raises(WebSocketAuthError):
            await authenticate_websocket(mock_websocket, token="invalid")
        
        # In production, close reasons should be generic
        auth_ws = AuthenticatedWebSocket(
            mock_websocket,
            Mock(),
            []
        )
        await auth_ws.close(code=1008, reason="Specific error details")
        
        assert mock_websocket.close_reason == "Policy violation"
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"})  
    async def test_detailed_errors_in_development(self, mock_websocket):
        """Test that development shows detailed errors"""
        import core.websocket_auth
        core.websocket_auth.IS_PRODUCTION = False
        
        auth_ws = AuthenticatedWebSocket(
            mock_websocket,
            Mock(),
            []
        )
        await auth_ws.close(code=1008, reason="Specific error details")
        
        assert mock_websocket.close_reason == "Specific error details"


class TestReconnectionScenarios:
    """Test WebSocket reconnection scenarios"""
    
    @pytest.mark.asyncio
    async def test_reconnection_with_new_token(self, mock_websocket, valid_token):
        """Test reconnection with refreshed token"""
        with patch("core.websocket_auth.verify_token") as mock_verify:
            # First connection
            mock_verify.return_value = Mock(
                user_id=1,
                username="testuser",
                roles=["admin"],
                tenant_ids=[1]
            )
            
            result1 = await authenticate_websocket(mock_websocket, token=valid_token)
            assert result1.user_id == 1
            
            # Simulate new connection with new token
            new_token = create_access_token({
                "sub": "1",
                "username": "testuser",
                "roles": ["admin"],
                "tenant_ids": [1],
            })
            
            new_ws = MockWebSocket()
            result2 = await authenticate_websocket(new_ws, token=new_token)
            assert result2.user_id == 1