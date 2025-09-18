"""
Menu and Recipe caching service with intelligent invalidation.

Provides caching for:
- Menu items and categories
- Recipe calculations
- Ingredient costs
- Nutritional information
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.redis_cache import redis_cache, cached
from ..models.menu import MenuItem, MenuCategory
from ..models.recipe import Recipe

logger = logging.getLogger(__name__)


class MenuCacheService:
    """Handles menu and recipe caching with smart invalidation."""
    
    CACHE_NAMESPACE = "menu"
    
    # Cache TTLs (in seconds)
    TTL_MENU_ITEM = 3600  # 1 hour
    TTL_MENU_CATEGORY = 3600  # 1 hour
    TTL_RECIPE = 1800  # 30 minutes
    TTL_RECIPE_COST = 300  # 5 minutes (prices change more frequently)
    TTL_MENU_FULL = 900  # 15 minutes
    TTL_NUTRITIONAL = 7200  # 2 hours
    
    @classmethod
    def get_menu_item_key(cls, item_id: int, tenant_id: Optional[int] = None) -> str:
        """Generate cache key for menu item."""
        if tenant_id:
            return f"item:{tenant_id}:{item_id}"
        return f"item:{item_id}"
        
    @classmethod
    def get_category_key(cls, category_id: int, tenant_id: Optional[int] = None) -> str:
        """Generate cache key for menu category."""
        if tenant_id:
            return f"category:{tenant_id}:{category_id}"
        return f"category:{category_id}"
        
    @classmethod
    def get_recipe_key(cls, recipe_id: int, tenant_id: Optional[int] = None) -> str:
        """Generate cache key for recipe."""
        if tenant_id:
            return f"recipe:{tenant_id}:{recipe_id}"
        return f"recipe:{recipe_id}"
        
    @classmethod
    def get_recipe_cost_key(cls, recipe_id: int, tenant_id: Optional[int] = None) -> str:
        """Generate cache key for recipe cost calculation."""
        if tenant_id:
            return f"recipe_cost:{tenant_id}:{recipe_id}"
        return f"recipe_cost:{recipe_id}"
        
    @classmethod
    async def cache_menu_item(
        cls,
        item: MenuItem,
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache a menu item."""
        key = cls.get_menu_item_key(item.id, tenant_id)
        
        # Prepare cacheable data
        data = {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": float(item.price),
            "category_id": item.category_id,
            "is_active": item.is_active,
            "is_available": item.is_available,
            "dietary_flags": item.dietary_flags,
            "preparation_time": item.preparation_time,
            "spice_level": item.spice_level,
            "calories": item.calories,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        
        # Cache with tags for invalidation
        return await redis_cache.set(
            key,
            data,
            ttl=cls.TTL_MENU_ITEM,
            namespace=cls.CACHE_NAMESPACE,
            tags=[
                f"tenant:{tenant_id}" if tenant_id else "global",
                f"category:{item.category_id}",
                "menu_items"
            ]
        )
        
    @classmethod
    async def get_menu_item(
        cls,
        item_id: int,
        tenant_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get menu item from cache."""
        key = cls.get_menu_item_key(item_id, tenant_id)
        return await redis_cache.get(key, namespace=cls.CACHE_NAMESPACE)
        
    @classmethod
    async def cache_recipe_cost(
        cls,
        recipe_id: int,
        cost_data: Dict[str, Any],
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache recipe cost calculation."""
        key = cls.get_recipe_cost_key(recipe_id, tenant_id)
        
        # Add timestamp to track freshness
        cost_data["calculated_at"] = datetime.utcnow().isoformat()
        
        return await redis_cache.set(
            key,
            cost_data,
            ttl=cls.TTL_RECIPE_COST,
            namespace=cls.CACHE_NAMESPACE,
            tags=[
                f"tenant:{tenant_id}" if tenant_id else "global",
                f"recipe:{recipe_id}",
                "recipe_costs"
            ]
        )
        
    @classmethod
    async def get_recipe_cost(
        cls,
        recipe_id: int,
        tenant_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get recipe cost from cache."""
        key = cls.get_recipe_cost_key(recipe_id, tenant_id)
        return await redis_cache.get(key, namespace=cls.CACHE_NAMESPACE)
        
    @classmethod
    async def cache_full_menu(
        cls,
        menu_data: Dict[str, Any],
        tenant_id: Optional[int] = None
    ) -> bool:
        """Cache full menu structure."""
        key = f"full_menu:{tenant_id}" if tenant_id else "full_menu:global"
        
        return await redis_cache.set(
            key,
            menu_data,
            ttl=cls.TTL_MENU_FULL,
            namespace=cls.CACHE_NAMESPACE,
            tags=[
                f"tenant:{tenant_id}" if tenant_id else "global",
                "full_menu"
            ]
        )
        
    @classmethod
    async def get_full_menu(
        cls,
        tenant_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get full menu from cache."""
        key = f"full_menu:{tenant_id}" if tenant_id else "full_menu:global"
        return await redis_cache.get(key, namespace=cls.CACHE_NAMESPACE)
        
    @classmethod
    async def invalidate_menu_item(
        cls,
        item_id: int,
        category_id: Optional[int] = None,
        tenant_id: Optional[int] = None
    ):
        """Invalidate menu item cache and related data."""
        # Delete specific item
        key = cls.get_menu_item_key(item_id, tenant_id)
        await redis_cache.delete(key, namespace=cls.CACHE_NAMESPACE)
        
        # Invalidate category if provided
        if category_id:
            await redis_cache.invalidate_tag(f"category:{category_id}")
            
        # Invalidate full menu
        await redis_cache.invalidate_tag("full_menu")
        
        # Invalidate tenant-specific caches
        if tenant_id:
            await redis_cache.invalidate_tag(f"tenant:{tenant_id}")
            
    @classmethod
    async def invalidate_recipe(
        cls,
        recipe_id: int,
        tenant_id: Optional[int] = None
    ):
        """Invalidate recipe cache and related cost calculations."""
        # Delete specific recipe
        key = cls.get_recipe_key(recipe_id, tenant_id)
        await redis_cache.delete(key, namespace=cls.CACHE_NAMESPACE)
        
        # Delete recipe cost
        cost_key = cls.get_recipe_cost_key(recipe_id, tenant_id)
        await redis_cache.delete(cost_key, namespace=cls.CACHE_NAMESPACE)
        
        # Invalidate recipe-related tags
        await redis_cache.invalidate_tag(f"recipe:{recipe_id}")
        
    @classmethod
    async def invalidate_all_recipe_costs(cls):
        """Invalidate all recipe cost calculations (e.g., when ingredient prices change)."""
        await redis_cache.invalidate_tag("recipe_costs")
        
    @classmethod
    async def warm_menu_cache(cls, db: Session, tenant_id: Optional[int] = None):
        """Proactively warm menu cache."""
        try:
            # Get active menu items
            query = db.query(MenuItem).filter(MenuItem.is_active == True)
            if tenant_id:
                query = query.filter(MenuItem.tenant_id == tenant_id)
                
            items = query.all()
            
            # Cache each item
            cached_count = 0
            for item in items:
                if await cls.cache_menu_item(item, tenant_id):
                    cached_count += 1
                    
            logger.info(f"Warmed cache with {cached_count} menu items")
            
        except Exception as e:
            logger.error(f"Error warming menu cache: {e}")


# Decorated functions for common operations
@cached(namespace="menu", ttl=3600, tags=["menu_categories"])
async def get_cached_categories(tenant_id: Optional[int] = None) -> List[Dict]:
    """
    This is a placeholder that would be implemented by the actual service.
    The decorator handles the caching automatically.
    """
    pass


@cached(
    key_func=lambda item_id, with_recipe=False: f"item_detail:{item_id}:{with_recipe}",
    namespace="menu",
    ttl=1800,
    tags=["menu_items"]
)
async def get_cached_menu_item_detail(
    item_id: int,
    with_recipe: bool = False
) -> Optional[Dict]:
    """
    This is a placeholder that would be implemented by the actual service.
    The decorator handles the caching automatically.
    """
    pass


# Export the service
__all__ = ["MenuCacheService"]