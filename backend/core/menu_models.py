# backend/core/menu_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Float, Text, Boolean, JSON)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from core.mixins import TimestampMixin
import uuid


class MenuCategory(Base, TimestampMixin):
    """Menu categories for organizing menu items"""
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    parent_category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=True)
    image_url = Column(String(500), nullable=True)
    created_by = Column(Integer, nullable=True)  # User ID who created this
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    parent_category = relationship("MenuCategory", remote_side=[id])
    subcategories = relationship("MenuCategory", back_populates="parent_category")
    menu_items = relationship("MenuItem", back_populates="category")

    def __repr__(self):
        return f"<MenuCategory(id={self.id}, name='{self.name}')>"


class MenuItem(Base, TimestampMixin):
    """Individual menu items"""
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False)
    sku = Column(String(50), nullable=True, unique=True, index=True)
    
    # Status and availability
    is_active = Column(Boolean, nullable=False, default=True)
    is_available = Column(Boolean, nullable=False, default=True)
    availability_start_time = Column(String(8), nullable=True)  # HH:MM:SS format
    availability_end_time = Column(String(8), nullable=True)    # HH:MM:SS format
    
    # Nutritional and dietary info
    calories = Column(Integer, nullable=True)
    allergens = Column(JSON, nullable=True)  # List of allergens
    dietary_tags = Column(JSON, nullable=True)  # vegetarian, vegan, gluten-free, etc.
    
    # Preparation and serving
    prep_time_minutes = Column(Integer, nullable=True)
    serving_size = Column(String(50), nullable=True)
    
    # Media
    image_url = Column(String(500), nullable=True)
    images = Column(JSON, nullable=True)  # Multiple images
    
    # Metadata
    display_order = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    category = relationship("MenuCategory", back_populates="menu_items")
    modifiers = relationship("MenuItemModifier", back_populates="menu_item")
    inventory_mappings = relationship("MenuItemInventory", back_populates="menu_item")

    def __repr__(self):
        return f"<MenuItem(id={self.id}, name='{self.name}', price={self.price})>"


class ModifierGroup(Base, TimestampMixin):
    """Groups of modifiers (e.g., 'Size', 'Toppings', 'Spice Level')"""
    __tablename__ = "modifier_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Selection rules
    selection_type = Column(String(20), nullable=False, default="single")  # single, multiple
    min_selections = Column(Integer, nullable=False, default=0)
    max_selections = Column(Integer, nullable=True)  # None = unlimited
    is_required = Column(Boolean, nullable=False, default=False)
    
    # Display
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    modifiers = relationship("Modifier", back_populates="modifier_group")
    menu_item_modifiers = relationship("MenuItemModifier", back_populates="modifier_group")

    def __repr__(self):
        return f"<ModifierGroup(id={self.id}, name='{self.name}')>"


class Modifier(Base, TimestampMixin):
    """Individual modifier options within a group"""
    __tablename__ = "modifiers"

    id = Column(Integer, primary_key=True, index=True)
    modifier_group_id = Column(Integer, ForeignKey("modifier_groups.id"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Pricing
    price_adjustment = Column(Float, nullable=False, default=0.0)  # Can be negative
    price_type = Column(String(20), nullable=False, default="fixed")  # fixed, percentage
    
    # Availability
    is_active = Column(Boolean, nullable=False, default=True)
    is_available = Column(Boolean, nullable=False, default=True)
    
    # Display
    display_order = Column(Integer, nullable=False, default=0)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    modifier_group = relationship("ModifierGroup", back_populates="modifiers")

    def __repr__(self):
        return f"<Modifier(id={self.id}, name='{self.name}', price_adjustment={self.price_adjustment})>"


class MenuItemModifier(Base, TimestampMixin):
    """Many-to-many relationship between menu items and modifier groups"""
    __tablename__ = "menu_item_modifiers"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    modifier_group_id = Column(Integer, ForeignKey("modifier_groups.id"), nullable=False)
    
    # Override settings for this specific menu item
    is_required = Column(Boolean, nullable=True)  # Override group setting
    min_selections = Column(Integer, nullable=True)  # Override group setting
    max_selections = Column(Integer, nullable=True)  # Override group setting
    display_order = Column(Integer, nullable=False, default=0)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    menu_item = relationship("MenuItem", back_populates="modifiers")
    modifier_group = relationship("ModifierGroup", back_populates="menu_item_modifiers")

    def __repr__(self):
        return f"<MenuItemModifier(menu_item_id={self.menu_item_id}, modifier_group_id={self.modifier_group_id})>"


class MenuItemInventory(Base, TimestampMixin):
    """Relationship between menu items and inventory items for tracking usage"""
    __tablename__ = "menu_item_inventory"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    quantity_needed = Column(Float, nullable=False)  # How much inventory is used per menu item
    unit = Column(String(20), nullable=True)  # Unit of measurement
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    menu_item = relationship("MenuItem", back_populates="inventory_mappings")
    inventory_item = relationship("Inventory", back_populates="menu_mappings")

    def __repr__(self):
        return f"<MenuItemInventory(menu_item_id={self.menu_item_id}, inventory_id={self.inventory_id}, quantity={self.quantity_needed})>"


# NOTE: The Inventory model has been moved to core.inventory_models to avoid duplicate table definitions
# Please import from core.inventory_models instead:
# from core.inventory_models import Inventory

    def __repr__(self):
        return f"<Inventory(id={self.id}, item_name='{self.item_name}', quantity={self.quantity})>"