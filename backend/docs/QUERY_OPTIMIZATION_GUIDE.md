# Query Optimization Guide

This guide documents query optimization patterns and best practices for the AuraConnect AI backend to prevent N+1 queries and improve database performance.

## Table of Contents
1. [N+1 Query Problem](#n1-query-problem)
2. [Eager Loading Strategies](#eager-loading-strategies)
3. [Caching Implementation](#caching-implementation)
4. [Query Logging & Monitoring](#query-logging--monitoring)
5. [Performance Testing](#performance-testing)
6. [Best Practices](#best-practices)

## N+1 Query Problem

### What is the N+1 Query Problem?

The N+1 query problem occurs when code executes 1 query to fetch a list of records, then N additional queries to fetch related data for each record. This creates significant performance issues as the dataset grows.

### Example of N+1 Problem
```python
# BAD: This causes N+1 queries
orders = db.query(Order).all()  # 1 query
for order in orders:
    print(order.customer.name)  # N queries (one per order)
```

### Solution
```python
# GOOD: Use eager loading
orders = db.query(Order).options(
    joinedload(Order.customer)
).all()  # 1 query with JOIN
for order in orders:
    print(order.customer.name)  # No additional queries
```

## Eager Loading Strategies

SQLAlchemy provides several eager loading techniques:

### 1. joinedload()
Use for one-to-one and many-to-one relationships.

```python
# Load orders with their customers
query = db.query(Order).options(
    joinedload(Order.customer)
)
```

### 2. selectinload()
Use for one-to-many and many-to-many relationships to avoid cartesian products.

```python
# Load customers with their orders
query = db.query(Customer).options(
    selectinload(Customer.orders)
)
```

### 3. Nested Eager Loading
Load multiple levels of relationships.

```python
# Load orders with customers and their addresses
query = db.query(Order).options(
    joinedload(Order.customer).joinedload(Customer.addresses)
)
```

### 4. Batch Loading Pattern
For complex scenarios, load related data in batches.

```python
# Batch load menu items
item_ids = [item_id for item_id, _, _ in item_counts]
menu_items = db.query(MenuItem).options(
    joinedload(MenuItem.category)
).filter(
    MenuItem.id.in_(item_ids)
).all()

# Create mapping for O(1) lookup
menu_item_map = {item.id: item for item in menu_items}
```

## Caching Implementation

### Cache Service Usage

The cache service provides automatic query result caching with Redis.

#### Basic Caching
```python
from core.cache_service import cached, cache_service

@cached("customer_orders", ttl=600)  # Cache for 10 minutes
def get_customer_orders(customer_id: int):
    return db.query(Order).filter(
        Order.customer_id == customer_id
    ).all()
```

#### Cache Invalidation
```python
from core.cache_service import invalidate_on_change

@invalidate_on_change("customer:*", "orders:*")
def update_customer(customer_id: int, data: dict):
    # Update customer
    # Cache automatically invalidated
    pass
```

#### Manual Cache Control
```python
# Invalidate specific patterns
cache_service.delete_pattern("customer:123:*")

# Skip cache for specific call
orders = get_customer_orders(customer_id, skip_cache=True)
```

### Cache Key Patterns

- `customer:{id}:*` - Customer-specific data
- `orders:list:*` - Order list queries
- `menu:*` - Menu-related data
- `staff:schedule:*` - Staff schedules

## Query Logging & Monitoring

### Development Configuration

Enable query logging in development by setting environment variables:

```bash
# .env file
LOG_SQL_QUERIES=true
DEBUG=true
ENVIRONMENT=development
```

### Using Query Logger

```python
from core.query_logger import log_query_performance, analyze_n_plus_one

# Log performance of specific operations
with log_query_performance("fetch_customer_orders"):
    orders = db.query(Order).all()
    # Logs: Operation 'fetch_customer_orders': X queries in Y.YYYs

# Decorator for automatic N+1 detection
@analyze_n_plus_one(threshold=10)
def get_orders_with_items():
    # Function that might have N+1 issues
    # Warns if > 10 queries executed
    pass
```

### Query Statistics

The query logger tracks:
- Total number of queries
- Slow queries (> 1 second)
- Queries by table
- Average query time

## Performance Testing

### Running Performance Tests

```bash
pytest backend/tests/test_query_performance.py -v
```

### Writing Performance Tests

```python
def test_no_n_plus_one(db_session, query_counter):
    # Setup test data
    create_test_data(db_session)
    
    # Reset counter
    query_counter.reset()
    
    # Execute code
    result = your_function(db_session)
    
    # Assert query count
    assert query_counter.count <= expected_count
    
    # Test relationship access
    query_counter.reset()
    for item in result:
        _ = item.relationship.field
    
    assert query_counter.count == 0  # No N+1
```

## Best Practices

### 1. Always Use Eager Loading for Known Relationships

```python
# In service functions
def get_orders_service(db: Session, **kwargs):
    query = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.order_items),
        joinedload(Order.category)
    )
    return query.all()
```

### 2. Use Pagination

```python
# Paginate large result sets
query = query.offset(offset).limit(limit)
```

### 3. Select Only Required Columns

```python
# Use load_only for large tables
query = db.query(Customer).options(
    joinedload(Customer.notifications).load_only(
        'id', 'type', 'status', 'created_at'
    )
)
```

### 4. Index Foreign Keys

```sql
-- Always index foreign key columns
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
```

### 5. Monitor Query Performance

```python
# Use context managers in critical paths
with log_query_performance("critical_operation"):
    # Your code here
    pass
```

### 6. Cache Expensive Queries

```python
@cached("expensive_aggregation", ttl=3600)
def get_sales_report(start_date, end_date):
    # Complex aggregation query
    return results
```

### 7. Batch Operations

```python
# BAD: Individual queries
for item_id in item_ids:
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()

# GOOD: Batch query
items = db.query(MenuItem).filter(MenuItem.id.in_(item_ids)).all()
item_map = {item.id: item for item in items}
```

## Common Patterns

### Pattern 1: List Endpoint with Relationships

```python
def get_items_with_relationships(db: Session, params):
    # Base query with eager loading
    query = db.query(Model).options(
        joinedload(Model.relationship1),
        joinedload(Model.relationship2)
    )
    
    # Apply filters
    query = apply_filters(query, params)
    
    # Count before pagination
    total = query.count()
    
    # Paginate
    items = query.offset(params.offset).limit(params.limit).all()
    
    return items, total
```

### Pattern 2: Detail Endpoint with Nested Data

```python
def get_item_detail(db: Session, item_id: int):
    item = db.query(Model).options(
        joinedload(Model.relationship1),
        selectinload(Model.relationship2).selectinload(
            Relationship2.nested_relationship
        )
    ).filter(Model.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404)
    
    return item
```

### Pattern 3: Aggregation with Caching

```python
@cached("aggregation_result", ttl=1800)
def get_aggregated_data(db: Session, filters):
    result = db.query(
        func.count(Model.id).label('count'),
        func.sum(Model.amount).label('total')
    ).filter(
        apply_filters(filters)
    ).first()
    
    return {
        'count': result.count,
        'total': float(result.total or 0)
    }
```

## Troubleshooting

### Detecting N+1 Queries

1. Enable query logging in development
2. Look for repeated similar queries
3. Use the query counter in tests
4. Monitor slow query logs

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Cartesian product with joinedload | Use selectinload for one-to-many |
| Cache invalidation too aggressive | Use specific key patterns |
| Slow count queries | Consider approximate counts or caching |
| Memory issues with large datasets | Use pagination and limit eager loading depth |

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/db
LOG_SQL_QUERIES=true  # Enable SQL logging

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Development
DEBUG=true
ENVIRONMENT=development
```

## Monitoring Checklist

- [ ] Query count per endpoint < 10
- [ ] No endpoints with O(n) query patterns
- [ ] Response time < 200ms for list endpoints
- [ ] Response time < 100ms for detail endpoints
- [ ] Cache hit rate > 80% for read-heavy endpoints
- [ ] Slow query log reviewed weekly
- [ ] Database indexes optimized

## References

- [SQLAlchemy Eager Loading](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html)
- [Redis Caching Best Practices](https://redis.io/docs/manual/patterns/)
- [PostgreSQL Query Optimization](https://www.postgresql.org/docs/current/performance-tips.html)