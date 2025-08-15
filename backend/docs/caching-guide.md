# Redis Caching Guide for AuraConnect AI

## Overview

The AuraConnect AI platform implements a comprehensive Redis caching strategy to improve performance, reduce database load, and provide better response times. This guide covers the caching patterns, best practices, and implementation details.

## Architecture

### Components

1. **Redis Client** (`redis_client.py`)
   - Connection pooling with 50 max connections
   - Automatic retry on timeout
   - Health check intervals
   - Singleton pattern for connection reuse

2. **Cache Manager** (`cache_manager.py`)
   - Centralized cache management
   - Namespace isolation
   - TTL management
   - Statistics tracking

3. **Decorators** (`decorators.py`)
   - Function-level caching
   - Automatic key generation
   - Tenant and user awareness
   - Cache invalidation

4. **Cache Warmer** (`cache_warmer.py`)
   - Pre-populate frequently accessed data
   - Parallel warming support
   - Scheduled warming capabilities

5. **Monitoring** (`monitoring.py`)
   - Performance metrics
   - Health checks
   - Slow operation tracking
   - Comprehensive reporting

## Cache Types and TTLs

| Cache Type | TTL | Use Case |
|------------|-----|----------|
| Menu Items | 1 hour | Menu items, categories, recipes |
| User Permissions | 5 minutes | User roles, permissions, access control |
| Restaurant Settings | 10 minutes | Configuration, timezone, currency |
| Analytics Aggregations | 5 minutes | Reports, metrics, aggregated data |
| API Response | 1 minute | General API responses |
| Search Results | 3 minutes | Search queries, filters |
| Report Data | 15 minutes | Generated reports, exports |
| Static Content | 24 hours | Images, files, rarely changing data |

## Usage Patterns

### 1. Basic Caching with Decorators

```python
from core.cache.decorators import cache_menu, cache_permissions

@cache_menu()
def get_menu_items(restaurant_id: int):
    """Automatically cached for 1 hour"""
    return db.query(MenuItem).filter_by(
        restaurant_id=restaurant_id,
        is_active=True
    ).all()

@cache_permissions()
def get_user_permissions(user_id: int):
    """Automatically cached for 5 minutes"""
    user = db.query(User).get(user_id)
    return user.get_permissions()
```

### 2. Custom TTL and Cache Type

```python
from core.cache.decorators import cache
from core.cache.cache_manager import CacheTTL

@cache(cache_type="analytics", ttl=300)
def get_daily_revenue(restaurant_id: int, date: datetime):
    """Custom cache with 5-minute TTL"""
    return calculate_revenue(restaurant_id, date)

@cache(cache_type="api", ttl=CacheTTL.API_RESPONSE)
def get_customer_list(restaurant_id: int, page: int = 1):
    """Using predefined TTL enum"""
    return paginate_customers(restaurant_id, page)
```

### 3. Tenant-Aware Caching

```python
@cache(cache_type="settings", tenant_aware=True)
def get_restaurant_settings(restaurant_id: int):
    """Cache key includes tenant ID for isolation"""
    return db.query(RestaurantSettings).filter_by(
        restaurant_id=restaurant_id
    ).first()
```

### 4. User-Aware Caching

```python
@cache(cache_type="permissions", user_aware=True)
def get_user_dashboard(user_id: int):
    """Cache key includes user ID for personalization"""
    return build_dashboard(user_id)
```

### 5. Cache Invalidation

```python
from core.cache.decorators import invalidate_cache

@invalidate_cache("menu")
def update_menu_item(item_id: int, restaurant_id: int, data: dict):
    """Automatically invalidates menu cache after update"""
    item = db.query(MenuItem).get(item_id)
    item.update(data)
    db.commit()
    return item

# Manual invalidation
from core.cache.cache_manager import cache_manager

def bulk_update_menu(restaurant_id: int):
    # Perform updates
    update_all_items(restaurant_id)
    
    # Invalidate all menu cache for restaurant
    cache_manager.invalidate_menu(restaurant_id)
```

### 6. Cache-Aside Pattern

```python
from core.cache.cache_manager import cache_manager

def get_expensive_calculation(key: str):
    """Manual cache-aside pattern"""
    # Try to get from cache
    result = cache_manager.get("analytics", key)
    
    if result is None:
        # Cache miss - calculate and store
        result = perform_expensive_calculation()
        cache_manager.set("analytics", key, result, ttl=300)
    
    return result
```

### 7. Cache Warming

```python
from core.cache.cache_warmer import CacheWarmer

def warm_cache_for_restaurant(restaurant_id: int):
    """Pre-populate cache for a restaurant"""
    db = get_db()
    warmer = CacheWarmer(db)
    
    # Warm specific cache types
    warmer.warm_menu_cache(tenant_id=restaurant_id)
    warmer.warm_settings_cache(tenant_id=restaurant_id)
    
    # Or warm all caches
    warmer.warm_all(tenant_id=restaurant_id, parallel=True)

# Schedule periodic warming
from core.cache.cache_warmer import schedule_cache_warming

# Warm cache every 30 minutes
schedule_cache_warming(tenant_id=restaurant_id, interval_minutes=30)
```

## Best Practices

### 1. Key Naming Conventions

- Use hierarchical keys: `type:tenant:entity:id`
- Include tenant ID for multi-tenancy: `menu:t1:item:123`
- Include user ID for personalization: `dashboard:u5:widgets`
- Use consistent separators (colons)

### 2. TTL Selection

- **Short TTL (< 5 min)**: Frequently changing data, user permissions
- **Medium TTL (5-60 min)**: Menu items, settings, aggregations
- **Long TTL (> 1 hour)**: Static content, historical data
- **No TTL**: Use with extreme caution, only for permanent data

### 3. Cache Invalidation Strategies

- **Time-based**: Use appropriate TTLs
- **Event-based**: Invalidate on create/update/delete
- **Pattern-based**: Invalidate groups of keys
- **Manual**: For complex scenarios

### 4. Memory Management

- Monitor memory usage with cache monitoring
- Set max memory policy in Redis config
- Use eviction policies (LRU recommended)
- Regularly review and adjust TTLs

### 5. Error Handling

```python
from core.cache.decorators import cache

@cache(cache_type="api", ttl=60)
def get_data_with_fallback(id: int):
    try:
        return fetch_from_database(id)
    except Exception as e:
        # Cache will not store None/exceptions
        logger.error(f"Failed to fetch data: {e}")
        return get_default_data()
```

### 6. Cache Monitoring

```python
from core.cache.monitoring import cache_monitor

# Get cache metrics
metrics = cache_monitor.get_metrics(
    cache_type="menu",
    last_minutes=60
)

# Check cache health
health = cache_monitor.check_health()
if health['status'] != 'healthy':
    alert_ops_team(health['issues'])

# Get comprehensive report
report = cache_monitor.get_cache_report()
```

## Performance Optimization

### 1. Batch Operations

```python
from core.cache.cache_manager import cache_manager

# Get multiple values at once
keys = ["item1", "item2", "item3"]
values = cache_manager.caches["menu"].mget(keys)

# Set multiple values at once
data = {
    "item1": {"name": "Pizza"},
    "item2": {"name": "Burger"},
    "item3": {"name": "Salad"}
}
cache_manager.caches["menu"].mset(data, ttl=3600)
```

### 2. Pipeline Operations

```python
from core.cache.redis_client import RedisClient

client = RedisClient.get_client()
pipe = client.pipeline()

# Queue multiple operations
for item_id in item_ids:
    pipe.get(f"menu:item:{item_id}")

# Execute all at once
results = pipe.execute()
```

### 3. Connection Pool Tuning

```python
# In redis_client.py, adjust pool settings:
pool_kwargs = {
    'max_connections': 50,  # Increase for high concurrency
    'socket_timeout': 5,     # Adjust based on network
    'retry_on_timeout': True,
    'health_check_interval': 30
}
```

## Troubleshooting

### Common Issues

1. **High Cache Miss Rate**
   - Review TTL values
   - Check cache warming schedule
   - Verify key generation logic

2. **Memory Issues**
   - Monitor Redis memory usage
   - Review eviction policy
   - Reduce TTLs for large objects

3. **Connection Errors**
   - Check Redis server status
   - Verify network connectivity
   - Review connection pool settings

4. **Slow Operations**
   - Use cache monitoring to identify slow keys
   - Consider data structure optimization
   - Review serialization method

### Debug Logging

```python
import logging

# Enable debug logging for cache operations
logging.getLogger('core.cache').setLevel(logging.DEBUG)

# This will show:
# - Cache hits/misses
# - Key generation
# - Invalidation operations
# - Error details
```

## Testing

### Unit Testing with Mocks

```python
from unittest.mock import patch
from core.cache.decorators import cache

@patch('core.cache.cache_manager.cache_manager')
def test_cached_function(mock_manager):
    mock_manager.get.return_value = {"cached": "data"}
    
    @cache(cache_type="test")
    def get_data():
        return {"fresh": "data"}
    
    result = get_data()
    assert result == {"cached": "data"}
```

### Integration Testing

```python
import pytest
from core.cache.cache_manager import cache_manager

@pytest.fixture
def clear_cache():
    """Clear cache before and after test"""
    cache_manager.caches["test"].clear_namespace()
    yield
    cache_manager.caches["test"].clear_namespace()

def test_cache_integration(clear_cache):
    key = "test:key"
    value = {"test": "data"}
    
    # Test set and get
    cache_manager.set("test", key, value, ttl=60)
    result = cache_manager.get("test", key)
    assert result == value
```

## Migration Guide

### Adding Caching to Existing Endpoints

1. **Identify Candidates**
   - Frequently accessed data
   - Expensive queries
   - Static or slowly changing data

2. **Add Decorator**
   ```python
   # Before
   def get_menu_items(restaurant_id: int):
       return db.query(MenuItem).filter_by(
           restaurant_id=restaurant_id
       ).all()
   
   # After
   @cache_menu()
   def get_menu_items(restaurant_id: int):
       return db.query(MenuItem).filter_by(
           restaurant_id=restaurant_id
       ).all()
   ```

3. **Add Invalidation**
   ```python
   @invalidate_cache("menu")
   def update_menu_item(item_id: int, data: dict):
       # Update logic
   ```

4. **Test and Monitor**
   - Verify cache hits
   - Monitor performance improvement
   - Adjust TTLs as needed

## Security Considerations

1. **Sensitive Data**
   - Never cache passwords or tokens
   - Be cautious with PII
   - Use encryption for sensitive cached data

2. **Access Control**
   - Include user/tenant IDs in cache keys
   - Validate permissions before serving cached data
   - Clear user cache on logout

3. **Redis Security**
   - Use password authentication
   - Enable SSL/TLS for connections
   - Restrict network access
   - Regular security updates

## Conclusion

The Redis caching implementation in AuraConnect AI provides a robust, scalable solution for improving application performance. By following the patterns and best practices outlined in this guide, developers can effectively leverage caching to build responsive, efficient features while maintaining data consistency and security.