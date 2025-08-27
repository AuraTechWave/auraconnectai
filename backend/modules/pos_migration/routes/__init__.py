# backend/modules/pos_migration/routes/__init__.py

from .migration_routes import router as migration_router

__all__ = ["migration_router"]