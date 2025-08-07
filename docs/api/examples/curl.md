# cURL Examples

This page provides cURL command examples for interacting with the AuraConnect API.

## Authentication

### Login
```bash
curl -X POST https://api.auraconnect.ai/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@auraconnect.ai",
    "password": "your-password"
  }'
```

### Using the Access Token
After login, use the access token in the Authorization header:
```bash
export ACCESS_TOKEN="your-access-token-here"

curl -X GET https://api.auraconnect.ai/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Orders Management

### Create Order
```bash
curl -X POST https://api.auraconnect.ai/api/v1/orders \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_type": "dine_in",
    "table_number": "12",
    "customer_id": 123,
    "items": [
      {
        "menu_item_id": 10,
        "quantity": 2,
        "modifiers": [
          {"modifier_id": 5, "quantity": 1}
        ],
        "special_instructions": "No onions please"
      }
    ],
    "notes": "Birthday celebration"
  }'
```

### List Orders
```bash
# Get all orders
curl -X GET "https://api.auraconnect.ai/api/v1/orders" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# With pagination and filtering
curl -X GET "https://api.auraconnect.ai/api/v1/orders?page=1&page_size=20&status=pending" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Order Details
```bash
curl -X GET "https://api.auraconnect.ai/api/v1/orders/1001" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Update Order Status
```bash
curl -X PUT "https://api.auraconnect.ai/api/v1/orders/1001" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "preparing"
  }'
```

### Cancel Order
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/orders/1001/cancel" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Customer request",
    "notes": "Customer had to leave unexpectedly"
  }'
```

## Menu Management

### List Menu Items
```bash
# All menu items
curl -X GET "https://api.auraconnect.ai/api/v1/menu/items" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Filter by category
curl -X GET "https://api.auraconnect.ai/api/v1/menu/items?category=Burgers&is_active=true" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Create Menu Item
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/menu/items" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Veggie Burger",
    "description": "Plant-based patty with avocado and sprouts",
    "category": "Burgers",
    "price": "11.99",
    "is_active": true,
    "dietary_flags": ["vegetarian", "vegan"],
    "allergens": ["gluten", "soy"],
    "calories": 450,
    "preparation_time_minutes": 10,
    "image_url": "https://cdn.auraconnect.ai/menu/veggie-burger.jpg"
  }'
```

### Update Menu Item
```bash
curl -X PUT "https://api.auraconnect.ai/api/v1/menu/items/10" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price": "13.99",
    "is_featured": true
  }'
```

## Recipe Management

### Create Recipe
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/menu/recipes" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "menu_item_id": 10,
    "name": "Classic Burger Recipe",
    "yield_quantity": 1,
    "yield_unit": "burger",
    "prep_time_minutes": 5,
    "cook_time_minutes": 7,
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
      }
    ],
    "instructions": "1. Form beef into patty\\n2. Season with salt and pepper\\n3. Grill for 3-4 minutes per side"
  }'
```

### Get Recipe Cost Analysis
```bash
curl -X GET "https://api.auraconnect.ai/api/v1/menu/recipes/1/cost-analysis" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Staff Management

### Clock In
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/staff/clock-in" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": 1,
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    }
  }'
```

### Create Schedule
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/staff/schedules" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": 1,
    "shift_date": "2025-01-15",
    "start_time": "09:00",
    "end_time": "17:00",
    "break_duration_minutes": 30,
    "position": "server",
    "section": "main_dining"
  }'
```

## Inventory Management

### Adjust Stock
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/inventory/101/adjust" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "adjustment_type": "purchase",
    "quantity": 50,
    "unit_cost": "7.50",
    "reference_number": "PO-2025-0123",
    "supplier_id": 1,
    "notes": "Weekly delivery"
  }'
```

### Get Low Stock Items
```bash
curl -X GET "https://api.auraconnect.ai/api/v1/inventory/low-stock" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Analytics

### Get Sales Analytics
```bash
# Today's sales
curl -X GET "https://api.auraconnect.ai/api/v1/analytics/sales?period=today" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Custom date range
curl -X GET "https://api.auraconnect.ai/api/v1/analytics/sales?start_date=2025-01-01&end_date=2025-01-31&group_by=day" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Generate Custom Report
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/analytics/custom-report" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "sales_by_category",
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-01-31"
    },
    "filters": {
      "categories": ["Burgers", "Pizza"]
    },
    "group_by": ["category", "day"],
    "metrics": ["revenue", "quantity", "average_order_value"]
  }'
```

## Payments

### Process Payment
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/payments/process" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### Process Refund
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/payments/refund" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pay_abc123",
    "amount": "52.34",
    "reason": "customer_request",
    "notes": "Wrong order delivered"
  }'
```

## Customer Management

### Create Customer
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/customers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1-555-0123",
    "birthday": "1990-05-15",
    "preferences": {
      "dietary_restrictions": ["gluten-free"],
      "favorite_items": [10, 15, 22]
    },
    "marketing_consent": true
  }'
```

### Add Loyalty Points
```bash
curl -X POST "https://api.auraconnect.ai/api/v1/customers/123/loyalty/points" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "add",
    "points": 100,
    "reason": "order_purchase",
    "reference_id": "ORD-2025-1001"
  }'
```

## Useful Tips

### Environment Variables
Save common values as environment variables:
```bash
export API_BASE_URL="https://api.auraconnect.ai"
export ACCESS_TOKEN="your-access-token"
```

### Pretty Print JSON Response
Use `jq` to format JSON responses:
```bash
curl -X GET "$API_BASE_URL/api/v1/orders" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
```

### Save Response to File
```bash
curl -X GET "$API_BASE_URL/api/v1/analytics/sales?period=month" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o monthly-sales.json
```

### Debug Mode
Use `-v` for verbose output:
```bash
curl -v -X POST "$API_BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@auraconnect.ai", "password": "password"}'
```

### Include Response Headers
Use `-i` to include headers in output:
```bash
curl -i -X GET "$API_BASE_URL/api/v1/orders" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```