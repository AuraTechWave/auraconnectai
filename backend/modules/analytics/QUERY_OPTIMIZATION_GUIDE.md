# Query Optimization Guidelines for AuraConnect Analytics

This document provides comprehensive guidelines for optimizing database queries in the AuraConnect analytics module. Follow these best practices to ensure optimal performance and scalability.

## Table of Contents
1. [General Principles](#general-principles)
2. [Common Anti-Patterns and Solutions](#common-anti-patterns-and-solutions)
3. [Performance Monitoring](#performance-monitoring)
4. [Caching Strategies](#caching-strategies)
5. [Materialized Views](#materialized-views)
6. [Index Usage](#index-usage)
7. [Query Writing Best Practices](#query-writing-best-practices)
8. [Testing and Validation](#testing-and-validation)

## General Principles

### 1. Avoid N+1 Query Patterns
**Problem:** Executing additional queries for each row in a result set.

**Solution:** Use joins, subqueries, or batch loading.

```python
# BAD: N+1 Pattern
providers = db.query(Provider).all()
for provider in providers:
    # This executes a new query for each provider
    terminal_count = db.query(Terminal).filter_by(provider_id=provider.id).count()

# GOOD: Single Query with Subquery
from modules.analytics.services.optimized_queries import OptimizedAnalyticsQueries
results = OptimizedAnalyticsQueries.get_provider_summaries_optimized(db, start_date, end_date)
```

### 2. Use Appropriate Fetch Strategies
- **Lazy Loading:** Default, loads related data when accessed
- **Eager Loading:** Use `joinedload()` for one-to-many relationships
- **Subquery Loading:** Use `selectinload()` for collections

```python
# Eager load related data to prevent N+1
orders = db.query(Order).options(
    joinedload(Order.customer),
    selectinload(Order.items).joinedload(OrderItem.menu_item)
).all()
```

### 3. Limit Result Sets Early
Always filter and limit data as early as possible in the query.

```python
# Apply filters before aggregation
query = db.query(Order).filter(
    Order.created_at >= start_date,
    Order.status.in_(['completed', 'paid'])
).limit(100)
```

## Common Anti-Patterns and Solutions

### Anti-Pattern 1: Loading Entire Tables
```python
# BAD: Loads all orders into memory
all_orders = db.query(Order).all()
recent_orders = [o for o in all_orders if o.created_at > cutoff_date]

# GOOD: Filter at database level
recent_orders = db.query(Order).filter(Order.created_at > cutoff_date).all()
```

### Anti-Pattern 2: Inefficient Aggregations
```python
# BAD: Python-level aggregation
orders = db.query(Order).all()
total_revenue = sum(order.total_amount for order in orders)

# GOOD: Database-level aggregation
total_revenue = db.query(func.sum(Order.total_amount)).scalar()
```

### Anti-Pattern 3: Multiple Round Trips
```python
# BAD: Multiple queries
provider_count = db.query(Provider).count()
active_count = db.query(Provider).filter_by(is_active=True).count()
inactive_count = db.query(Provider).filter_by(is_active=False).count()

# GOOD: Single query with conditional aggregation
stats = db.query(
    func.count(Provider.id).label('total'),
    func.sum(case((Provider.is_active == True, 1), else_=0)).label('active'),
    func.sum(case((Provider.is_active == False, 1), else_=0)).label('inactive')
).first()
```

## Performance Monitoring

### Using the Query Monitor
All analytics queries should be decorated with performance monitoring:

```python
from modules.analytics.utils.query_monitor import monitor_query_performance

@monitor_query_performance("analytics.get_sales_summary")
async def get_sales_summary(self, filters):
    # Query implementation
    pass
```

### Viewing Performance Statistics
```python
from modules.analytics.utils.query_monitor import query_monitor

# Get statistics for a specific query
stats = query_monitor.get_statistics("analytics.get_sales_summary")

# Get all slow queries
slow_queries = query_monitor.get_slow_queries(limit=10)

# Generate optimization report
from modules.analytics.utils.query_monitor import QueryOptimizationHints
report = QueryOptimizationHints.generate_optimization_report()
```

## Caching Strategies

### 1. Query Result Caching
Use the `@cached_query` decorator for expensive queries:

```python
from modules.analytics.utils.cache_manager import cached_query

@cached_query("sales_metrics", ttl=600)  # Cache for 10 minutes
def get_sales_metrics(self, filters):
    # Expensive query
    pass
```

### 2. Cache Invalidation
Invalidate cache when data changes:

```python
from modules.analytics.utils.cache_manager import CacheInvalidator

# After updating sales data
await CacheInvalidator.invalidate_sales_analytics(date_range=(start_date, end_date))

# After updating POS data
await CacheInvalidator.invalidate_pos_analytics(provider_id=123)
```

### 3. Cache Warming
Proactively populate cache for frequently accessed data:

```python
from modules.analytics.utils.cache_manager import CacheWarmer

warmer = CacheWarmer(db_session)
await warmer.start_cache_warming(interval_minutes=30)
```

## Materialized Views

### Available Materialized Views
1. **mv_daily_sales_summary** - Pre-aggregated daily sales metrics
2. **mv_product_performance** - Product sales performance by day
3. **mv_hourly_sales_patterns** - Hourly sales patterns for last 90 days
4. **mv_customer_lifetime_value** - Customer segmentation and CLV
5. **mv_pos_provider_daily_summary** - POS provider daily metrics

### Using Materialized Views
```python
from modules.analytics.services.materialized_view_queries import MaterializedViewQueries

# Get daily sales from materialized view (very fast)
daily_sales = MaterializedViewQueries.get_daily_sales_summary(
    db, start_date, end_date, restaurant_id
)

# Get customer segments
segments = MaterializedViewQueries.get_customer_segments(db, restaurant_id)
```

### Refreshing Materialized Views
```python
# Refresh all views
MaterializedViewQueries.refresh_materialized_views(db)

# Refresh specific view
MaterializedViewQueries.refresh_materialized_views(db, "mv_daily_sales_summary")
```

## Index Usage

### Critical Indexes for Analytics
The following indexes have been created for optimal performance:

1. **Order Queries**
   - `idx_order_date_status` - For date range filtering
   - `idx_order_customer_date` - For customer order history
   - `idx_order_staff_date` - For staff performance

2. **POS Analytics**
   - `idx_pos_analytics_snapshot_provider_date` - Provider summaries
   - `idx_pos_terminal_health_provider_status` - Terminal health checks
   - `idx_pos_analytics_alert_provider_active` - Active alerts

3. **Product Performance**
   - `idx_order_item_product_order` - Product sales queries
   - `idx_menu_item_category` - Category aggregations

### Verifying Index Usage
Use EXPLAIN ANALYZE to verify indexes are being used:

```python
# In development, check query plans
result = db.execute(text("EXPLAIN ANALYZE SELECT ..."))
```

## Query Writing Best Practices

### 1. Use Window Functions for Rankings
```python
# Efficient ranking with window functions
query = db.query(
    Product.id,
    Product.name,
    func.sum(OrderItem.quantity).label('total_sold'),
    func.rank().over(
        order_by=func.sum(OrderItem.quantity).desc()
    ).label('sales_rank')
).group_by(Product.id, Product.name)
```

### 2. Batch Processing for Large Datasets
```python
# Process large datasets in batches
batch_size = 1000
offset = 0

while True:
    batch = query.offset(offset).limit(batch_size).all()
    if not batch:
        break
    
    process_batch(batch)
    offset += batch_size
```

### 3. Use CTEs for Complex Queries
```python
# Common Table Expression for readability
customer_stats = db.query(
    Order.customer_id,
    func.count(Order.id).label('order_count'),
    func.sum(Order.total_amount).label('total_spent')
).filter(
    Order.status == 'completed'
).group_by(Order.customer_id).cte('customer_stats')

# Use the CTE
high_value_customers = db.query(Customer).join(
    customer_stats,
    Customer.id == customer_stats.c.customer_id
).filter(customer_stats.c.total_spent > 1000)
```

## Testing and Validation

### 1. Performance Testing
```python
import time

def test_query_performance():
    start = time.time()
    results = expensive_query()
    duration = time.time() - start
    
    assert duration < 1.0  # Should complete in under 1 second
    assert len(results) > 0  # Should return results
```

### 2. Query Plan Analysis
```python
def analyze_query_plan(query):
    # Get the SQL
    sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
    
    # Get execution plan
    plan = db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}")).fetchall()
    
    # Check for sequential scans on large tables
    for line in plan:
        if 'Seq Scan' in str(line) and 'rows=' in str(line):
            # May indicate missing index
            logger.warning(f"Sequential scan detected: {line}")
```

### 3. Load Testing
Use tools like locust or artillery to test query performance under load:

```python
# locustfile.py
from locust import HttpUser, task, between

class AnalyticsUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def get_dashboard(self):
        self.client.get("/api/analytics/dashboard")
    
    @task
    def get_sales_report(self):
        self.client.get("/api/analytics/sales/summary")
```

## Monitoring and Alerts

### Set Up Query Performance Alerts
```python
# Check for slow queries periodically
async def check_slow_queries():
    stats = query_monitor.get_statistics()
    
    for query in stats['queries']:
        if query['average_time'] > 2.0:  # 2 second threshold
            # Send alert
            logger.error(f"Slow query detected: {query['query_name']} - {query['average_time']}s avg")
```

### Database Connection Pool Monitoring
```python
# Monitor connection pool usage
from sqlalchemy.pool import NullPool, QueuePool

# Log pool statistics
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.info(f"Pool size: {engine.pool.size()}, Checked out: {engine.pool.checkedout()}")
```

## Conclusion

Following these guidelines will help ensure optimal query performance in the AuraConnect analytics system. Remember to:

1. Always monitor query performance in production
2. Use caching strategically for expensive queries
3. Leverage materialized views for pre-aggregated data
4. Test query performance as part of the development process
5. Regularly review and optimize slow queries

For specific optimization help, check the query monitor statistics and use the optimization hints provided by the system.