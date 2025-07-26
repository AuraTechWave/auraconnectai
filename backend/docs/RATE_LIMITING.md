# API Rate Limiting

AuraConnect includes comprehensive API rate limiting to protect against abuse, ensure fair resource usage, and maintain system stability.

## Overview

The rate limiting system provides:
- **DDoS Protection**: Prevents overwhelming the server with requests
- **Fair Usage**: Ensures equitable access to API resources
- **Authentication Security**: Special limits for sensitive endpoints
- **Flexible Configuration**: Customizable limits per endpoint
- **Redis Support**: Distributed rate limiting for scaled deployments

## Configuration

### Environment Variables

```bash
# Enable/disable rate limiting
RATE_LIMIT_ENABLED=true

# Default limits
DEFAULT_RATE_LIMIT=100  # requests per minute
AUTH_RATE_LIMIT=5       # login attempts per minute

# Redis for distributed rate limiting
REDIS_URL=redis://localhost:6379
```

### Default Rate Limits

| Endpoint Category | Limit | Window | Description |
|------------------|-------|---------|-------------|
| General API | 100 req/min | 60s | Default for all endpoints |
| Authentication | 5 req/min | 60s | Login/registration attempts |
| Payroll Processing | 10 req/5min | 300s | Resource-intensive operations |
| Order Management | 200 req/min | 60s | High-frequency operations |
| Admin Operations | 20 req/min | 60s | Administrative functions |
| Health Checks | 1000 req/min | 60s | Monitoring endpoints |

## Implementation

### Memory-Based Rate Limiting

For single-instance deployments:

```python
from core.rate_limiter import MemoryRateLimiter, RateLimitRule

limiter = MemoryRateLimiter()
rule = RateLimitRule(requests=100, window=60)

allowed, retry_after = await limiter.is_allowed("client_key", rule)
```

### Redis-Based Rate Limiting

For distributed deployments:

```python
from core.rate_limiter import RedisRateLimiter

limiter = RedisRateLimiter("redis://localhost:6379")
await limiter.connect()

allowed, retry_after = await limiter.is_allowed("client_key", rule)
```

### Middleware Integration

Rate limiting is automatically applied via middleware:

```python
from core.rate_limiter import rate_limit_middleware

app.middleware("http")(rate_limit_middleware)
```

## Client Identification

Clients are identified using the following priority:

1. **Authenticated User ID**: `user:123`
2. **IP Address**: `ip:192.168.1.1`
3. **Forwarded Headers**: X-Forwarded-For, X-Real-IP

## Custom Rate Limits

### Decorator Approach

```python
from core.rate_limiter import rate_limit

@rate_limit(requests=10, window=300)  # 10 requests per 5 minutes
async def sensitive_operation():
    pass
```

### Programmatic Configuration

```python
from core.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
limiter.add_rule("/api/v1/custom", requests=50, window=60)
```

## Response Headers

Rate limit information is included in response headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Window: 60
```

When rate limited:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Window: 60

{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again in 45 seconds.",
  "retry_after": 45
}
```

## Algorithm

### Sliding Window

Uses a sliding window algorithm that:
- Tracks requests within a time window
- Allows bursts up to the limit
- Automatically expires old requests
- Provides smooth rate limiting behavior

Example with 5 requests per 60 seconds:

```
Time:    0s    20s    40s    60s    80s
Window:  [------ 60s window ------]
Requests: 2     3      0      2      1
Status:   OK    OK     OK     OK     OK

Time:    100s (6th request in current window)
Status:   BLOCKED (retry after 20s)
```

## Testing Rate Limits

### Unit Tests

```python
import pytest
from core.rate_limiter import MemoryRateLimiter, RateLimitRule

@pytest.mark.asyncio
async def test_rate_limiting():
    limiter = MemoryRateLimiter()
    rule = RateLimitRule(requests=2, window=60)
    
    # First two requests should pass
    assert (await limiter.is_allowed("test", rule))[0] is True
    assert (await limiter.is_allowed("test", rule))[0] is True
    
    # Third request should be blocked
    assert (await limiter.is_allowed("test", rule))[0] is False
```

### Integration Tests

```bash
# Test with curl
for i in {1..10}; do
  curl -w "%{http_code}\n" http://localhost:8000/api/v1/test
done

# Expected: First 5 return 200, rest return 429
```

## Monitoring

### Metrics

Track rate limiting effectiveness:

```python
# Metrics to monitor
- rate_limit_blocks_total
- rate_limit_requests_total
- rate_limit_client_counts
- rate_limit_rule_hits
```

### Logs

Rate limiting events are logged:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "WARNING",
  "message": "Rate limit exceeded",
  "client_key": "ip:192.168.1.1",
  "endpoint": "/api/v1/orders",
  "limit": 200,
  "window": 60,
  "retry_after": 30
}
```

## Production Considerations

### Redis Configuration

For production deployments with multiple instances:

```bash
# Redis cluster or sentinel for high availability
REDIS_URL=redis://redis-cluster:6379

# Connection pooling
REDIS_POOL_SIZE=10
REDIS_POOL_TIMEOUT=30
```

### Load Balancer Integration

Ensure proper client IP detection:

```nginx
# Nginx configuration
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
```

### Scaling Considerations

- **Memory Usage**: Each client key uses ~1KB memory
- **Redis Memory**: Plan for 1000 clients ≈ 1MB Redis memory
- **Performance**: Rate limiting adds ~1ms latency per request

## Troubleshooting

### Common Issues

1. **Rate Limits Too Restrictive**
   ```bash
   # Increase limits in environment
   DEFAULT_RATE_LIMIT=200
   ```

2. **Redis Connection Issues**
   ```bash
   # Check Redis connectivity
   redis-cli -u $REDIS_URL ping
   ```

3. **Incorrect Client Identification**
   ```bash
   # Verify X-Forwarded-For headers
   curl -H "X-Forwarded-For: 192.168.1.1" localhost:8000/api/test
   ```

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger("core.rate_limiter").setLevel(logging.DEBUG)
```

## Security Best Practices

1. **Authentication Limits**: Use restrictive limits for auth endpoints
2. **Progressive Penalties**: Increase delays for repeated violations
3. **Whitelist Critical IPs**: Allow unlimited access for monitoring
4. **Monitor Patterns**: Watch for suspicious request patterns
5. **Fail Safely**: Continue serving if rate limiter fails

## Future Enhancements

- **Adaptive Limits**: Adjust based on server load
- **Client Reputation**: Lower limits for problematic clients
- **Geographic Limits**: Different limits by region
- **Time-Based Rules**: Lower limits during peak hours
- **Machine Learning**: Detect and block abuse patterns

---

The rate limiting system provides robust protection while maintaining flexibility for legitimate usage patterns.