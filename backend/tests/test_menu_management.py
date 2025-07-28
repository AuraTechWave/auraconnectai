# backend/tests/test_menu_management.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.core.database import get_db
from backend.core.menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier
from backend.core.menu_service import MenuService


client = TestClient(app)


class TestMenuService:
    """Test cases for menu service functionality"""

    def test_create_menu_category(self, db_session: Session):
        """Test creating a menu category"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import MenuCategoryCreate
        category_data = MenuCategoryCreate(
            name="Appetizers",
            description="Delicious starters",
            display_order=1,
            is_active=True
        )
        
        category = service.create_category(category_data)
        
        assert category.id is not None
        assert category.name == "Appetizers"
        assert category.description == "Delicious starters"
        assert category.display_order == 1
        assert category.is_active is True

    def test_create_menu_item(self, db_session: Session):
        """Test creating a menu item"""
        service = MenuService(db_session)
        
        # First create a category
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate
        category_data = MenuCategoryCreate(name="Main Courses", display_order=1)
        category = service.create_category(category_data)
        
        # Create menu item
        item_data = MenuItemCreate(
            name="Grilled Chicken",
            description="Perfectly grilled chicken breast",
            price=15.99,
            category_id=category.id,
            sku="GC001",
            calories=350,
            dietary_tags=["Gluten-Free"],
            prep_time_minutes=20
        )
        
        item = service.create_menu_item(item_data)
        
        assert item.id is not None
        assert item.name == "Grilled Chicken"
        assert item.price == 15.99
        assert item.category_id == category.id
        assert item.sku == "GC001"
        assert item.calories == 350
        assert "Gluten-Free" in item.dietary_tags

    def test_create_modifier_group(self, db_session: Session):
        """Test creating a modifier group"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import ModifierGroupCreate
        group_data = ModifierGroupCreate(
            name="Size Options",
            description="Choose your size",
            selection_type="single",
            min_selections=1,
            max_selections=1,
            is_required=True
        )
        
        group = service.create_modifier_group(group_data)
        
        assert group.id is not None
        assert group.name == "Size Options"
        assert group.selection_type == "single"
        assert group.is_required is True

    def test_create_modifier(self, db_session: Session):
        """Test creating a modifier"""
        service = MenuService(db_session)
        
        # First create a modifier group
        from backend.core.menu_schemas import ModifierGroupCreate, ModifierCreate
        group_data = ModifierGroupCreate(name="Size Options", selection_type="single")
        group = service.create_modifier_group(group_data)
        
        # Create modifier
        modifier_data = ModifierCreate(
            modifier_group_id=group.id,
            name="Large",
            description="Large size",
            price_adjustment=2.50,
            price_type="fixed"
        )
        
        modifier = service.create_modifier(modifier_data)
        
        assert modifier.id is not None
        assert modifier.name == "Large"
        assert modifier.price_adjustment == 2.50
        assert modifier.price_type == "fixed"
        assert modifier.modifier_group_id == group.id

    def test_menu_item_search(self, db_session: Session):
        """Test menu item search functionality"""
        service = MenuService(db_session)
        
        # Create test data
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate, MenuSearchParams
        category_data = MenuCategoryCreate(name="Test Category", display_order=1)
        category = service.create_category(category_data)
        
        # Create multiple items
        items_data = [
            MenuItemCreate(name="Chicken Burger", price=12.99, category_id=category.id),
            MenuItemCreate(name="Beef Burger", price=14.99, category_id=category.id),
            MenuItemCreate(name="Fish Tacos", price=11.99, category_id=category.id)
        ]
        
        for item_data in items_data:
            service.create_menu_item(item_data)
        
        # Test search
        search_params = MenuSearchParams(query="burger", limit=10, offset=0)
        items, total = service.get_menu_items(search_params)
        
        assert total == 2
        assert len(items) == 2
        assert all("burger" in item.name.lower() for item in items)

    def test_price_filter(self, db_session: Session):
        """Test menu item price filtering"""
        service = MenuService(db_session)
        
        # Create test data
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate, MenuSearchParams
        category_data = MenuCategoryCreate(name="Test Category", display_order=1)
        category = service.create_category(category_data)
        
        # Create items with different prices
        items_data = [
            MenuItemCreate(name="Cheap Item", price=5.99, category_id=category.id),
            MenuItemCreate(name="Medium Item", price=12.99, category_id=category.id),
            MenuItemCreate(name="Expensive Item", price=25.99, category_id=category.id)
        ]
        
        for item_data in items_data:
            service.create_menu_item(item_data)
        
        # Test price filtering
        search_params = MenuSearchParams(min_price=10.0, max_price=20.0, limit=10, offset=0)
        items, total = service.get_menu_items(search_params)
        
        assert total == 1
        assert len(items) == 1
        assert items[0].name == "Medium Item"

    def test_sku_uniqueness(self, db_session: Session):
        """Test SKU uniqueness constraint"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate
        category_data = MenuCategoryCreate(name="Test Category", display_order=1)
        category = service.create_category(category_data)
        
        # Create first item with SKU
        item_data = MenuItemCreate(
            name="First Item",
            price=10.99,
            category_id=category.id,
            sku="TEST001"
        )
        service.create_menu_item(item_data)
        
        # Try to create second item with same SKU
        duplicate_item_data = MenuItemCreate(
            name="Second Item",
            price=15.99,
            category_id=category.id,
            sku="TEST001"
        )
        
        with pytest.raises(Exception):  # Should raise HTTPException or database constraint error
            service.create_menu_item(duplicate_item_data)

    def test_category_hierarchy(self, db_session: Session):
        """Test category parent-child relationship"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import MenuCategoryCreate
        
        # Create parent category
        parent_data = MenuCategoryCreate(name="Beverages", display_order=1)
        parent = service.create_category(parent_data)
        
        # Create child category
        child_data = MenuCategoryCreate(
            name="Hot Beverages",
            parent_category_id=parent.id,
            display_order=1
        )
        child = service.create_category(child_data)
        
        assert child.parent_category_id == parent.id

    def test_get_menu_stats(self, db_session: Session):
        """Test menu statistics functionality"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate, ModifierGroupCreate, ModifierCreate
        
        # Create test data
        category_data = MenuCategoryCreate(name="Test Category", display_order=1)
        category = service.create_category(category_data)
        
        # Create menu items
        active_item = MenuItemCreate(name="Active Item", price=10.99, category_id=category.id, is_active=True, is_available=True)
        inactive_item = MenuItemCreate(name="Inactive Item", price=12.99, category_id=category.id, is_active=False, is_available=False)
        
        service.create_menu_item(active_item)
        service.create_menu_item(inactive_item)
        
        # Create modifier
        group_data = ModifierGroupCreate(name="Test Group", selection_type="single")
        group = service.create_modifier_group(group_data)
        
        modifier_data = ModifierCreate(modifier_group_id=group.id, name="Test Modifier", price_adjustment=1.0)
        service.create_modifier(modifier_data)
        
        # Get stats
        stats = service.get_menu_stats()
        
        assert stats["total_categories"] == 1
        assert stats["total_items"] == 1  # Only active items
        assert stats["available_items"] == 1
        assert stats["unavailable_items"] == 0
        assert stats["total_modifiers"] == 1


class TestMenuAPI:
    """Test cases for menu API endpoints"""

    def test_create_category_endpoint(self):
        """Test category creation API endpoint"""
        category_data = {
            "name": "Test Category",
            "description": "Test description",
            "display_order": 1,
            "is_active": True
        }
        
        # Note: This test would need proper authentication setup
        # response = client.post("/menu/categories", json=category_data)
        # assert response.status_code == 201
        # assert response.json()["name"] == "Test Category"

    def test_get_categories_endpoint(self):
        """Test get categories API endpoint"""
        # Note: This test would need proper authentication setup
        # response = client.get("/menu/categories")
        # assert response.status_code == 200
        # assert isinstance(response.json(), list)

    def test_menu_item_validation(self):
        """Test menu item validation"""
        invalid_item_data = {
            "name": "",  # Empty name should fail
            "price": -5.0,  # Negative price should fail
            "category_id": 999999  # Non-existent category
        }
        
        # Note: This test would need proper authentication setup
        # response = client.post("/menu/items", json=invalid_item_data)
        # assert response.status_code == 422  # Validation error

    def test_modifier_group_validation(self):
        """Test modifier group validation"""
        invalid_group_data = {
            "name": "",  # Empty name should fail
            "selection_type": "invalid",  # Invalid selection type
            "min_selections": -1,  # Negative minimum
            "max_selections": 0  # Max less than min
        }
        
        # Note: This test would need proper authentication setup
        # response = client.post("/menu/modifier-groups", json=invalid_group_data)
        # assert response.status_code == 422  # Validation error


class TestMenuIntegration:
    """Integration tests for menu management"""

    def test_complete_menu_setup(self, db_session: Session):
        """Test complete menu setup workflow"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import (
            MenuCategoryCreate, MenuItemCreate, ModifierGroupCreate, 
            ModifierCreate, MenuItemModifierCreate
        )
        
        # 1. Create category
        category_data = MenuCategoryCreate(name="Burgers", display_order=1)
        category = service.create_category(category_data)
        
        # 2. Create menu item
        item_data = MenuItemCreate(
            name="Classic Burger",
            price=12.99,
            category_id=category.id,
            description="Beef patty with lettuce and tomato"
        )
        item = service.create_menu_item(item_data)
        
        # 3. Create modifier group
        group_data = ModifierGroupCreate(
            name="Size Options",
            selection_type="single",
            is_required=True
        )
        group = service.create_modifier_group(group_data)
        
        # 4. Create modifiers
        modifiers_data = [
            ModifierCreate(modifier_group_id=group.id, name="Regular", price_adjustment=0.0),
            ModifierCreate(modifier_group_id=group.id, name="Large", price_adjustment=2.0)
        ]
        
        for modifier_data in modifiers_data:
            service.create_modifier(modifier_data)
        
        # 5. Link modifier group to menu item
        link_data = MenuItemModifierCreate(
            menu_item_id=item.id,
            modifier_group_id=group.id,
            is_required=True
        )
        service.add_modifier_to_item(link_data)
        
        # Verify the complete setup
        assert category.id is not None
        assert item.id is not None
        assert group.id is not None
        
        # Verify item has modifiers
        item_modifiers = service.get_item_modifiers(item.id)
        assert len(item_modifiers) == 1
        assert item_modifiers[0].modifier_group_id == group.id

    def test_menu_availability_logic(self, db_session: Session):
        """Test menu item availability logic"""
        service = MenuService(db_session)
        
        from backend.core.menu_schemas import MenuCategoryCreate, MenuItemCreate, MenuSearchParams
        
        # Create category
        category_data = MenuCategoryCreate(name="Test Category", display_order=1)
        category = service.create_category(category_data)
        
        # Create items with different availability
        items_data = [
            MenuItemCreate(
                name="Available Item",
                price=10.99,
                category_id=category.id,
                is_active=True,
                is_available=True
            ),
            MenuItemCreate(
                name="Unavailable Item",
                price=12.99,
                category_id=category.id,
                is_active=True,
                is_available=False
            ),
            MenuItemCreate(
                name="Inactive Item",
                price=8.99,
                category_id=category.id,
                is_active=False,
                is_available=True
            )
        ]
        
        for item_data in items_data:
            service.create_menu_item(item_data)
        
        # Test filtering by availability
        available_params = MenuSearchParams(is_available=True, limit=10, offset=0)
        available_items, available_total = service.get_menu_items(available_params)
        
        unavailable_params = MenuSearchParams(is_available=False, limit=10, offset=0)
        unavailable_items, unavailable_total = service.get_menu_items(unavailable_params)
        
        assert available_total == 2  # Available Item + Inactive Item (both have is_available=True)
        assert unavailable_total == 1  # Only Unavailable Item


@pytest.fixture
def db_session():
    """Mock database session for testing"""
    # This would need to be implemented with a test database
    # For now, this is a placeholder
    pass


if __name__ == "__main__":
    pytest.main([__file__])