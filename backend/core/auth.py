"""
Simple authentication system for AuraConnect API endpoints.

Provides JWT-based authentication and role-based authorization for
payroll and other sensitive endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration
SECRET_KEY = "your-secret-key-here"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    roles: List[str] = []
    tenant_ids: List[int] = []


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
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


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


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        roles: List[str] = payload.get("roles", [])
        tenant_ids: List[int] = payload.get("tenant_ids", [])
        
        if user_id is None:
            return None
            
        return TokenData(
            user_id=user_id,
            username=username,
            roles=roles,
            tenant_ids=tenant_ids
        )
    except JWTError:
        return None


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