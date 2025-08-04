# backend/tests/factories/order.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute, SubFactory
import random
from datetime import datetime
from .base import BaseFactory
from .auth import UserFactory
from .menu import MenuItemFactory
from modules.orders.models.order_models import Order, OrderItem, OrderStatus


class OrderFactory(BaseFactory):
    """Factory for creating orders."""
    
    class Meta:
        model = Order
    
    id = Sequence(lambda n: n + 1)
    order_number = LazyFunction(lambda: f"ORD-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}")
    
    # Status
    status = OrderStatus.PENDING
    
    # Financial
    subtotal = LazyFunction(lambda: round(random.uniform(10.0, 100.0), 2))
    tax_amount = LazyAttribute(lambda obj: round(obj.subtotal * 0.08, 2))  # 8% tax
    discount_amount = 0.0
    total_amount = LazyAttribute(lambda obj: obj.subtotal + obj.tax_amount - obj.discount_amount)
    
    # Table/location
    table_no = LazyFunction(lambda: random.randint(1, 20))
    
    # User tracking
    created_by_user = SubFactory(UserFactory)
    created_by = LazyAttribute(lambda obj: obj.created_by_user.id)
    staff_id = LazyAttribute(lambda obj: obj.created_by)
    
    # Customer info (optional)
    customer_name = Faker("name")
    customer_phone = Faker("phone_number")
    customer_email = Faker("email")
    
    # Notes
    notes = None
    special_instructions = None


class OrderItemFactory(BaseFactory):
    """Factory for creating order items."""
    
    class Meta:
        model = OrderItem
    
    id = Sequence(lambda n: n + 1)
    
    # Relationships
    order = SubFactory(OrderFactory)
    order_id = LazyAttribute(lambda obj: obj.order.id)
    menu_item = SubFactory(MenuItemFactory)
    menu_item_id = LazyAttribute(lambda obj: obj.menu_item.id)
    
    # Quantity and pricing
    quantity = LazyFunction(lambda: random.randint(1, 5))
    price = LazyAttribute(lambda obj: obj.menu_item.price if obj.menu_item else 10.0)
    subtotal = LazyAttribute(lambda obj: obj.price * obj.quantity)
    
    # Status
    status = "pending"
    
    # Notes
    notes = None
    special_instructions = None
    
    # Display
    display_order = Sequence(lambda n: n)


class OrderWithItemsFactory(OrderFactory):
    """Factory for creating orders with items."""
    
    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # Use provided items
            for item_data in extracted:
                if isinstance(item_data, dict):
                    OrderItemFactory(
                        order=self,
                        **item_data
                    )
                else:
                    # Assume it's a menu item
                    OrderItemFactory(
                        order=self,
                        menu_item=item_data
                    )
        else:
            # Create 1-3 random items
            num_items = random.randint(1, 3)
            for i in range(num_items):
                OrderItemFactory(
                    order=self,
                    display_order=i
                )
        
        # Update order totals based on items
        if hasattr(self, 'order_items') and self.order_items:
            subtotal = sum(item.subtotal for item in self.order_items)
            self.subtotal = subtotal
            self.tax_amount = round(subtotal * 0.08, 2)
            self.total_amount = self.subtotal + self.tax_amount - self.discount_amount