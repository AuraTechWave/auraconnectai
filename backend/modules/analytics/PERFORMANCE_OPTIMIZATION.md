# AI Insights Performance Optimization Guide

## Database Indexes

The following indexes should be created for optimal performance. A migration script is provided at `backend/migrations/add_analytics_indexes.sql`.

### Required Indexes

```sql
-- Primary indexes for Order table
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_date_status ON orders(order_date, status);

-- Composite index for analytics queries
CREATE INDEX idx_orders_analytics ON orders(order_date, status, customer_id, staff_id);

-- Function-based indexes for time analysis
CREATE INDEX idx_orders_hour ON orders(EXTRACT(hour FROM order_date));
CREATE INDEX idx_orders_dow ON orders(EXTRACT(dow FROM order_date));

-- Partial index for completed orders
CREATE INDEX idx_orders_completed ON orders(order_date, customer_id, total_amount) 
WHERE status IN ('completed', 'paid');
```

## Cache Configuration

### Structured Cache Keys
The system uses structured cache keys to ensure consistency:
```
ai:insights:{insight_types}:{date_from}:{date_to}:{confidence_level}
```

Example:
```
ai:insights:peak_time_product_trend:2025-01-01:2025-01-29:medium
```

### Cache TTL Settings
- Default TTL: 3600 seconds (1 hour)
- Pre-generated insights: 86400 seconds (24 hours)
- Task results: 3600 seconds (1 hour)

## Performance Thresholds

### Query Performance Targets

| Analysis Type | Warning (seconds) | Critical (seconds) | Max Records |
|--------------|-------------------|-------------------|-------------|
| Peak Time Analysis | 2.0 | 5.0 | 100,000 |
| Product Trends | 3.0 | 8.0 | 50,000 |
| Customer Patterns | 4.0 | 10.0 | 200,000 |
| Anomaly Detection | 2.0 | 5.0 | 50,000 |

### Optimization Strategies

1. **For Large Date Ranges (>90 days)**
   - Use async endpoints (`/ai-insights/generate-async`)
   - Consider pre-aggregated snapshots
   - Implement date-based partitioning

2. **For High-Volume Data**
   - Enable background job processing
   - Use materialized views for common queries
   - Implement result pagination

3. **For Real-Time Requirements**
   - Pre-generate insights during off-peak hours
   - Use aggressive caching strategies
   - Consider read replicas for analytics queries

## Background Job Configuration

### Daily Pre-generation Schedule
Run at 2 AM daily to pre-generate common insights:
```python
# Cron expression: 0 2 * * *
await run_daily_insights_generation()
```

### Pre-generated Configurations
- Last 7 days comprehensive
- Last 30 days comprehensive  
- Last 14 days peak times
- Last 30 days product trends

## Monitoring and Alerts

### Performance Metrics Logging
The system logs structured metrics for monitoring:
```json
{
  "timestamp": "2025-01-29T12:00:00Z",
  "insight_type": "peak_time",
  "date_range_days": 30,
  "record_count": 5000,
  "execution_time_seconds": 1.5,
  "cache_hit": false,
  "records_per_second": 3333
}
```

### Alert Thresholds
- Slow query alert: >1 second for single analysis
- Performance warning: >5 seconds for comprehensive analysis
- Critical alert: >10 seconds or timeout

## Redis Configuration

### Recommended Settings
```
maxmemory 4gb
maxmemory-policy allkeys-lru
timeout 300
tcp-keepalive 60
```

### Connection Pool Settings
```python
REDIS_POOL_SIZE = 10
REDIS_MAX_CONNECTIONS = 50
REDIS_SOCKET_TIMEOUT = 5
REDIS_SOCKET_CONNECT_TIMEOUT = 5
```

## Query Optimization Tips

### 1. Use Selective Date Ranges
```python
# Good: Specific date range
date_from = date.today() - timedelta(days=30)
date_to = date.today()

# Avoid: Open-ended queries
date_from = None  # Defaults to 30 days, but explicit is better
```

### 2. Leverage Partial Indexes
The partial index on completed orders significantly improves performance:
```sql
-- This query uses the partial index
WHERE status IN ('completed', 'paid') AND order_date >= '2025-01-01'
```

### 3. Batch Multiple Analyses
When requesting multiple insight types, use comprehensive endpoints to batch queries:
```python
# Good: Single request for multiple insights
request = InsightRequest(
    insight_types=[InsightType.PEAK_TIME, InsightType.PRODUCT_TREND],
    date_from=start_date,
    date_to=end_date
)

# Avoid: Multiple separate requests
```

## Deployment Checklist

- [ ] Run database migration script for indexes
- [ ] Verify Redis is configured and accessible
- [ ] Set up background job scheduler
- [ ] Configure monitoring alerts
- [ ] Test with production-scale data
- [ ] Enable query logging for slow queries
- [ ] Set up performance dashboards

## Troubleshooting

### Slow Peak Time Analysis
1. Check if hourly indexes exist
2. Verify date range is reasonable (<90 days)
3. Check database connection pool settings

### Cache Misses
1. Verify Redis connectivity
2. Check cache key format
3. Monitor Redis memory usage

### Memory Issues
1. Reduce batch sizes for large queries
2. Enable streaming for exports
3. Increase worker memory limits

## Future Optimizations

1. **Materialized Views**: Pre-aggregate hourly/daily metrics
2. **Time-Series Database**: Consider TimescaleDB for time-series data
3. **Horizontal Scaling**: Implement read replicas for analytics
4. **GPU Acceleration**: For future ML model inference
5. **Column Store**: Consider columnar storage for analytics tables