# Inventory Deduction Implementation - AUR-364

## Overview

This document describes the implementation of automatic inventory deduction when orders are completed, including support for partial fulfillment, cancellations, and comprehensive audit logging.

## Features Implemented

### 1. Automatic Inventory Deduction

- **Trigger**: Inventory is automatically deducted when an order status changes to `COMPLETED`
- **Recipe-Based**: Deduction is based on the BOM (Bill of Materials) defined in recipes
- **Recursive**: Handles sub-recipes automatically
- **Batch Processing**: Optimized for performance with bulk operations

### 2. Order Completion with Inventory

**Endpoint**: `POST /api/v1/orders/{order_id}/complete-with-inventory`

```python
# Request (optional)
{
    "skip_inventory": false,  # Skip deduction for special cases
    "force_deduction": false  # Force even if insufficient inventory
}

# Response
{
    "success": true,
    "order_id": 123,
    "status": "completed",
    "completed_at": "2025-08-06T15:00:00Z",
    "inventory_deducted": true,
    "inventory_result": {
        "success": true,
        "deducted_items": [
            {
                "inventory_id": 1,
                "item_name": "Flour",
                "quantity_deducted": 0.6,
                "unit": "kg",
                "new_quantity": 99.4
            }
        ],
        "low_stock_alerts": [],
        "items_without_recipes": [],
        "total_items_deducted": 3
    }
}
```

### 3. Order Cancellation with Reversal

**Endpoint**: `POST /api/v1/orders/{order_id}/cancel-with-inventory`

```python
# Request
{
    "reason": "Customer cancelled",
    "reverse_inventory": true  # Restore deducted inventory
}

# Response
{
    "success": true,
    "order_id": 123,
    "status": "cancelled",
    "cancelled_at": "2025-08-06T15:30:00Z",
    "inventory_reversed": true,
    "reversal_result": {
        "success": true,
        "reversed_items": [
            {
                "inventory_id": 1,
                "item_name": "Flour",
                "quantity_restored": 0.6,
                "unit": "kg",
                "new_quantity": 100.0
            }
        ],
        "total_items_reversed": 3
    }
}
```

### 4. Partial Fulfillment

**Endpoint**: `POST /api/v1/orders/{order_id}/partial-fulfillment`

```python
# Request
{
    "fulfilled_items": [
        {
            "menu_item_id": 1,
            "fulfilled_quantity": 1  # Fulfill 1 out of 2 ordered
        }
    ]
}

# Response
{
    "success": true,
    "order_id": 123,
    "fulfilled_items": [...],
    "inventory_result": {
        "success": true,
        "deducted_items": [...],
        "total_items_deducted": 3
    }
}
```

### 5. Inventory Availability Check

**Endpoint**: `GET /api/v1/orders/{order_id}/inventory-availability`

```python
# Response
{
    "can_fulfill": true,
    "impact_preview": [
        {
            "inventory_id": 1,
            "item_name": "Flour",
            "current_quantity": 100.0,
            "required_quantity": 0.6,
            "new_quantity": 99.4,
            "unit": "kg",
            "sufficient_stock": true,
            "will_be_low_stock": false,
            "recipes_using": [
                {
                    "recipe_id": 1,
                    "recipe_name": "Pizza Dough",
                    "quantity_used": 0.6
                }
            ]
        }
    ],
    "warnings": []
}
```

### 6. Manual Reversal

**Endpoint**: `POST /api/v1/orders/{order_id}/reverse-deduction?reason=Correction&force=false`

- Requires `ORDER_UPDATE` permission
- Force reversal requires `ADMIN_ACCESS` permission

## Configuration

The system behavior can be configured via environment variables:

```bash
# When to trigger deduction
INVENTORY_DEDUCTION_DEDUCTION_TRIGGER=order_completed  # order_placed, order_preparing, order_completed

# Inventory behavior
INVENTORY_DEDUCTION_ALLOW_NEGATIVE_INVENTORY=false
INVENTORY_DEDUCTION_AUTO_REVERSE_ON_CANCEL=true

# Alerts
INVENTORY_DEDUCTION_LOW_STOCK_ALERT_PERCENTAGE=20
INVENTORY_DEDUCTION_CRITICAL_STOCK_ALERT_PERCENTAGE=10

# Performance
INVENTORY_DEDUCTION_BATCH_DEDUCTION_SIZE=100
INVENTORY_DEDUCTION_USE_BULK_OPERATIONS=true
INVENTORY_DEDUCTION_CACHE_RECIPE_LOOKUPS=true
```

## Audit Trail

All inventory operations are logged with comprehensive audit trails:

### Inventory Adjustments

```sql
-- Each deduction creates an adjustment record
SELECT * FROM inventory_adjustments 
WHERE reference_type = 'order' 
AND reference_id = 123;
```

### Audit Logs

```sql
-- Detailed audit logs for compliance
SELECT * FROM audit_logs 
WHERE entity_type = 'order' 
AND action IN ('inventory_deduction', 'inventory_reversal');
```

## Error Handling

### Insufficient Inventory

```json
{
    "detail": {
        "message": "Insufficient inventory for recipe ingredients",
        "items": [
            {
                "inventory_id": 1,
                "item_name": "Flour",
                "available": 0.5,
                "required": 0.6,
                "unit": "kg"
            }
        ]
    }
}
```

### Missing Recipes

```json
{
    "inventory_result": {
        "items_without_recipes": [
            {
                "menu_item_id": 5,
                "menu_item_name": "Daily Special"
            }
        ]
    }
}
```

## Testing

Comprehensive test coverage includes:

1. **Unit Tests** (`test_inventory_deduction_integration.py`)
   - Deduction calculations
   - Reversal logic
   - Error scenarios

2. **API Tests** (`test_inventory_deduction_full.py`)
   - End-to-end workflows
   - Edge cases
   - Performance scenarios

### Running Tests

```bash
cd backend
pytest modules/orders/tests/test_inventory_deduction* -v
```

## Performance Considerations

1. **Batch Processing**: Multiple ingredients are processed in bulk
2. **Optimized Queries**: Prefetch recipes with ingredients in single query
3. **Transaction Safety**: All operations wrapped in database transactions
4. **Caching**: Recipe lookups cached for 5 minutes (configurable)

## Rollback Mechanism

The system includes comprehensive rollback support:

1. **Automatic Rollback**: On any error during deduction
2. **Manual Reversal**: Admin can reverse deductions
3. **Cancellation Reversal**: Automatic when order cancelled
4. **Audit Trail**: All reversals logged

## Future Enhancements

1. **Real-time Notifications**: Push notifications for low stock
2. **Predictive Analytics**: Forecast inventory needs
3. **Multi-location Support**: Track inventory per location
4. **External Integration**: Sync with POS systems
5. **Waste Tracking**: Integrate with waste management

## Migration Guide

1. Run database migration:
   ```bash
   alembic upgrade head
   ```

2. Ensure all active menu items have recipes defined

3. Set initial inventory levels

4. Configure environment variables

5. Test with pilot orders before full rollout