from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..schemas.pos_schemas import SyncResponse


class BasePOSAdapter(ABC):
    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials

    @abstractmethod
    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        """Push order data to POS system"""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if credentials are valid and connection works"""
        pass

    @abstractmethod
    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Transform internal order format to POS-specific format"""
        pass

    @abstractmethod
    async def get_vendor_orders(
        self, since_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Pull orders from POS system, optionally filtered by timestamp"""
        pass

    # Menu synchronization methods
    @abstractmethod
    async def get_menu_categories(
        self, since_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get menu categories from POS system"""
        pass

    @abstractmethod
    async def get_menu_items(
        self, since_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get menu items from POS system"""
        pass

    @abstractmethod
    async def get_modifier_groups(
        self, since_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get modifier groups from POS system"""
        pass

    @abstractmethod
    async def get_modifiers(self, modifier_group_id: str) -> List[Dict[str, Any]]:
        """Get modifiers for a specific modifier group"""
        pass

    @abstractmethod
    async def create_menu_category(
        self, category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new menu category in POS system"""
        pass

    @abstractmethod
    async def update_menu_category(
        self, category_id: str, category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing menu category in POS system"""
        pass

    @abstractmethod
    async def delete_menu_category(self, category_id: str) -> bool:
        """Delete a menu category from POS system"""
        pass

    @abstractmethod
    async def create_menu_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new menu item in POS system"""
        pass

    @abstractmethod
    async def update_menu_item(
        self, item_id: str, item_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing menu item in POS system"""
        pass

    @abstractmethod
    async def delete_menu_item(self, item_id: str) -> bool:
        """Delete a menu item from POS system"""
        pass

    @abstractmethod
    async def create_modifier_group(
        self, modifier_group_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new modifier group in POS system"""
        pass

    @abstractmethod
    async def update_modifier_group(
        self, modifier_group_id: str, modifier_group_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing modifier group in POS system"""
        pass

    @abstractmethod
    async def delete_modifier_group(self, modifier_group_id: str) -> bool:
        """Delete a modifier group from POS system"""
        pass

    @abstractmethod
    async def create_modifier(
        self, modifier_group_id: str, modifier_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new modifier in POS system"""
        pass

    @abstractmethod
    async def update_modifier(
        self, modifier_id: str, modifier_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing modifier in POS system"""
        pass

    @abstractmethod
    async def delete_modifier(self, modifier_id: str) -> bool:
        """Delete a modifier from POS system"""
        pass

    def transform_category_to_pos(
        self, category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform AuraConnect category format to POS-specific format"""
        # Default implementation - can be overridden by specific adapters
        return {
            "name": category_data.get("name", ""),
            "description": category_data.get("description", ""),
            "display_order": category_data.get("display_order", 0),
            "is_active": category_data.get("is_active", True),
        }

    def transform_item_to_pos(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform AuraConnect item format to POS-specific format"""
        # Default implementation - can be overridden by specific adapters
        return {
            "name": item_data.get("name", ""),
            "description": item_data.get("description", ""),
            "price": item_data.get("price", 0.0),
            "category_id": item_data.get("category_id"),
            "sku": item_data.get("sku", ""),
            "is_active": item_data.get("is_active", True),
            "is_available": item_data.get("is_available", True),
        }

    def transform_modifier_group_to_pos(
        self, modifier_group_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform AuraConnect modifier group format to POS-specific format"""
        # Default implementation - can be overridden by specific adapters
        return {
            "name": modifier_group_data.get("name", ""),
            "description": modifier_group_data.get("description", ""),
            "selection_type": modifier_group_data.get("selection_type", "single"),
            "min_selections": modifier_group_data.get("min_selections", 0),
            "max_selections": modifier_group_data.get("max_selections"),
            "is_required": modifier_group_data.get("is_required", False),
        }

    def transform_modifier_to_pos(
        self, modifier_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform AuraConnect modifier format to POS-specific format"""
        # Default implementation - can be overridden by specific adapters
        return {
            "name": modifier_data.get("name", ""),
            "description": modifier_data.get("description", ""),
            "price_adjustment": modifier_data.get("price_adjustment", 0.0),
            "price_type": modifier_data.get("price_type", "fixed"),
            "is_active": modifier_data.get("is_active", True),
            "is_available": modifier_data.get("is_available", True),
        }

    def transform_category_from_pos(
        self, pos_category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform POS category format to AuraConnect format"""
        # Default implementation - should be overridden by specific adapters
        return pos_category_data

    def transform_item_from_pos(self, pos_item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform POS item format to AuraConnect format"""
        # Default implementation - should be overridden by specific adapters
        return pos_item_data

    def transform_modifier_group_from_pos(
        self, pos_modifier_group_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform POS modifier group format to AuraConnect format"""
        # Default implementation - should be overridden by specific adapters
        return pos_modifier_group_data

    def transform_modifier_from_pos(
        self, pos_modifier_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform POS modifier format to AuraConnect format"""
        # Default implementation - should be overridden by specific adapters
        return pos_modifier_data
