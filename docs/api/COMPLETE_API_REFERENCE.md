# AuraConnect Complete API Reference

This document provides a comprehensive reference for all API endpoints in the AuraConnect platform.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Staff Management](#staff-management)
3. [Orders Management](#orders-management)
4. [Menu Management](#menu-management)
5. [Inventory Management](#inventory-management)
6. [Kitchen Display System](#kitchen-display-system)
7. [Payroll Management](#payroll-management)
8. [Tax Management](#tax-management)
9. [Analytics & Insights](#analytics--insights)
10. [Customer Management](#customer-management)
11. [Payments](#payments)
12. [POS Integration](#pos-integration)
13. [Promotions & Marketing](#promotions--marketing)
14. [Reservations](#reservations)
15. [Table Management](#table-management)
16. [Feedback & Reviews](#feedback--reviews)
17. [Loyalty & Rewards](#loyalty--rewards)

## Authentication & Authorization

### POST /api/v1/auth/login
Login with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "role": "manager",
    "restaurant_id": 1
  }
}
```

### POST /api/v1/auth/logout
Logout and invalidate tokens.

**Headers:**
- `Authorization: Bearer {token}`

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### POST /api/v1/auth/refresh
Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### GET /api/v1/auth/me
Get current authenticated user details.

**Headers:**
- `Authorization: Bearer {token}`

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "manager",
  "restaurant_id": 1,
  "permissions": ["menu:read", "menu:write", "orders:read"]
}
```

## Staff Management

### GET /api/v1/staff
List all staff members with pagination and filtering.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 20, max: 100)
- `search` (string): Search by name or email
- `role` (string): Filter by role
- `status` (string): Filter by status (active, inactive)
- `department` (string): Filter by department

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "employee_id": "EMP001",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@restaurant.com",
      "phone": "+1-555-0123",
      "role": "server",
      "department": "front_of_house",
      "status": "active",
      "hourly_rate": "15.50",
      "employment_type": "full_time",
      "start_date": "2023-01-15",
      "created_at": "2023-01-10T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "total_count": 98,
    "has_next": true,
    "has_previous": false
  }
}
```

### POST /api/v1/staff
Create a new staff member.

**Request Body:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@restaurant.com",
  "phone": "+1-555-0124",
  "role": "chef",
  "department": "kitchen",
  "hourly_rate": "20.00",
  "employment_type": "full_time",
  "start_date": "2025-02-01",
  "emergency_contact": {
    "name": "John Smith",
    "phone": "+1-555-0125",
    "relationship": "spouse"
  },
  "bank_details": {
    "account_number": "****1234",
    "routing_number": "****5678",
    "account_type": "checking"
  }
}
```

### GET /api/v1/staff/{id}
Get detailed information about a specific staff member.

### PUT /api/v1/staff/{id}
Update staff member information.

### DELETE /api/v1/staff/{id}
Delete a staff member (soft delete).

### POST /api/v1/staff/clock-in
Clock in for a shift.

**Request Body:**
```json
{
  "employee_id": 1,
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060
  },
  "biometric_data": "fingerprint_hash_optional"
}
```

### POST /api/v1/staff/clock-out
Clock out from a shift.

### GET /api/v1/staff/schedules
Get staff schedules.

**Query Parameters:**
- `start_date` (date): Start date for schedule
- `end_date` (date): End date for schedule
- `employee_id` (integer): Filter by employee
- `department` (string): Filter by department

### POST /api/v1/staff/schedules
Create a new schedule.

**Request Body:**
```json
{
  "employee_id": 1,
  "shift_date": "2025-01-15",
  "start_time": "09:00",
  "end_time": "17:00",
  "break_duration_minutes": 30,
  "position": "server",
  "section": "main_dining",
  "notes": "Training shift with senior staff"
}
```

## Orders Management

### GET /api/v1/orders
List orders with filtering and pagination.

**Query Parameters:**
- `page` (integer): Page number
- `page_size` (integer): Items per page
- `status` (string): Filter by status (pending, preparing, ready, completed, cancelled)
- `order_type` (string): Filter by type (dine_in, takeout, delivery)
- `date_from` (datetime): Start date filter
- `date_to` (datetime): End date filter
- `customer_id` (integer): Filter by customer
- `table_number` (string): Filter by table

**Response:**
```json
{
  "data": [
    {
      "id": 1001,
      "order_number": "ORD-2025-1001",
      "status": "preparing",
      "order_type": "dine_in",
      "table_number": "12",
      "customer_id": 123,
      "subtotal": "42.31",
      "tax_amount": "3.68",
      "tip_amount": "6.35",
      "total_amount": "52.34",
      "items_count": 3,
      "created_at": "2025-01-08T12:30:00Z",
      "estimated_ready_time": "2025-01-08T12:45:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_pages": 10,
    "total_count": 198
  }
}
```

### POST /api/v1/orders
Create a new order.

**Request Body:**
```json
{
  "order_type": "dine_in",
  "table_number": "12",
  "customer_id": 123,
  "items": [
    {
      "menu_item_id": 10,
      "quantity": 2,
      "modifiers": [
        {
          "modifier_id": 5,
          "quantity": 1
        }
      ],
      "special_instructions": "No onions please"
    },
    {
      "menu_item_id": 15,
      "quantity": 1,
      "variant_id": 3
    }
  ],
  "notes": "Birthday celebration - bring dessert with candle",
  "promotional_code": "BIRTHDAY10"
}
```

### GET /api/v1/orders/{id}
Get detailed order information.

**Response:**
```json
{
  "id": 1001,
  "order_number": "ORD-2025-1001",
  "status": "preparing",
  "order_type": "dine_in",
  "table_number": "12",
  "customer": {
    "id": 123,
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-0123"
  },
  "items": [
    {
      "id": 2001,
      "menu_item_id": 10,
      "name": "Classic Burger",
      "quantity": 2,
      "unit_price": "12.99",
      "total_price": "27.48",
      "status": "preparing",
      "modifiers": [
        {
          "id": 5,
          "name": "Extra Cheese",
          "price": "1.50"
        }
      ],
      "special_instructions": "No onions please",
      "kitchen_status": {
        "station": "grill",
        "assigned_to": "Chef Mike",
        "started_at": "2025-01-08T12:32:00Z"
      }
    }
  ],
  "payment_status": "pending",
  "subtotal": "42.31",
  "tax_amount": "3.68",
  "tip_amount": "0.00",
  "discount_amount": "4.23",
  "total_amount": "41.76",
  "applied_promotions": [
    {
      "code": "BIRTHDAY10",
      "discount": "4.23",
      "type": "percentage"
    }
  ],
  "created_at": "2025-01-08T12:30:00Z",
  "updated_at": "2025-01-08T12:32:00Z",
  "estimated_ready_time": "2025-01-08T12:45:00Z"
}
```

### PUT /api/v1/orders/{id}
Update an existing order.

### POST /api/v1/orders/{id}/cancel
Cancel an order.

**Request Body:**
```json
{
  "reason": "Customer request",
  "notes": "Customer had emergency and had to leave"
}
```

### POST /api/v1/orders/{id}/complete
Mark order as completed.

### GET /api/v1/orders/{id}/receipt
Get order receipt.

### POST /api/v1/orders/{id}/send-to-kitchen
Send order to kitchen display system.

## Menu Management

### GET /api/v1/menu/items
List all menu items.

**Query Parameters:**
- `category` (string): Filter by category
- `is_active` (boolean): Filter by active status
- `dietary_flags` (array): Filter by dietary flags
- `search` (string): Search in name and description

**Response:**
```json
{
  "data": [
    {
      "id": 10,
      "name": "Classic Burger",
      "description": "Juicy beef patty with lettuce, tomato, and our special sauce",
      "category": "Burgers",
      "price": "12.99",
      "is_active": true,
      "is_featured": false,
      "dietary_flags": [],
      "allergens": ["gluten", "dairy"],
      "calories": 650,
      "preparation_time_minutes": 12,
      "image_url": "https://cdn.auraconnect.ai/menu/classic-burger.jpg",
      "modifiers": [
        {
          "id": 5,
          "name": "Extra Cheese",
          "price": "1.50"
        },
        {
          "id": 6,
          "name": "Bacon",
          "price": "2.00"
        }
      ],
      "variants": [
        {
          "id": 1,
          "name": "Single Patty",
          "price": "12.99"
        },
        {
          "id": 2,
          "name": "Double Patty",
          "price": "15.99"
        }
      ]
    }
  ],
  "meta": {
    "total_count": 145
  }
}
```

### POST /api/v1/menu/items
Create a new menu item.

**Request Body:**
```json
{
  "name": "Veggie Burger",
  "description": "Plant-based patty with avocado and sprouts",
  "category": "Burgers",
  "price": "11.99",
  "is_active": true,
  "dietary_flags": ["vegetarian", "vegan"],
  "allergens": ["gluten", "soy"],
  "calories": 450,
  "preparation_time_minutes": 10,
  "image_url": "https://cdn.auraconnect.ai/menu/veggie-burger.jpg",
  "ingredients_description": "Black bean patty, avocado, sprouts, tomato, whole wheat bun"
}
```

### GET /api/v1/menu/items/{id}
Get specific menu item details.

### PUT /api/v1/menu/items/{id}
Update menu item.

### DELETE /api/v1/menu/items/{id}
Delete menu item (soft delete).

### GET /api/v1/menu/categories
List all menu categories.

### POST /api/v1/menu/categories
Create a new category.

### GET /api/v1/menu/recipes
List all recipes.

### POST /api/v1/menu/recipes
Create a recipe for a menu item.

**Request Body:**
```json
{
  "menu_item_id": 10,
  "name": "Classic Burger Recipe",
  "yield_quantity": 1,
  "yield_unit": "burger",
  "prep_time_minutes": 5,
  "cook_time_minutes": 7,
  "total_time_minutes": 12,
  "difficulty_level": "easy",
  "ingredients": [
    {
      "inventory_id": 101,
      "quantity": 0.25,
      "unit": "lb",
      "notes": "80/20 ground beef"
    },
    {
      "inventory_id": 102,
      "quantity": 1,
      "unit": "piece",
      "notes": "Sesame seed bun"
    },
    {
      "inventory_id": 103,
      "quantity": 2,
      "unit": "leaves",
      "notes": "Iceberg lettuce"
    },
    {
      "inventory_id": 104,
      "quantity": 2,
      "unit": "slices",
      "notes": "Tomato"
    },
    {
      "inventory_id": 105,
      "quantity": 30,
      "unit": "ml",
      "notes": "Special sauce"
    }
  ],
  "instructions": "1. Form beef into patty\n2. Season with salt and pepper\n3. Grill for 3-4 minutes per side\n4. Toast bun\n5. Assemble with lettuce, tomato, and sauce",
  "notes": "Internal temp should reach 160°F for well-done"
}
```

### GET /api/v1/menu/recipes/{id}/cost-analysis
Get cost analysis for a recipe.

**Response:**
```json
{
  "recipe_id": 1,
  "recipe_name": "Classic Burger Recipe",
  "total_cost": "3.25",
  "cost_per_serving": "3.25",
  "ingredient_costs": [
    {
      "ingredient": "Ground Beef",
      "quantity": 0.25,
      "unit": "lb",
      "unit_cost": "8.00",
      "total_cost": "2.00"
    },
    {
      "ingredient": "Bun",
      "quantity": 1,
      "unit": "piece",
      "unit_cost": "0.50",
      "total_cost": "0.50"
    }
  ],
  "menu_price": "12.99",
  "profit_margin": "9.74",
  "markup_percentage": "299.69",
  "food_cost_percentage": "25.02"
}
```

## Inventory Management

### GET /api/v1/inventory
List inventory items.

**Query Parameters:**
- `category` (string): Filter by category
- `low_stock` (boolean): Show only low stock items
- `supplier_id` (integer): Filter by supplier
- `search` (string): Search by name or SKU

### POST /api/v1/inventory
Create inventory item.

**Request Body:**
```json
{
  "name": "Ground Beef 80/20",
  "sku": "BEEF-001",
  "category": "proteins",
  "unit": "lb",
  "current_quantity": 50,
  "minimum_quantity": 20,
  "maximum_quantity": 100,
  "unit_cost": "8.00",
  "supplier_id": 1,
  "storage_location": "Walk-in Freezer",
  "temperature_requirements": "< 0°F",
  "shelf_life_days": 90,
  "expiry_tracking": true,
  "auto_order": true,
  "auto_order_quantity": 50
}
```

### GET /api/v1/inventory/{id}
Get inventory item details.

### PUT /api/v1/inventory/{id}
Update inventory item.

### POST /api/v1/inventory/{id}/adjust
Adjust inventory stock.

**Request Body:**
```json
{
  "adjustment_type": "purchase",
  "quantity": 50,
  "unit_cost": "7.50",
  "reference_number": "PO-2025-0123",
  "supplier_id": 1,
  "notes": "Weekly delivery",
  "batch_number": "BATCH-20250108",
  "expiry_date": "2025-04-08"
}
```

**Adjustment Types:**
- `purchase`: Stock received from supplier
- `usage`: Stock used in operations
- `waste`: Stock wasted/spoiled
- `adjustment`: Manual count adjustment
- `transfer`: Transfer between locations

### GET /api/v1/inventory/low-stock
Get items below minimum quantity.

### GET /api/v1/inventory/expiring
Get items expiring soon.

**Query Parameters:**
- `days` (integer): Days until expiry (default: 7)

### POST /api/v1/inventory/count
Submit inventory count.

**Request Body:**
```json
{
  "count_date": "2025-01-08",
  "counted_by": 1,
  "items": [
    {
      "inventory_id": 101,
      "counted_quantity": 48.5,
      "notes": "2 packages damaged"
    },
    {
      "inventory_id": 102,
      "counted_quantity": 150
    }
  ]
}
```

## Kitchen Display System (KDS)

### GET /api/v1/kds/orders
Get orders for kitchen display.

**Query Parameters:**
- `station` (string): Filter by kitchen station
- `status` (string): Filter by preparation status

### PUT /api/v1/kds/orders/{id}/status
Update order item status in kitchen.

**Request Body:**
```json
{
  "item_id": 2001,
  "status": "preparing",
  "station": "grill",
  "chef_id": 5
}
```

### POST /api/v1/kds/orders/{id}/bump
Bump order to next station.

## Payroll Management

### GET /api/v1/payroll/pay-periods
List pay periods.

### POST /api/v1/payroll/calculate
Calculate payroll for period.

**Request Body:**
```json
{
  "pay_period_id": 1,
  "include_overtime": true,
  "include_tips": true,
  "include_deductions": true
}
```

### GET /api/v1/payroll/pay-stubs/{employee_id}
Get employee pay stubs.

### POST /api/v1/payroll/process
Process payroll payments.

### GET /api/v1/payroll/reports/summary
Get payroll summary report.

## Tax Management

### POST /api/v1/tax/calculate
Calculate taxes for order or payroll.

**Request Body:**
```json
{
  "type": "sales",
  "amount": "100.00",
  "location": {
    "address": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001"
  },
  "items": [
    {
      "category": "food",
      "amount": "85.00"
    },
    {
      "category": "alcohol",
      "amount": "15.00"
    }
  ]
}
```

### GET /api/v1/tax/rates
Get current tax rates by jurisdiction.

### GET /api/v1/tax/reports
Generate tax reports.

## Analytics & Insights

### GET /api/v1/analytics/sales
Get sales analytics.

**Query Parameters:**
- `period` (string): Time period (today, week, month, year, custom)
- `start_date` (date): Start date for custom period
- `end_date` (date): End date for custom period
- `group_by` (string): Grouping (hour, day, week, month)

### GET /api/v1/analytics/revenue
Revenue analytics with trends.

### GET /api/v1/analytics/popular-items
Most popular menu items.

### GET /api/v1/analytics/staff-performance
Staff performance metrics.

### GET /api/v1/analytics/customer-insights
Customer behavior analytics.

### POST /api/v1/analytics/custom-report
Generate custom report.

**Request Body:**
```json
{
  "report_type": "sales_by_category",
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-01-31"
  },
  "filters": {
    "categories": ["Burgers", "Pizza"],
    "locations": [1, 2]
  },
  "group_by": ["category", "day"],
  "metrics": ["revenue", "quantity", "average_order_value"]
}
```

## Customer Management

### GET /api/v1/customers
List customers.

### POST /api/v1/customers
Create customer profile.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone": "+1-555-0123",
  "birthday": "1990-05-15",
  "preferences": {
    "dietary_restrictions": ["gluten-free"],
    "favorite_items": [10, 15, 22],
    "preferred_payment": "credit_card"
  },
  "marketing_consent": true
}
```

### GET /api/v1/customers/{id}
Get customer details.

### PUT /api/v1/customers/{id}
Update customer profile.

### GET /api/v1/customers/{id}/orders
Get customer order history.

### GET /api/v1/customers/{id}/loyalty
Get loyalty points and rewards.

### POST /api/v1/customers/{id}/loyalty/points
Add or redeem loyalty points.

**Request Body:**
```json
{
  "action": "add",
  "points": 100,
  "reason": "order_purchase",
  "reference_id": "ORD-2025-1001"
}
```

## Payments

### POST /api/v1/payments/process
Process payment for order.

**Request Body:**
```json
{
  "order_id": 1001,
  "payment_method": "credit_card",
  "amount": "52.34",
  "card_details": {
    "number": "4242424242424242",
    "exp_month": "12",
    "exp_year": "2025",
    "cvv": "123",
    "zip": "10001"
  },
  "tip_amount": "8.00"
}
```

### POST /api/v1/payments/refund
Process refund.

**Request Body:**
```json
{
  "payment_id": "pay_abc123",
  "amount": "52.34",
  "reason": "customer_request",
  "notes": "Wrong order delivered"
}
```

### POST /api/v1/payments/split
Split payment between multiple methods.

**Request Body:**
```json
{
  "order_id": 1001,
  "splits": [
    {
      "payment_method": "credit_card",
      "amount": "26.17",
      "card_details": {
        "number": "4242424242424242",
        "exp_month": "12",
        "exp_year": "2025",
        "cvv": "123"
      }
    },
    {
      "payment_method": "cash",
      "amount": "26.17"
    }
  ]
}
```

### GET /api/v1/payments/methods
List available payment methods.

## POS Integration

### POST /api/v1/pos/sync
Trigger manual sync with POS system.

### GET /api/v1/pos/status
Get current sync status.

### POST /api/v1/pos/webhook
Webhook endpoint for POS updates.

### GET /api/v1/pos/mappings
Get field mappings configuration.

### PUT /api/v1/pos/mappings
Update field mappings.

## Promotions & Marketing

### GET /api/v1/promotions
List active promotions.

### POST /api/v1/promotions
Create promotion campaign.

**Request Body:**
```json
{
  "name": "Happy Hour Special",
  "description": "50% off appetizers",
  "type": "percentage_discount",
  "value": 50,
  "applies_to": "category",
  "category_ids": [3],
  "start_date": "2025-01-15T16:00:00Z",
  "end_date": "2025-01-15T18:00:00Z",
  "days_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday"],
  "minimum_order_amount": "20.00",
  "maximum_discount_amount": "25.00",
  "usage_limit_per_customer": 1,
  "total_usage_limit": 500,
  "requires_code": true,
  "code": "HAPPY50"
}
```

### GET /api/v1/promotions/{id}
Get promotion details.

### PUT /api/v1/promotions/{id}
Update promotion.

### DELETE /api/v1/promotions/{id}
Deactivate promotion.

### GET /api/v1/promotions/{id}/usage
Get promotion usage statistics.

### POST /api/v1/promotions/validate
Validate promotion code.

**Request Body:**
```json
{
  "code": "HAPPY50",
  "order_amount": "45.00",
  "items": [
    {
      "menu_item_id": 5,
      "quantity": 2,
      "category": "appetizers"
    }
  ]
}
```

## Reservations

### GET /api/v1/reservations
List reservations.

**Query Parameters:**
- `date` (date): Filter by date
- `status` (string): Filter by status
- `customer_id` (integer): Filter by customer

### POST /api/v1/reservations
Create reservation.

**Request Body:**
```json
{
  "customer_id": 123,
  "party_size": 4,
  "reservation_date": "2025-01-20",
  "reservation_time": "19:00",
  "duration_minutes": 120,
  "table_preferences": "window",
  "special_requests": "Birthday celebration",
  "contact_phone": "+1-555-0123",
  "contact_email": "john@example.com"
}
```

### GET /api/v1/reservations/{id}
Get reservation details.

### PUT /api/v1/reservations/{id}
Update reservation.

### POST /api/v1/reservations/{id}/confirm
Confirm reservation.

### POST /api/v1/reservations/{id}/cancel
Cancel reservation.

### GET /api/v1/reservations/availability
Check table availability.

**Query Parameters:**
- `date` (date): Date to check
- `time` (time): Time to check
- `party_size` (integer): Number of guests
- `duration_minutes` (integer): Expected duration

## Table Management

### GET /api/v1/tables
List all tables.

### GET /api/v1/tables/{id}
Get table details.

### PUT /api/v1/tables/{id}/status
Update table status.

**Request Body:**
```json
{
  "status": "occupied",
  "party_size": 4,
  "server_id": 5,
  "order_id": 1001
}
```

### GET /api/v1/tables/layout
Get restaurant floor layout.

### PUT /api/v1/tables/layout
Update floor layout.

## Feedback & Reviews

### GET /api/v1/feedback
List customer feedback.

### POST /api/v1/feedback
Submit feedback.

**Request Body:**
```json
{
  "order_id": 1001,
  "customer_id": 123,
  "rating": 4,
  "food_rating": 5,
  "service_rating": 4,
  "ambiance_rating": 4,
  "comments": "Great food, service was a bit slow",
  "would_recommend": true
}
```

### GET /api/v1/feedback/{id}
Get feedback details.

### POST /api/v1/feedback/{id}/respond
Respond to feedback.

## Loyalty & Rewards

### GET /api/v1/loyalty/programs
List loyalty programs.

### GET /api/v1/loyalty/rewards
List available rewards.

### POST /api/v1/loyalty/rewards/redeem
Redeem reward.

**Request Body:**
```json
{
  "customer_id": 123,
  "reward_id": 10,
  "order_id": 1001
}
```

### GET /api/v1/loyalty/tiers
Get loyalty tier information.

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### 401 Unauthorized
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required"
  }
}
```

### 403 Forbidden
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Insufficient permissions"
  }
}
```

### 404 Not Found
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found"
  }
}
```

### 429 Too Many Requests
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "retry_after": 3600
  }
}
```

### 500 Internal Server Error
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "request_id": "req_abc123"
  }
}
```

## Webhook Events

The API can send webhook notifications for the following events:

- `order.created` - New order created
- `order.updated` - Order updated
- `order.completed` - Order completed
- `order.cancelled` - Order cancelled
- `payment.completed` - Payment processed
- `payment.refunded` - Payment refunded
- `inventory.low_stock` - Item below minimum quantity
- `staff.clocked_in` - Employee clocked in
- `staff.clocked_out` - Employee clocked out
- `customer.created` - New customer registered
- `reservation.created` - New reservation made
- `reservation.cancelled` - Reservation cancelled
- `feedback.received` - New feedback submitted

## Rate Limiting

API rate limits are enforced per API key:

- **Default**: 1,000 requests per hour
- **Authenticated**: 5,000 requests per hour
- **Enterprise**: Custom limits

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1704724800
```

## Pagination

Most list endpoints support pagination with the following parameters:

- `page`: Page number (starting from 1)
- `page_size`: Number of items per page (max 100)

Paginated responses include metadata:

```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "total_count": 98,
    "has_next": true,
    "has_previous": false
  }
}
```

## Filtering and Sorting

Most list endpoints support filtering and sorting:

- `search`: Full-text search
- `sort_by`: Field to sort by
- `sort_order`: Sort direction (asc/desc)
- Various field-specific filters

## Versioning

The API uses URL versioning. Current version is v1:

```
https://api.auraconnect.ai/api/v1/...
```

## SDK Support

Official SDKs are available for:

- Python: `pip install auraconnect`
- JavaScript/TypeScript: `npm install @auraconnect/sdk`
- PHP: `composer require auraconnect/sdk`
- Ruby: `gem install auraconnect`

---

For more information, visit the [AuraConnect Developer Portal](https://developers.auraconnect.ai)