# Orders Module API Reference

## Base URL

```
https://api.auraconnect.com/api/v1/orders
```

## Authentication

All endpoints require JWT authentication:

```http
Authorization: Bearer <token>
```

## Order Management Endpoints

### List Orders

Retrieve a paginated list of orders with optional filters.

```http
GET /api/v1/orders
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `page` | integer | Page number | 1 |
| `page_size` | integer | Items per page (max 100) | 20 |
| `status` | string | Filter by order status | - |
| `customer_id` | integer | Filter by customer | - |
| `location_id` | integer | Filter by location | - |
| `order_type` | string | Filter by order type | - |
| `date_from` | string | Start date (ISO 8601) | - |
| `date_to` | string | End date (ISO 8601) | - |
| `search` | string | Search order number or customer | - |
| `sort_by` | string | Sort field | created_at |
| `sort_order` | string | Sort direction (asc/desc) | desc |

#### Response

```json
{
  "data": [
    {
      "id": 1234,
      "order_number": "ORD-2024-0001",
      "customer": {
        "id": 123,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "(555) 123-4567"
      },
      "location_id": 1,
      "order_type": "dine_in",
      "table_number": "5",
      "status": "confirmed",
      "items_count": 3,
      "subtotal": "45.50",
      "tax_amount": "4.10",
      "tip_amount": "6.82",
      "total_amount": "56.42",
      "created_at": "2024-01-15T14:30:00Z",
      "updated_at": "2024-01-15T14:35:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "total_count": 98
  }
}
```

### Create Order

Create a new order.

```http
POST /api/v1/orders
```

#### Request Body

```json
{
  "customer_id": 123,
  "location_id": 1,
  "order_type": "dine_in",
  "table_number": "5",
  "items": [
    {
      "menu_item_id": 10,
      "quantity": 2,
      "modifiers": [
        {
          "id": 101,
          "name": "Extra Cheese",
          "price": "1.50"
        }
      ],
      "special_instructions": "Well done, no onions"
    },
    {
      "menu_item_id": 15,
      "quantity": 1,
      "modifiers": []
    }
  ],
  "discount_code": "SUMMER20",
  "notes": "Birthday celebration"
}
```

#### Response

```json
{
  "id": 1235,
  "order_number": "ORD-2024-0002",
  "customer": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com"
  },
  "location_id": 1,
  "order_type": "dine_in",
  "table_number": "5",
  "status": "pending",
  "items": [
    {
      "id": 5001,
      "menu_item": {
        "id": 10,
        "name": "Cheeseburger",
        "price": "12.99"
      },
      "quantity": 2,
      "unit_price": "12.99",
      "modifiers": [
        {
          "id": 101,
          "name": "Extra Cheese",
          "price": "1.50"
        }
      ],
      "subtotal": "28.98",
      "special_instructions": "Well done, no onions"
    },
    {
      "id": 5002,
      "menu_item": {
        "id": 15,
        "name": "Caesar Salad",
        "price": "9.99"
      },
      "quantity": 1,
      "unit_price": "9.99",
      "modifiers": [],
      "subtotal": "9.99"
    }
  ],
  "subtotal": "38.97",
  "discount": {
    "code": "SUMMER20",
    "amount": "7.79",
    "percentage": 20
  },
  "tax_amount": "2.80",
  "total_amount": "33.98",
  "notes": "Birthday celebration",
  "created_at": "2024-01-15T15:00:00Z",
  "payment_status": "unpaid",
  "preparation_time_minutes": 20
}
```

### Get Order Details

Retrieve detailed information about a specific order.

```http
GET /api/v1/orders/{order_id}
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | integer | Order ID |

#### Response

```json
{
  "id": 1234,
  "order_number": "ORD-2024-0001",
  "customer": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "(555) 123-4567",
    "loyalty_points": 150
  },
  "location": {
    "id": 1,
    "name": "Downtown Branch",
    "address": "123 Main St"
  },
  "order_type": "dine_in",
  "table_number": "5",
  "status": "preparing",
  "items": [
    {
      "id": 5000,
      "menu_item": {
        "id": 10,
        "name": "Cheeseburger",
        "category": "Burgers",
        "price": "12.99"
      },
      "quantity": 2,
      "unit_price": "12.99",
      "modifiers": [
        {
          "id": 101,
          "name": "Extra Cheese",
          "price": "1.50"
        }
      ],
      "subtotal": "28.98",
      "special_instructions": "Well done",
      "status": "preparing"
    }
  ],
  "subtotal": "45.50",
  "tax_breakdown": [
    {
      "name": "State Tax",
      "rate": 0.06,
      "amount": "2.73"
    },
    {
      "name": "Local Tax",
      "rate": 0.03,
      "amount": "1.37"
    }
  ],
  "tax_amount": "4.10",
  "tip_amount": "6.82",
  "total_amount": "56.42",
  "payment": {
    "status": "paid",
    "method": "credit_card",
    "last_four": "4242",
    "transaction_id": "ch_1234567890",
    "paid_at": "2024-01-15T14:35:00Z"
  },
  "status_history": [
    {
      "status": "pending",
      "timestamp": "2024-01-15T14:30:00Z",
      "user": "System"
    },
    {
      "status": "confirmed",
      "timestamp": "2024-01-15T14:31:00Z",
      "user": "System"
    },
    {
      "status": "preparing",
      "timestamp": "2024-01-15T14:35:00Z",
      "user": "Kitchen Staff"
    }
  ],
  "preparation_time_minutes": 20,
  "estimated_ready_time": "2024-01-15T14:55:00Z",
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-15T14:35:00Z"
}
```

### Update Order

Update an existing order (only allowed in certain states).

```http
PUT /api/v1/orders/{order_id}
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | integer | Order ID |

#### Request Body

```json
{
  "table_number": "7",
  "notes": "Customer has allergy to nuts"
}
```

#### Response

Returns the updated order object.

### Update Order Status

Update the status of an order.

```http
PUT /api/v1/orders/{order_id}/status
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | integer | Order ID |

#### Request Body

```json
{
  "status": "preparing",
  "reason": "Kitchen started preparation",
  "estimated_ready_time": "2024-01-15T15:20:00Z"
}
```

#### Valid Status Transitions

- `pending` → `confirmed`, `cancelled`
- `confirmed` → `preparing`, `cancelled`
- `preparing` → `ready`, `cancelled`
- `ready` → `completed`

#### Response

```json
{
  "id": 1234,
  "status": "preparing",
  "previous_status": "confirmed",
  "updated_by": "kitchen_user_1",
  "updated_at": "2024-01-15T14:35:00Z",
  "estimated_ready_time": "2024-01-15T15:20:00Z"
}
```

### Cancel Order

Cancel an order.

```http
POST /api/v1/orders/{order_id}/cancel
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | integer | Order ID |

#### Request Body

```json
{
  "reason": "customer_request",
  "notes": "Customer changed their mind",
  "refund_amount": "33.98"
}
```

#### Cancellation Reasons

- `customer_request` - Customer requested cancellation
- `out_of_stock` - Items not available
- `kitchen_error` - Kitchen unable to prepare
- `payment_failed` - Payment processing failed
- `other` - Other reason (requires notes)

#### Response

```json
{
  "id": 1234,
  "status": "cancelled",
  "cancellation": {
    "reason": "customer_request",
    "notes": "Customer changed their mind",
    "cancelled_by": "staff_user_1",
    "cancelled_at": "2024-01-15T14:40:00Z"
  },
  "refund": {
    "amount": "33.98",
    "status": "processing",
    "transaction_id": "rf_1234567890"
  }
}
```

## Order Items Endpoints

### Add Items to Order

Add items to an existing order (only in pending/confirmed status).

```http
POST /api/v1/orders/{order_id}/items
```

#### Request Body

```json
{
  "items": [
    {
      "menu_item_id": 20,
      "quantity": 1,
      "modifiers": [],
      "special_instructions": "No ice"
    }
  ]
}
```

#### Response

```json
{
  "added_items": [
    {
      "id": 5003,
      "menu_item": {
        "id": 20,
        "name": "Iced Coffee",
        "price": "4.99"
      },
      "quantity": 1,
      "unit_price": "4.99",
      "subtotal": "4.99",
      "special_instructions": "No ice"
    }
  ],
  "order_totals": {
    "subtotal": "43.96",
    "tax_amount": "3.96",
    "total_amount": "47.92"
  }
}
```

### Update Order Item

Update an item in an order.

```http
PUT /api/v1/orders/{order_id}/items/{item_id}
```

#### Request Body

```json
{
  "quantity": 3,
  "modifiers": [
    {
      "id": 102,
      "name": "Extra Bacon",
      "price": "2.00"
    }
  ],
  "special_instructions": "Extra crispy bacon"
}
```

### Remove Order Item

Remove an item from an order.

```http
DELETE /api/v1/orders/{order_id}/items/{item_id}
```

## Kitchen Integration Endpoints

### Get Kitchen Queue

Retrieve orders in the kitchen queue.

```http
GET /api/v1/kitchen/orders
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `location_id` | integer | Filter by location | Required |
| `station` | string | Filter by kitchen station | - |
| `status` | array | Filter by statuses | [confirmed, preparing] |

#### Response

```json
{
  "data": [
    {
      "id": 1234,
      "order_number": "ORD-2024-0001",
      "order_type": "dine_in",
      "table_number": "5",
      "status": "confirmed",
      "priority": "normal",
      "items": [
        {
          "id": 5000,
          "name": "Cheeseburger",
          "quantity": 2,
          "modifiers": ["Extra Cheese"],
          "special_instructions": "Well done",
          "station": "grill"
        }
      ],
      "created_at": "2024-01-15T14:30:00Z",
      "wait_time_minutes": 5
    }
  ]
}
```

### Start Order Preparation

Mark an order as being prepared.

```http
POST /api/v1/kitchen/orders/{order_id}/prepare
```

#### Request Body

```json
{
  "station": "grill",
  "estimated_minutes": 15,
  "chef_id": 456
}
```

### Mark Order Ready

Mark an order as ready for pickup/serving.

```http
POST /api/v1/kitchen/orders/{order_id}/ready
```

## Reporting Endpoints

### Order Summary Report

Get order summary statistics.

```http
GET /api/v1/orders/reports/summary
```

#### Query Parameters

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `date_from` | string | Start date | Yes |
| `date_to` | string | End date | Yes |
| `location_id` | integer | Filter by location | No |
| `group_by` | string | Grouping (day/week/month) | No |

#### Response

```json
{
  "summary": {
    "total_orders": 156,
    "total_revenue": "8945.67",
    "average_order_value": "57.34",
    "orders_by_type": {
      "dine_in": 89,
      "takeout": 45,
      "delivery": 22
    },
    "orders_by_status": {
      "completed": 145,
      "cancelled": 11
    }
  },
  "daily_breakdown": [
    {
      "date": "2024-01-15",
      "orders": 45,
      "revenue": "2567.89"
    }
  ]
}
```

## Webhooks

### Order Status Changed

Triggered when an order status changes.

```json
{
  "event": "order.status_changed",
  "timestamp": "2024-01-15T14:35:00Z",
  "data": {
    "order_id": 1234,
    "order_number": "ORD-2024-0001",
    "previous_status": "confirmed",
    "new_status": "preparing",
    "location_id": 1
  }
}
```

### Order Created

Triggered when a new order is created.

```json
{
  "event": "order.created",
  "timestamp": "2024-01-15T14:30:00Z",
  "data": {
    "order_id": 1234,
    "order_number": "ORD-2024-0001",
    "customer_id": 123,
    "location_id": 1,
    "total_amount": "56.42"
  }
}
```

## Error Responses

### Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": [
      {
        "field": "items[0].quantity",
        "message": "Quantity must be greater than 0"
      }
    ],
    "request_id": "req_1234567890"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Order not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `INVALID_STATE` | 409 | Invalid state transition |
| `MENU_ITEM_UNAVAILABLE` | 400 | Menu item not available |
| `INSUFFICIENT_INVENTORY` | 400 | Not enough inventory |
| `PAYMENT_FAILED` | 402 | Payment processing failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |

## Rate Limiting

- **Default limit**: 1000 requests per hour per API key
- **Burst limit**: 100 requests per minute
- **Headers returned**:
  - `X-RateLimit-Limit`: Request limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset timestamp

## SDK Examples

### Python

```python
from auraconnect import OrdersClient

client = OrdersClient(api_key="your_api_key")

# Create order
order = client.orders.create(
    customer_id=123,
    location_id=1,
    order_type="dine_in",
    items=[
        {
            "menu_item_id": 10,
            "quantity": 2,
            "modifiers": [{"id": 101}]
        }
    ]
)

# Update status
client.orders.update_status(
    order_id=order.id,
    status="preparing"
)
```

### JavaScript/TypeScript

```typescript
import { OrdersClient } from '@auraconnect/sdk';

const client = new OrdersClient({ apiKey: 'your_api_key' });

// Create order
const order = await client.orders.create({
  customerId: 123,
  locationId: 1,
  orderType: 'dine_in',
  items: [
    {
      menuItemId: 10,
      quantity: 2,
      modifiers: [{ id: 101 }]
    }
  ]
});

// Listen for updates
client.orders.onStatusChange(order.id, (status) => {
  console.log(`Order ${order.orderNumber} is now ${status}`);
});
```

---

*Last Updated: January 2025*