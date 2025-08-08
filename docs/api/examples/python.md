# Python SDK Examples

This page provides examples of using the AuraConnect API with Python.

## Installation

```bash
pip install auraconnect
# or for async support
pip install auraconnect[async]
```

## Basic Usage

### Initialize Client

```python
from auraconnect import AuraConnectClient

# Initialize client
client = AuraConnectClient(
    base_url="https://api.auraconnect.ai",
    api_key="your-api-key"  # or use email/password auth
)

# Or with email/password authentication
client = AuraConnectClient(
    base_url="https://api.auraconnect.ai"
)
client.auth.login("admin@auraconnect.ai", "your-password")
```

### Async Client

```python
from auraconnect import AsyncAuraConnectClient
import asyncio

async def main():
    async with AsyncAuraConnectClient(base_url="https://api.auraconnect.ai") as client:
        await client.auth.login("admin@auraconnect.ai", "your-password")
        
        # Use the client
        orders = await client.orders.list()
        print(f"Found {len(orders)} orders")

asyncio.run(main())
```

## Authentication

### Login and Token Management

```python
# Manual token management
response = client.auth.login("admin@auraconnect.ai", "password")
print(f"Access token: {response.access_token}")
print(f"Expires in: {response.expires_in} seconds")

# Token is automatically stored and used for subsequent requests
me = client.auth.get_current_user()
print(f"Logged in as: {me.email}")

# Refresh token when needed
client.auth.refresh_token()

# Logout
client.auth.logout()
```

### Context Manager (Recommended)

```python
from auraconnect import AuraConnectClient

with AuraConnectClient() as client:
    client.auth.login("admin@auraconnect.ai", "password")
    
    # Client automatically handles token refresh
    # and cleanup on exit
    orders = client.orders.list()
```

## Orders Management

### Create Order

```python
from auraconnect.models import OrderCreate, OrderItem

# Create order
order = client.orders.create(
    order_type="dine_in",
    table_number="12",
    customer_id=123,
    items=[
        OrderItem(
            menu_item_id=10,
            quantity=2,
            modifiers=[{"modifier_id": 5, "quantity": 1}],
            special_instructions="No onions please"
        ),
        OrderItem(
            menu_item_id=15,
            quantity=1
        )
    ],
    notes="Birthday celebration"
)

print(f"Created order: {order.order_number}")
print(f"Total: ${order.total_amount}")
```

### List Orders with Filtering

```python
from datetime import datetime, timedelta

# Get today's orders
today = datetime.now().date()
orders = client.orders.list(
    date_from=today,
    date_to=today + timedelta(days=1),
    status="pending",
    page=1,
    page_size=50
)

for order in orders.items:
    print(f"{order.order_number}: ${order.total_amount} - {order.status}")

# Pagination
print(f"Page {orders.meta.page} of {orders.meta.total_pages}")
```

### Update Order Status

```python
# Get order
order = client.orders.get(1001)

# Update status
updated_order = client.orders.update(
    order_id=order.id,
    status="preparing"
)

# Cancel order
client.orders.cancel(
    order_id=order.id,
    reason="Customer request",
    notes="Had to leave unexpectedly"
)
```

## Menu Management

### List Menu Items

```python
# Get all active menu items
menu_items = client.menu.list_items(
    is_active=True,
    category="Burgers"
)

for item in menu_items:
    print(f"{item.name}: ${item.price}")
    if item.dietary_flags:
        print(f"  Dietary: {', '.join(item.dietary_flags)}")
```

### Create Menu Item with Recipe

```python
# Create menu item
menu_item = client.menu.create_item(
    name="Veggie Burger",
    description="Plant-based patty with avocado",
    category="Burgers",
    price=11.99,
    dietary_flags=["vegetarian", "vegan"],
    allergens=["gluten", "soy"],
    calories=450,
    preparation_time_minutes=10
)

# Create recipe for the item
recipe = client.menu.create_recipe(
    menu_item_id=menu_item.id,
    name="Veggie Burger Recipe",
    yield_quantity=1,
    yield_unit="burger",
    prep_time_minutes=5,
    cook_time_minutes=5,
    ingredients=[
        {
            "inventory_id": 201,
            "quantity": 1,
            "unit": "piece",
            "notes": "Plant-based patty"
        },
        {
            "inventory_id": 102,
            "quantity": 1,
            "unit": "piece",
            "notes": "Whole wheat bun"
        }
    ],
    instructions="1. Grill patty for 5 minutes\n2. Toast bun\n3. Assemble"
)

# Get cost analysis
cost = client.menu.get_recipe_cost(recipe.id)
print(f"Cost per serving: ${cost.cost_per_serving}")
print(f"Profit margin: ${cost.profit_margin}")
```

## Staff Management

### Clock In/Out

```python
from auraconnect.models import ClockInRequest

# Clock in
clock_in = client.staff.clock_in(
    employee_id=1,
    location={
        "latitude": 40.7128,
        "longitude": -74.0060
    }
)
print(f"Clocked in at: {clock_in.timestamp}")

# Clock out
clock_out = client.staff.clock_out(
    employee_id=1,
    notes="Completed shift"
)
print(f"Shift duration: {clock_out.duration_hours} hours")
```

### Schedule Management

```python
from datetime import date

# Create schedule
schedule = client.staff.create_schedule(
    employee_id=1,
    shift_date=date(2025, 1, 15),
    start_time="09:00",
    end_time="17:00",
    break_duration_minutes=30,
    position="server",
    section="main_dining"
)

# Get weekly schedule
weekly_schedule = client.staff.get_schedules(
    start_date=date(2025, 1, 13),
    end_date=date(2025, 1, 19),
    employee_id=1
)

for shift in weekly_schedule:
    print(f"{shift.shift_date}: {shift.start_time} - {shift.end_time}")
```

## Analytics

### Sales Reports

```python
# Get today's sales
sales = client.analytics.get_sales(period="today")
print(f"Today's revenue: ${sales.total_revenue}")
print(f"Orders: {sales.order_count}")
print(f"Average order: ${sales.average_order_value}")

# Get monthly sales with daily breakdown
monthly_sales = client.analytics.get_sales(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
    group_by="day"
)

for day in monthly_sales.data:
    print(f"{day.date}: ${day.revenue} ({day.order_count} orders)")
```

### Custom Reports

```python
# Generate custom report
report = client.analytics.create_report(
    report_type="sales_by_category",
    date_range={
        "start": date(2025, 1, 1),
        "end": date(2025, 1, 31)
    },
    filters={
        "categories": ["Burgers", "Pizza"],
        "locations": [1, 2]
    },
    group_by=["category", "day"],
    metrics=["revenue", "quantity", "average_order_value"]
)

# Export report
client.analytics.export_report(
    report_id=report.id,
    format="csv",
    output_file="sales_report.csv"
)
```

## Error Handling

```python
from auraconnect.exceptions import (
    AuraConnectError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError
)

try:
    order = client.orders.create(...)
except ValidationError as e:
    print(f"Validation failed: {e.message}")
    for error in e.errors:
        print(f"  {error.field}: {error.message}")
except AuthenticationError:
    print("Authentication failed. Please login again.")
    client.auth.refresh_token()
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except NotFoundError:
    print("Resource not found")
except AuraConnectError as e:
    print(f"API error: {e}")
```

## Batch Operations

```python
# Batch create menu items
items_data = [
    {"name": "Item 1", "price": 10.99, "category": "Appetizers"},
    {"name": "Item 2", "price": 12.99, "category": "Appetizers"},
    {"name": "Item 3", "price": 8.99, "category": "Appetizers"}
]

results = client.menu.batch_create_items(items_data)
print(f"Created {len(results.successful)} items")
if results.failed:
    print(f"Failed to create {len(results.failed)} items")
```

## Webhooks

```python
# Register webhook
webhook = client.webhooks.create(
    url="https://myapp.com/webhooks/auraconnect",
    events=["order.created", "order.completed", "payment.completed"],
    secret="your-webhook-secret"
)

print(f"Webhook ID: {webhook.id}")
print(f"Webhook secret: {webhook.secret}")

# List webhooks
webhooks = client.webhooks.list()
for wh in webhooks:
    print(f"{wh.url}: {', '.join(wh.events)}")

# Test webhook
client.webhooks.test(webhook.id, event="order.created")
```

## File Uploads

```python
# Upload menu item image
with open("burger.jpg", "rb") as f:
    image_url = client.files.upload(
        file=f,
        type="menu_item_image",
        entity_id=menu_item.id
    )

# Update menu item with image
client.menu.update_item(
    item_id=menu_item.id,
    image_url=image_url
)
```

## Real-time Updates (WebSocket)

```python
import asyncio
from auraconnect import AsyncAuraConnectClient

async def handle_order_update(order):
    print(f"Order {order.order_number} updated: {order.status}")

async def main():
    async with AsyncAuraConnectClient() as client:
        await client.auth.login("admin@auraconnect.ai", "password")
        
        # Subscribe to order updates
        await client.realtime.subscribe(
            channel="orders",
            event="order.updated",
            callback=handle_order_update
        )
        
        # Keep connection alive
        await asyncio.sleep(3600)

asyncio.run(main())
```

## Configuration

```python
from auraconnect import AuraConnectClient, Config

# Custom configuration
config = Config(
    base_url="https://api.auraconnect.ai",
    timeout=30,  # Request timeout in seconds
    max_retries=3,
    retry_delay=1,
    verify_ssl=True,
    proxy="http://proxy.example.com:8080"
)

client = AuraConnectClient(config=config)

# Or use environment variables
# AURACONNECT_BASE_URL=https://api.auraconnect.ai
# AURACONNECT_API_KEY=your-api-key
# AURACONNECT_TIMEOUT=30

client = AuraConnectClient.from_env()
```

## Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger('auraconnect')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(handler)

# Client will now log all requests and responses
client = AuraConnectClient()
```

## Testing

```python
from auraconnect.testing import MockAuraConnectClient
import pytest

@pytest.fixture
def client():
    return MockAuraConnectClient()

def test_create_order(client):
    # Mock response
    client.orders.create.return_value = Order(
        id=1001,
        order_number="ORD-2025-1001",
        total_amount=52.34
    )
    
    # Test your code
    order = create_customer_order(client, customer_id=123)
    assert order.order_number == "ORD-2025-1001"
```

## Complete Example

```python
#!/usr/bin/env python3
"""
Complete example of using AuraConnect API
"""

from auraconnect import AuraConnectClient
from datetime import datetime, date
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

def main():
    # Initialize client
    with AuraConnectClient(base_url="https://api.auraconnect.ai") as client:
        # Authenticate
        client.auth.login("manager@restaurant.com", "password")
        
        # Get current user
        user = client.auth.get_current_user()
        print(f"Logged in as: {user.first_name} {user.last_name}")
        
        # Get today's stats
        today = date.today()
        
        # Get orders
        orders = client.orders.list(
            date_from=today,
            status="completed"
        )
        
        print(f"\nToday's Orders: {len(orders.items)}")
        total_revenue = sum(float(o.total_amount) for o in orders.items)
        print(f"Total Revenue: ${total_revenue:.2f}")
        
        # Get low stock items
        low_stock = client.inventory.get_low_stock()
        if low_stock:
            print(f"\nLow Stock Alert: {len(low_stock)} items")
            for item in low_stock[:5]:
                print(f"  - {item.name}: {item.current_quantity} {item.unit}")
        
        # Get staff on duty
        schedules = client.staff.get_schedules(
            shift_date=today
        )
        print(f"\nStaff on duty: {len(schedules)}")
        
        # Generate daily report
        report = client.analytics.get_sales(period="today")
        print(f"\nDaily Summary:")
        print(f"  Revenue: ${report.total_revenue}")
        print(f"  Orders: {report.order_count}")
        print(f"  Avg Order: ${report.average_order_value}")
        print(f"  Top Item: {report.top_items[0].name if report.top_items else 'N/A'}")

if __name__ == "__main__":
    main()
```