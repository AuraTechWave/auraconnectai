"""
Simple authentication system for AuraConnect API endpoints.

Provides JWT-based authentication and role-based authorization for
payroll and other sensitive endpoints.
"""

import os
import inspect
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, TYPE_CHECKING
from contextlib import contextmanager

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
import secrets
import logging

from .secrets import get_required_secret
from .database import SessionLocal
from .rbac_models import user_roles
from .auth_context import AuthContextData, get_auth_context, set_auth_context

if TYPE_CHECKING:
    from .rbac_service import RBACService
    from .rbac_models import RBACUser

logger = logging.getLogger(__name__)

# Security Configuration - Environment Variables
# Handle test environments gracefully
if os.getenv('PYTEST_CURRENT_TEST') is not None:
    # For tests, use environment variable or test default
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
else:
    # For non-test environments, require proper secret
    SECRET_KEY = get_required_secret("JWT_SECRET_KEY", "JWT_SECRET_KEY")

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
    email: Optional[str] = None
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


MOCK_USERS: Dict[str, Dict[str, Any]] = {}


@contextmanager
def _get_sync_session() -> Session:
    """Yield a database session for synchronous helpers."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_rbac_service(db: Session) -> "RBACService":
    """Construct an RBAC service instance lazily to avoid circular imports."""

    from .rbac_service import RBACService  # Local import to prevent circular dependency

    return RBACService(db)


def _collect_active_tenant_ids(
    rbac_user: "RBACUser", rbac_service: "RBACService"
) -> List[int]:
    """Collect all tenant IDs available to a user."""

    tenant_ids: Set[int] = set()

    if rbac_user.accessible_tenant_ids:
        for tenant_id in rbac_user.accessible_tenant_ids:
            if tenant_id is not None:
                tenant_ids.add(int(tenant_id))

    if rbac_user.default_tenant_id is not None:
        tenant_ids.add(int(rbac_user.default_tenant_id))

    assignments = (
        rbac_service.db.query(user_roles.c.tenant_id)
        .filter(
            user_roles.c.user_id == rbac_user.id,
            user_roles.c.is_active == True,  # noqa: E712 - SQLAlchemy boolean comparison
        )
        .all()
    )

    for assignment in assignments:
        tenant_value = None

        if hasattr(assignment, "tenant_id"):
            tenant_value = assignment.tenant_id
        elif hasattr(assignment, "_mapping"):
            tenant_value = assignment._mapping.get("tenant_id")
        elif isinstance(assignment, (list, tuple)) and assignment:
            tenant_value = assignment[0]

        if tenant_value is not None:
            tenant_ids.add(int(tenant_value))

    return sorted(tenant_ids)


def _rbac_user_to_auth_user(
    rbac_user: "RBACUser", rbac_service: "RBACService"
) -> User:
    """Convert RBAC user model into lightweight auth representation."""

    roles = [role.name for role in rbac_service.get_user_roles(rbac_user.id)]
    tenant_ids = _collect_active_tenant_ids(rbac_user, rbac_service)

    return User(
        id=rbac_user.id,
        username=rbac_user.username,
        email=rbac_user.email,
        roles=roles,
        tenant_ids=tenant_ids,
        is_active=rbac_user.is_active,
    )


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


def get_user(
    username: Optional[str] = None, *, user_id: Optional[int] = None
) -> Optional[User]:
    """Retrieve a user from the RBAC store or legacy mock cache."""

    rbac_user: Optional[RBACUser] = None

    with _get_sync_session() as db:
        rbac_service = _build_rbac_service(db)

        if user_id is not None:
            rbac_user = rbac_service.get_user_by_id(user_id)

        if rbac_user is None and username:
            rbac_user = rbac_service.get_user_by_username(username)

        if rbac_user:
            return _rbac_user_to_auth_user(rbac_user, rbac_service)

    if username:
        user_data = MOCK_USERS.get(username)
        if user_data:
            logger.warning("Falling back to legacy mock user for %s", username)
            return User(**user_data)

    return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password against the RBAC store."""

    with _get_sync_session() as db:
        rbac_service = _build_rbac_service(db)
        rbac_user = rbac_service.authenticate_user(username, password)

        if rbac_user:
            if needs_password_rehash(rbac_user.hashed_password):
                rbac_user.hashed_password = get_password_hash(password)
                db.commit()

            return _rbac_user_to_auth_user(rbac_user, rbac_service)

    user_data = MOCK_USERS.get(username)
    if user_data and verify_password(password, user_data.get("hashed_password", "")):
        logger.warning("Authenticating against legacy mock user store for %s", username)
        return User(**user_data)

    return None


def generate_token_id() -> str:
    """Generate a unique token ID for tracking."""
    return secrets.token_urlsafe(32)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
) -> str:
    """Create a JWT access token using secure configuration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Add token tracking information and security claims
    token_id = generate_token_id()
    issuer = os.getenv("JWT_ISSUER", "auraconnect-api")
    audience = os.getenv("JWT_AUDIENCE", "auraconnect-ws")
    
    to_encode.update(
        {
            "exp": expire,
            "type": "access",
            "jti": token_id,  # JWT ID for token tracking
            "iat": datetime.utcnow().timestamp(),  # Issued at
            "iss": issuer,  # Issuer
            "aud": audience,  # Audience
        }
    )

    if session_id:
        to_encode["session_id"] = session_id

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, session_id: Optional[str] = None) -> str:
    """Create a JWT refresh token with longer expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Add token tracking information and security claims
    token_id = generate_token_id()
    issuer = os.getenv("JWT_ISSUER", "auraconnect-api")
    audience = os.getenv("JWT_AUDIENCE", "auraconnect-ws")
    
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": token_id,  # JWT ID for token tracking
            "iat": datetime.utcnow().timestamp(),  # Issued at
            "iss": issuer,  # Issuer
            "aud": audience,  # Audience
        }
    )

    if session_id:
        to_encode["session_id"] = session_id

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(
    token: str, token_type: str = "access", check_blacklist: bool = True
) -> Optional[TokenData]:
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

        # Enhanced JWT options with issuer/audience validation
        jwt_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_iss": True,
            "verify_aud": True,
            "require": ["exp", "iat", "type"],
        }
        
        # Expected issuer and audience
        expected_issuer = os.getenv("JWT_ISSUER", "auraconnect-api")
        expected_audience = os.getenv("JWT_AUDIENCE", "auraconnect-ws")
        leeway_seconds = int(os.getenv("JWT_LEEWAY_SECONDS", "120"))

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options=jwt_options,
            issuer=expected_issuer,
            audience=expected_audience,
            leeway=leeway_seconds  # Allow 2 minutes clock skew
        )

        # Check token type
        if payload.get("type") != token_type:
            logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
            return None

        # Prevent algorithm confusion attacks
        if payload.get("alg") == "none":
            logger.warning("Attempted use of 'none' algorithm")
            return None

        # Handle sub as string (JWT standard) but convert to int for internal use
        sub = payload.get("sub")
        if sub is None:
            return None
        
        try:
            user_id: int = int(sub)
        except (ValueError, TypeError):
            return None
            
        username: str = payload.get("username")
        email: Optional[str] = payload.get("email")
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
            email=email,
            roles=roles,
            tenant_ids=tenant_ids,
            session_id=session_id,
            token_id=token_id,
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("Invalid token issuer")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("Invalid token audience")
        return None
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
        "sub": str(token_data.user_id),
        "username": token_data.username,
        "email": token_data.email,
        "roles": token_data.roles,
        "tenant_ids": token_data.tenant_ids,
    }

    access_token = create_access_token(new_token_data, session_id=token_data.session_id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "session_id": token_data.session_id,
    }


def create_user_session(user: User, request: Optional[Request] = None) -> dict:
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
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "tenant_ids": user.tenant_ids,
    }

    # Create refresh token first (needed for session)
    refresh_token_expires = datetime.utcnow() + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    refresh_token = create_refresh_token(token_data)

    # Create session
    session_id = session_manager.create_session(
        user_id=user.id,
        username=user.username,
        refresh_token=refresh_token,
        expires_at=refresh_token_expires,
        user_agent=user_agent,
        ip_address=ip_address,
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
            "tenant_ids": user.tenant_ids,
        },
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
            logger.info(
                f"Logged out session {token_data.session_id} for user {token_data.username}"
            )

        return True

    except Exception as e:
        logger.error(f"Logout failed: {e}")
        return False


DEFAULT_CONTEXT_EMAIL_DOMAIN = "auraconnect.local"


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _build_auth_context(token_data: TokenData) -> AuthContextData:
    if token_data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles = list(token_data.roles or [])
    tenant_ids = list(token_data.tenant_ids or [])
    active_tenant_id = tenant_ids[0] if tenant_ids else None

    return AuthContextData(
        user_id=token_data.user_id,
        username=token_data.username or "",
        roles=roles,
        tenant_ids=tenant_ids,
        active_tenant_id=active_tenant_id,
        email=token_data.email,
    )


def _ensure_auth_context(
    credentials: Optional[HTTPAuthorizationCredentials],
    credentials_exception: HTTPException,
) -> AuthContextData:
    context = get_auth_context()
    if context:
        return context

    if not credentials:
        raise credentials_exception

    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception

    context = _build_auth_context(token_data)
    set_auth_context(context)
    return context


def _user_from_context(context: AuthContextData) -> User:
    fallback_username = context.username or f"user-{context.user_id}"
    fallback_email = context.email or f"{fallback_username}@{DEFAULT_CONTEXT_EMAIL_DOMAIN}"

    source_user = get_user(user_id=context.user_id, username=context.username or None)
    roles = context.roles
    tenant_ids = context.tenant_ids

    if source_user:
        return User(
            id=source_user.id,
            username=source_user.username,
            email=source_user.email or fallback_email,
            roles=roles or source_user.roles,
            tenant_ids=tenant_ids or source_user.tenant_ids,
            is_active=source_user.is_active,
        )

    return User(
        id=context.user_id,
        username=fallback_username,
        email=fallback_email,
        roles=roles,
        tenant_ids=tenant_ids,
        is_active=True,
    )


def _current_user_from_context() -> User:
    context = get_auth_context()
    if context is None:
        raise _credentials_exception()
    return _user_from_context(context)


class AuthorizationRequirement:
    """Callable that can act as a FastAPI dependency or decorator."""

    def __init__(self, check_fn, error_detail: str):
        self._check_fn = check_fn
        self._error_detail = error_detail

    def __call__(self, maybe_callable=None):
        if maybe_callable is not None and callable(maybe_callable):
            return self._decorate(maybe_callable)
        return self._dependency()

    def _dependency(self) -> User:
        user = _current_user_from_context()
        if not self._check_fn(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=self._error_detail,
            )
        return user

    def _decorate(self, func):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                self._dependency()
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            self._dependency()
            return func(*args, **kwargs)

        return sync_wrapper


PERMISSION_ROLE_MAP: Dict[str, List[str]] = {
    "admin:recipes": ["admin"],
    "manager:recipes": ["admin", "manager"],
    "permission.name": ["admin"],
    "ai.configure_alerts": ["admin", "ai_admin"],
    "ai.export_data": ["admin", "ai_admin"],
    "ai.view_insights": ["admin", "ai_admin", "analytics_viewer", "manager"],
    "analytics:read": ["admin", "analytics_admin", "analytics_viewer", "manager"],
    "inventory:create": ["admin", "inventory_admin", "manager"],
    "inventory:delete": ["admin", "inventory_admin"],
    "inventory:read": ["admin", "inventory_admin", "manager", "staff"],
    "inventory:update": ["admin", "inventory_admin", "manager"],
    "manage_tips": ["admin", "manager", "payroll_manager"],
    "menu:create": ["admin", "menu_admin", "manager"],
    "menu:delete": ["admin", "menu_admin"],
    "menu:read": ["admin", "menu_admin", "manager", "staff"],
    "menu:update": ["admin", "menu_admin", "manager"],
    "order:delete": ["admin", "manager"],
    "order:manage_kitchen": ["admin", "manager", "kitchen_manager"],
    "order:read": ["admin", "manager", "staff"],
    "order:write": ["admin", "manager"],
    "order.split": ["admin", "manager", "staff"],
    "payroll:approve": ["admin", "payroll_manager"],
    "payroll:export": ["admin", "payroll_manager"],
    "payroll:read": ["admin", "payroll_manager", "payroll_clerk"],
    "payroll:write": ["admin", "payroll_manager"],
    "pricing.apply": ["admin", "pricing_admin", "manager", "staff"],
    "pricing.create": ["admin", "pricing_admin", "manager"],
    "pricing.delete": ["admin", "pricing_admin"],
    "pricing.update": ["admin", "pricing_admin", "manager"],
    "pricing.view_metrics": ["admin", "pricing_admin", "manager", "analytics_viewer"],
    "refunds.approve": ["admin", "refund_admin", "manager"],
    "refunds.create": ["admin", "refund_admin", "manager", "staff"],
    "refunds.manage": ["admin", "refund_admin", "manager"],
    "refunds.manage_policies": ["admin", "refund_admin"],
    "refunds.process": ["admin", "refund_admin"],
    "refunds.view": ["admin", "refund_admin", "manager", "staff"],
    "refunds.view_statistics": ["admin", "refund_admin", "manager", "analytics_viewer"],
    "schedule.manage": ["admin", "schedule_admin", "manager", "scheduler"],
    "schedule.publish": ["admin", "schedule_admin", "manager"],
    "staff:delete": ["admin", "staff_manager"],
    "staff:manage_schedule": ["admin", "staff_manager", "manager"],
    "staff:read": ["admin", "staff_manager", "manager", "staff_viewer"],
    "staff:write": ["admin", "staff_manager", "manager"],
    "system:audit": ["admin", "system_admin"],
    "system:read": ["admin", "system_admin"],
    "system:write": ["admin", "system_admin"],
    "tables.manage_layout": ["admin", "table_admin", "manager"],
    "tables.manage_reservations": ["admin", "table_admin", "manager", "host"],
    "tables.manage_sessions": ["admin", "table_admin", "manager", "host"],
    "tables.update_status": ["admin", "table_admin", "manager", "host", "server"],
    "tables.view_analytics": ["admin", "table_admin", "manager", "analytics_viewer"],
    "tax.admin": ["admin", "tax_admin"],
    "tax.audit": ["admin", "tax_admin", "tax_manager"],
    "tax.calculate": ["admin", "tax_admin", "tax_manager"],
    "tax.file": ["admin", "tax_admin", "tax_manager"],
    "tax.pay": ["admin", "tax_admin", "tax_manager"],
    "tax.report": ["admin", "tax_admin", "tax_manager"],
    "tax.view": ["admin", "tax_admin", "tax_manager", "tax_viewer"],
    "user:delete": ["admin"],
    "user:manage_roles": ["admin"],
    "user:read": ["admin", "system_admin"],
    "user:write": ["admin", "system_admin"],
}


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """Resolve the current authenticated user from the request context."""

    credentials_exception = _credentials_exception()
    context = _ensure_auth_context(credentials, credentials_exception)
    user = _user_from_context(context)

    if not user.is_active:
        raise credentials_exception

    return user



def require_roles(required_roles: List[str]):
    """Enforce that the current user holds at least one of the specified roles."""

    required_set = set(required_roles)

    def check(user: User) -> bool:
        user_roles = set(user.roles or [])
        if "admin" in user_roles:
            return True
        return bool(user_roles & required_set)

    error_detail = f"Operation requires one of these roles: {required_roles}"
    return AuthorizationRequirement(check, error_detail)



def require_tenant_access(tenant_id: int):
    """Ensure the active tenant matches the required tenant identifier."""

    expected_tenant = int(tenant_id)

    def check(user: User) -> bool:
        user_roles = set(user.roles or [])
        if "admin" in user_roles:
            return True

        context = get_auth_context()
        if context and context.active_tenant_id is not None:
            return context.active_tenant_id == expected_tenant

        tenants = context.tenant_ids if context else user.tenant_ids or []
        return expected_tenant in tenants

    return AuthorizationRequirement(check, "Access denied for this tenant")


# Common role dependencies
require_admin = require_roles(["admin"])
require_payroll_access = require_roles(["admin", "payroll_manager", "payroll_clerk"])
require_payroll_write = require_roles(["admin", "payroll_manager"])
require_staff_access = require_roles(
    ["admin", "payroll_manager", "payroll_clerk", "manager", "staff_viewer"]
)


def require_permission(permission: str, *, allow_admin: bool = True) -> AuthorizationRequirement:
    """Construct an authorization requirement for the supplied permission string."""

    allowed_roles = set(PERMISSION_ROLE_MAP.get(permission, []))

    def check(user: User) -> bool:
        user_roles = set(user.roles or [])
        if allow_admin and "admin" in user_roles:
            return True
        if not allowed_roles:
            return False
        return bool(user_roles & allowed_roles)

    return AuthorizationRequirement(
        check,
        error_detail=f"Missing required permission: {permission}",
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        context = _ensure_auth_context(credentials, _credentials_exception())
    except HTTPException:
        return None

    return _user_from_context(context)


# Tenant support (placeholder)
async def get_current_tenant() -> Optional[int]:
    """Get current tenant ID - placeholder for multi-tenant support"""
    return None
