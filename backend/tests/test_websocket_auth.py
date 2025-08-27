"""
Tests for WebSocket authentication.
"""

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta
import json

from core.auth import create_access_token, SECRET_KEY, ALGORITHM
from core.websocket_auth import WebSocketAuthError, authenticate_websocket


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.messages = []
        
    async def accept(self):
        self.accepted = True
        
    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        
    async def receive_text(self):
        if self.messages:
            return self.messages.pop(0)
        raise Exception("No messages")
        
    async def send_text(self, data):
        pass
        
    async def send_json(self, data):
        pass


class TestWebSocketAuth:
    """Test WebSocket authentication functionality."""
    
    @pytest.fixture
    def valid_token(self):
        """Create a valid JWT token."""
        token_data = {
            "sub": "1",
            "username": "testuser",
            "roles": ["admin"],
            "tenant_ids": [1, 2, 3]
        }
        return create_access_token(token_data)
    
    @pytest.fixture
    def expired_token(self):
        """Create an expired JWT token."""
        token_data = {
            "sub": "1",
            "username": "testuser",
            "roles": ["admin"],
            "tenant_ids": [1, 2, 3]
        }
        expire = datetime.utcnow() - timedelta(hours=1)
        to_encode = token_data.copy()
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @pytest.fixture
    def invalid_token(self):
        """Create an invalid JWT token."""
        return "invalid.token.here"
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_with_query_token(self, valid_token):
        """Test authentication with token in query parameter."""
        websocket = MockWebSocket()
        
        token_data = await authenticate_websocket(websocket, valid_token)
        
        assert token_data is not None
        assert token_data.username == "testuser"
        assert token_data.roles == ["admin"]
        assert not websocket.closed
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_with_auth_message(self):
        """Test authentication with token in first message."""
        websocket = MockWebSocket()
        token = create_access_token({
            "sub": "1",
            "username": "testuser",
            "roles": ["staff"],
            "tenant_ids": [1]
        })
        
        # Set up auth message
        auth_message = json.dumps({
            "type": "auth",
            "token": token
        })
        websocket.messages = [auth_message]
        
        token_data = await authenticate_websocket(websocket, None)
        
        assert token_data is not None
        assert token_data.username == "testuser"
        assert token_data.roles == ["staff"]
        assert websocket.accepted  # Should accept to receive auth message
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_expired_token(self, expired_token):
        """Test authentication with expired token."""
        websocket = MockWebSocket()
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(websocket, expired_token)
        
        assert "Invalid or expired token" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_invalid_token(self, invalid_token):
        """Test authentication with invalid token."""
        websocket = MockWebSocket()
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(websocket, invalid_token)
        
        assert "Invalid or expired token" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_no_token(self):
        """Test authentication with no token."""
        websocket = MockWebSocket()
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(websocket, None)
        
        assert "No authentication token provided" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_invalid_auth_message(self):
        """Test authentication with invalid auth message format."""
        websocket = MockWebSocket()
        websocket.messages = ["not json"]
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(websocket, None)
        
        assert "Invalid auth message format" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_wrong_message_type(self):
        """Test authentication with wrong message type."""
        websocket = MockWebSocket()
        websocket.messages = [json.dumps({"type": "subscribe", "token": "test"})]
        
        with pytest.raises(WebSocketAuthError) as exc:
            await authenticate_websocket(websocket, None)
        
        assert "First message must be auth message" in str(exc.value)


# Integration tests
@pytest.mark.integration
class TestWebSocketEndpoints:
    """Integration tests for WebSocket endpoints."""
    
    @pytest.mark.asyncio
    async def test_analytics_dashboard_websocket_auth_success(self, client: TestClient, valid_token):
        """Test successful authentication to analytics dashboard WebSocket."""
        with client.websocket_connect(
            f"/analytics/realtime/dashboard?token={valid_token}"
        ) as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "connection_established"
            assert "user" in data
            assert data["user"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_analytics_dashboard_websocket_auth_failure(self, client: TestClient):
        """Test failed authentication to analytics dashboard WebSocket."""
        with pytest.raises(Exception):  # WebSocket should close
            with client.websocket_connect("/analytics/realtime/dashboard") as websocket:
                # Should not reach here
                pass
    
    @pytest.mark.asyncio
    async def test_kds_websocket_requires_kitchen_role(self, client: TestClient):
        """Test KDS WebSocket requires kitchen role."""
        # Create token without kitchen role
        token = create_access_token({
            "sub": "1",
            "username": "testuser",
            "roles": ["cashier"],  # No kitchen access
            "tenant_ids": [1]
        })
        
        with pytest.raises(Exception):  # Should close due to insufficient permissions
            with client.websocket_connect(
                f"/api/v1/kds/ws/1?token={token}"
            ) as websocket:
                pass
    
    @pytest.mark.asyncio
    async def test_table_websocket_requires_restaurant_access(self, client: TestClient):
        """Test table WebSocket requires restaurant access."""
        # Create token without restaurant access
        token = create_access_token({
            "sub": "1",
            "username": "testuser",
            "roles": ["staff"],
            "tenant_ids": [2, 3]  # No access to restaurant 1
        })
        
        with pytest.raises(Exception):
            with client.websocket_connect(
                f"/api/v1/tables/ws/tables/1?token={token}"
            ) as websocket:
                pass