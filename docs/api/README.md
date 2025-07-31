# AuraConnect API Reference

## Overview

The AuraConnect API is a RESTful API that provides programmatic access to all restaurant management features. Built with FastAPI, it offers automatic documentation, type validation, and high performance.

## Base URL

```
Production: https://api.auraconnect.com
Staging: https://api-staging.auraconnect.com
Local Development: http://localhost:8000
```

## API Documentation

- **Interactive Docs (Swagger UI)**: `{base_url}/docs`
- **Alternative Docs (ReDoc)**: `{base_url}/redoc`
- **OpenAPI Schema**: `{base_url}/openapi.json`

## Authentication

AuraConnect uses JWT (JSON Web Tokens) for authentication.

### Obtaining Tokens

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using Tokens

Include the access token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### Refreshing Tokens

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

## API Versioning

The API uses URL versioning. The current version is `v1`.

```
https://api.auraconnect.com/api/v1/...
```

## Request Format

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | Bearer token for authentication |
| `Content-Type` | Yes* | `application/json` for POST/PUT requests |
| `X-Tenant-ID` | Sometimes | Required for multi-tenant operations |
| `Accept-Language` | No | Preferred language (e.g., `en-US`) |

### Request Body

All POST and PUT requests should send JSON:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

## Response Format

### Success Response

```json
{
  "data": {
    "id": 123,
    "field1": "value1",
    "field2": "value2"
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Paginated Response

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

### Error Response

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
    ],
    "request_id": "req_xyz789",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

## Common Parameters

### Pagination

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page (max 100) |

### Filtering

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Full-text search |
| `status` | string | Filter by status |
| `created_from` | datetime | Start date filter |
| `created_to` | datetime | End date filter |

### Sorting

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_by` | string | created_at | Field to sort by |
| `sort_order` | string | desc | Sort direction (asc/desc) |

## Core Resources

### Authentication & Authorization

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Auth](./auth.md) | `/api/v1/auth` | Authentication endpoints |
| [Users](./users.md) | `/api/v1/users` | User management |
| [Roles](./roles.md) | `/api/v1/roles` | Role-based access control |

### Restaurant Management

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Restaurants](./restaurants.md) | `/api/v1/restaurants` | Restaurant profiles |
| [Locations](./locations.md) | `/api/v1/locations` | Location management |
| [Settings](./settings.md) | `/api/v1/settings` | Configuration settings |

### Operations

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Orders](./orders.md) | `/api/v1/orders` | Order management |
| [Menu](./menu.md) | `/api/v1/menu` | Menu items and categories |
| [Inventory](./inventory.md) | `/api/v1/inventory` | Stock management |
| [Tables](./tables.md) | `/api/v1/tables` | Table management |

### Staff & HR

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Staff](./staff.md) | `/api/v1/staff` | Employee management |
| [Schedules](./schedules.md) | `/api/v1/schedules` | Shift scheduling |
| [Time Tracking](./time-tracking.md) | `/api/v1/time` | Clock in/out |
| [Payroll](./payroll.md) | `/api/v1/payroll` | Payroll processing |

### Customer Management

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Customers](./customers.md) | `/api/v1/customers` | Customer profiles |
| [Loyalty](./loyalty.md) | `/api/v1/loyalty` | Rewards program |
| [Feedback](./feedback.md) | `/api/v1/feedback` | Reviews and ratings |
| [Promotions](./promotions.md) | `/api/v1/promotions` | Marketing campaigns |

### Analytics & Reporting

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [Analytics](./analytics.md) | `/api/v1/analytics` | Business analytics |
| [Reports](./reports.md) | `/api/v1/reports` | Generated reports |
| [Insights](./insights.md) | `/api/v1/insights` | AI-powered insights |

### Integrations

| Resource | Endpoint | Description |
|----------|----------|-------------|
| [POS](./pos.md) | `/api/v1/pos` | POS integrations |
| [Payments](./payments.md) | `/api/v1/payments` | Payment processing |
| [Webhooks](./webhooks.md) | `/api/v1/webhooks` | Event webhooks |

## Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 204 | No Content | Request successful, no content |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service down |

## Error Codes

| Code | Description |
|------|-------------|
| `UNAUTHORIZED` | Invalid or missing authentication |
| `FORBIDDEN` | Insufficient permissions |
| `NOT_FOUND` | Resource not found |
| `VALIDATION_ERROR` | Request validation failed |
| `DUPLICATE_ENTRY` | Resource already exists |
| `INVALID_STATE` | Invalid state transition |
| `RATE_LIMITED` | Too many requests |
| `INTERNAL_ERROR` | Internal server error |

## Rate Limiting

### Default Limits

| Tier | Requests/Hour | Burst | Description |
|------|---------------|-------|-------------|
| Free | 1,000 | 100/min | Free tier |
| Basic | 10,000 | 500/min | Small restaurants |
| Pro | 50,000 | 1000/min | Medium chains |
| Enterprise | Unlimited | Custom | Large chains |

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
X-RateLimit-Retry-After: 3600
```

## Webhooks

Webhooks allow you to receive real-time notifications:

### Available Events

- `order.created`
- `order.status_changed`
- `payment.completed`
- `inventory.low_stock`
- `staff.clocked_in`
- `customer.created`

### Webhook Payload

```json
{
  "event": "order.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "id": 123,
    "order_number": "ORD-2024-0001",
    "total_amount": "45.50"
  },
  "signature": "sha256=abc123..."
}
```

## SDKs & Libraries

### Official SDKs

- **Python**: `pip install auraconnect`
- **JavaScript/TypeScript**: `npm install @auraconnect/sdk`
- **PHP**: `composer require auraconnect/sdk`
- **Ruby**: `gem install auraconnect`

### Example Usage

#### Python

```python
from auraconnect import Client

client = Client(api_key="your_api_key")

# Create an order
order = client.orders.create(
    customer_id=123,
    items=[
        {"menu_item_id": 10, "quantity": 2}
    ]
)

print(f"Order created: {order.order_number}")
```

#### JavaScript

```javascript
import { AuraConnect } from '@auraconnect/sdk';

const client = new AuraConnect({ apiKey: 'your_api_key' });

// Create an order
const order = await client.orders.create({
  customerId: 123,
  items: [
    { menuItemId: 10, quantity: 2 }
  ]
});

console.log(`Order created: ${order.orderNumber}`);
```

## Testing

### Test Environment

```
Base URL: https://api-sandbox.auraconnect.com
Test API Key: test_key_...
```

### Test Data

Test credit cards:
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- Insufficient funds: `4000 0000 0000 9995`

## API Changelog

### Version 1.2.0 (2024-01-15)
- Added webhook support
- Improved error messages
- Added batch operations

### Version 1.1.0 (2023-12-01)
- Added analytics endpoints
- Enhanced filtering options
- Performance improvements

### Version 1.0.0 (2023-10-01)
- Initial public release

## Best Practices

### 1. Use Pagination
Always paginate list requests to avoid timeouts:

```python
page = 1
while True:
    response = client.orders.list(page=page, page_size=50)
    process_orders(response.data)
    
    if not response.has_next:
        break
    page += 1
```

### 2. Handle Errors Gracefully
```python
try:
    order = client.orders.create(...)
except ValidationError as e:
    print(f"Validation failed: {e.details}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ApiError as e:
    print(f"API error: {e.message}")
```

### 3. Use Idempotency Keys
For critical operations, use idempotency keys:

```http
X-Idempotency-Key: unique-key-123
```

### 4. Implement Exponential Backoff
```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            
            wait_time = (2 ** i) + random.uniform(0, 1)
            time.sleep(wait_time)
```

## Support

- **API Status**: https://status.auraconnect.com
- **Developer Forum**: https://developers.auraconnect.com/forum
- **Email**: api-support@auraconnect.com
- **Discord**: https://discord.gg/auraconnect-dev

---

*For detailed endpoint documentation, see the individual resource pages.*