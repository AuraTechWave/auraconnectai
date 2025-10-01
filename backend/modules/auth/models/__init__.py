"""Compatibility re-exports for auth models.

Historically the FastAPI routes imported `modules.auth.models` to obtain the
`User` ORM model. The modern codebase moved the authoritative RBAC models into
`core.rbac_models`. This shim keeps legacy imports working so the application
can boot inside Docker/Compose without immediately raising `ImportError`.
"""

from core.rbac_models import RBACUser, RBACRole, RBACPermission

User = RBACUser
Role = RBACRole
Permission = RBACPermission

__all__ = ["User", "Role", "Permission", "RBACUser", "RBACRole", "RBACPermission"]
