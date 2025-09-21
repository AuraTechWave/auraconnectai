"""Lightweight SQLAlchemy user model for compatibility in tests."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime

from core.database import Base
try:  # pragma: no cover - optional in lightweight test runs
    from core.password_models import PasswordResetToken  # noqa: F401
except Exception:  # pragma: no cover - skip heavy password models for unit tests
    PasswordResetToken = None  # type: ignore[assignment]


class AuthUser(Base):
    """Minimal user model providing the ``users`` table expected by FKs."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Backwards-compatible export
User = AuthUser

__all__ = ["User", "AuthUser"]
if PasswordResetToken is not None:
    __all__.append("PasswordResetToken")
