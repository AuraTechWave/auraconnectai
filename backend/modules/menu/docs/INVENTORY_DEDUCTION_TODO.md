# Inventory Deduction Integration - TODO

## Overview

This document outlines the future integration between the Recipe Management system and automatic inventory deduction when orders are completed.

## Current State

The Recipe Management system is fully implemented with:
- Complete ingredient tracking for each menu item
- Accurate quantity specifications
- Sub-recipe support
- Cost calculations

However, inventory deduction is not yet automated when orders are placed.

## Proposed Integration

### 1. Order Completion Hook

When an order is marked as completed in the Orders module:

```python
# In orders/services/order_service.py
def complete_order(self, order_id: int):
    order = self.get_order(order_id)
    
    # Existing order completion logic
    order.status = OrderStatus.COMPLETED
    
    # NEW: Trigger inventory deduction
    inventory_service.deduct_for_order(order)
```

### 2. Inventory Deduction Service

Create a new service method to handle deductions:

```python
# In inventory/services/inventory_service.py
def deduct_for_order(self, order: Order):
    """Deduct inventory based on order items and their recipes"""
    
    for order_item in order.items:
        # Get recipe for menu item
        recipe = recipe_service.get_recipe_by_menu_item(order_item.menu_item_id)
        
        if recipe and recipe.status == RecipeStatus.ACTIVE:
            # Deduct each ingredient
            for ingredient in recipe.ingredients:
                quantity_to_deduct = ingredient.quantity * order_item.quantity
                
                # Create inventory adjustment
                adjustment = InventoryAdjustment(
                    inventory_id=ingredient.inventory_id,
                    adjustment_type=AdjustmentType.SALE,
                    quantity_adjusted=-quantity_to_deduct,
                    reference_type="order",
                    reference_id=str(order.id),
                    reason=f"Order #{order.order_number} - {order_item.menu_item.name}"
                )
                
                # Update inventory quantity
                inventory_item.quantity -= quantity_to_deduct
                
                # Check for low stock alerts
                if inventory_item.quantity <= inventory_item.threshold:
                    create_low_stock_alert(inventory_item)
```

### 3. Sub-Recipe Handling

Recursively process sub-recipes:

```python
def deduct_recipe_ingredients(self, recipe: Recipe, quantity_multiplier: float, order_reference: str):
    """Recursively deduct ingredients including sub-recipes"""
    
    # Deduct direct ingredients
    for ingredient in recipe.ingredients:
        deduct_inventory(
            ingredient.inventory_id,
            ingredient.quantity * quantity_multiplier,
            order_reference
        )
    
    # Process sub-recipes
    for sub_recipe_link in recipe.sub_recipes:
        sub_recipe = sub_recipe_link.sub_recipe
        sub_quantity = sub_recipe_link.quantity * quantity_multiplier
        
        # Recursive call
        deduct_recipe_ingredients(sub_recipe, sub_quantity, order_reference)
```

### 4. Transaction Safety

Implement proper transaction handling:

```python
def complete_order_with_inventory(self, order_id: int):
    """Complete order and deduct inventory in a single transaction"""
    
    with self.db.begin():
        try:
            # Complete order
            order = complete_order(order_id)
            
            # Deduct inventory
            deduct_for_order(order)
            
            # Create audit log
            create_audit_log(
                action="order_completed_with_inventory",
                order_id=order_id,
                timestamp=datetime.utcnow()
            )
            
            self.db.commit()
        except InsufficientInventoryError as e:
            self.db.rollback()
            # Handle insufficient inventory
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient inventory: {e.item_name}"
            )
        except Exception as e:
            self.db.rollback()
            raise
```

### 5. Configuration Options

Add settings for inventory deduction behavior:

```python
class InventoryDeductionSettings:
    # When to deduct inventory
    DEDUCTION_TRIGGER = "order_completed"  # or "order_placed", "order_prepared"
    
    # How to handle insufficient inventory
    ALLOW_NEGATIVE_INVENTORY = False
    
    # Whether to deduct for voided/cancelled items
    DEDUCT_CANCELLED_ITEMS = False
    
    # Alert thresholds
    LOW_STOCK_ALERT_PERCENTAGE = 20
    CRITICAL_STOCK_ALERT_PERCENTAGE = 10
```

## Implementation Steps

1. **Phase 1: Core Integration**
   - Add deduction logic to order completion
   - Handle direct ingredients only
   - Basic error handling

2. **Phase 2: Advanced Features**
   - Sub-recipe support
   - Batch deductions for performance
   - Configurable deduction rules

3. **Phase 3: Monitoring & Alerts**
   - Real-time inventory tracking
   - Predictive stock alerts
   - Usage analytics

## API Endpoints to Add

```
POST   /api/v1/inventory/deduct-for-order/{order_id}  # Manual deduction
GET    /api/v1/inventory/usage/by-order/{order_id}    # View deductions
POST   /api/v1/inventory/reverse-deduction/{order_id} # Reverse for refunds
```

## Testing Requirements

1. **Unit Tests**
   - Deduction calculations
   - Sub-recipe processing
   - Error handling

2. **Integration Tests**
   - Order completion flow
   - Transaction rollback
   - Concurrent deductions

3. **Performance Tests**
   - Bulk order processing
   - Large recipe deductions

## Monitoring & Alerts

1. **Metrics to Track**
   - Deduction success rate
   - Average deduction time
   - Inventory accuracy

2. **Alerts to Implement**
   - Failed deductions
   - Negative inventory
   - Unusual usage patterns

## Database Considerations

1. **New Indexes**
   ```sql
   CREATE INDEX idx_inventory_adjustments_reference 
   ON inventory_adjustments(reference_type, reference_id);
   
   CREATE INDEX idx_inventory_usage_logs_order 
   ON inventory_usage_logs(order_id, order_item_id);
   ```

2. **Performance Optimization**
   - Batch deductions by ingredient
   - Use database triggers for critical paths
   - Consider read replicas for analytics

## Security Considerations

1. **Permissions**
   - Only completed orders trigger deductions
   - Manual deductions require admin permission
   - Audit trail for all deductions

2. **Data Integrity**
   - Prevent double deductions
   - Handle concurrent order completions
   - Validate recipe quantities

## Future Enhancements

1. **Smart Deductions**
   - Predictive ordering based on usage
   - Automatic reorder suggestions
   - Waste tracking integration

2. **Analytics**
   - Ingredient usage trends
   - Recipe profitability analysis
   - Inventory turnover reports

3. **Integration**
   - POS system real-time sync
   - Supplier auto-ordering
   - Kitchen display integration

## Migration Strategy

1. **Preparation**
   - Ensure all active menu items have recipes
   - Validate recipe quantities
   - Set initial inventory levels

2. **Rollout**
   - Start with pilot location
   - Monitor deduction accuracy
   - Gradual rollout to all locations

3. **Validation**
   - Compare with manual counts
   - Audit deduction logs
   - Adjust recipes as needed

## Success Metrics

- 95%+ deduction accuracy
- < 100ms deduction time
- Zero data loss incidents
- 50% reduction in manual inventory counts

## Timeline Estimate

- Phase 1: 2-3 weeks
- Phase 2: 3-4 weeks
- Phase 3: 2-3 weeks
- Total: 7-10 weeks

## Dependencies

- Recipe management system (completed)
- Order management system (existing)
- Inventory tracking system (existing)
- Real-time notifications (planned)