# Customer Lifetime Value (CLV) Calculation

## Overview

Customer Lifetime Value (CLV) represents the total monetary value a customer brings to the business over their entire relationship. In AuraConnect, CLV is tracked separately from `total_spent` to account for refunds and adjustments.

## Key Fields

- **`total_spent`**: The sum of all completed/delivered orders. This is recalculated from order data and represents gross revenue. **This value is NEVER reduced by refunds.**
- **`lifetime_value`**: The net value after accounting for refunds and adjustments. This is the true CLV metric. Calculated as: `total_spent - total_refunds`

## Calculation Logic

### Order Completion
When an order is completed:
1. Loyalty points are awarded based on the order total
2. Customer statistics are updated via `update_customer_order_stats()`
3. Both `total_spent` and `lifetime_value` are synchronized

### Partial Refunds
When a partial refund is processed:
1. The refund amount is deducted ONLY from `lifetime_value` (NOT from `total_spent`)
2. Loyalty points are proportionally reversed if applicable
3. The difference between `total_spent` and `lifetime_value` represents total refunds issued

### Statistics Update
When `update_customer_order_stats()` is called:
1. `total_spent` is recalculated from all completed/delivered orders
2. The total refunds are calculated as: `current_total_spent - current_lifetime_value`
3. `lifetime_value` is updated as: `new_total_spent - total_refunds`

## Implementation Details

### Bug Fixes Applied

#### Bug 1: Refund Metrics Update Error
**Issue**: Customer financial metrics were only updated when loyalty points were reversed.
**Fix**: Moved `total_spent` and `lifetime_value` adjustments outside the points conditional block.

```python
# Only adjust lifetime_value for refunds, NOT total_spent
if customer.lifetime_value is None:
    customer.lifetime_value = float(customer.total_spent) if customer.total_spent else 0.0
customer.lifetime_value = max(0, float(customer.lifetime_value) - refund_amount)
```

#### Bug 2: CLV Overwrites Refund Adjustments
**Issue**: `update_customer_order_stats()` was overwriting `lifetime_value` with `total_spent`, losing refund history.
**Fix**: Calculate and preserve refund adjustments when updating statistics.

```python
# Calculate total refunds from the difference
total_refunds = current_total_spent - current_lifetime_value
# Update total_spent from orders
customer.total_spent = new_total_spent
# Apply refunds to get lifetime_value
customer.lifetime_value = new_total_spent - total_refunds
```

## Usage Examples

### Processing a Refund
```python
# Process a $30 partial refund
loyalty_integration.handle_partial_refund(order_id=123, refund_amount=30.0)
```

### Updating Customer Statistics
```python
# Update stats while preserving refund history
order_history_service.update_customer_order_stats(customer_id=456)
```

## Best Practices

1. **Always use `lifetime_value` for CLV reporting** - This reflects the true customer value after refunds
2. **Call `update_customer_order_stats()` after order status changes** - Ensures statistics stay current
3. **Handle refunds through the loyalty integration** - Maintains consistency across points and financial metrics
4. **Monitor the difference between `total_spent` and `lifetime_value`** - This indicates total refunds issued

## Database Schema

```sql
-- Customer table relevant fields
lifetime_value NUMERIC(12, 2) NOT NULL DEFAULT 0,  -- Net value after refunds
total_spent FLOAT DEFAULT 0.0,                      -- Gross order totals (never reduced)
total_orders INTEGER DEFAULT 0,
average_order_value FLOAT DEFAULT 0.0

-- Check constraint to ensure data integrity
ALTER TABLE customers ADD CONSTRAINT ck_lifetime_value_not_greater_than_total_spent 
CHECK (lifetime_value <= total_spent);
```

### Migration for Existing Data

For existing customers with null `lifetime_value`:
```sql
UPDATE customers 
SET lifetime_value = COALESCE(total_spent, 0.0)
WHERE lifetime_value IS NULL;
```

## Testing

Comprehensive tests are available in:
- `/tests/test_customer_lifetime_value.py` - Unit tests for CLV calculation
- `/modules/customers/tests/test_clv_refund_integration.py` - Integration tests

Key test scenarios:
- Partial refunds with and without loyalty points
- Multiple orders with multiple refunds
- Order status changes and soft deletes
- Concurrent refund handling
- Performance with large datasets

## Monitoring and Analytics

### Key Metrics to Track
- Average CLV by customer tier
- CLV to Customer Acquisition Cost (CAC) ratio
- Refund rate impact on CLV
- CLV trends over time

### SQL Query Examples

```sql
-- Customer refund analysis
SELECT 
    COUNT(*) as customer_count,
    AVG(total_spent) as avg_gross_revenue,
    AVG(lifetime_value) as avg_net_revenue,
    AVG(total_spent - lifetime_value) as avg_refunds_per_customer
FROM customers
WHERE status = 'active';

-- High-value customers with significant refunds
SELECT 
    id, 
    email,
    total_spent,
    lifetime_value,
    (total_spent - lifetime_value) as total_refunds,
    ((total_spent - lifetime_value) / total_spent * 100) as refund_percentage
FROM customers
WHERE total_spent > 1000
    AND (total_spent - lifetime_value) > 100
ORDER BY refund_percentage DESC;
```

## Future Enhancements

1. **Predictive CLV** - Use ML models to predict future customer value
2. **Cohort Analysis** - Track CLV by customer acquisition cohorts
3. **Churn Prevention** - Flag customers with declining CLV trends
4. **Segmentation** - Automatic customer segmentation based on CLV tiers