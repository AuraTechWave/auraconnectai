# backend/core/api_documentation.py

"""
API Documentation configuration and enhancements.
Provides comprehensive documentation for all API endpoints.
"""

from typing import Dict, List, Any
from fastapi import FastAPI
from pydantic import BaseModel


class APIExample(BaseModel):
    """API example model for documentation"""

    summary: str
    description: str
    value: Dict[str, Any]


# Common API examples for documentation
AUTH_EXAMPLES = {
    "login_success": APIExample(
        summary="Successful login",
        description="Login with valid credentials",
        value={"email": "admin@auraconnect.ai", "password": "securepassword"},
    ),
    "login_response": APIExample(
        summary="Login response",
        description="Successful authentication response",
        value={
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "token_type": "bearer",
            "expires_in": 1800,
            "user": {
                "id": 1,
                "email": "admin@auraconnect.ai",
                "role": "admin",
                "restaurant_id": 1,
            },
        },
    ),
}

ORDER_EXAMPLES = {
    "create_order": APIExample(
        summary="Create dine-in order",
        description="Create a new order for table service",
        value={
            "order_type": "dine_in",
            "table_number": "12",
            "customer_id": 123,
            "items": [
                {
                    "menu_item_id": 10,
                    "quantity": 2,
                    "modifiers": [{"modifier_id": 5, "quantity": 1}],
                    "special_instructions": "No onions please",
                },
                {"menu_item_id": 15, "quantity": 1},
            ],
            "notes": "Birthday celebration",
        },
    ),
    "order_response": APIExample(
        summary="Order created response",
        description="Successful order creation response",
        value={
            "id": 1001,
            "order_number": "ORD-2025-1001",
            "status": "pending",
            "order_type": "dine_in",
            "table_number": "12",
            "total_amount": "45.99",
            "tax_amount": "3.68",
            "subtotal": "42.31",
            "items": [
                {
                    "id": 2001,
                    "menu_item_id": 10,
                    "name": "Classic Burger",
                    "quantity": 2,
                    "unit_price": "12.99",
                    "total_price": "25.98",
                    "modifiers": [{"id": 5, "name": "Extra Cheese", "price": "1.50"}],
                }
            ],
            "created_at": "2025-01-08T10:30:00Z",
            "estimated_ready_time": "2025-01-08T10:45:00Z",
        },
    ),
}

MENU_EXAMPLES = {
    "create_menu_item": APIExample(
        summary="Create menu item",
        description="Add a new item to the menu",
        value={
            "name": "Margherita Pizza",
            "description": "Classic pizza with tomato sauce, mozzarella, and fresh basil",
            "category": "Pizza",
            "price": "14.99",
            "is_active": True,
            "dietary_flags": ["vegetarian"],
            "allergens": ["dairy", "gluten"],
            "preparation_time_minutes": 15,
            "calories": 850,
            "image_url": "https://cdn.auraconnect.ai/menu/margherita-pizza.jpg",
        },
    ),
    "recipe_example": APIExample(
        summary="Create recipe",
        description="Define recipe for menu item",
        value={
            "menu_item_id": 101,
            "name": "Margherita Pizza Recipe",
            "yield_quantity": 1,
            "yield_unit": "pizza",
            "prep_time_minutes": 10,
            "cook_time_minutes": 5,
            "ingredients": [
                {
                    "inventory_id": 201,
                    "quantity": 200,
                    "unit": "grams",
                    "notes": "Pizza dough",
                },
                {
                    "inventory_id": 202,
                    "quantity": 100,
                    "unit": "ml",
                    "notes": "Tomato sauce",
                },
                {
                    "inventory_id": 203,
                    "quantity": 150,
                    "unit": "grams",
                    "notes": "Mozzarella cheese",
                },
            ],
            "instructions": "1. Roll out dough\n2. Apply sauce\n3. Add cheese\n4. Bake at 450°F for 5 minutes",
        },
    ),
}

STAFF_EXAMPLES = {
    "create_employee": APIExample(
        summary="Create employee",
        description="Add a new staff member",
        value={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@restaurant.com",
            "phone": "+1-555-0123",
            "role": "server",
            "hourly_rate": "15.50",
            "employment_type": "full_time",
            "start_date": "2025-01-15",
            "department": "front_of_house",
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+1-555-0124",
                "relationship": "spouse",
            },
        },
    ),
    "schedule_shift": APIExample(
        summary="Schedule shift",
        description="Create a shift schedule",
        value={
            "employee_id": 101,
            "shift_date": "2025-01-15",
            "start_time": "09:00",
            "end_time": "17:00",
            "break_duration_minutes": 30,
            "position": "server",
            "section": "main_dining",
        },
    ),
}

INVENTORY_EXAMPLES = {
    "create_inventory_item": APIExample(
        summary="Create inventory item",
        description="Add a new inventory item",
        value={
            "name": "Tomato Sauce",
            "sku": "ING-001",
            "category": "sauces",
            "unit": "liters",
            "current_quantity": 50,
            "minimum_quantity": 10,
            "maximum_quantity": 100,
            "unit_cost": "2.50",
            "supplier_id": 1,
            "storage_location": "Walk-in Cooler A",
            "expiry_tracking": True,
        },
    ),
    "stock_adjustment": APIExample(
        summary="Adjust stock",
        description="Record stock adjustment",
        value={
            "inventory_id": 201,
            "adjustment_type": "purchase",
            "quantity": 25,
            "unit_cost": "2.45",
            "reference_number": "PO-2025-001",
            "notes": "Weekly delivery from supplier",
            "expiry_date": "2025-02-15",
        },
    ),
}


def add_api_examples(app: FastAPI):
    """
    Add comprehensive examples to API endpoints.

    Args:
        app: FastAPI application instance
    """
    # This would be implemented to add examples to specific routes
    # For now, this serves as a documentation reference
    pass


def generate_api_documentation_summary() -> Dict[str, Any]:
    """
    Generate a comprehensive API documentation summary.

    Returns:
        Dictionary containing API documentation metadata
    """
    return {
        "endpoints": {
            "authentication": [
                {
                    "method": "POST",
                    "path": "/api/v1/auth/login",
                    "description": "User login",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/auth/logout",
                    "description": "User logout",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/auth/refresh",
                    "description": "Refresh access token",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/auth/me",
                    "description": "Get current user",
                },
            ],
            "staff_management": [
                {
                    "method": "GET",
                    "path": "/api/v1/staff",
                    "description": "List all staff members",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/staff",
                    "description": "Create staff member",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/staff/{id}",
                    "description": "Get staff details",
                },
                {
                    "method": "PUT",
                    "path": "/api/v1/staff/{id}",
                    "description": "Update staff member",
                },
                {
                    "method": "DELETE",
                    "path": "/api/v1/staff/{id}",
                    "description": "Delete staff member",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/staff/schedules",
                    "description": "Get staff schedules",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/staff/schedules",
                    "description": "Create schedule",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/staff/clock-in",
                    "description": "Clock in",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/staff/clock-out",
                    "description": "Clock out",
                },
            ],
            "orders": [
                {
                    "method": "GET",
                    "path": "/api/v1/orders",
                    "description": "List orders",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/orders",
                    "description": "Create order",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/orders/{id}",
                    "description": "Get order details",
                },
                {
                    "method": "PUT",
                    "path": "/api/v1/orders/{id}",
                    "description": "Update order",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/orders/{id}/cancel",
                    "description": "Cancel order",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/orders/{id}/complete",
                    "description": "Complete order",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/orders/{id}/receipt",
                    "description": "Get receipt",
                },
            ],
            "menu": [
                {
                    "method": "GET",
                    "path": "/api/v1/menu/items",
                    "description": "List menu items",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/menu/items",
                    "description": "Create menu item",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/menu/items/{id}",
                    "description": "Get menu item",
                },
                {
                    "method": "PUT",
                    "path": "/api/v1/menu/items/{id}",
                    "description": "Update menu item",
                },
                {
                    "method": "DELETE",
                    "path": "/api/v1/menu/items/{id}",
                    "description": "Delete menu item",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/menu/categories",
                    "description": "List categories",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/menu/recipes",
                    "description": "Create recipe",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/menu/recipes/{id}/cost",
                    "description": "Get recipe cost",
                },
            ],
            "inventory": [
                {
                    "method": "GET",
                    "path": "/api/v1/inventory",
                    "description": "List inventory items",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/inventory",
                    "description": "Create inventory item",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/inventory/{id}",
                    "description": "Get inventory details",
                },
                {
                    "method": "PUT",
                    "path": "/api/v1/inventory/{id}",
                    "description": "Update inventory",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/inventory/{id}/adjust",
                    "description": "Adjust stock",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/inventory/low-stock",
                    "description": "Get low stock items",
                },
            ],
            "analytics": [
                {
                    "method": "GET",
                    "path": "/api/v1/analytics/sales",
                    "description": "Sales analytics",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/analytics/revenue",
                    "description": "Revenue reports",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/analytics/popular-items",
                    "description": "Popular items",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/analytics/staff-performance",
                    "description": "Staff metrics",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/analytics/custom-report",
                    "description": "Generate report",
                },
            ],
            "payments": [
                {
                    "method": "POST",
                    "path": "/api/v1/payments/process",
                    "description": "Process payment",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/payments/refund",
                    "description": "Process refund",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/payments/methods",
                    "description": "List payment methods",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/payments/split",
                    "description": "Split payment",
                },
            ],
            "customers": [
                {
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "description": "List customers",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/customers",
                    "description": "Create customer",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/customers/{id}",
                    "description": "Get customer details",
                },
                {
                    "method": "PUT",
                    "path": "/api/v1/customers/{id}",
                    "description": "Update customer",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/customers/{id}/orders",
                    "description": "Customer orders",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/customers/{id}/loyalty/points",
                    "description": "Add points",
                },
            ],
            "pos_integration": [
                {
                    "method": "POST",
                    "path": "/api/v1/pos/sync",
                    "description": "Sync with POS",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/pos/status",
                    "description": "Get sync status",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/pos/webhook",
                    "description": "POS webhook endpoint",
                },
                {
                    "method": "GET",
                    "path": "/api/v1/pos/mappings",
                    "description": "Get field mappings",
                },
            ],
        },
        "authentication_methods": [
            "Bearer Token (JWT)",
            "API Key (for server-to-server)",
            "OAuth2 (coming soon)",
        ],
        "rate_limits": {
            "default": "1000 requests/hour",
            "authenticated": "5000 requests/hour",
            "enterprise": "Unlimited",
        },
        "supported_formats": ["application/json"],
        "api_versions": ["v1"],
        "sdks": ["Python", "JavaScript/TypeScript", "PHP", "Ruby"],
    }
