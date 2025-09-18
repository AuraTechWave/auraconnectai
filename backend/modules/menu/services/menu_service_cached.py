"""
Example of menu service with integrated caching.

This demonstrates how to integrate the advanced caching
strategy into existing services.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.redis_cache import cached
from core.cache_config import get_cache_ttl
from .menu_cache_service import MenuCacheService
from ..models.menu import MenuItem, MenuCategory
from ..schemas.menu_schemas import MenuItemResponse, MenuCategoryResponse


class CachedMenuService:
    """Menu service with intelligent caching."""
    
    def __init__(self, db: Session, tenant_id: Optional[int] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.cache_service = MenuCacheService()
        
    @cached(
        namespace="menu",
        ttl=lambda: get_cache_ttl("menu", "item"),
        tags=lambda self, item_id: [
            f"tenant:{self.tenant_id}" if self.tenant_id else "global",
            f"item:{item_id}",
            "menu_items"
        ]
    )
    async def get_menu_item(
        self,
        item_id: int,
        include_recipe: bool = False
    ) -> Optional[MenuItemResponse]:
        """Get menu item with caching."""
        # Check cache first
        cached_item = await self.cache_service.get_menu_item(item_id, self.tenant_id)
        if cached_item and not include_recipe:
            return MenuItemResponse(**cached_item)
            
        # Query database
        query = self.db.query(MenuItem).filter(MenuItem.id == item_id)
        if self.tenant_id:
            query = query.filter(MenuItem.tenant_id == self.tenant_id)
            
        item = query.first()
        if not item:
            return None
            
        # Cache the result
        await self.cache_service.cache_menu_item(item, self.tenant_id)
        
        # Convert to response schema
        response = MenuItemResponse.from_orm(item)
        
        if include_recipe:
            # Include recipe data (would also be cached)
            response.recipe = await self._get_recipe_data(item_id)
            
        return response
        
    @cached(
        namespace="menu",
        ttl=lambda: get_cache_ttl("menu", "full_menu"),
        tags=lambda self: [
            f"tenant:{self.tenant_id}" if self.tenant_id else "global",
            "full_menu"
        ]
    )
    async def get_full_menu(
        self,
        include_unavailable: bool = False,
        category_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get full menu structure with caching."""
        # Try cache first
        cache_key = f"full_menu:{self.tenant_id}:{include_unavailable}:{category_id}"
        cached_menu = await self.cache_service.get_full_menu(self.tenant_id)
        
        if cached_menu:
            # Filter cached data based on parameters
            if not include_unavailable:
                cached_menu = self._filter_available_items(cached_menu)
            if category_id:
                cached_menu = self._filter_by_category(cached_menu, category_id)
            return cached_menu
            
        # Build menu from database
        menu_data = await self._build_menu_structure(
            include_unavailable,
            category_id
        )
        
        # Cache the complete menu
        await self.cache_service.cache_full_menu(menu_data, self.tenant_id)
        
        return menu_data
        
    async def update_menu_item(
        self,
        item_id: int,
        update_data: Dict[str, Any]
    ) -> MenuItemResponse:
        """Update menu item and invalidate cache."""
        # Update in database
        query = self.db.query(MenuItem).filter(MenuItem.id == item_id)
        if self.tenant_id:
            query = query.filter(MenuItem.tenant_id == self.tenant_id)
            
        item = query.first()
        if not item:
            raise ValueError(f"Menu item {item_id} not found")
            
        # Update fields
        for key, value in update_data.items():
            if hasattr(item, key):
                setattr(item, key, value)
                
        item.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Invalidate cache
        await self.cache_service.invalidate_menu_item(
            item_id,
            item.category_id,
            self.tenant_id
        )
        
        # Return updated item
        return MenuItemResponse.from_orm(item)
        
    @cached(
        namespace="menu",
        ttl=lambda: get_cache_ttl("menu", "recipe_cost"),
        tags=lambda self, recipe_id: [
            f"tenant:{self.tenant_id}" if self.tenant_id else "global",
            f"recipe:{recipe_id}",
            "recipe_costs"
        ]
    )
    async def calculate_recipe_cost(
        self,
        recipe_id: int,
        portion_size: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate recipe cost with caching."""
        # Check cache
        cached_cost = await self.cache_service.get_recipe_cost(
            recipe_id,
            self.tenant_id
        )
        
        if cached_cost and not portion_size:
            # Check if cached cost is recent enough
            calculated_at = datetime.fromisoformat(cached_cost["calculated_at"])
            age = datetime.utcnow() - calculated_at
            
            # If less than 5 minutes old, use it
            if age.total_seconds() < 300:
                return cached_cost
                
        # Calculate cost (expensive operation)
        cost_data = await self._calculate_recipe_cost_internal(
            recipe_id,
            portion_size
        )
        
        # Cache the result
        await self.cache_service.cache_recipe_cost(
            recipe_id,
            cost_data,
            self.tenant_id
        )
        
        return cost_data
        
    async def bulk_update_prices(
        self,
        price_updates: List[Dict[str, Any]]
    ):
        """Bulk update menu prices and invalidate cache."""
        # Update prices in database
        for update in price_updates:
            item_id = update["item_id"]
            new_price = update["price"]
            
            query = self.db.query(MenuItem).filter(MenuItem.id == item_id)
            if self.tenant_id:
                query = query.filter(MenuItem.tenant_id == self.tenant_id)
                
            query.update({"price": new_price, "updated_at": datetime.utcnow()})
            
        self.db.commit()
        
        # Invalidate all menu caches
        await self.cache_service.invalidate_all_recipe_costs()
        
        # Invalidate full menu cache
        if self.tenant_id:
            from core.redis_cache import redis_cache
            await redis_cache.invalidate_tag(f"tenant:{self.tenant_id}")
        else:
            await redis_cache.clear_namespace("menu")
            
    # Helper methods
    
    async def _get_recipe_data(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get recipe data for menu item."""
        # This would be implemented with recipe service
        pass
        
    async def _build_menu_structure(
        self,
        include_unavailable: bool,
        category_id: Optional[int]
    ) -> Dict[str, Any]:
        """Build complete menu structure from database."""
        # Query categories
        category_query = self.db.query(MenuCategory)
        if self.tenant_id:
            category_query = category_query.filter(
                MenuCategory.tenant_id == self.tenant_id
            )
        if category_id:
            category_query = category_query.filter(
                MenuCategory.id == category_id
            )
            
        categories = category_query.all()
        
        # Query items
        item_query = self.db.query(MenuItem)
        if self.tenant_id:
            item_query = item_query.filter(MenuItem.tenant_id == self.tenant_id)
        if not include_unavailable:
            item_query = item_query.filter(MenuItem.is_available == True)
        if category_id:
            item_query = item_query.filter(MenuItem.category_id == category_id)
            
        items = item_query.all()
        
        # Build structure
        menu_structure = {
            "categories": [],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        for category in categories:
            category_data = {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "display_order": category.display_order,
                "items": []
            }
            
            # Add items to category
            for item in items:
                if item.category_id == category.id:
                    category_data["items"].append({
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "price": float(item.price),
                        "is_available": item.is_available,
                        "dietary_flags": item.dietary_flags,
                        "preparation_time": item.preparation_time,
                    })
                    
            menu_structure["categories"].append(category_data)
            
        return menu_structure
        
    def _filter_available_items(self, menu_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out unavailable items from menu data."""
        filtered = menu_data.copy()
        
        for category in filtered.get("categories", []):
            category["items"] = [
                item for item in category.get("items", [])
                if item.get("is_available", True)
            ]
            
        return filtered
        
    def _filter_by_category(
        self,
        menu_data: Dict[str, Any],
        category_id: int
    ) -> Dict[str, Any]:
        """Filter menu data by category."""
        filtered = menu_data.copy()
        filtered["categories"] = [
            cat for cat in filtered.get("categories", [])
            if cat.get("id") == category_id
        ]
        return filtered
        
    async def _calculate_recipe_cost_internal(
        self,
        recipe_id: int,
        portion_size: Optional[float] = None
    ) -> Dict[str, float]:
        """Internal method to calculate recipe cost."""
        # This would contain actual cost calculation logic
        # For now, return mock data
        return {
            "total_cost": 15.50,
            "per_serving": 3.10,
            "ingredient_costs": {
                "flour": 2.50,
                "eggs": 3.00,
                "milk": 1.50,
                # etc.
            },
            "portion_size": portion_size or 1.0
        }


# Example usage in routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db

router = APIRouter()

@router.get("/menu/items/{item_id}")
async def get_menu_item(
    item_id: int,
    include_recipe: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = CachedMenuService(db, tenant_id=current_user.tenant_id)
    return await service.get_menu_item(item_id, include_recipe)
    
@router.get("/menu/full")
async def get_full_menu(
    include_unavailable: bool = False,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = CachedMenuService(db, tenant_id=current_user.tenant_id)
    return await service.get_full_menu(include_unavailable, category_id)
"""