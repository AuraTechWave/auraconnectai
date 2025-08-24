#!/usr/bin/env python3
"""
Seed test data for AuraConnect manual testing.

This script creates comprehensive test data for all modules.
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from core.config import settings

# Import all models
from core.rbac_models import RBACUser as User, RBACRole as Role, RBACPermission as Permission
from modules.staff.models import StaffProfile, Shift, Attendance
from modules.menu.models import MenuCategory, MenuItem, Modifier, ModifierGroup
from modules.menu.models.recipe_models import Recipe, RecipeIngredient
from modules.inventory.models import InventoryItem, Vendor, PurchaseOrder
from modules.customers.models import Customer
from modules.orders.models import Order, OrderItem
from modules.tables.models import Table, TableSection
from modules.settings.models import Setting, SettingDefinition, SettingGroup
from modules.loyalty.models import LoyaltyProgram, CustomerPoints

# Import services
from core.password_security import hash_password
from modules.menu.services.recipe_service import RecipeService


def create_test_users(db: Session):
    """Create test user accounts with different roles."""
    print("Creating test users...")
    
    # Create roles
    admin_role = Role(
        name="admin",
        display_name="Administrator",
        description="Full system access",
        is_active=True
    )
    
    manager_role = Role(
        name="manager",
        display_name="Manager",
        description="Restaurant management access",
        is_active=True
    )
    
    staff_role = Role(
        name="staff",
        display_name="Staff",
        description="Basic staff access",
        is_active=True
    )
    
    db.add_all([admin_role, manager_role, staff_role])
    db.commit()
    
    # Create permissions
    permissions_data = [
        ("system.admin", "Full system administration", "system", "admin"),
        ("staff.view", "View staff information", "staff", "view"),
        ("staff.manage", "Manage staff", "staff", "manage"),
        ("menu.view", "View menu", "menu", "view"),
        ("menu.manage", "Manage menu", "menu", "manage"),
        ("orders.view", "View orders", "orders", "view"),
        ("orders.manage", "Manage orders", "orders", "manage"),
        ("inventory.view", "View inventory", "inventory", "view"),
        ("inventory.manage", "Manage inventory", "inventory", "manage"),
        ("analytics.view", "View analytics", "analytics", "view"),
        ("settings.view", "View settings", "settings", "view"),
        ("settings.manage", "Manage settings", "settings", "manage"),
    ]
    
    permissions = []
    for key, name, resource, action in permissions_data:
        perm = Permission(
            key=key,
            name=name,
            description=name,
            resource=resource,
            action=action
        )
        permissions.append(perm)
        db.add(perm)
    
    db.commit()
    
    # Assign permissions to roles
    admin_role.permissions = permissions
    manager_role.permissions = [p for p in permissions if not p.key.startswith("system")]
    staff_role.permissions = [p for p in permissions if p.key.endswith(".view")]
    
    # Create users
    users = [
        {
            "username": "admin",
            "email": "admin@auraconnect.ai",
            "password": "admin123",
            "first_name": "Admin",
            "last_name": "User",
            "role": admin_role,
            "is_active": True
        },
        {
            "username": "manager",
            "email": "manager@auraconnect.ai",
            "password": "manager123",
            "first_name": "Manager",
            "last_name": "User",
            "role": manager_role,
            "is_active": True
        },
        {
            "username": "staff",
            "email": "staff@auraconnect.ai",
            "password": "staff123",
            "first_name": "Staff",
            "last_name": "User",
            "role": staff_role,
            "is_active": True
        }
    ]
    
    created_users = []
    for user_data in users:
        role = user_data.pop("role")
        password = user_data.pop("password")
        
        user = User(**user_data)
        user.hashed_password = hash_password(password)
        user.roles.append(role)
        user.default_tenant_id = 1  # Default tenant
        
        db.add(user)
        created_users.append(user)
    
    db.commit()  # Commit users before creating profiles
    
    # Create staff profiles
    for i, user in enumerate(created_users[1:], 1):  # Skip admin
        profile = StaffProfile(
            user_id=user.id,
            employee_id=f"EMP{i:03d}",
            hire_date=datetime.now() - timedelta(days=365 * i),
            phone=f"+1234567890{i}",
            hourly_rate=Decimal("15.00") + Decimal(i * 2),
            department="Restaurant",
            position=user.roles[0].display_name
        )
        db.add(profile)
    
    db.commit()
    print(f"Created {len(created_users)} users")
    return created_users


def create_test_menu(db: Session):
    """Create test menu items with categories and modifiers."""
    print("Creating test menu...")
    
    # Create categories
    categories = [
        MenuCategory(name="Appetizers", display_name="Appetizers", sort_order=1),
        MenuCategory(name="Main Courses", display_name="Main Courses", sort_order=2),
        MenuCategory(name="Desserts", display_name="Desserts", sort_order=3),
        MenuCategory(name="Beverages", display_name="Beverages", sort_order=4),
    ]
    
    for cat in categories:
        db.add(cat)
    db.commit()
    
    # Create modifier groups
    size_group = ModifierGroup(
        name="Size",
        display_name="Choose Size",
        min_selections=1,
        max_selections=1,
        is_required=True
    )
    
    toppings_group = ModifierGroup(
        name="Toppings",
        display_name="Add Toppings",
        min_selections=0,
        max_selections=5,
        is_required=False
    )
    
    db.add_all([size_group, toppings_group])
    db.commit()
    
    # Create modifiers
    sizes = [
        Modifier(name="Small", display_name="Small", price_adjustment=Decimal("0"), group_id=size_group.id),
        Modifier(name="Medium", display_name="Medium", price_adjustment=Decimal("2"), group_id=size_group.id),
        Modifier(name="Large", display_name="Large", price_adjustment=Decimal("4"), group_id=size_group.id),
    ]
    
    toppings = [
        Modifier(name="Cheese", display_name="Extra Cheese", price_adjustment=Decimal("1.5"), group_id=toppings_group.id),
        Modifier(name="Bacon", display_name="Bacon", price_adjustment=Decimal("2.5"), group_id=toppings_group.id),
        Modifier(name="Mushrooms", display_name="Mushrooms", price_adjustment=Decimal("1"), group_id=toppings_group.id),
    ]
    
    db.add_all(sizes + toppings)
    db.commit()
    
    # Create menu items
    items_data = [
        # Appetizers
        ("Spring Rolls", "Crispy vegetable spring rolls", Decimal("8.99"), categories[0]),
        ("Caesar Salad", "Fresh romaine with caesar dressing", Decimal("10.99"), categories[0]),
        ("Soup of the Day", "Chef's daily soup selection", Decimal("6.99"), categories[0]),
        
        # Main Courses
        ("Grilled Salmon", "Atlantic salmon with vegetables", Decimal("24.99"), categories[1]),
        ("Ribeye Steak", "12oz ribeye with mashed potatoes", Decimal("32.99"), categories[1]),
        ("Margherita Pizza", "Classic pizza with fresh mozzarella", Decimal("16.99"), categories[1]),
        ("Pasta Carbonara", "Creamy pasta with bacon", Decimal("18.99"), categories[1]),
        
        # Desserts
        ("Chocolate Cake", "Rich chocolate layer cake", Decimal("8.99"), categories[2]),
        ("Tiramisu", "Classic Italian dessert", Decimal("7.99"), categories[2]),
        ("Ice Cream", "Three scoops of your choice", Decimal("5.99"), categories[2]),
        
        # Beverages
        ("Soft Drinks", "Coke, Sprite, Orange", Decimal("3.99"), categories[3]),
        ("Fresh Juice", "Orange, Apple, Cranberry", Decimal("4.99"), categories[3]),
        ("Coffee", "Freshly brewed coffee", Decimal("2.99"), categories[3]),
    ]
    
    menu_items = []
    for name, desc, price, category in items_data:
        item = MenuItem(
            name=name,
            display_name=name,
            description=desc,
            price=price,
            category_id=category.id,
            is_active=True,
            is_available=True
        )
        
        # Add modifiers to some items
        if "Pizza" in name:
            item.modifier_groups.extend([size_group, toppings_group])
        elif "Ice Cream" in name:
            item.modifier_groups.append(size_group)
        
        db.add(item)
        menu_items.append(item)
    
    db.commit()
    print(f"Created {len(menu_items)} menu items")
    return menu_items


def create_test_inventory(db: Session):
    """Create test inventory items and vendors."""
    print("Creating test inventory...")
    
    # Create vendors
    vendors = [
        Vendor(
            name="Fresh Foods Inc",
            contact_name="John Smith",
            email="john@freshfoods.com",
            phone="+1234567890",
            address="123 Supply St"
        ),
        Vendor(
            name="Beverage Distributors",
            contact_name="Jane Doe",
            email="jane@beverages.com",
            phone="+0987654321",
            address="456 Drink Ave"
        ),
    ]
    
    db.add_all(vendors)
    db.commit()
    
    # Create inventory items
    items_data = [
        ("Tomatoes", "KG", 50, 10, 100, Decimal("2.50"), vendors[0]),
        ("Mozzarella Cheese", "KG", 30, 5, 50, Decimal("8.00"), vendors[0]),
        ("Flour", "KG", 100, 20, 200, Decimal("1.50"), vendors[0]),
        ("Salmon Fillet", "KG", 20, 5, 30, Decimal("25.00"), vendors[0]),
        ("Ribeye Steak", "Unit", 15, 5, 25, Decimal("18.00"), vendors[0]),
        ("Coffee Beans", "KG", 10, 2, 20, Decimal("15.00"), vendors[1]),
        ("Orange Juice", "Liter", 20, 5, 40, Decimal("3.00"), vendors[1]),
    ]
    
    inventory_items = []
    for name, unit, qty, min_qty, max_qty, cost, vendor in items_data:
        item = InventoryItem(
            name=name,
            sku=f"SKU-{name.upper().replace(' ', '-')}",
            unit=unit,
            quantity=qty,
            min_quantity=min_qty,
            max_quantity=max_qty,
            cost_per_unit=cost,
            vendor_id=vendor.id
        )
        db.add(item)
        inventory_items.append(item)
    
    db.commit()
    print(f"Created {len(inventory_items)} inventory items")
    return inventory_items


def create_test_tables(db: Session):
    """Create test table layout."""
    print("Creating test tables...")
    
    # Create sections
    sections = [
        TableSection(name="Main Dining", display_name="Main Dining Room"),
        TableSection(name="Patio", display_name="Outdoor Patio"),
        TableSection(name="Bar", display_name="Bar Area"),
    ]
    
    db.add_all(sections)
    db.commit()
    
    # Create tables
    tables = []
    table_configs = [
        (sections[0], 10, 4),  # Main dining: 10 tables, 4 seats each
        (sections[1], 6, 4),   # Patio: 6 tables, 4 seats each
        (sections[2], 8, 2),   # Bar: 8 tables, 2 seats each
    ]
    
    for section, count, seats in table_configs:
        for i in range(1, count + 1):
            table = Table(
                number=f"{section.name[0]}{i}",
                display_name=f"{section.display_name} Table {i}",
                section_id=section.id,
                seats=seats,
                is_active=True,
                status="available"
            )
            db.add(table)
            tables.append(table)
    
    db.commit()
    print(f"Created {len(tables)} tables")
    return tables


def create_test_customers(db: Session):
    """Create test customer accounts."""
    print("Creating test customers...")
    
    customers_data = [
        {
            "email": "customer@example.com",
            "phone": "+1234567890",
            "first_name": "John",
            "last_name": "Doe",
            "password": hash_password("customer123")
        },
        {
            "email": "vip@example.com",
            "phone": "+0987654321",
            "first_name": "Jane",
            "last_name": "Smith",
            "password": hash_password("vip123"),
            "is_vip": True
        },
        {
            "email": "regular@example.com",
            "phone": "+1122334455",
            "first_name": "Bob",
            "last_name": "Johnson",
            "password": hash_password("regular123")
        },
    ]
    
    customers = []
    for data in customers_data:
        customer = Customer(**data)
        db.add(customer)
        customers.append(customer)
    
    db.commit()
    
    # Create loyalty points
    for customer in customers:
        points = CustomerPoints(
            customer_id=customer.id,
            points_balance=random.randint(0, 1000),
            lifetime_points=random.randint(0, 5000)
        )
        db.add(points)
    
    db.commit()
    print(f"Created {len(customers)} customers")
    return customers


def create_test_orders(db: Session, menu_items, customers, tables):
    """Create test orders."""
    print("Creating test orders...")
    
    orders = []
    statuses = ["pending", "confirmed", "preparing", "ready", "completed"]
    
    for i in range(20):
        order_date = datetime.now() - timedelta(days=random.randint(0, 30))
        
        order = Order(
            order_number=f"ORD-{1000 + i}",
            customer_id=random.choice(customers).id if random.random() > 0.3 else None,
            table_id=random.choice(tables).id if random.random() > 0.5 else None,
            status=random.choice(statuses),
            order_type="dine_in" if random.random() > 0.3 else "takeout",
            created_at=order_date,
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0")
        )
        
        # Add order items
        num_items = random.randint(1, 5)
        subtotal = Decimal("0")
        
        for _ in range(num_items):
            item = random.choice(menu_items)
            quantity = random.randint(1, 3)
            
            order_item = OrderItem(
                menu_item_id=item.id,
                quantity=quantity,
                unit_price=item.price,
                subtotal=item.price * quantity,
                item_name=item.name
            )
            order.items.append(order_item)
            subtotal += order_item.subtotal
        
        order.subtotal = subtotal
        order.tax = subtotal * Decimal("0.08")  # 8% tax
        order.total = order.subtotal + order.tax
        
        db.add(order)
        orders.append(order)
    
    db.commit()
    print(f"Created {len(orders)} orders")
    return orders


def create_test_settings(db: Session):
    """Create test settings."""
    print("Creating test settings...")
    
    # This is handled by the migration, just set some values
    settings_data = [
        ("restaurant_name", "AuraConnect Demo Restaurant"),
        ("restaurant_address", "123 Demo Street, Demo City, DC 12345"),
        ("restaurant_phone", "+1 (555) 123-4567"),
        ("timezone", "America/New_York"),
        ("currency", "USD"),
        ("tax_rate", "8.5"),
        ("order_timeout_minutes", "60"),
        ("table_turn_time_target", "45"),
    ]
    
    for key, value in settings_data:
        setting = db.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = f'"{value}"' if isinstance(value, str) else value
        else:
            setting = Setting(
                key=key,
                value=f'"{value}"' if isinstance(value, str) else value,
                scope="restaurant",
                restaurant_id=1
            )
            db.add(setting)
    
    db.commit()
    print("Settings configured")


def main():
    """Run all seeding functions."""
    print("Starting test data seeding...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clear existing data (optional)
        if input("Clear existing data? (y/N): ").lower() == 'y':
            print("Clearing existing data...")
            # Add table truncation logic here if needed
        
        # Create test data
        users = create_test_users(db)
        menu_items = create_test_menu(db)
        inventory_items = create_test_inventory(db)
        tables = create_test_tables(db)
        customers = create_test_customers(db)
        orders = create_test_orders(db, menu_items, customers, tables)
        create_test_settings(db)
        
        print("\nTest data seeding completed successfully!")
        print("\nTest Accounts:")
        print("- Admin: admin / admin123")
        print("- Manager: manager / manager123")
        print("- Staff: staff / staff123")
        print("- Customer: customer@example.com / customer123")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()