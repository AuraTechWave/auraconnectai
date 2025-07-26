"""
Authentication routes for AuraConnect API.

Provides JWT-based authentication endpoints for secure API access.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from ....core.auth import (
    authenticate_user, create_access_token, get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES, User
)


class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    user_info: dict


class UserInfo(BaseModel):
    """User information response model."""
    id: int
    username: str
    email: str
    roles: list
    tenant_ids: list
    is_active: bool


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT access token.
    
    ## Request Body (Form Data)
    - **username**: Username for authentication
    - **password**: Password for authentication
    
    ## Response
    Returns JWT access token and user information.
    
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
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "roles": user.roles,
            "tenant_ids": user.tenant_ids
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_info={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
            "tenant_ids": user.tenant_ids
        }
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


@router.post("/refresh", response_model=Token)
async def refresh_access_token(current_user: User = Depends(get_current_user)):
    """
    Refresh JWT access token.
    
    ## Authentication Required
    - Requires valid JWT token in Authorization header
    
    ## Response
    Returns new JWT access token with extended expiration.
    """
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": current_user.id,
            "username": current_user.username,
            "roles": current_user.roles,
            "tenant_ids": current_user.tenant_ids
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_info={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "roles": current_user.roles,
            "tenant_ids": current_user.tenant_ids
        }
    )