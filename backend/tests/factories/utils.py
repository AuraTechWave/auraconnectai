# backend/tests/factories/utils.py

import random
from typing import Dict, List, Optional
from .auth import UserFactory, RoleFactory
from .inventory import InventoryFactory
from .menu import CategoryFactory, MenuItemFactory
from .recipe import RecipeWithIngredientsFactory
from .order import OrderWithItemsFactory


def create_restaurant_setup(
    num_categories: int = 3,
    num_menu_items: int = 5,
    num_inventory_items: int = 10,
    user: Optional = None
) -> Dict:
    """
    Create a complete restaurant setup for testing.
    
    Args:
        num_categories: Number of menu categories to create
        num_menu_items: Number of menu items to create
        num_inventory_items: Number of inventory items to create
        user: User to use as creator (creates one if not provided)
    
    Returns:
        Dict containing all created objects
    """
    if not user:
        user = UserFactory(roles=[RoleFactory(name="manager")])
    
    # Create categories
    categories = []
    category_names = ["Appetizers", "Main Courses", "Desserts", "Beverages", "Sides"]
    for i in range(min(num_categories, len(category_names))):
        category = CategoryFactory(
            name=category_names[i],
            created_by=user.id
        )
        categories.append(category)
    
    # Create inventory items
    inventory_items = []
    for i in range(num_inventory_items):
        item = InventoryFactory(
            item_name=f"Ingredient {i + 1}",
            created_by=user.id
        )
        inventory_items.append(item)
    
    # Create menu items with recipes
    menu_items = []
    for i in range(num_menu_items):
        category = random.choice(categories)
        menu_item = MenuItemFactory(
            name=f"Dish {i + 1}",
            category=category,
            created_by=user.id
        )
        
        # Create recipe with random ingredients
        num_ingredients = random.randint(2, 4)
        selected_ingredients = random.sample(
            inventory_items, 
            min(num_ingredients, len(inventory_items))
        )
        
        recipe = RecipeWithIngredientsFactory(
            menu_item=menu_item,
            created_by=user.id,
            ingredients=[
                {
                    "inventory_item": ingredient,
                    "quantity": round(random.uniform(0.1, 1.0), 2),
                    "created_by": user.id
                }
                for ingredient in selected_ingredients
            ]
        )
        
        menu_items.append(menu_item)
    
    return {
        "user": user,
        "categories": categories,
        "inventory_items": inventory_items,
        "menu_items": menu_items
    }


def create_order_scenario(
    user: Optional = None,
    num_items: int = 2,
    with_recipes: bool = True
) -> Dict:
    """
    Create an order with items ready for testing.
    
    Args:
        user: User creating the order
        num_items: Number of items in the order
        with_recipes: Whether to create recipes for menu items
    
    Returns:
        Dict containing order and related objects
    """
    if not user:
        user = UserFactory(roles=[RoleFactory(name="staff")])
    
    # Create menu items
    menu_items = []
    for i in range(num_items):
        menu_item = MenuItemFactory(created_by=user.id)
        
        if with_recipes:
            # Create recipe with ingredients
            RecipeWithIngredientsFactory(
                menu_item=menu_item,
                created_by=user.id
            )
        
        menu_items.append(menu_item)
    
    # Create order
    order = OrderWithItemsFactory(
        created_by_user=user,
        items=[
            {
                "menu_item": item,
                "quantity": random.randint(1, 3)
            }
            for item in menu_items
        ]
    )
    
    return {
        "user": user,
        "order": order,
        "menu_items": menu_items
    }


def create_low_stock_scenario(threshold_percentage: float = 20.0) -> Dict:
    """
    Create inventory items with low stock for testing alerts.
    
    Args:
        threshold_percentage: Percentage of max quantity to set as threshold
    
    Returns:
        Dict containing low stock items
    """
    low_stock_items = []
    normal_stock_items = []
    
    # Create some items at or below threshold
    for i in range(3):
        max_quantity = random.uniform(50, 100)
        threshold = max_quantity * (threshold_percentage / 100)
        current_quantity = threshold * random.uniform(0.5, 1.0)  # At or below threshold
        
        item = InventoryFactory(
            item_name=f"Low Stock Item {i + 1}",
            quantity=current_quantity,
            threshold=threshold,
            max_quantity=max_quantity
        )
        low_stock_items.append(item)
    
    # Create some items with normal stock
    for i in range(3):
        max_quantity = random.uniform(50, 100)
        threshold = max_quantity * (threshold_percentage / 100)
        current_quantity = random.uniform(threshold * 2, max_quantity)  # Well above threshold
        
        item = InventoryFactory(
            item_name=f"Normal Stock Item {i + 1}",
            quantity=current_quantity,
            threshold=threshold,
            max_quantity=max_quantity
        )
        normal_stock_items.append(item)
    
    return {
        "low_stock_items": low_stock_items,
        "normal_stock_items": normal_stock_items,
        "all_items": low_stock_items + normal_stock_items
    }