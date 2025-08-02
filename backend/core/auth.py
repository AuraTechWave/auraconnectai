"""
Simple authentication system for AuraConnect API endpoints.

Provides JWT-based authentication and role-based authorization for
payroll and other sensitive endpoints.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import secrets
import logging

logger = logging.getLogger(__name__)

# Security Configuration - Environment Variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
DEFAULT_RATE_LIMIT = int(os.getenv("DEFAULT_RATE_LIMIT", "100"))  # requests per minute
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "5"))  # login attempts per minute

# Import enhanced password security
from .password_security import password_security

# Password hashing (legacy support)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    roles: List[str] = []
    tenant_ids: List[int] = []
    session_id: Optional[str] = None
    token_id: Optional[str] = None


class User(BaseModel):
    """User model for authentication."""
    id: int
    username: str
    email: str
    roles: List[str]
    tenant_ids: List[int]
    is_active: bool = True


# Mock user database (in production, this would be a real database)
MOCK_USERS = {
    "admin": {
        "id": 1,
        "username": "admin",
        "email": "admin@auraconnect.ai",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "roles": ["admin", "payroll_manager", "staff_manager"],
        "tenant_ids": [1, 2, 3],
        "is_active": True
    },
    "payroll_clerk": {
        "id": 2,
        "username": "payroll_clerk",
        "email": "payroll@auraconnect.ai",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "roles": ["payroll_clerk"],
        "tenant_ids": [1],
        "is_active": True
    },
    "manager": {
        "id": 3,
        "username": "manager",
        "email": "manager@auraconnect.ai",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "roles": ["manager", "staff_viewer"],
        "tenant_ids": [1],
        "is_active": True
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using enhanced security."""
    # Try enhanced password security first
    if password_security.verify_password(plain_password, hashed_password):
        return True
    
    # Fallback to legacy method for existing passwords
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using enhanced security."""
    return password_security.hash_password(password)


def needs_password_rehash(hashed_password: str) -> bool:
    """Check if password hash needs to be rehashed with stronger algorithm."""
    return password_security.needs_rehash(hashed_password)


def get_user(username: str) -> Optional[User]:
    """Get user by username."""
    user_data = MOCK_USERS.get(username)
    if user_data:
        return User(**user_data)
    return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password."""
    user_data = MOCK_USERS.get(username)
    if not user_data:
        return None
    if not verify_password(password, user_data["hashed_password"]):
        return None
    return User(**user_data)


def generate_token_id() -> str:
    """Generate a unique token ID for tracking."""
    return secrets.token_urlsafe(32)


def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None
) -> str:
    """Create a JWT access token using secure configuration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add token tracking information
    token_id = generate_token_id()
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": token_id,  # JWT ID for token tracking
        "iat": datetime.utcnow().timestamp(),  # Issued at
    })
    
    if session_id:
        to_encode["session_id"] = session_id
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, session_id: Optional[str] = None) -> str:
    """Create a JWT refresh token with longer expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Add token tracking information
    token_id = generate_token_id()
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": token_id,  # JWT ID for token tracking
        "iat": datetime.utcnow().timestamp(),  # Issued at
    })
    
    if session_id:
        to_encode["session_id"] = session_id
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access", check_blacklist: bool = True) -> Optional[TokenData]:
    """
    Verify and decode a JWT token with optional blacklist checking.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")
        check_blacklist: Whether to check if token is blacklisted
        
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        # Import here to avoid circular imports
        from .session_manager import session_manager
        
        # Check blacklist if enabled
        if check_blacklist and session_manager.is_token_blacklisted(token):
            logger.warning("Attempted use of blacklisted token")
            return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
            
        # Parse user_id from string sub field
        sub = payload.get("sub")
        if sub is None:
            return None
            
        try:
            user_id = int(sub) if isinstance(sub, str) else sub
        except (ValueError, TypeError):
            return None
            
        username: str = payload.get("username")
        roles: List[str] = payload.get("roles", [])
        tenant_ids: List[int] = payload.get("tenant_ids", [])
        session_id: str = payload.get("session_id")
        token_id: str = payload.get("jti")
        
        # For refresh tokens, verify session exists and is valid
        if token_type == "refresh" and session_id:
            session = session_manager.get_session(session_id)
            if not session or not session.is_active:
                logger.warning(f"Invalid session {session_id} for refresh token")
                return None
            
            # Verify the refresh token matches
            if session.refresh_token != token:
                logger.warning(f"Refresh token mismatch for session {session_id}")
                return None
            
        return TokenData(
            user_id=user_id,
            username=username,
            roles=roles,
            tenant_ids=tenant_ids,
            session_id=session_id,
            token_id=token_id
        )
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def refresh_access_token(refresh_token: str) -> Optional[dict]:
    """
    Generate new access token from valid refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        Dictionary with new access token and metadata, or None if invalid
    """
    token_data = verify_token(refresh_token, token_type="refresh")
    if not token_data:
        return None
    
    # Create new access token with same data
    new_token_data = {
        "sub": token_data.user_id,
        "username": token_data.username, 
        "roles": token_data.roles,
        "tenant_ids": token_data.tenant_ids
    }
    
    access_token = create_access_token(new_token_data, session_id=token_data.session_id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "session_id": token_data.session_id
    }


def create_user_session(
    user: User,
    request: Optional[Request] = None
) -> dict:
    """
    Create a new authenticated session for a user.
    
    Args:
        user: Authenticated user
        request: FastAPI request object for metadata
        
    Returns:
        Dictionary with access token, refresh token, and session info
    """
    from .session_manager import session_manager
    
    # Extract client information
    user_agent = None
    ip_address = None
    if request:
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None
    
    # Create tokens
    token_data = {
        "sub": str(user.id),  # JWT standard requires sub to be a string
        "username": user.username,
        "roles": user.roles,
        "tenant_ids": user.tenant_ids
    }
    
    # Create refresh token first (needed for session)
    refresh_token_expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(token_data)
    
    # Create session
    session_id = session_manager.create_session(
        user_id=user.id,
        username=user.username,
        refresh_token=refresh_token,
        expires_at=refresh_token_expires,
        user_agent=user_agent,
        ip_address=ip_address
    )
    
    # Create access token with session ID
    access_token = create_access_token(token_data, session_id=session_id)
    
    logger.info(f"Created session {session_id} for user {user.username}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "access_expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "session_id": session_id,
        "user_info": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
            "tenant_ids": user.tenant_ids
        }
    }


def logout_user(token: str, logout_all_sessions: bool = False) -> bool:
    """
    Logout user by revoking tokens and sessions.
    
    Args:
        token: Access or refresh token
        logout_all_sessions: Whether to logout from all sessions
        
    Returns:
        True if logout successful, False otherwise
    """
    from .session_manager import session_manager
    
    try:
        # Try to get token data (could be access or refresh token)
        token_data = verify_token(token, "access", check_blacklist=False)
        if not token_data:
            token_data = verify_token(token, "refresh", check_blacklist=False)
        
        if not token_data:
            return False
        
        # Blacklist the current token
        session_manager.blacklist_token(token)
        
        if logout_all_sessions:
            # Revoke all user sessions
            session_manager.revoke_all_user_sessions(token_data.user_id)
            logger.info(f"Logged out all sessions for user {token_data.username}")
        elif token_data.session_id:
            # Revoke specific session
            session_manager.revoke_session(token_data.session_id)
            logger.info(f"Logged out session {token_data.session_id} for user {token_data.username}")
        
        return True
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        return False


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    
    return user


def require_roles(required_roles: List[str]):
    """Dependency factory for role-based authorization."""
    def check_roles(current_user: User = Depends(get_current_user)) -> User:
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of these roles: {required_roles}"
            )
        return current_user
    return check_roles


def require_tenant_access(tenant_id: int):
    """Dependency factory for tenant-based authorization."""
    def check_tenant_access(current_user: User = Depends(get_current_user)) -> User:
        if tenant_id not in current_user.tenant_ids and "admin" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this tenant"
            )
        return current_user
    return check_tenant_access


# Common role dependencies
require_admin = require_roles(["admin"])
require_payroll_access = require_roles(["admin", "payroll_manager", "payroll_clerk"])
require_payroll_write = require_roles(["admin", "payroll_manager"])
require_staff_access = require_roles(["admin", "payroll_manager", "payroll_clerk", "manager", "staff_viewer"])

# Add permission function factory to support require_permission("tax.admin") pattern
def require_permission(permission: str):
    """Create a dependency that requires specific permission"""
    # Map permission strings to roles
    permission_role_map = {
        "tax.admin": ["admin", "tax_admin"],
        "tax.write": ["admin", "tax_admin", "tax_manager"],
        "tax.read": ["admin", "tax_admin", "tax_manager", "tax_viewer"],
        "tax.view": ["admin", "tax_admin", "tax_manager", "tax_viewer"],
        "tax.report": ["admin", "tax_admin", "tax_manager"],
        "menu:create": ["admin", "manager", "menu_admin"],
        "menu:read": ["admin", "manager", "menu_admin", "staff"],
        "menu:update": ["admin", "manager", "menu_admin"],
        "menu:delete": ["admin", "menu_admin"],
        "inventory:create": ["admin", "manager", "inventory_admin"],
        "inventory:read": ["admin", "manager", "inventory_admin", "staff"],
        "inventory:update": ["admin", "manager", "inventory_admin"],
        "inventory:delete": ["admin", "inventory_admin"],
    }
    roles = permission_role_map.get(permission, ["admin"])
    return require_roles(roles)


# Tenant support (placeholder)
async def get_current_tenant() -> Optional[int]:
    """Get current tenant ID - placeholder for multi-tenant support"""
    return None

# Optional authentication (for public endpoints that can be enhanced with auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        return None
    
    return get_user(username=token_data.username)