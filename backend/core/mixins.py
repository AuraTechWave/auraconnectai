from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func


class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class TenantMixin:
    """Mixin for multi-tenant support"""
    tenant_id = Column(Integer, nullable=True)  # Nullable for single-tenant mode
