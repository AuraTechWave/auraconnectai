# Order Splitting Implementation Review & Required Fixes

Based on the comprehensive review checklist, here are the issues found and fixes needed:

## 🔴 Critical Issues

### 1. Data Model Issues

#### Missing ON DELETE Behavior
**Issue**: Foreign keys lack CASCADE/RESTRICT behavior
```python
# Current - No ON DELETE specified
parent_order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
```

**Fix Required**:
```python
parent_order_id = Column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
split_order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
```

#### Missing Database Constraints
**Issue**: split_type and payment_status are strings without DB constraints
```python
split_type = Column(String, nullable=False)  # No enum constraint
payment_status = Column(String, nullable=False, default="pending")
```

**Fix Required**: Add to migration:
```sql
ALTER TABLE order_splits ADD CONSTRAINT check_split_type 
CHECK (split_type IN ('ticket', 'delivery', 'payment'));

ALTER TABLE split_payments ADD CONSTRAINT check_payment_status 
CHECK (payment_status IN ('pending', 'paid', 'partial', 'failed', 'refunded'));
```

### 2. Money Math Issues

#### Float Usage in Payment Validation
**Issue**: Line 759 uses float for money comparison
```python
if abs(float(parent_order.final_amount) - total_split_amount) > 0.01:
```

**Fix Required**:
```python
from decimal import Decimal
total_split_amount = sum(Decimal(str(split.get('amount', 0))) for split in payment_request.splits)
if abs(parent_order.final_amount - total_split_amount) > Decimal('0.01'):
```

#### JSON Response Float Conversion
**Issue**: Line 815 converts Decimal to float for JSON
```python
"amount": float(split_config['amount'])
```

**Fix Required**: Keep as string or use custom JSON encoder

### 3. Concurrency & Transaction Issues

#### No Locking on Parent Order
**Issue**: Multiple staff could split same order simultaneously

**Fix Required**:
```python
# Add row-level lock
parent_order = self.db.query(Order).filter(
    Order.id == order_id
).with_for_update().first()
```

#### Missing Idempotency
**Issue**: Same split request could create duplicates

**Fix Required**: Add idempotency key or check existing splits

### 4. Tax/Fee Proration Issues

#### Simplistic Tax Calculation
**Issue**: Lines 299-301 use basic proportion without rounding strategy
```python
tax_rate = float(parent_order.tax_amount / parent_order.subtotal) if parent_order.subtotal else 0
tax_amount = subtotal * Decimal(str(tax_rate))
```

**Fix Required**: Implement deterministic rounding and remainder distribution

### 5. Security Issues

#### Missing Role Checks
**Issue**: No permission validation in routes

**Fix Required**:
```python
@require_permission("order.split")
async def split_order(...):
```

#### No Tenant Isolation
**Issue**: Multi-tenant queries not filtered

**Fix Required**: Add tenant filtering to all queries

## 🟡 Important Issues

### 6. API Issues

#### 501 Not Implemented in Production
**Issue**: Bulk split endpoint returns 501
```python
raise HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail="Bulk split functionality coming soon"
)
```

**Fix Required**: Remove endpoint or implement

#### Inconsistent Error Responses
**Issue**: Mix of error formats

**Fix Required**: Standardize error shape

### 7. Performance Issues

#### N+1 Query Risk
**Issue**: get_split_tracking loops through splits without eager loading

**Fix Required**:
```python
splits = self.db.query(OrderSplit).options(
    joinedload(OrderSplit.split_order),
    joinedload(OrderSplit.split_order.order_items)
).filter(OrderSplit.parent_order_id == order_id).all()
```

### 8. Testing Gaps

#### Missing Edge Cases
- Zero-tax orders
- Discount allocation
- Tip distribution
- Concurrent split attempts
- 3+ way payment splits with rounding

**Fix Required**: Add comprehensive edge case tests

## 🟢 Good Practices Found

### Positive Aspects
- ✅ Using Decimal for money storage
- ✅ Indexes on foreign keys
- ✅ Transaction rollback on errors
- ✅ Webhook notifications
- ✅ Comprehensive validation before split
- ✅ Audit trail in metadata

## Recommended Fixes Implementation

### 1. Update Models
```python
# order_models.py
class OrderSplit(Base, TimestampMixin):
    __tablename__ = "order_splits"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_order_id = Column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    split_order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    split_type = Column(Enum(SplitType), nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    # ... rest of fields

class SplitPayment(Base, TimestampMixin):
    __tablename__ = "split_payments"
    
    # ... fields
    amount = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
```

### 2. Add Locking and Idempotency
```python
def split_order(self, order_id: int, split_request: OrderSplitRequest, current_user_id: int, idempotency_key: Optional[str] = None):
    try:
        # Check idempotency
        if idempotency_key:
            existing = self.db.query(OrderSplit).filter(
                OrderSplit.idempotency_key == idempotency_key
            ).first()
            if existing:
                return self._get_existing_split_response(existing)
        
        # Lock parent order
        parent_order = self.db.query(Order).filter(
            Order.id == order_id
        ).with_for_update().first()
        
        # Validate within transaction
        validation = self.validate_split_request(order_id, split_request)
        # ... rest of implementation
```

### 3. Fix Money Math
```python
def _calculate_split_amounts(self, parent_order: Order, splits: List[Dict]) -> List[Dict]:
    """Calculate split amounts with proper rounding and remainder distribution"""
    total_amount = parent_order.final_amount
    
    # Use banker's rounding
    from decimal import ROUND_HALF_EVEN
    
    # Calculate proportional amounts
    calculated_splits = []
    running_total = Decimal('0')
    
    for i, split in enumerate(splits[:-1]):
        proportion = Decimal(str(split['proportion']))
        amount = (total_amount * proportion).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        calculated_splits.append({**split, 'amount': amount})
        running_total += amount
    
    # Last split gets remainder to ensure exact total
    calculated_splits.append({
        **splits[-1],
        'amount': total_amount - running_total
    })
    
    return calculated_splits
```

### 4. Add Permission Decorators
```python
from core.auth.decorators import require_permission

@router.post("/{order_id}/split")
@require_permission("order.split")
@handle_api_errors
async def split_order(...):
```

### 5. Implement Proper Webhook Pattern
```python
class WebhookOutbox(Base):
    """Ensures webhook delivery with retry"""
    __tablename__ = "webhook_outbox"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), default="pending")
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 6. Add Comprehensive Tests
```python
def test_concurrent_splits(db):
    """Test concurrent split attempts"""
    # Create order
    order = create_test_order(total=100.00)
    
    # Simulate concurrent requests
    from threading import Thread
    results = []
    
    def attempt_split():
        try:
            service = OrderSplitService(db)
            result = service.split_order(order.id, split_request, user_id=1)
            results.append(('success', result))
        except Exception as e:
            results.append(('error', str(e)))
    
    threads = [Thread(target=attempt_split) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Only one should succeed
    successes = [r for r in results if r[0] == 'success']
    assert len(successes) == 1
```

## Migration Update

```sql
-- Add constraints and indexes
ALTER TABLE order_splits 
ADD COLUMN idempotency_key VARCHAR(255) UNIQUE,
ADD CONSTRAINT check_split_type CHECK (split_type IN ('ticket', 'delivery', 'payment'));

ALTER TABLE split_payments 
ADD CONSTRAINT check_payment_status CHECK (payment_status IN ('pending', 'paid', 'partial', 'failed', 'refunded'));

-- Add composite index for faster lookups
CREATE INDEX idx_order_splits_parent_type ON order_splits(parent_order_id, split_type);
CREATE INDEX idx_split_payments_status ON split_payments(payment_status) WHERE payment_status != 'paid';
```

## Rollout Plan

1. **Phase 1**: Fix critical issues (money math, locking)
2. **Phase 2**: Add constraints and validations
3. **Phase 3**: Implement idempotency and webhook outbox
4. **Phase 4**: Add permission system
5. **Phase 5**: Performance optimizations

## Feature Flags

```python
FEATURE_FLAGS = {
    "order_splitting_enabled": False,
    "payment_splitting_enabled": False,
    "bulk_splitting_enabled": False,
}
```

## Monitoring

Add metrics for:
- Split operation success/failure rates
- Payment collection rates
- Average split processing time
- Concurrent split attempt conflicts