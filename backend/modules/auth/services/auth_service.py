"""Lightweight auth service adapter.

Provides a stable import path for dependencies expected by routers while
delegating to core.auth implementations.
"""

from core.auth import get_current_user as _core_get_current_user

# Re-export as the dependency callable expected by routers
get_current_user = _core_get_current_user

