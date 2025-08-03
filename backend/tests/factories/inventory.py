# backend/tests/factories/inventory.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute, SubFactory
from datetime import datetime
import random
from .base import BaseFactory
from .auth import UserFactory
from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType


class InventoryFactory(BaseFactory):
    """Factory for creating inventory items."""
    
    class Meta:
        model = Inventory
    
    id = Sequence(lambda n: n + 1)
    item_name = Faker("word")
    description = Faker("sentence")
    quantity = LazyFunction(lambda: round(random.uniform(10.0, 100.0), 2))
    unit = factory.Iterator(["kg", "liter", "piece", "dozen", "gram", "ml"])
    threshold = LazyAttribute(lambda obj: round(obj.quantity * 0.2, 2))  # 20% of quantity
    reorder_quantity = LazyAttribute(lambda obj: round(obj.quantity * 0.5, 2))
    cost_per_unit = LazyFunction(lambda: round(random.uniform(1.0, 20.0), 2))
    is_active = True
    created_by = LazyAttribute(lambda obj: UserFactory().id)


class InventoryAdjustmentFactory(BaseFactory):
    """Factory for creating inventory adjustments."""
    
    class Meta:
        model = InventoryAdjustment
    
    id = Sequence(lambda n: n + 1)
    inventory_id = SubFactory(InventoryFactory)
    adjustment_type = factory.Iterator([t.value for t in AdjustmentType])
    
    # Quantity changes
    quantity_before = LazyAttribute(lambda obj: obj.inventory_item.quantity if hasattr(obj, 'inventory_item') else 100.0)
    quantity_change = LazyFunction(lambda: round(random.uniform(-10.0, 10.0), 2))
    quantity_after = LazyAttribute(lambda obj: obj.quantity_before + obj.quantity_change)
    unit = LazyAttribute(lambda obj: obj.inventory_item.unit if hasattr(obj, 'inventory_item') else "unit")
    
    # Reference
    reference_type = factory.Iterator(["order", "manual", "waste", "delivery"])
    reference_id = Sequence(lambda n: str(n))
    
    # Details
    reason = Faker("sentence")
    notes = Faker("text", max_nb_chars=200)
    
    # User tracking
    performed_by = LazyAttribute(lambda obj: UserFactory().id)
    created_by = LazyAttribute(lambda obj: obj.performed_by)