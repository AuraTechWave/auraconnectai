# Inventory Deduction Error Handling Guide

This guide documents the comprehensive error handling and logging system implemented for inventory deduction failures in the AuraConnect platform.

## Overview

The enhanced error handling system provides:
- **Custom exception classes** for specific failure scenarios
- **Structured logging** with detailed context
- **Manual review queue** for issues requiring human intervention  
- **Automatic notifications** for critical failures
- **Fallback mechanisms** to ensure order processing continuity

## Error Types and Handling

### 1. Missing Recipe Configuration

**Error Class**: `MissingRecipeError`

**When it occurs**: Menu items don't have associated recipe configurations.

**Handling**:
- Logs error with menu item details
- Creates manual review request (priority: 5)
- Marks order for review
- Notifies managers

**Example**:
```python
try:
    await service.deduct_inventory_for_order(order_items, order_id, user_id)
except MissingRecipeError as e:
    # Automatically logged and queued for review
    print(f"Missing recipes for items: {e.menu_items}")
```

### 2. Insufficient Inventory

**Error Class**: `InsufficientInventoryError`

**When it occurs**: Not enough stock to fulfill order requirements.

**Handling**:
- Logs shortage details for each item
- Creates manual review request (priority: 6)
- For high-value orders (>$500), sends critical alert
- Supports partial fulfillment if enabled

**Example**:
```python
# Enable partial fulfillment
result = await service.deduct_inventory_for_order(
    order_items=items,
    order_id=order_id,
    user_id=user_id,
    allow_partial=True
)

if result.get("partial_deduction"):
    print(f"Partially fulfilled. Skipped items: {result['skipped_due_to_insufficient_stock']}")
```

### 3. Inventory Not Found

**Error Class**: `InventoryNotFoundError`

**When it occurs**: Recipe references non-existent inventory items.

**Handling**:
- Logs missing inventory IDs
- Creates high-priority manual review (priority: 8)
- Indicates data integrity issue

### 4. Recipe Circular Dependency

**Error Class**: `RecipeLoopError`

**When it occurs**: Recipes contain circular sub-recipe references.

**Handling**:
- Logs the circular dependency chain
- Creates manual review (priority: 7)
- Prevents infinite recursion

### 5. Concurrent Deduction

**Error Class**: `ConcurrentDeductionError`

**When it occurs**: Multiple attempts to deduct inventory for the same order.

**Handling**:
- Prevents double deduction
- Logs existing adjustment IDs
- Skips duplicate processing

### 6. External System Sync Conflict

**Error Class**: `InventorySyncError`

**When it occurs**: Attempting to modify inventory already synced to external systems.

**Handling**:
- Blocks modification unless forced
- Creates high-priority review (priority: 8)
- Requires admin override

## Logging System

### Structured Logging

All inventory operations use structured logging with contextual data:

```python
from ..utils.inventory_logging import InventoryLogger

logger = InventoryLogger()

# Log deduction start
logger.log_deduction_start(
    order_id=123,
    user_id=456,
    order_items=items,
    deduction_type="order_completion"
)

# Log success with metrics
logger.log_deduction_success(
    order_id=123,
    deducted_items=deducted,
    low_stock_alerts=alerts,
    processing_time_ms=150.5
)
```

### Log Events

- `deduction_start` - Operation initiated
- `deduction_success` - Successful completion
- `deduction_error` - Operation failed
- `insufficient_inventory` - Stock shortage detected
- `missing_recipe` - Recipe configuration missing
- `inventory_not_found` - Invalid inventory reference
- `concurrent_deduction` - Duplicate attempt blocked
- `low_stock_alert` - Inventory below threshold
- `manual_review_required` - Human intervention needed
- `reversal_start` - Reversal initiated
- `reversal_success` - Reversal completed

### Operation Decorator

Use the `@log_inventory_operation` decorator for automatic logging:

```python
@log_inventory_operation("custom_operation")
async def my_inventory_function(order_id: int, user_id: int):
    # Automatically logs start, completion, and errors
    pass
```

## Manual Review System

### Creating Review Requests

Reviews are automatically created for errors, but can also be created manually:

```python
from ..services.manual_review_service import ManualReviewService
from ..models.manual_review_models import ReviewReason

review_service = ManualReviewService(db)

review = await review_service.create_review_request(
    order_id=order_id,
    reason=ReviewReason.MISSING_RECIPE,
    error=error,
    priority=7  # 0-10, higher = more urgent
)
```

### Review Workflow

1. **Pending** - Initial state, awaiting assignment
2. **In Review** - Assigned to a user
3. **Resolved** - Issue addressed
4. **Escalated** - Requires higher authority
5. **Cancelled** - No longer relevant

### API Endpoints

```bash
# Get pending reviews
GET /api/manual-reviews/pending?priority_threshold=5

# Assign review
POST /api/manual-reviews/{review_id}/assign
{
    "assignee_id": 123
}

# Resolve review
POST /api/manual-reviews/{review_id}/resolve
{
    "resolution_action": "manually_added_recipe",
    "notes": "Created recipe configuration for Pizza item",
    "mark_order_completed": true
}

# Escalate review
POST /api/manual-reviews/{review_id}/escalate
{
    "escalation_reason": "Requires system configuration change"
}

# Get review statistics
GET /api/manual-reviews/statistics?start_date=2025-01-01
```

## Notification System

### Automatic Notifications

1. **Low Stock Alerts**
   - Sent to: `inventory_manager` role
   - Trigger: Inventory falls below threshold
   - Priority: High if <50% of threshold

2. **Critical Alerts**
   - Sent to: `admin` and `manager` roles
   - Triggers:
     - High-value order failures (>$500)
     - System configuration issues
     - Data integrity problems

3. **Manual Review Notifications**
   - Sent to: `manager` role
   - Trigger: New review request created
   - Priority: Based on review priority

### Custom Notifications

```python
from core.notification_service import NotificationService

notification_service = NotificationService(db)

# Role-based notification
await notification_service.send_role_notification(
    role="manager",
    subject="Urgent: Inventory Issue",
    message="Multiple orders failing due to stock shortage",
    priority="urgent"
)

# Critical system alert
await notification_service.send_critical_alert(
    alert_type="inventory_failure",
    message="System-wide inventory sync failure",
    affected_resources=[
        {"type": "inventory", "id": 123, "name": "Flour"}
    ]
)
```

## Configuration

### Enable/Disable Features

```python
# In recipe_inventory_service_enhanced.py

# Allow partial order fulfillment
result = await service.deduct_inventory_for_order(
    order_items=items,
    order_id=order_id,
    user_id=user_id,
    allow_partial=True,  # Default: False
    create_review_on_failure=True  # Default: True
)

# Force inventory reversal despite sync
result = await service.reverse_inventory_deduction(
    order_id=order_id,
    user_id=user_id,
    reason="Admin override",
    force=True  # Default: False
)
```

### Logging Configuration

```python
import logging

# Set log level
logging.getLogger("inventory_deduction").setLevel(logging.DEBUG)

# Add custom handler
handler = logging.FileHandler("inventory_errors.log")
logging.getLogger("inventory_deduction").addHandler(handler)
```

## Best Practices

1. **Always handle specific exceptions** rather than generic exceptions
2. **Use structured logging** for better searchability and monitoring
3. **Set appropriate priorities** for manual reviews (0-10 scale)
4. **Include context** in error messages and logs
5. **Test error scenarios** thoroughly
6. **Monitor review queue** metrics regularly
7. **Document resolution actions** in review notes

## Migration Guide

To migrate from the old service to the enhanced version:

1. Update imports:
   ```python
   # Old
   from ..services.recipe_inventory_service import RecipeInventoryService
   
   # New
   from ..services.recipe_inventory_service_enhanced import RecipeInventoryServiceEnhanced
   ```

2. Handle new exceptions:
   ```python
   try:
       result = await service.deduct_inventory_for_order(...)
   except InsufficientInventoryError as e:
       # Handle insufficient stock
       pass
   except MissingRecipeError as e:
       # Handle missing recipes
       pass
   except InventoryDeductionError as e:
       # Handle other inventory errors
       pass
   ```

3. Run database migration:
   ```bash
   alembic upgrade head
   ```

4. Configure notification endpoints in your notification service

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Manual Review Queue**
   - Pending review count
   - Average resolution time
   - Escalation rate

2. **Error Rates**
   - Missing recipe errors/hour
   - Insufficient stock errors/hour
   - Failed deduction attempts

3. **Performance**
   - Average deduction time
   - Concurrent deduction conflicts
   - Low stock alert frequency

### Dashboard Queries

```sql
-- High priority reviews pending
SELECT COUNT(*) FROM manual_review_queue 
WHERE status = 'pending' AND priority >= 7;

-- Average resolution time (hours)
SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600)
FROM manual_review_queue 
WHERE status = 'resolved';

-- Most common error reasons
SELECT reason, COUNT(*) as count
FROM manual_review_queue
GROUP BY reason
ORDER BY count DESC;
```

## Troubleshooting

### Common Issues

1. **Reviews not being created**
   - Check `create_review_on_failure` parameter
   - Verify database migrations ran successfully
   - Check notification service configuration

2. **Duplicate deduction attempts**
   - Verify order status transitions
   - Check for race conditions in order processing
   - Review concurrent request handling

3. **Performance degradation**
   - Monitor database query performance
   - Check for lock contention
   - Review logging volume

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or for specific module
logging.getLogger("inventory_deduction").setLevel(logging.DEBUG)
logging.getLogger("manual_review").setLevel(logging.DEBUG)
```