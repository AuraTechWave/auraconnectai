"""
WebSocket authentication middleware for JWT token verification.

Provides secure authentication for WebSocket connections using JWT tokens.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, Callable, Set
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status, Request
from jose import JWTError, jwt
import json
import time
from datetime import datetime, timedelta

from .auth import verify_token, TokenData, User, get_user, SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)

# Security configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT.lower() in ["production", "prod"]
AUTH_MESSAGE_TIMEOUT = int(os.getenv("WS_AUTH_MESSAGE_TIMEOUT", "5"))  # seconds
MAX_AUTH_MESSAGE_SIZE = int(os.getenv("WS_MAX_AUTH_MESSAGE_SIZE", "4096"))  # bytes
MAX_AUTH_ATTEMPTS = int(os.getenv("WS_MAX_AUTH_ATTEMPTS", "3"))

# Rate limiting for auth attempts
auth_attempts: Dict[str, Dict[str, Any]] = {}  # IP -> {count, last_attempt}
AUTH_RATE_LIMIT_WINDOW = 60  # seconds


class WebSocketAuthError(Exception):
    """Custom exception for WebSocket authentication errors"""
    pass


def cleanup_auth_attempts():
    """Clean up old auth attempt records"""
    current_time = time.time()
    expired_ips = []
    
    for ip, data in auth_attempts.items():
        if current_time - data["last_attempt"] > AUTH_RATE_LIMIT_WINDOW:
            expired_ips.append(ip)
    
    for ip in expired_ips:
        del auth_attempts[ip]


def check_auth_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded auth rate limit"""
    cleanup_auth_attempts()
    current_time = time.time()
    
    if client_ip in auth_attempts:
        data = auth_attempts[client_ip]
        if data["count"] >= MAX_AUTH_ATTEMPTS:
            if current_time - data["last_attempt"] < AUTH_RATE_LIMIT_WINDOW:
                return False
            else:
                # Reset count after window
                auth_attempts[client_ip] = {"count": 1, "last_attempt": current_time}
        else:
            data["count"] += 1
            data["last_attempt"] = current_time
    else:
        auth_attempts[client_ip] = {"count": 1, "last_attempt": current_time}
    
    return True


def get_client_ip(websocket: WebSocket) -> str:
    """Extract client IP from WebSocket connection"""
    if hasattr(websocket, "client") and websocket.client:
        return websocket.client.host
    return "unknown"


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
    use_query_param: bool = True
) -> TokenData:
    """
    Authenticate a WebSocket connection using JWT token.
    
    Args:
        websocket: The WebSocket connection
        token: JWT token (from query parameter or first message)
        use_query_param: Whether to accept query parameter tokens
        
    Returns:
        TokenData object containing user information
        
    Raises:
        WebSocketAuthError: If authentication fails
    """
    client_ip = get_client_ip(websocket)
    
    # Check rate limiting
    if not check_auth_rate_limit(client_ip):
        logger.warning(f"Auth rate limit exceeded for IP: {client_ip}")
        raise WebSocketAuthError("Authentication rate limit exceeded")
    
    # In production, reject query param tokens for security
    if IS_PRODUCTION and token and use_query_param:
        logger.warning(f"Query param token rejected in production from IP: {client_ip}")
        raise WebSocketAuthError("Authentication method not allowed")
    
    # If token not provided or rejected, try first message auth
    if not token or (IS_PRODUCTION and use_query_param):
        try:
            # Accept connection temporarily to receive auth message
            await websocket.accept()
            connection_accepted = True
            
            # Set timeout for auth message
            try:
                auth_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=AUTH_MESSAGE_TIMEOUT
                )
            except asyncio.TimeoutError:
                raise WebSocketAuthError("Authentication timeout")
            
            # Check message size
            if len(auth_message.encode()) > MAX_AUTH_MESSAGE_SIZE:
                raise WebSocketAuthError("Auth message too large")
            
            # Parse auth message with strict schema
            try:
                auth_data = json.loads(auth_message)
                if not isinstance(auth_data, dict):
                    raise WebSocketAuthError("Invalid auth message format")
                
                if auth_data.get("type") != "auth":
                    raise WebSocketAuthError("First message must be auth message")
                
                token = auth_data.get("token")
                if not token or not isinstance(token, str):
                    raise WebSocketAuthError("Invalid token format")
                    
            except json.JSONDecodeError:
                raise WebSocketAuthError("Invalid auth message JSON")
                
        except WebSocketDisconnect:
            raise WebSocketAuthError("Client disconnected during authentication")
        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"WebSocket auth error from {client_ip}: {e}")
            raise WebSocketAuthError("Authentication failed")
    
    if not token:
        raise WebSocketAuthError("No authentication token provided")
    
    # Verify token with enhanced validation
    try:
        token_data = verify_token(token, check_blacklist=True)
        if not token_data:
            raise WebSocketAuthError("Invalid or expired token")
        
        # Additional validation for WebSocket context
        if not token_data.user_id or not token_data.username:
            raise WebSocketAuthError("Invalid token claims")
        
        return token_data
        
    except Exception as e:
        logger.warning(f"Token verification failed from {client_ip}: {e}")
        raise WebSocketAuthError("Token validation failed")


async def get_websocket_user(
    websocket: WebSocket,
    token: Optional[str] = None,
    use_query_param: bool = True
) -> User:
    """
    Get authenticated user from WebSocket connection.
    
    Args:
        websocket: The WebSocket connection
        token: JWT token
        use_query_param: Whether to accept query parameter tokens
        
    Returns:
        User object
        
    Raises:
        WebSocketAuthError: If authentication fails or user not found
    """
    token_data = await authenticate_websocket(websocket, token, use_query_param)
    
    user = get_user(username=token_data.username)
    if not user:
        raise WebSocketAuthError("User not found")
    
    # Ensure user is active
    if hasattr(user, 'is_active') and not user.is_active:
        raise WebSocketAuthError("User account is disabled")
    
    return user


def validate_tenant_access(user: User, required_tenant_id: int) -> bool:
    """
    Validate that user has access to the required tenant.
    
    Args:
        user: Authenticated user
        required_tenant_id: Tenant ID to validate
        
    Returns:
        True if user has access, False otherwise
    """
    # Admin bypasses tenant restrictions
    if "admin" in user.roles:
        return True
    
    # Check if user has access to the tenant
    return required_tenant_id in user.tenant_ids


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
    
    def __init__(self, websocket: WebSocket, user: User, permissions: list[str], token_exp: Optional[float] = None):
        self.websocket = websocket
        self.user = user
        self.permissions = permissions
        self.user_id = user.id
        self.username = user.username
        self.token_exp = token_exp
        self.connection_time = datetime.utcnow()
        self.accepted = False
        
    async def accept(self):
        """Accept the WebSocket connection if not already accepted"""
        if self.accepted:
            return
            
        try:
            await self.websocket.accept()
            self.accepted = True
        except RuntimeError:
            # Already accepted
            self.accepted = True
    
    async def send_text(self, data: str):
        """Send text data"""
        await self._check_token_validity()
        await self.websocket.send_text(data)
        
    async def send_json(self, data: Dict[str, Any]):
        """Send JSON data with minimal info"""
        await self._check_token_validity()
        # Remove sensitive data from logs
        safe_data = self._sanitize_for_logging(data)
        if safe_data != data:
            logger.debug(f"Sending data to {self.user_id} (sanitized)")
        await self.websocket.send_json(data)
        
    async def receive_text(self) -> str:
        """Receive text data"""
        await self._check_token_validity()
        return await self.websocket.receive_text()
        
    async def receive_json(self) -> Dict[str, Any]:
        """Receive JSON data"""
        await self._check_token_validity()
        return await self.websocket.receive_json()
        
    async def close(self, code: int = 1008, reason: str = "Policy violation"):
        """Close the WebSocket connection with secure defaults"""
        # Use generic reason in production
        if IS_PRODUCTION:
            reason = "Policy violation"
        await self.websocket.close(code=code, reason=reason)
        
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.permissions or "admin" in self.user.roles
    
    async def _check_token_validity(self):
        """Check if token is still valid"""
        if self.token_exp:
            current_time = datetime.utcnow().timestamp()
            if current_time >= self.token_exp:
                logger.warning(f"Token expired for user {self.user_id}")
                await self.close(code=1008, reason="Authentication expired")
                raise WebSocketAuthError("Token expired")
    
    def _sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data for logging"""
        if not isinstance(data, dict):
            return data
        
        sensitive_keys = {"token", "password", "secret", "key", "authorization"}
        sanitized = {}
        
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_for_logging(value)
            else:
                sanitized[key] = value
                
        return sanitized


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