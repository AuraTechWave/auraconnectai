"""
Enhanced Authentication routes for AuraConnect API.

Provides JWT-based authentication endpoints with refresh tokens,
session management, and comprehensive security features.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer
from pydantic import BaseModel
from typing import Optional

from ....core.auth import (
    authenticate_user, create_user_session, get_current_user, logout_user,
    refresh_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, User
)
from ....core.session_manager import session_manager


class Token(BaseModel):
    """Enhanced token response model."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    access_expires_in: int
    refresh_expires_in: Optional[int] = None
    session_id: Optional[str] = None
    user_info: dict


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request model."""
    logout_all_sessions: bool = False


class UserInfo(BaseModel):
    """User information response model."""
    id: int
    username: str
    email: str
    roles: list
    tenant_ids: list
    is_active: bool


class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str
    created_at: str
    last_accessed: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: bool


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
):
    """
    Authenticate user and return JWT access and refresh tokens.
    
    ## Request Body (Form Data)
    - **username**: Username for authentication
    - **password**: Password for authentication
    
    ## Response
    Returns JWT access token, refresh token, and user information with session management.
    
    ## Features
    - Creates secure session with Redis storage
    - Issues both access and refresh tokens
    - Tracks user agent and IP address
    - Provides comprehensive security logging
    
    ## Test Credentials
    - **Username**: admin, **Password**: secret (Admin access)
    - **Username**: payroll_clerk, **Password**: secret (Payroll access)
    - **Username**: manager, **Password**: secret (Manager access)
    
    ## Example
    ```bash
    curl -X POST "http://localhost:8000/auth/login" \
         -H "Content-Type: application/x-www-form-urlencoded" \
         -d "username=admin&password=secret"
    ```
    """
    # Rate limiting check could be added here
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )
    
    # Create session with tokens
    session_data = create_user_session(user, request)
    
    return Token(
        access_token=session_data["access_token"],
        refresh_token=session_data["refresh_token"],
        token_type=session_data["token_type"],
        access_expires_in=session_data["access_expires_in"],
        refresh_expires_in=session_data["refresh_expires_in"],
        session_id=session_data["session_id"],
        user_info=session_data["user_info"]
    )


@router.get("/me", response_model=UserInfo)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    ## Authentication Required
    - Requires valid JWT token in Authorization header
    
    ## Response
    Returns current user information including roles and tenant access.
    
    ## Example
    ```bash
    curl -X GET "http://localhost:8000/auth/me" \
         -H "Authorization: Bearer YOUR_JWT_TOKEN"
    ```
    """
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        roles=current_user.roles,
        tenant_ids=current_user.tenant_ids,
        is_active=current_user.is_active
    )


@router.post("/refresh")
async def refresh_token_endpoint(refresh_request: RefreshTokenRequest):
    """
    Refresh JWT access token using refresh token.
    
    ## Request Body
    - **refresh_token**: Valid refresh token
    
    ## Response
    Returns new JWT access token with extended expiration.
    
    ## Security Features
    - Validates refresh token against session store
    - Checks token blacklist
    - Updates session last accessed time
    - Maintains session continuity
    
    ## Example
    ```bash
    curl -X POST "http://localhost:8000/auth/refresh" \
         -H "Content-Type: application/json" \
         -d '{"refresh_token": "your_refresh_token"}'
    ```
    """
    token_data = refresh_access_token(refresh_request.refresh_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "access_token": token_data["access_token"],
        "token_type": token_data["token_type"],
        "expires_in": token_data["expires_in"],
        "session_id": token_data.get("session_id")
    }


@router.post("/logout")
async def logout_endpoint(
    logout_request: LogoutRequest = LogoutRequest(),
    current_user: User = Depends(get_current_user),
    authorization: str = Depends(HTTPBearer())
):
    """
    Logout user and revoke tokens.
    
    ## Authentication Required
    - Requires valid JWT token in Authorization header
    
    ## Request Body
    - **logout_all_sessions**: Whether to logout from all sessions (default: false)
    
    ## Response
    Returns logout confirmation.
    
    ## Security Features
    - Blacklists current token immediately
    - Revokes session(s) from Redis store
    - Optional logout from all user sessions
    - Comprehensive security logging
    
    ## Example
    ```bash
    curl -X POST "http://localhost:8000/auth/logout" \
         -H "Authorization: Bearer your_access_token" \
         -H "Content-Type: application/json" \
         -d '{"logout_all_sessions": false}'
    ```
    """
    token = authorization.credentials
    success = logout_user(token, logout_request.logout_all_sessions)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )
    
    return {
        "message": "Logged out successfully",
        "logout_all_sessions": logout_request.logout_all_sessions
    }


@router.get("/sessions")
async def get_user_sessions(current_user: User = Depends(get_current_user)):
    """
    Get current user's active sessions.
    
    ## Authentication Required
    - Requires valid JWT token in Authorization header
    
    ## Response
    Returns list of active sessions with metadata.
    
    ## Example
    ```bash
    curl -X GET "http://localhost:8000/auth/sessions" \
         -H "Authorization: Bearer your_access_token"
    ```
    """
    session_count = session_manager.get_user_session_count(current_user.id)
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "active_sessions": session_count,
        "message": "Session management available via Redis store"
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke a specific session.
    
    ## Authentication Required
    - Requires valid JWT token in Authorization header
    
    ## Path Parameters
    - **session_id**: Session ID to revoke
    
    ## Response
    Returns revocation confirmation.
    
    ## Example
    ```bash
    curl -X DELETE "http://localhost:8000/auth/sessions/session_id" \
         -H "Authorization: Bearer your_access_token"
    ```
    """
    # Verify session belongs to current user
    session = session_manager.get_session(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied"
        )
    
    success = session_manager.revoke_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke session"
        )
    
    return {
        "message": f"Session {session_id} revoked successfully"
    }