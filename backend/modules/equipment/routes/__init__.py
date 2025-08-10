# backend/modules/equipment/routes/__init__.py
"""Equipment routes module"""

from .equipment_routes import router
from .equipment_routes_improved import router as router_improved

__all__ = ["router", "router_improved"]