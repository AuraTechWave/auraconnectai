# backend/core/deps.py

"""
Common dependencies for the application
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user as auth_get_current_user
from .rbac_models import RBACUser as User

# Re-export commonly used dependencies
security = HTTPBearer()

# Re-export get_current_user from auth module
get_current_user = auth_get_current_user

# Optional user dependency
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    try:
        return await auth_get_current_user(credentials)
    except HTTPException:
        return None

# Database dependency
get_db = get_db