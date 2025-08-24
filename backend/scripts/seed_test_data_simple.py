#!/usr/bin/env python3
"""
Simple seed test data for AuraConnect manual testing.
This version creates minimal test data focusing on core functionality.
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables if not set
os.environ.setdefault('DATABASE_URL', 'postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev')
os.environ.setdefault('JWT_SECRET_KEY', 'your-super-secret-key-change-this-in-production')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('ENVIRONMENT', 'development')

from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from core.rbac_models import RBACUser as User, RBACRole as Role, RBACPermission as Permission
from core.password_security import hash_password

def create_test_users(db: Session):
    """Create basic test user accounts."""
    print("Creating test users...")
    
    try:
        # Create basic roles
        roles_data = [
            ("admin", "Administrator", "Full system access"),
            ("manager", "Manager", "Restaurant management access"),
            ("staff", "Staff", "Basic staff access"),
        ]
        
        roles = {}
        for name, display_name, description in roles_data:
            role = Role(
                name=name,
                display_name=display_name,
                description=description,
                is_active=True,
                is_system_role=True
            )
            db.add(role)
            roles[name] = role
        
        db.commit()
        
        # Create basic permissions
        permissions_data = [
            ("system.admin", "System Admin", "Full system administration", "system", "admin"),
            ("menu.view", "View Menu", "View menu items", "menu", "view"),
            ("menu.manage", "Manage Menu", "Create and edit menu items", "menu", "manage"),
            ("orders.view", "View Orders", "View orders", "orders", "view"),
            ("orders.manage", "Manage Orders", "Create and edit orders", "orders", "manage"),
            ("staff.view", "View Staff", "View staff information", "staff", "view"),
            ("staff.manage", "Manage Staff", "Manage staff", "staff", "manage"),
        ]
        
        permissions = []
        for key, name, description, resource, action in permissions_data:
            perm = Permission(
                key=key,
                name=name,
                description=description,
                resource=resource,
                action=action,
                is_active=True,
                is_system_permission=True
            )
            db.add(perm)
            permissions.append(perm)
        
        db.commit()
        
        # Assign permissions to roles
        roles['admin'].permissions = permissions
        roles['manager'].permissions = [p for p in permissions if not p.key.startswith("system")]
        roles['staff'].permissions = [p for p in permissions if p.action == "view"]
        
        db.commit()
        
        # Create users
        users_data = [
            ("admin", "admin@auraconnect.ai", "admin123", "Admin", "User", roles['admin']),
            ("manager", "manager@auraconnect.ai", "manager123", "Manager", "User", roles['manager']),
            ("staff", "staff@auraconnect.ai", "staff123", "Staff", "User", roles['staff']),
        ]
        
        created_users = []
        for username, email, password, first_name, last_name, role in users_data:
            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_email_verified=True,
                default_tenant_id=1
            )
            user.roles.append(role)
            db.add(user)
            created_users.append(user)
        
        db.commit()
        print(f"Created {len(created_users)} users")
        
        # Also create a customer user if Customer model exists
        try:
            from modules.customers.models import Customer
            
            customer = Customer(
                email="customer@example.com",
                phone="+1234567890",
                first_name="Test",
                last_name="Customer",
                password=hash_password("customer123")
            )
            db.add(customer)
            db.commit()
            print("Created customer account")
        except ImportError:
            print("Customer model not found, skipping customer creation")
        
        return created_users
        
    except Exception as e:
        print(f"Error creating users: {e}")
        db.rollback()
        raise


def create_basic_menu(db: Session):
    """Create basic menu items for testing."""
    print("Creating basic menu items...")
    
    try:
        from modules.menu.models import MenuCategory, MenuItem
        
        # Create categories
        categories_data = [
            ("appetizers", "Appetizers", 1),
            ("main_courses", "Main Courses", 2),
            ("beverages", "Beverages", 3),
        ]
        
        categories = {}
        for name, display_name, sort_order in categories_data:
            cat = MenuCategory(
                name=name,
                display_name=display_name,
                sort_order=sort_order,
                is_active=True
            )
            db.add(cat)
            categories[name] = cat
        
        db.commit()
        
        # Create menu items
        items_data = [
            ("Spring Rolls", "Crispy vegetable spring rolls", Decimal("8.99"), categories['appetizers']),
            ("Caesar Salad", "Fresh romaine with caesar dressing", Decimal("10.99"), categories['appetizers']),
            ("Grilled Salmon", "Atlantic salmon with vegetables", Decimal("24.99"), categories['main_courses']),
            ("Ribeye Steak", "12oz ribeye with mashed potatoes", Decimal("32.99"), categories['main_courses']),
            ("Soft Drinks", "Coke, Sprite, Orange", Decimal("3.99"), categories['beverages']),
            ("Coffee", "Freshly brewed coffee", Decimal("2.99"), categories['beverages']),
        ]
        
        items = []
        for name, description, price, category in items_data:
            item = MenuItem(
                name=name,
                display_name=name,
                description=description,
                price=price,
                category_id=category.id,
                is_active=True,
                is_available=True
            )
            db.add(item)
            items.append(item)
        
        db.commit()
        print(f"Created {len(items)} menu items")
        
    except ImportError:
        print("Menu models not found, skipping menu creation")
    except Exception as e:
        print(f"Error creating menu: {e}")
        db.rollback()


def create_basic_tables(db: Session):
    """Create basic table layout."""
    print("Creating basic tables...")
    
    try:
        from modules.tables.models import Table, TableSection
        
        # Create sections
        section = TableSection(
            name="main_dining",
            display_name="Main Dining",
            is_active=True
        )
        db.add(section)
        db.commit()
        
        # Create tables
        tables = []
        for i in range(1, 11):
            table = Table(
                number=f"T{i}",
                display_name=f"Table {i}",
                section_id=section.id,
                seats=4,
                is_active=True,
                status="available"
            )
            db.add(table)
            tables.append(table)
        
        db.commit()
        print(f"Created {len(tables)} tables")
        
    except ImportError:
        print("Table models not found, skipping table creation")
    except Exception as e:
        print(f"Error creating tables: {e}")
        db.rollback()


def main():
    """Run all seeding functions."""
    print("Starting simple test data seeding...")
    print("=" * 50)
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create test data
        create_test_users(db)
        create_basic_menu(db)
        create_basic_tables(db)
        
        print("\n" + "=" * 50)
        print("Simple test data seeding completed successfully!")
        print("\nTest Accounts:")
        print("- Admin: admin / admin123")
        print("- Manager: manager / manager123")
        print("- Staff: staff / staff123")
        print("- Customer: customer@example.com / customer123")
        
    except Exception as e:
        print(f"\nError seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()