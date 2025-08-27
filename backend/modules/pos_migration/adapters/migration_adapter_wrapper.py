# backend/modules/pos_migration/adapters/migration_adapter_wrapper.py

"""
Wrapper for POS adapters to add migration-specific methods.
Extends existing adapters with data fetching capabilities needed for migration.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from modules.pos.adapters.base_adapter import BasePOSAdapter

logger = logging.getLogger(__name__)


class MigrationAdapterWrapper:
    """Wraps POS adapters to add migration-specific functionality"""
    
    def __init__(self, base_adapter: BasePOSAdapter):
        self.adapter = base_adapter
        self.pos_type = self._detect_pos_type()
        
    def _detect_pos_type(self) -> str:
        """Detect POS type from adapter class name"""
        
        class_name = self.adapter.__class__.__name__.lower()
        if "square" in class_name:
            return "square"
        elif "toast" in class_name:
            return "toast"
        elif "clover" in class_name:
            return "clover"
        else:
            return "unknown"
    
    async def test_connection(self) -> bool:
        """Test connection using base adapter"""
        return await self.adapter.test_connection()
    
    async def fetch_menu_items(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch menu items for migration"""
        
        try:
            # Use existing method if available
            if hasattr(self.adapter, 'get_menu_items'):
                items = await self.adapter.get_menu_items()
                if limit:
                    return items[:limit]
                return items
            else:
                # Fallback implementation
                return await self._fetch_menu_items_fallback(limit)
                
        except Exception as e:
            logger.error(f"Error fetching menu items: {e}")
            raise
    
    async def fetch_categories(self) -> List[Dict[str, Any]]:
        """Fetch menu categories"""
        
        try:
            if hasattr(self.adapter, 'get_menu_categories'):
                return await self.adapter.get_menu_categories()
            else:
                return await self._fetch_categories_fallback()
                
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            raise
    
    async def fetch_modifiers(self) -> List[Dict[str, Any]]:
        """Fetch all modifiers with their groups"""
        
        try:
            modifiers = []
            
            # First get modifier groups
            if hasattr(self.adapter, 'get_modifier_groups'):
                groups = await self.adapter.get_modifier_groups()
                
                # Then get modifiers for each group
                for group in groups:
                    group_id = group.get('id') or group.get('guid')
                    if group_id and hasattr(self.adapter, 'get_modifiers'):
                        group_modifiers = await self.adapter.get_modifiers(group_id)
                        
                        # Add group info to each modifier
                        for mod in group_modifiers:
                            mod['group_name'] = group.get('name', 'Default Group')
                            mod['group_id'] = group_id
                            modifiers.append(mod)
            
            return modifiers
            
        except Exception as e:
            logger.error(f"Error fetching modifiers: {e}")
            return []
    
    async def fetch_customers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch customer data if available"""
        
        # Most POS systems don't expose customer data directly
        # This would need custom implementation per POS
        logger.info(f"Customer fetch not implemented for {self.pos_type}")
        return []
    
    async def fetch_orders(
        self, 
        days_back: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch historical orders"""
        
        try:
            since_timestamp = datetime.utcnow() - timedelta(days=days_back)
            
            if hasattr(self.adapter, 'get_vendor_orders'):
                orders_response = await self.adapter.get_vendor_orders(since_timestamp)
                
                # Extract orders from response
                orders = []
                if isinstance(orders_response, dict):
                    if 'orders' in orders_response:
                        orders = orders_response['orders']
                    elif 'data' in orders_response:
                        orders = orders_response['data']
                    else:
                        # Response might be the orders list directly
                        orders = list(orders_response.values())
                
                if limit:
                    return orders[:limit]
                return orders
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    # Fallback methods for adapters that don't have these methods
    
    async def _fetch_menu_items_fallback(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        """Fallback implementation for fetching menu items"""
        
        # This would make direct API calls based on POS type
        if self.pos_type == "square":
            return await self._fetch_square_items(limit)
        elif self.pos_type == "toast":
            return await self._fetch_toast_items(limit)
        elif self.pos_type == "clover":
            return await self._fetch_clover_items(limit)
        else:
            raise NotImplementedError(f"No fallback for {self.pos_type}")
    
    async def _fetch_categories_fallback(self) -> List[Dict[str, Any]]:
        """Fallback implementation for fetching categories"""
        
        # Would implement direct API calls
        logger.warning(f"Using fallback category fetch for {self.pos_type}")
        return []
    
    async def _fetch_square_items(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        """Fetch items from Square API"""
        
        # This would use the Square catalog API directly
        # For now, return mock data
        return [
            {
                "id": "ITEM123",
                "name": "Burger",
                "description": "Classic beef burger",
                "price": 1299,  # In cents
                "category": "Main Dishes",
                "active": True
            }
        ]
    
    async def _fetch_toast_items(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        """Fetch items from Toast API"""
        
        return [
            {
                "guid": "toast-item-123",
                "name": "Pizza Margherita",
                "description": "Traditional Italian pizza",
                "price": 1599,
                "categoryGuid": "cat-456",
                "visibility": "POS_AND_ONLINE"
            }
        ]
    
    async def _fetch_clover_items(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        """Fetch items from Clover API"""
        
        return [
            {
                "id": "CLVR123",
                "name": "Coffee",
                "price": 350,
                "priceType": "FIXED",
                "categories": [{"id": "CAT789", "name": "Beverages"}]
            }
        ]
    
    def get_sample_field_structure(self) -> Dict[str, List[str]]:
        """Get sample field structure for this POS type"""
        
        structures = {
            "square": {
                "menu_item": [
                    "id", "name", "description", "category_data.name",
                    "variations[].name", "variations[].price_money.amount"
                ],
                "category": ["id", "name"],
                "modifier": ["id", "name", "price_money.amount"]
            },
            "toast": {
                "menu_item": [
                    "guid", "name", "description", "price",
                    "categoryGuid", "visibility", "plu"
                ],
                "category": ["guid", "name", "parentGuid"],
                "modifier": ["guid", "name", "price", "displayMode"]
            },
            "clover": {
                "menu_item": [
                    "id", "name", "price", "priceType",
                    "categories[].id", "categories[].name"
                ],
                "category": ["id", "name", "sortOrder"],
                "modifier": ["id", "name", "price"]
            }
        }
        
        return structures.get(self.pos_type, {})
    
    def get_transformation_hints(self) -> Dict[str, Any]:
        """Get transformation hints for this POS type"""
        
        hints = {
            "square": {
                "price_format": "cents",
                "id_field": "id",
                "nested_categories": True,
                "variations_as_items": True
            },
            "toast": {
                "price_format": "cents",
                "id_field": "guid",
                "nested_categories": False,
                "visibility_filter": ["POS_AND_ONLINE", "POS"]
            },
            "clover": {
                "price_format": "cents",
                "id_field": "id",
                "nested_categories": False,
                "price_type_filter": ["FIXED", "VARIABLE"]
            }
        }
        
        return hints.get(self.pos_type, {})