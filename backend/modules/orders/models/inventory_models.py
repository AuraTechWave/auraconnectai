# NOTE: The Inventory model has been moved to core.inventory_models
# to avoid duplicate table definitions. 
# Please import from core.inventory_models instead:
# from core.inventory_models import Inventory


# NOTE: MenuItemInventory is defined in core.menu_models to avoid duplicate table definitions
# class MenuItemInventory(Base, TimestampMixin):
#     __tablename__ = "menu_item_inventory"
#
#     id = Column(Integer, primary_key=True, index=True)
#     menu_item_id = Column(Integer, nullable=False, index=True)
#     inventory_id = Column(Integer, ForeignKey("inventory.id"),
#                           nullable=False, index=True)
#     quantity_needed = Column(Float, nullable=False)
#
#     inventory_item = relationship("Inventory", back_populates="menu_mappings")
