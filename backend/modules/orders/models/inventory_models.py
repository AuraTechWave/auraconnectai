from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text, Float)
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class Inventory(Base, TimestampMixin):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=False)
    threshold = Column(Float, nullable=False, default=0.0)
    vendor_id = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    menu_mappings = relationship("MenuItemInventory", back_populates="inventory_item")


class MenuItemInventory(Base, TimestampMixin):
    __tablename__ = "menu_item_inventory"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_id = Column(Integer, nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)
    quantity_needed = Column(Float, nullable=False)

    inventory_item = relationship("Inventory", back_populates="menu_mappings")
