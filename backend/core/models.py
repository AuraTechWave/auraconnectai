"""Compatibility module exposing common SQLAlchemy mixins."""

from .mixins import TimestampMixin, TenantMixin  # noqa: F401

__all__ = ["TimestampMixin", "TenantMixin"]
