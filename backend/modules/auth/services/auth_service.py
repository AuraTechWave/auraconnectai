"""Legacy AuthService wrapper bridging to ``core.auth`` functions."""

from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user as core_get_current_user,
    logout_user,
    refresh_access_token,
    security,
    User,
)


class AuthService:
    """Simple wrapper exposing authentication helpers as static methods."""

    authenticate_user = staticmethod(authenticate_user)
    create_access_token = staticmethod(create_access_token)
    create_refresh_token = staticmethod(create_refresh_token)
    logout_user = staticmethod(logout_user)
    refresh_access_token = staticmethod(refresh_access_token)

    @staticmethod
    async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> User:
        return await core_get_current_user(credentials)

    @staticmethod
    def issue_access_token(data: dict) -> str:
        return create_access_token(data=data)

    @staticmethod
    def issue_refresh_token(data: dict) -> str:
        return create_refresh_token(data=data)


# Convenience re-export for dependency injection
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    return await core_get_current_user(credentials)
