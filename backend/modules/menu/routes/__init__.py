# backend/modules/menu/routes/__init__.py

from fastapi import APIRouter
from .menu_routes import router as menu_router
from .inventory_routes import router as inventory_router
from .versioning_routes import router as versioning_router
from .recipe_routes import router as recipe_router

# Create main router for menu module
router = APIRouter()

# Include sub-routers
router.include_router(menu_router)
router.include_router(inventory_router)
router.include_router(versioning_router)
router.include_router(recipe_router)