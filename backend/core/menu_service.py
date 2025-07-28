# backend/core/menu_service.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func, text
from fastapi import HTTPException, status
from datetime import datetime

from .menu_versioning_triggers import create_manual_version_on_bulk_change

from .menu_models import (
    MenuCategory, MenuItem, ModifierGroup, Modifier, 
    MenuItemModifier, MenuItemInventory, Inventory
)
from .menu_schemas import (
    MenuCategoryCreate, MenuCategoryUpdate, MenuItemCreate, MenuItemUpdate,
    ModifierGroupCreate, ModifierGroupUpdate, ModifierCreate, ModifierUpdate,
    MenuItemModifierCreate, MenuItemModifierUpdate, InventoryCreate, InventoryUpdate,
    MenuItemInventoryCreate, MenuItemInventoryUpdate, MenuSearchParams, InventorySearchParams
)


class MenuService:
    """Service class for menu management operations"""

    def __init__(self, db: Session):
        self.db = db

    # Menu Category operations
    def create_category(self, category_data: MenuCategoryCreate, user_id: int = None) -> MenuCategory:
        """Create a new menu category"""
        # Check if parent category exists if specified
        if category_data.parent_category_id:
            parent = self.get_category_by_id(category_data.parent_category_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent category not found"
                )

        category = MenuCategory(
            **category_data.dict(),
            created_by=user_id
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def get_categories(self, active_only: bool = True) -> List[MenuCategory]:
        """Get all menu categories"""
        query = self.db.query(MenuCategory).filter(MenuCategory.deleted_at.is_(None))
        
        if active_only:
            query = query.filter(MenuCategory.is_active == True)
        
        return query.order_by(MenuCategory.display_order, MenuCategory.name).all()

    def get_category_by_id(self, category_id: int) -> Optional[MenuCategory]:
        """Get category by ID"""
        return self.db.query(MenuCategory).filter(
            MenuCategory.id == category_id,
            MenuCategory.deleted_at.is_(None)
        ).first()

    def update_category(self, category_id: int, category_data: MenuCategoryUpdate, user_id: int = None) -> MenuCategory:
        """Update a menu category"""
        category = self.get_category_by_id(category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        # Check if parent category exists if specified
        if category_data.parent_category_id and category_data.parent_category_id != category_id:
            parent = self.get_category_by_id(category_data.parent_category_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent category not found"
                )

        update_data = category_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(category, key, value)

        self.db.commit()
        self.db.refresh(category)
        return category

    def delete_category(self, category_id: int, user_id: int = None) -> bool:
        """Soft delete a menu category"""
        category = self.get_category_by_id(category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        # Check if category has menu items
        items_count = self.db.query(MenuItem).filter(
            MenuItem.category_id == category_id,
            MenuItem.deleted_at.is_(None)
        ).count()

        if items_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete category with menu items. Move or delete items first."
            )

        category.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    # Menu Item operations
    def create_menu_item(self, item_data: MenuItemCreate, user_id: int = None) -> MenuItem:
        """Create a new menu item"""
        # Verify category exists
        category = self.get_category_by_id(item_data.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        # Check SKU uniqueness if provided
        if item_data.sku:
            existing_item = self.db.query(MenuItem).filter(
                MenuItem.sku == item_data.sku,
                MenuItem.deleted_at.is_(None)
            ).first()
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SKU already exists"
                )

        menu_item = MenuItem(
            **item_data.dict(),
            created_by=user_id
        )
        self.db.add(menu_item)
        self.db.commit()
        self.db.refresh(menu_item)
        return menu_item

    def get_menu_items(self, params: MenuSearchParams) -> Tuple[List[MenuItem], int]:
        """Get menu items with search and pagination"""
        query = self.db.query(MenuItem).filter(MenuItem.deleted_at.is_(None))

        # Apply filters
        if params.query:
            search_term = f"%{params.query}%"
            query = query.filter(
                or_(
                    MenuItem.name.ilike(search_term),
                    MenuItem.description.ilike(search_term),
                    MenuItem.sku.ilike(search_term)
                )
            )

        if params.category_id:
            query = query.filter(MenuItem.category_id == params.category_id)

        if params.is_active is not None:
            query = query.filter(MenuItem.is_active == params.is_active)

        if params.is_available is not None:
            query = query.filter(MenuItem.is_available == params.is_available)

        if params.min_price is not None:
            query = query.filter(MenuItem.price >= params.min_price)

        if params.max_price is not None:
            query = query.filter(MenuItem.price <= params.max_price)

        if params.dietary_tags:
            for tag in params.dietary_tags:
                query = query.filter(MenuItem.dietary_tags.contains([tag]))

        if params.allergens:
            for allergen in params.allergens:
                query = query.filter(~MenuItem.allergens.contains([allergen]))

        # Count total before pagination
        total = query.count()

        # Apply sorting
        sort_column = getattr(MenuItem, params.sort_by, MenuItem.display_order)
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        items = query.offset(params.offset).limit(params.limit).all()

        return items, total

    def get_menu_item_by_id(self, item_id: int) -> Optional[MenuItem]:
        """Get menu item by ID"""
        return self.db.query(MenuItem).filter(
            MenuItem.id == item_id,
            MenuItem.deleted_at.is_(None)
        ).first()

    def update_menu_item(self, item_id: int, item_data: MenuItemUpdate, user_id: int = None) -> MenuItem:
        """Update a menu item"""
        menu_item = self.get_menu_item_by_id(item_id)
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Verify category exists if being updated
        if item_data.category_id:
            category = self.get_category_by_id(item_data.category_id)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Category not found"
                )

        # Check SKU uniqueness if being updated
        if item_data.sku and item_data.sku != menu_item.sku:
            existing_item = self.db.query(MenuItem).filter(
                MenuItem.sku == item_data.sku,
                MenuItem.id != item_id,
                MenuItem.deleted_at.is_(None)
            ).first()
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SKU already exists"
                )

        update_data = item_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(menu_item, key, value)

        self.db.commit()
        self.db.refresh(menu_item)
        return menu_item

    def delete_menu_item(self, item_id: int, user_id: int = None) -> bool:
        """Soft delete a menu item"""
        menu_item = self.get_menu_item_by_id(item_id)
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        menu_item.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    # Modifier Group operations
    def create_modifier_group(self, group_data: ModifierGroupCreate, user_id: int = None) -> ModifierGroup:
        """Create a new modifier group"""
        modifier_group = ModifierGroup(
            **group_data.dict(),
            created_by=user_id
        )
        self.db.add(modifier_group)
        self.db.commit()
        self.db.refresh(modifier_group)
        return modifier_group

    def get_modifier_groups(self, active_only: bool = True) -> List[ModifierGroup]:
        """Get all modifier groups"""
        query = self.db.query(ModifierGroup).filter(ModifierGroup.deleted_at.is_(None))
        
        if active_only:
            query = query.filter(ModifierGroup.is_active == True)
        
        return query.order_by(ModifierGroup.display_order, ModifierGroup.name).all()

    def get_modifier_group_by_id(self, group_id: int) -> Optional[ModifierGroup]:
        """Get modifier group by ID"""
        return self.db.query(ModifierGroup).filter(
            ModifierGroup.id == group_id,
            ModifierGroup.deleted_at.is_(None)
        ).first()

    def update_modifier_group(self, group_id: int, group_data: ModifierGroupUpdate, user_id: int = None) -> ModifierGroup:
        """Update a modifier group"""
        modifier_group = self.get_modifier_group_by_id(group_id)
        if not modifier_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier group not found"
            )

        update_data = group_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(modifier_group, key, value)

        self.db.commit()
        self.db.refresh(modifier_group)
        return modifier_group

    def delete_modifier_group(self, group_id: int, user_id: int = None) -> bool:
        """Soft delete a modifier group"""
        modifier_group = self.get_modifier_group_by_id(group_id)
        if not modifier_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier group not found"
            )

        # Check if group has modifiers
        modifiers_count = self.db.query(Modifier).filter(
            Modifier.modifier_group_id == group_id,
            Modifier.deleted_at.is_(None)
        ).count()

        if modifiers_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete modifier group with modifiers. Delete modifiers first."
            )

        modifier_group.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    # Modifier operations
    def create_modifier(self, modifier_data: ModifierCreate, user_id: int = None) -> Modifier:
        """Create a new modifier"""
        # Verify modifier group exists
        group = self.get_modifier_group_by_id(modifier_data.modifier_group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier group not found"
            )

        modifier = Modifier(
            **modifier_data.dict(),
            created_by=user_id
        )
        self.db.add(modifier)
        self.db.commit()
        self.db.refresh(modifier)
        return modifier

    def get_modifiers_by_group(self, group_id: int, active_only: bool = True) -> List[Modifier]:
        """Get modifiers by group ID"""
        query = self.db.query(Modifier).filter(
            Modifier.modifier_group_id == group_id,
            Modifier.deleted_at.is_(None)
        )
        
        if active_only:
            query = query.filter(Modifier.is_active == True)
        
        return query.order_by(Modifier.display_order, Modifier.name).all()

    def get_modifier_by_id(self, modifier_id: int) -> Optional[Modifier]:
        """Get modifier by ID"""
        return self.db.query(Modifier).filter(
            Modifier.id == modifier_id,
            Modifier.deleted_at.is_(None)
        ).first()

    def update_modifier(self, modifier_id: int, modifier_data: ModifierUpdate, user_id: int = None) -> Modifier:
        """Update a modifier"""
        modifier = self.get_modifier_by_id(modifier_id)
        if not modifier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier not found"
            )

        # Verify modifier group exists if being updated
        if modifier_data.modifier_group_id:
            group = self.get_modifier_group_by_id(modifier_data.modifier_group_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Modifier group not found"
                )

        update_data = modifier_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(modifier, key, value)

        self.db.commit()
        self.db.refresh(modifier)
        return modifier

    def delete_modifier(self, modifier_id: int, user_id: int = None) -> bool:
        """Soft delete a modifier"""
        modifier = self.get_modifier_by_id(modifier_id)
        if not modifier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier not found"
            )

        modifier.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    # Menu Item Modifier operations
    def add_modifier_to_item(self, link_data: MenuItemModifierCreate, user_id: int = None) -> MenuItemModifier:
        """Add a modifier group to a menu item"""
        # Verify menu item exists
        menu_item = self.get_menu_item_by_id(link_data.menu_item_id)
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Verify modifier group exists
        modifier_group = self.get_modifier_group_by_id(link_data.modifier_group_id)
        if not modifier_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier group not found"
            )

        # Check if link already exists
        existing_link = self.db.query(MenuItemModifier).filter(
            MenuItemModifier.menu_item_id == link_data.menu_item_id,
            MenuItemModifier.modifier_group_id == link_data.modifier_group_id,
            MenuItemModifier.deleted_at.is_(None)
        ).first()

        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Modifier group already linked to this menu item"
            )

        menu_item_modifier = MenuItemModifier(
            **link_data.dict(),
            created_by=user_id
        )
        self.db.add(menu_item_modifier)
        self.db.commit()
        self.db.refresh(menu_item_modifier)
        return menu_item_modifier

    def get_item_modifiers(self, menu_item_id: int) -> List[MenuItemModifier]:
        """Get all modifier groups for a menu item"""
        return self.db.query(MenuItemModifier).filter(
            MenuItemModifier.menu_item_id == menu_item_id,
            MenuItemModifier.deleted_at.is_(None)
        ).order_by(MenuItemModifier.display_order).all()

    def remove_modifier_from_item(self, menu_item_id: int, modifier_group_id: int, user_id: int = None) -> bool:
        """Remove a modifier group from a menu item"""
        link = self.db.query(MenuItemModifier).filter(
            MenuItemModifier.menu_item_id == menu_item_id,
            MenuItemModifier.modifier_group_id == modifier_group_id,
            MenuItemModifier.deleted_at.is_(None)
        ).first()

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Modifier group not linked to this menu item"
            )

        link.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    # Menu Item Inventory operations
    def add_inventory_to_item(self, link_data: MenuItemInventoryCreate, user_id: int = None) -> MenuItemInventory:
        """Link an inventory item to a menu item"""
        # Verify menu item exists
        menu_item = self.get_menu_item_by_id(link_data.menu_item_id)
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Verify inventory item exists
        inventory_item = self.get_inventory_by_id(link_data.inventory_id)
        if not inventory_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found"
            )

        # Check if link already exists
        existing_link = self.db.query(MenuItemInventory).filter(
            MenuItemInventory.menu_item_id == link_data.menu_item_id,
            MenuItemInventory.inventory_id == link_data.inventory_id,
            MenuItemInventory.deleted_at.is_(None)
        ).first()

        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inventory item already linked to this menu item"
            )

        menu_item_inventory = MenuItemInventory(
            **link_data.dict(),
            created_by=user_id
        )
        self.db.add(menu_item_inventory)
        self.db.commit()
        self.db.refresh(menu_item_inventory)
        return menu_item_inventory

    # Inventory operations
    def get_inventory(self, params: InventorySearchParams) -> Tuple[List[Inventory], int]:
        """Get inventory items with search and pagination"""
        query = self.db.query(Inventory).filter(Inventory.deleted_at.is_(None))

        # Apply filters
        if params.query:
            search_term = f"%{params.query}%"
            query = query.filter(
                or_(
                    Inventory.item_name.ilike(search_term),
                    Inventory.description.ilike(search_term),
                    Inventory.sku.ilike(search_term)
                )
            )

        if params.low_stock:
            query = query.filter(Inventory.quantity <= Inventory.threshold)

        if params.is_active is not None:
            query = query.filter(Inventory.is_active == params.is_active)

        if params.vendor_id:
            query = query.filter(Inventory.vendor_id == params.vendor_id)

        # Count total before pagination
        total = query.count()

        # Apply sorting
        sort_column = getattr(Inventory, params.sort_by, Inventory.item_name)
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        items = query.offset(params.offset).limit(params.limit).all()

        return items, total

    def get_inventory_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """Get inventory item by ID"""
        return self.db.query(Inventory).filter(
            Inventory.id == inventory_id,
            Inventory.deleted_at.is_(None)
        ).first()

    def get_low_stock_items(self) -> List[Inventory]:
        """Get items that are below their reorder threshold"""
        return self.db.query(Inventory).filter(
            Inventory.quantity <= Inventory.threshold,
            Inventory.is_active == True,
            Inventory.deleted_at.is_(None)
        ).order_by(Inventory.item_name).all()

    # Bulk operations
    def bulk_update_items(self, item_ids: List[int], updates: MenuItemUpdate, user_id: int = None) -> List[MenuItem]:
        """Bulk update menu items"""
        items = self.db.query(MenuItem).filter(
            MenuItem.id.in_(item_ids),
            MenuItem.deleted_at.is_(None)
        ).all()

        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No menu items found"
            )

        update_data = updates.dict(exclude_unset=True)
        for item in items:
            for key, value in update_data.items():
                setattr(item, key, value)

        self.db.commit()
        for item in items:
            self.db.refresh(item)

        return items

    # Analytics and reporting
    def get_menu_stats(self) -> Dict[str, Any]:
        """Get menu statistics"""
        total_categories = self.db.query(MenuCategory).filter(
            MenuCategory.deleted_at.is_(None),
            MenuCategory.is_active == True
        ).count()

        total_items = self.db.query(MenuItem).filter(
            MenuItem.deleted_at.is_(None),
            MenuItem.is_active == True
        ).count()

        available_items = self.db.query(MenuItem).filter(
            MenuItem.deleted_at.is_(None),
            MenuItem.is_active == True,
            MenuItem.is_available == True
        ).count()

        total_modifiers = self.db.query(Modifier).filter(
            Modifier.deleted_at.is_(None),
            Modifier.is_active == True
        ).count()

        return {
            "total_categories": total_categories,
            "total_items": total_items,
            "available_items": available_items,
            "unavailable_items": total_items - available_items,
            "total_modifiers": total_modifiers
        }

    # Bulk operations with versioning integration
    def bulk_update_items(self, item_ids: List[int], updates: Dict[str, Any], user_id: int = None) -> Dict[str, Any]:
        """Bulk update multiple menu items and create version if needed"""
        
        items = self.db.query(MenuItem).filter(
            MenuItem.id.in_(item_ids),
            MenuItem.deleted_at.is_(None)
        ).all()
        
        if not items:
            return {"updated": 0, "errors": ["No items found"]}
        
        updated_count = 0
        errors = []
        
        for item in items:
            try:
                # Track price changes for versioning
                if 'price' in updates and updates['price'] != item.price:
                    item._price_changed = True
                
                # Track availability changes for versioning
                if 'is_available' in updates and updates['is_available'] != item.is_available:
                    item._availability_changed = True
                
                # Apply updates
                for field, value in updates.items():
                    if hasattr(item, field):
                        setattr(item, field, value)
                
                updated_count += 1
                
            except Exception as e:
                errors.append(f"Item {item.id}: {str(e)}")
        
        if updated_count > 0:
            self.db.commit()
            
            # Create version for significant bulk changes
            version_id = create_manual_version_on_bulk_change(
                self.db, 
                "bulk_update_items", 
                updated_count, 
                user_id or 1
            )
            
            return {
                "updated": updated_count,
                "errors": errors,
                "version_created": version_id is not None,
                "version_id": version_id
            }
        
        return {"updated": 0, "errors": errors}
    
    def bulk_activate_items(self, item_ids: List[int], active: bool, user_id: int = None) -> Dict[str, Any]:
        """Bulk activate/deactivate menu items"""
        
        result = self.bulk_update_items(item_ids, {"is_active": active}, user_id)
        
        # Create version for bulk activation changes
        if result["updated"] > 0:
            version_id = create_manual_version_on_bulk_change(
                self.db,
                f"bulk_{'activate' if active else 'deactivate'}_items",
                result["updated"],
                user_id or 1
            )
            
            result["version_created"] = version_id is not None
            result["version_id"] = version_id
        
        return result
    
    def bulk_update_prices(self, price_updates: List[Dict[str, Any]], user_id: int = None) -> Dict[str, Any]:
        """Bulk update item prices - this always creates a version due to criticality"""
        
        updated_count = 0
        errors = []
        
        for update in price_updates:
            try:
                item_id = update.get('item_id')
                new_price = update.get('price')
                
                if not item_id or new_price is None:
                    errors.append("Missing item_id or price in update")
                    continue
                
                item = self.get_menu_item_by_id(item_id)
                if not item:
                    errors.append(f"Item {item_id} not found")
                    continue
                
                # Track for versioning
                item._price_changed = True
                item.price = new_price
                updated_count += 1
                
            except Exception as e:
                errors.append(f"Error updating item {update.get('item_id', 'unknown')}: {str(e)}")
        
        if updated_count > 0:
            self.db.commit()
            
            # Always create version for price changes
            version_id = create_manual_version_on_bulk_change(
                self.db,
                "bulk_price_update",
                updated_count,
                user_id or 1
            )
            
            return {
                "updated": updated_count,
                "errors": errors,
                "version_created": True,  # Always true for price changes
                "version_id": version_id
            }
        
        return {"updated": 0, "errors": errors}
    
    def bulk_delete_items(self, item_ids: List[int], user_id: int = None) -> Dict[str, Any]:
        """Bulk soft-delete menu items"""
        
        items = self.db.query(MenuItem).filter(
            MenuItem.id.in_(item_ids),
            MenuItem.deleted_at.is_(None)
        ).all()
        
        if not items:
            return {"deleted": 0, "errors": ["No items found"]}
        
        deleted_count = len(items)
        
        # Soft delete all items
        for item in items:
            item.deleted_at = datetime.utcnow()
        
        self.db.commit()
        
        # Create version for bulk deletions
        version_id = create_manual_version_on_bulk_change(
            self.db,
            "bulk_delete_items",
            deleted_count,
            user_id or 1
        )
        
        return {
            "deleted": deleted_count,
            "errors": [],
            "version_created": version_id is not None,
            "version_id": version_id
        }