# Integration Tests for Automatic Inventory Deduction

This directory contains comprehensive integration tests for the automatic inventory deduction feature implemented in AUR-360/AUR-361.

## Test Coverage

### 1. **test_inventory_deduction_integration.py**
Complete end-to-end tests for the order-to-inventory flow:
- ✅ Order placement triggers ingredient deduction based on recipes
- ✅ Order cancellation reverses inventory deductions
- ✅ Multiple menu items with shared ingredients are aggregated correctly
- ✅ Insufficient inventory blocks order processing
- ✅ Low stock alerts are generated at thresholds
- ✅ Deduction on completion mode (vs on progress)
- ✅ Complex order flows with modifications
- ✅ Concurrent orders competing for limited inventory

### 2. **test_inventory_api_integration.py**
API endpoint integration tests:
- ✅ Preview inventory impact before order processing
- ✅ Preview items without creating orders
- ✅ Partial fulfillment handling
- ✅ Inventory reversal endpoint
- ✅ Authentication and authorization (manager-only operations)
- ✅ Low stock detection in previews
- ✅ Error handling for insufficient stock

### 3. **test_order_service_inventory_integration.py**
Order service integration with inventory system:
- ✅ Order status changes trigger appropriate deductions
- ✅ Auto-reversal on cancellation
- ✅ Sub-recipe handling (nested recipes)
- ✅ Configuration-based behavior (deduct on progress vs completion)
- ✅ Low stock warning logging
- ✅ Complete order workflow tracking

### 4. **test_recipe_inventory_concurrent.py**
Concurrent operation testing:
- ✅ Multiple orders competing for same inventory
- ✅ Concurrent order and reversal operations
- ✅ Deadlock prevention with cross-dependent ingredients
- ✅ Race condition handling

## Running the Tests

### Prerequisites
```bash
pip install pytest pytest-asyncio pytest-mock sqlalchemy fastapi
```

### Run All Integration Tests
```bash
# From the backend directory
pytest modules/orders/tests/test_inventory_*integration*.py -v

# Run with coverage
pytest modules/orders/tests/test_inventory_*integration*.py --cov=modules.orders.services --cov-report=html
```

### Run Specific Test Files
```bash
# End-to-end flow tests
pytest modules/orders/tests/test_inventory_deduction_integration.py -v

# API tests
pytest modules/orders/tests/test_inventory_api_integration.py -v

# Service integration tests
pytest modules/orders/tests/test_order_service_inventory_integration.py -v

# Concurrent operation tests
pytest modules/orders/tests/test_recipe_inventory_concurrent.py -v
```

### Run Specific Test Cases
```bash
# Test order placement and deduction
pytest modules/orders/tests/test_inventory_deduction_integration.py::TestOrderInventoryIntegration::test_place_order_verify_ingredient_deduction -v

# Test cancellation rollback
pytest modules/orders/tests/test_inventory_deduction_integration.py::TestOrderInventoryIntegration::test_cancel_order_ensure_inventory_rollback -v
```

## Test Data Setup

Each test file includes fixtures that set up:
1. **Inventory Items**: Base ingredients with quantities and thresholds
2. **Menu Items**: Products that can be ordered
3. **Recipes**: Bill of materials linking menu items to ingredients
4. **Sub-Recipes**: Complex recipes that include other recipes
5. **Users**: Test users with appropriate roles (staff, manager, admin)

## Key Test Scenarios

### 1. Happy Path
- Customer places order → Status changes to IN_PROGRESS → Ingredients deducted
- Multiple items ordered → Shared ingredients aggregated → Single deduction per ingredient
- Order completed successfully → Audit trail created

### 2. Cancellation Flow
- Order processed → Ingredients deducted → Order cancelled → Ingredients restored
- Reversal creates RETURN adjustments → Original quantities restored

### 3. Edge Cases
- Insufficient inventory → Order blocked → Clear error message
- Low stock reached → Warning generated → Notification triggered (when configured)
- Concurrent orders → First-come-first-served → Later orders may fail

### 4. Configuration Modes
- DEDUCT_ON_PROGRESS (default): Deduct when kitchen starts
- DEDUCT_ON_COMPLETION: Deduct when customer receives
- AUTO_REVERSE_ON_CANCELLATION: Automatic rollback enabled

## Assertions and Verifications

Each test verifies:
1. **Inventory Quantities**: Correct amounts deducted/restored
2. **Adjustment Records**: Proper audit trail with metadata
3. **Order Status**: Correct transitions and blocks
4. **Error Handling**: Appropriate exceptions and messages
5. **Authorization**: Role-based access control
6. **Concurrency**: No race conditions or deadlocks

## Debugging Failed Tests

If tests fail:
1. Check test database is clean (SQLite in-memory)
2. Verify all migrations have run
3. Check fixture data matches expectations
4. Enable SQL logging: `logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)`
5. Use pytest's `-s` flag to see print statements

## Future Test Additions

Consider adding tests for:
- [ ] External system sync prevention
- [ ] Notification service integration
- [ ] Performance under high load
- [ ] Database transaction rollback scenarios
- [ ] Multi-tenant isolation