from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Minimal user model for typing and lightweight runtime usage.

    Fields chosen to satisfy common dependencies (id, restaurant context, roles).
    Replace with real ORM/Pydantic models as needed without changing import path.
    """

    id: int
    email: EmailStr
    name: Optional[str] = None
    restaurant_id: Optional[int] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True


class PasswordResetToken(BaseModel):
    token: str
    user_id: int
    expires_at: datetime

