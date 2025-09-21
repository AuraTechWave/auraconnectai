# backend/modules/menu/routes/__init__.py

from fastapi import APIRouter
from .menu_routes import router as menu_router
from .inventory_routes import router as inventory_router
from .versioning_routes import router as versioning_router
from .recipe_routes import router as recipe_router
try:
    from .recipe_routes_optimized import router as recipe_optimized_router
except SyntaxError:  # pragma: no cover - fallback for invalid legacy file
    recipe_optimized_router = None
# Some optional routers may fail to import in minimal test environments
try:
    from .recipe_export_routes import router as recipe_export_router
except ImportError:  # pragma: no cover - optional dependency
    recipe_export_router = None
from .recommendation_routes import router as recommendation_router

# Create main router for menu module
router = APIRouter()

# Include sub-routers
router.include_router(menu_router)
router.include_router(inventory_router)
router.include_router(versioning_router)
router.include_router(recipe_router)
if recipe_optimized_router is not None:
    router.include_router(recipe_optimized_router)
if recipe_export_router is not None:
    router.include_router(recipe_export_router)
router.include_router(recommendation_router)
