# Rate Limiting & API Quotas

## Overview

AuraConnect implements rate limiting to ensure fair usage and maintain API performance for all users. Rate limits are applied per API key or authenticated user.

## Rate Limit Headers

All API responses include rate limit information in the headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 998
X-RateLimit-Reset: 1691496000
X-RateLimit-Reset-After: 3600
X-RateLimit-Bucket: api-general
```

### Header Definitions

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in the window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |
| `X-RateLimit-Reset-After` | Seconds until limit resets |
| `X-RateLimit-Bucket` | Rate limit bucket identifier |

## Rate Limit Tiers

### Free Tier
- 1,000 requests per hour
- 10,000 requests per day
- 2 requests per second burst

### Professional Tier
- 10,000 requests per hour
- 100,000 requests per day
- 10 requests per second burst

### Enterprise Tier
- 100,000 requests per hour
- 1,000,000 requests per day
- 100 requests per second burst
- Custom limits available

## Endpoint-Specific Limits

Different endpoints have different rate limits based on their resource intensity:

### Standard Endpoints
Default rate limits apply to most endpoints:
- GET requests: Standard tier limits
- POST/PUT/DELETE: 50% of tier limits

### Resource-Intensive Endpoints

#### Analytics & Reports
```
/api/v1/analytics/*
/api/v1/reports/*
```
- 100 requests per hour
- 1,000 requests per day

#### Bulk Operations
```
/api/v1/orders/bulk
/api/v1/inventory/bulk-update
```
- 10 requests per hour
- 100 requests per day

#### Export Endpoints
```
/api/v1/exports/*
/api/v1/reports/export
```
- 20 requests per hour
- 100 requests per day

### Real-time Endpoints

#### WebSocket Connections
- 5 concurrent connections per user
- 1,000 messages per minute per connection

#### Server-Sent Events
- 10 concurrent connections
- 100 events per minute

## Rate Limit Response

When rate limit is exceeded:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 3600
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1691496000

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded",
    "details": {
      "limit": 1000,
      "window": "1h",
      "retry_after": 3600
    }
  }
}
```

## Handling Rate Limits

### Exponential Backoff

Implement exponential backoff when encountering rate limits:

```python
import time
import random

def make_request_with_backoff(url, max_retries=5):
    for attempt in range(max_retries):
        response = requests.get(url)
        
        if response.status_code == 429:
            # Get retry time from header or calculate
            retry_after = int(response.headers.get('Retry-After', 60))
            
            # Add jitter to prevent thundering herd
            jitter = random.uniform(0, 10)
            wait_time = min(retry_after + jitter, 300)  # Cap at 5 minutes
            
            time.sleep(wait_time)
            continue
            
        return response
    
    raise Exception("Max retries exceeded")
```

### JavaScript Example

```javascript
async function fetchWithRateLimit(url, options = {}) {
  const maxRetries = 5;
  let lastError;

  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url, options);
      
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
        const jitter = Math.random() * 10;
        const waitTime = Math.min(retryAfter + jitter, 300) * 1000;
        
        console.log(`Rate limited. Waiting ${waitTime/1000} seconds...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
        continue;
      }
      
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  
  throw lastError || new Error('Max retries exceeded');
}
```

## Best Practices

### 1. Monitor Usage

Track your API usage to avoid hitting limits:

```http
GET /api/v1/account/usage
Authorization: Bearer {access_token}

Response:
{
  "period": "2025-08-08",
  "usage": {
    "requests": {
      "total": 5420,
      "by_endpoint": {
        "/api/v1/orders": 2100,
        "/api/v1/menu": 1500,
        "/api/v1/analytics": 820
      }
    },
    "rate_limit": {
      "tier": "professional",
      "limit": 10000,
      "remaining": 4580,
      "resets_at": "2025-08-09T00:00:00Z"
    }
  }
}
```

### 2. Batch Operations

Use batch endpoints to reduce request count:

```http
POST /api/v1/orders/batch
Content-Type: application/json

{
  "operations": [
    {"method": "GET", "path": "/orders/1001"},
    {"method": "GET", "path": "/orders/1002"},
    {"method": "GET", "path": "/orders/1003"}
  ]
}
```

### 3. Implement Caching

Cache responses to reduce API calls:

```python
import redis
import json

cache = redis.Redis()

def get_menu_items(restaurant_id):
    cache_key = f"menu:{restaurant_id}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fetch from API
    response = requests.get(f"/api/v1/menu?restaurant_id={restaurant_id}")
    data = response.json()
    
    # Cache for 5 minutes
    cache.setex(cache_key, 300, json.dumps(data))
    
    return data
```

### 4. Use Webhooks

Instead of polling, use webhooks for real-time updates:

```python
# Don't do this - polling
while True:
    orders = fetch_orders(status="new")
    process_orders(orders)
    time.sleep(10)  # Wastes API calls

# Do this - webhooks
@app.post("/webhook/order-created")
def handle_order_webhook(data):
    process_order(data["order"])
```

## Rate Limit Buckets

Rate limits are organized into buckets for different functionality:

### General API
- Bucket: `api-general`
- Covers most CRUD operations
- Standard tier limits apply

### Analytics
- Bucket: `api-analytics`
- Covers reports and analytics endpoints
- Lower limits due to resource intensity

### Bulk Operations
- Bucket: `api-bulk`
- Covers batch and import endpoints
- Strict limits to prevent abuse

### Webhooks
- Bucket: `webhooks-delivery`
- Limits webhook deliveries
- Prevents webhook storms

## Quota Management

### Checking Quotas

```http
GET /api/v1/account/quotas
Authorization: Bearer {access_token}

Response:
{
  "quotas": {
    "api_calls": {
      "used": 45000,
      "limit": 100000,
      "period": "day",
      "resets_at": "2025-08-09T00:00:00Z"
    },
    "storage": {
      "used_bytes": 1073741824,
      "limit_bytes": 10737418240,
      "percentage": 10
    },
    "restaurants": {
      "used": 5,
      "limit": 10
    },
    "users": {
      "used": 25,
      "limit": 100
    }
  }
}
```

### Quota Exceeded Response

```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Monthly API quota exceeded",
    "details": {
      "quota_type": "api_calls",
      "used": 1000000,
      "limit": 1000000,
      "resets_at": "2025-09-01T00:00:00Z"
    }
  }
}
```

## Advanced Rate Limiting

### IP-Based Limits

Additional limits based on IP address:
- 10,000 requests per hour per IP
- Applies regardless of authentication

### Concurrent Request Limits

- 10 concurrent requests per user
- 100 concurrent requests per organization

### Geographic Rate Limits

Different limits may apply based on region:
- Requests routed through edge locations
- Local rate limits for compliance

## Increasing Rate Limits

### Temporary Increase

Request temporary rate limit increase:

```http
POST /api/v1/account/rate-limit-increase
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "reason": "Black Friday sale processing",
  "requested_limit": 50000,
  "duration_hours": 48,
  "endpoints": ["/api/v1/orders", "/api/v1/payments"]
}
```

### Permanent Upgrade

- Contact sales for enterprise limits
- Custom limits based on use case
- SLA guarantees available

## Rate Limiting for Testing

### Development Environment
- Relaxed rate limits
- 10,000 requests per hour
- No quota enforcement

### Sandbox Environment
- Production-like rate limits
- Quota enforcement
- Rate limit testing endpoints

### Testing Rate Limits

```http
GET /api/v1/test/rate-limit
Authorization: Bearer {access_token}

Response:
{
  "current_usage": 150,
  "limit": 1000,
  "remaining": 850,
  "resets_in": 2400
}
```

## Monitoring & Alerts

### Usage Alerts

Configure alerts for rate limit usage:

```http
POST /api/v1/account/alerts
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "type": "rate_limit",
  "threshold_percentage": 80,
  "notification_email": "devops@restaurant.com",
  "notification_webhook": "https://alerts.restaurant.com/webhook"
}
```

### Rate Limit Dashboard

Access real-time usage dashboard:
- Current usage across all buckets
- Historical usage patterns
- Prediction of limit exhaustion
- Endpoint-specific metrics

## SDK Support

### Python SDK

```python
from auraconnect import Client, RateLimitError

client = Client(api_key="your_key")

try:
    orders = client.orders.list()
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
    time.sleep(e.retry_after)
    orders = client.orders.list()
```

### JavaScript SDK

```javascript
import { AuraConnectClient, RateLimitError } from '@auraconnect/sdk';

const client = new AuraConnectClient({ apiKey: 'your_key' });

try {
  const orders = await client.orders.list();
} catch (error) {
  if (error instanceof RateLimitError) {
    console.log(`Rate limited. Retry after ${error.retryAfter} seconds`);
    await sleep(error.retryAfter * 1000);
    const orders = await client.orders.list();
  }
}
```

## FAQs

### Q: When do rate limits reset?
A: Hourly limits reset at the top of each hour. Daily limits reset at midnight UTC.

### Q: Can I check rate limits without making a request?
A: Yes, use the `/api/v1/account/rate-limit-status` endpoint.

### Q: Are rate limits per user or per organization?
A: Rate limits apply per API key. Organization-wide limits are available in Enterprise tier.

### Q: What happens to queued requests when rate limited?
A: Requests are not queued. Clients must retry after the rate limit resets.

### Q: Do failed requests count against rate limits?
A: Yes, all requests including 4xx errors count. 5xx errors are not counted.