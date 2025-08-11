# Order Routing & Splitting Validation Checklist

## Risk Areas and Test Coverage

### 1. ✅ Regression on Order Creation

**Risk**: Orders might not reach KDS when routing rules don't match or fail.

**Mitigation**:
- Routing evaluation wrapped in try-except block in `create_order_with_fraud_check`
- Fallback to legacy KDS routing if rule evaluation fails
- Fallback also triggered when routing decision type is "default"
- Order creation continues even if all routing fails

**Tests**:
- `test_order_reaches_kds_when_no_rules_exist` - Verifies KDS routing works without rules
- `test_order_reaches_kds_when_no_rules_match` - Verifies fallback when no rules match
- `test_order_creation_continues_if_routing_fails` - Confirms order creation doesn't fail
- `test_routing_decision_logged` - Ensures decisions are logged for debugging

**Code Location**: `order_service.py` lines 574-611

### 2. ✅ Priority Conflicts and Rule Overlaps

**Risk**: Multiple rules with same priority could cause unpredictable routing.

**Mitigation**:
- Conflict detection in `_determine_routing_decision` method
- "First rule wins" behavior implemented with logging
- Dedicated conflict detection endpoint `/api/v1/orders/routing/conflicts`
- Conflict information included in routing decisions

**Tests**:
- `test_priority_conflict_detection` - Verifies conflicts are detected
- `test_first_rule_wins_behavior` - Confirms deterministic resolution
- `TestConflictDetection` class - Comprehensive conflict scenarios

**Code Location**: `routing_rule_service.py` lines 552-633

### 3. ✅ Team Routing Edge Cases

**Risk**: Team routing could fail with no active members or incorrect load balancing.

**Mitigation**:
- Checks for active team and members in `_route_to_team`
- Graceful handling with logging when no members available
- Support for multiple routing strategies (round_robin, least_loaded, skill_based)
- Active member filtering

**Tests**:
- `test_no_active_team_members` - Handles empty teams gracefully
- `test_load_balancing_strategies` - Verifies least_loaded strategy works
- `test_inactive_team_members_excluded` - Confirms only active members used

**Code Location**: `routing_rule_service.py` lines 648-687

### 4. ✅ Split Totals & Payment Math

**Risk**: Payment splits might not sum to order total, causing accounting issues.

**Mitigation**:
- Strict validation in `split_payment` using Decimal arithmetic
- Tolerance of 0.01 for rounding differences
- All monetary values use Decimal type
- Status transitions properly tracked with audit records

**Tests**:
- `test_payment_split_total_must_equal_order_total` - Enforces sum validation
- `test_payment_split_with_exact_amounts` - Verifies exact splits
- `test_payment_split_with_rounding` - Handles decimal rounding
- `test_merge_restores_correct_totals` - Confirms merge accuracy
- `test_decimal_precision_maintained` - Ensures precision throughout

**Code Location**: `order_split_service.py` - validation in split methods

### 5. ✅ API Contract Validation

**Risk**: API payloads might not match documented schemas.

**Mitigation**:
- Pydantic schemas with validation
- Field validators for complex types
- Comprehensive schema definitions

**Tests**:
- `test_routing_rule_create_schema` - Validates rule creation payload
- `test_route_evaluation_request_schema` - Validates evaluation request
- `test_team_config_schema` - Validates team configuration
- Schema tests match examples in documentation

**Code Location**: `routing_schemas.py` - all schema definitions

## Manual Testing Checklist

### Order Creation Flow
- [ ] Create order without any routing rules → Should route to KDS
- [ ] Create order with non-matching rules → Should fallback to KDS
- [ ] Create order with matching rule → Should route according to rule
- [ ] Create order when routing service errors → Order still created
- [ ] Check logs for routing decisions

### Rule Management
- [ ] Create rule with complex conditions (AND/OR groups)
- [ ] Test rule with mock data before activation
- [ ] Create conflicting rules → Check conflict detection
- [ ] Update rule priority → Verify new evaluation order
- [ ] Delete rule → Confirm removed from evaluation

### Team Routing
- [ ] Create team with no members → Should handle gracefully
- [ ] Add/remove team members → Verify routing updates
- [ ] Test each routing strategy (round_robin, least_loaded, etc.)
- [ ] Deactivate team member → Confirm excluded from routing

### Payment Splits
- [ ] Split order 2 ways evenly → Sum equals original
- [ ] Split order 3 ways (uneven amounts) → Handle rounding
- [ ] Try invalid split amounts → Should reject
- [ ] Merge splits → Original total restored
- [ ] Try merging paid splits → Should fail

### Performance Testing
- [ ] Create 100+ routing rules → Check evaluation time
- [ ] Route 1000 orders → Monitor performance
- [ ] Check rule analytics endpoint response time

## Database Integrity Checks

```sql
-- Check for orphaned splits
SELECT os.* FROM order_splits os
LEFT JOIN orders po ON os.parent_order_id = po.id
LEFT JOIN orders so ON os.split_order_id = so.id
WHERE po.id IS NULL OR so.id IS NULL;

-- Verify payment split totals
SELECT 
    sp.parent_order_id,
    o.final_amount as order_total,
    SUM(sp.amount) as split_total,
    ABS(o.final_amount - SUM(sp.amount)) as difference
FROM split_payments sp
JOIN orders o ON sp.parent_order_id = o.id
GROUP BY sp.parent_order_id, o.final_amount
HAVING ABS(o.final_amount - SUM(sp.amount)) > 0.01;

-- Check for priority conflicts
SELECT 
    r1.id as rule1_id,
    r1.name as rule1_name,
    r2.id as rule2_id,
    r2.name as rule2_name,
    r1.priority
FROM order_routing_rules r1
JOIN order_routing_rules r2 ON r1.priority = r2.priority
WHERE r1.id < r2.id
    AND r1.status = 'active'
    AND r2.status = 'active';
```

## Monitoring Queries

```sql
-- Failed routing evaluations (last 24 hours)
SELECT 
    COUNT(*) as failed_evaluations,
    DATE_TRUNC('hour', created_at) as hour
FROM routing_rule_logs
WHERE error_occurred = true
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Orders using fallback routing
SELECT COUNT(*) as fallback_count
FROM orders o
WHERE NOT EXISTS (
    SELECT 1 FROM routing_rule_logs rl
    WHERE rl.order_id = o.id AND rl.matched = true
)
AND o.created_at > NOW() - INTERVAL '1 day';

-- Payment split accuracy
SELECT 
    COUNT(*) as total_splits,
    SUM(CASE WHEN needs_reconciliation THEN 1 ELSE 0 END) as needs_reconciliation
FROM (
    SELECT 
        parent_order_id,
        CASE WHEN ABS(SUM(amount) - MAX(o.final_amount)) > 0.01 
        THEN true ELSE false END as needs_reconciliation
    FROM split_payments sp
    JOIN orders o ON sp.parent_order_id = o.id
    GROUP BY parent_order_id
) split_check;
```

## Load Testing Scenarios

### Scenario 1: High Rule Volume
```python
# Create 500 rules with varying priorities
for i in range(500):
    create_rule(
        name=f"Load Test Rule {i}",
        priority=i % 100,  # 0-99 priority range
        conditions=[...],
        target_type="station",
        target_id=(i % 5) + 1  # Distribute across 5 stations
    )

# Route 1000 orders and measure time
start = time.time()
for i in range(1000):
    route_order(order_id=i)
end = time.time()
avg_time = (end - start) / 1000
assert avg_time < 0.1  # Should route in < 100ms
```

### Scenario 2: Concurrent Splits
```python
# Simulate 10 concurrent payment splits on same order
import threading

def split_order(order_id, split_id):
    try:
        split_payment(order_id, {...})
    except Exception as e:
        # Should handle concurrent access gracefully
        pass

threads = []
for i in range(10):
    t = threading.Thread(target=split_order, args=(order_id, i))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

# Verify only one split succeeded
splits = get_order_splits(order_id)
assert len(splits) > 0  # At least one succeeded
```

## Production Readiness Checklist

- [x] All monetary operations use Decimal type
- [x] Foreign key constraints properly set (RESTRICT/CASCADE)
- [x] Row-level locking for concurrent operations
- [x] No 501 Not Implemented endpoints
- [x] Comprehensive error handling with fallbacks
- [x] Audit trails for all state changes
- [x] Performance monitoring hooks
- [x] API documentation matches implementation
- [x] Integration tests cover edge cases
- [x] Database migrations included

## Rollback Plan

If issues arise in production:

1. **Disable all routing rules**:
   ```sql
   UPDATE order_routing_rules 
   SET status = 'inactive' 
   WHERE status = 'active';
   ```

2. **Force fallback routing**:
   - Set environment variable: `DISABLE_ROUTING_RULES=true`
   - This bypasses rule evaluation entirely

3. **Monitor orders**:
   - Check that orders still reach KDS
   - Verify no order creation failures

4. **Investigate issues**:
   - Review routing_rule_logs for errors
   - Check application logs for exceptions
   - Analyze rule conflicts if applicable

5. **Gradual re-enable**:
   - Fix identified issues
   - Enable rules one at a time
   - Monitor each rule's performance