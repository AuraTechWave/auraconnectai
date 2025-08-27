"""
WebSocket authentication middleware for JWT token verification.

Provides secure authentication for WebSocket connections using JWT tokens.
"""

import logging
from typing import Optional, Dict, Any, Callable
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status
from jose import JWTError, jwt
import json

from .auth import verify_token, TokenData, User, get_user, SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)


class WebSocketAuthError(Exception):
    """Custom exception for WebSocket authentication errors"""
    pass


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = None
) -> TokenData:
    """
    Authenticate a WebSocket connection using JWT token.
    
    Args:
        websocket: The WebSocket connection
        token: JWT token (from query parameter or first message)
        
    Returns:
        TokenData object containing user information
        
    Raises:
        WebSocketAuthError: If authentication fails
    """
    
    # If token not provided in query, try to get from first message
    if not token:
        try:
            # Accept connection temporarily to receive auth message
            await websocket.accept()
            
            # Wait for auth message (with timeout)
            first_message = await websocket.receive_text()
            try:
                auth_data = json.loads(first_message)
                if auth_data.get("type") == "auth":
                    token = auth_data.get("token")
                else:
                    raise WebSocketAuthError("First message must be auth message")
            except json.JSONDecodeError:
                raise WebSocketAuthError("Invalid auth message format")
                
        except WebSocketDisconnect:
            raise WebSocketAuthError("Client disconnected during authentication")
        except Exception as e:
            logger.error(f"WebSocket auth error: {e}")
            raise WebSocketAuthError(str(e))
    
    if not token:
        raise WebSocketAuthError("No authentication token provided")
    
    # Verify token
    token_data = verify_token(token)
    if not token_data:
        raise WebSocketAuthError("Invalid or expired token")
    
    return token_data


async def get_websocket_user(
    websocket: WebSocket,
    token: Optional[str] = None
) -> User:
    """
    Get authenticated user from WebSocket connection.
    
    Args:
        websocket: The WebSocket connection
        token: JWT token
        
    Returns:
        User object
        
    Raises:
        WebSocketAuthError: If authentication fails or user not found
    """
    token_data = await authenticate_websocket(websocket, token)
    
    user = get_user(username=token_data.username)
    if not user:
        raise WebSocketAuthError("User not found")
    
    return user


def require_websocket_permission(required_permissions: list[str]) -> Callable:
    """
    Decorator for WebSocket endpoints that require specific permissions.
    
    Args:
        required_permissions: List of required permission strings
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(websocket: WebSocket, *args, **kwargs):
            # Extract token from query params or kwargs
            token = kwargs.get('token')
            
            try:
                # Authenticate and get user
                user = await get_websocket_user(websocket, token)
                
                # Check permissions
                user_permissions = []
                for role in user.roles:
                    # Map roles to permissions (this should match your permission system)
                    if role == "admin":
                        user_permissions.extend(required_permissions)  # Admin has all
                    elif role == "analytics_viewer":
                        user_permissions.extend([
                            "analytics.view_dashboard",
                            "analytics.view_sales_reports"
                        ])
                    elif role == "analytics_admin":
                        user_permissions.extend([
                            "analytics.view_dashboard",
                            "analytics.view_sales_reports",
                            "analytics.access_realtime",
                            "analytics.admin_analytics"
                        ])
                    # Add more role mappings as needed
                
                # Check if user has required permissions
                has_permission = any(
                    perm in user_permissions for perm in required_permissions
                )
                
                if not has_permission:
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="Insufficient permissions"
                    )
                    return
                
                # Add user to kwargs for the endpoint
                kwargs['current_user'] = user
                kwargs['user_permissions'] = user_permissions
                
                # Call the actual endpoint
                return await func(websocket, *args, **kwargs)
                
            except WebSocketAuthError as e:
                logger.warning(f"WebSocket authentication failed: {e}")
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=str(e)
                )
                return
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.close(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Internal server error"
                )
                return
                
        return wrapper
    return decorator


class AuthenticatedWebSocket:
    """
    Wrapper class for authenticated WebSocket connections.
    
    Provides convenient access to both WebSocket and user information.
    """
    
    def __init__(self, websocket: WebSocket, user: User, permissions: list[str]):
        self.websocket = websocket
        self.user = user
        self.permissions = permissions
        self.user_id = user.id
        self.username = user.username
        
    async def accept(self):
        """Accept the WebSocket connection if not already accepted"""
        try:
            await self.websocket.accept()
        except RuntimeError:
            # Already accepted
            pass
    
    async def send_text(self, data: str):
        """Send text data"""
        await self.websocket.send_text(data)
        
    async def send_json(self, data: Dict[str, Any]):
        """Send JSON data"""
        await self.websocket.send_json(data)
        
    async def receive_text(self) -> str:
        """Receive text data"""
        return await self.websocket.receive_text()
        
    async def receive_json(self) -> Dict[str, Any]:
        """Receive JSON data"""
        return await self.websocket.receive_json()
        
    async def close(self, code: int = 1000, reason: str = ""):
        """Close the WebSocket connection"""
        await self.websocket.close(code=code, reason=reason)
        
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.permissions or "admin" in self.user.roles


# WebSocket authentication flow examples
"""
Authentication Flow Options:

1. Query Parameter (Recommended for browser clients):
   ws://localhost:8000/ws/endpoint?token=<JWT_TOKEN>

2. First Message Authentication:
   Client connects and sends:
   {
     "type": "auth",
     "token": "<JWT_TOKEN>"
   }

3. Using the decorator:
   @router.websocket("/ws/protected")
   @require_websocket_permission(["analytics.view_dashboard"])
   async def protected_websocket(websocket: WebSocket, current_user: User):
       # current_user is automatically injected
       pass

Example WebSocket endpoint with authentication:

@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    try:
        # Authenticate
        user = await get_websocket_user(websocket, token)
        
        # Create authenticated websocket
        auth_ws = AuthenticatedWebSocket(
            websocket=websocket,
            user=user,
            permissions=get_user_permissions(user)
        )
        
        await auth_ws.accept()
        
        # Send welcome message
        await auth_ws.send_json({
            "type": "connected",
            "user": {
                "id": user.id,
                "username": user.username
            }
        })
        
        # Handle messages
        while True:
            message = await auth_ws.receive_json()
            # Process message...
            
    except WebSocketAuthError as e:
        await websocket.close(code=1008, reason=str(e))
    except WebSocketDisconnect:
        # Handle disconnect
        pass
"""