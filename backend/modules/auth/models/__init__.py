"""Auth domain models bridging RBAC implementation with legacy imports."""

try:  # pragma: no cover - optional in minimal test environments
    from core.rbac_models import (  # noqa: F401
        RBACUser,
        RBACRole,
        RBACPermission,
        UserPermission,
    )
except Exception:  # pragma: no cover - allow tests without full RBAC stack
    RBACUser = RBACRole = RBACPermission = UserPermission = None  # type: ignore

try:  # pragma: no cover - optional in minimal test environments
    from core.password_models import (  # noqa: F401
        PasswordResetToken,
        PasswordHistory,
        SecurityAuditLog,
    )
except Exception:  # pragma: no cover - avoid pulling heavy password models in tests
    PasswordResetToken = PasswordHistory = SecurityAuditLog = None  # type: ignore

from .user_models import AuthUser as User  # noqa: F401

# Re-export with legacy names expected by modules
Role = RBACRole
Permission = RBACPermission

__all__ = ["User", "Role", "Permission"]

if RBACUser is not None:
    __all__.extend(["RBACUser", "RBACRole", "RBACPermission", "UserPermission"])
if PasswordResetToken is not None:
    __all__.extend([
        "PasswordResetToken",
        "PasswordHistory",
        "SecurityAuditLog",
    ])
