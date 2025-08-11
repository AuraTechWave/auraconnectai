# Order Splitting Functionality Guide

## Overview

The order splitting functionality allows restaurants to split customer orders into multiple tickets or deliveries, supporting separate preparation and payment handling. This feature is essential for:

- **Kitchen efficiency**: Splitting orders by preparation station
- **Flexible delivery**: Separating items for different delivery times/addresses
- **Payment flexibility**: Allowing multiple customers to pay for their portions

## Key Features

### 1. Split Types

#### Ticket Split
- Splits orders for different kitchen stations or preparation areas
- Each split creates a separate kitchen ticket
- Useful for routing items to appropriate stations (grill, salad, dessert, etc.)

#### Delivery Split
- Splits orders for separate deliveries
- Supports different delivery addresses and times
- Maintains customer assignments for each split

#### Payment Split
- Splits orders for payment purposes
- Tracks individual payment responsibilities
- Supports multiple payment methods per order

### 2. Core Capabilities

- **Validation**: Pre-validate splits before execution
- **Tracking**: Comprehensive tracking of all split orders
- **Status Management**: Update split order statuses independently
- **Payment Tracking**: Monitor payment collection across splits
- **Merge Operations**: Combine split orders back together
- **Webhook Integration**: Real-time notifications for split events

## API Endpoints

### Split Validation

```http
POST /api/v1/orders/{order_id}/split/validate
```

Validates if an order can be split as requested without making changes.

**Request Body:**
```json
{
  "split_type": "ticket",
  "items": [
    {
      "item_id": 1,
      "quantity": 2,
      "notes": "Rush order"
    }
  ],
  "split_reason": "Kitchen efficiency"
}
```

**Response:**
```json
{
  "can_split": true,
  "reason": null,
  "splittable_items": [
    {
      "item_id": 1,
      "menu_item_id": 101,
      "quantity": 2,
      "unit_price": 25.00,
      "total_price": 50.00
    }
  ],
  "warnings": [],
  "estimated_totals": {
    "subtotal": 50.00,
    "tax_amount": 5.00,
    "total_amount": 55.00
  }
}
```

### Create Split

```http
POST /api/v1/orders/{order_id}/split
```

Splits an order into multiple orders based on the specified type.

**Request Body (Ticket Split):**
```json
{
  "split_type": "ticket",
  "items": [
    {
      "item_id": 1,
      "quantity": 1
    },
    {
      "item_id": 2,
      "quantity": 1
    }
  ],
  "split_reason": "Send appetizers first"
}
```

**Request Body (Delivery Split):**
```json
{
  "split_type": "delivery",
  "items": [
    {
      "item_id": 3,
      "quantity": 2
    }
  ],
  "split_reason": "Separate delivery requested",
  "customer_id": 456,
  "scheduled_time": "2024-01-20T14:00:00Z",
  "delivery_address": {
    "street": "123 Main St",
    "city": "New York",
    "zip": "10001"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Order split successfully into 2 orders",
  "parent_order_id": 123,
  "split_order_ids": [124, 125],
  "split_details": [
    {
      "split_order_id": 124,
      "group_name": "Ticket 1",
      "items": [...],
      "total_amount": 35.00
    },
    {
      "split_order_id": 125,
      "group_name": "Ticket 2",
      "items": [...],
      "total_amount": 20.00
    }
  ]
}
```

### Payment Split

```http
POST /api/v1/orders/{order_id}/split/payment
```

Splits payment for an order among multiple parties.

**Request Body:**
```json
{
  "splits": [
    {
      "amount": 55.00,
      "customer_id": 123,
      "payment_method": "card",
      "split_by_name": "John Doe"
    },
    {
      "amount": 55.00,
      "customer_id": 456,
      "payment_method": "cash",
      "split_by_name": "Jane Smith"
    }
  ]
}
```

### Get Split Summary

```http
GET /api/v1/orders/{order_id}/splits
```

Returns comprehensive information about all splits for an order.

**Response:**
```json
{
  "parent_order_id": 123,
  "total_splits": 2,
  "split_orders": [
    {
      "id": 1,
      "parent_order_id": 123,
      "split_order_id": 124,
      "split_type": "payment",
      "split_reason": "Split check requested",
      "split_by": 1,
      "created_at": "2024-01-20T12:00:00Z"
    }
  ],
  "payment_splits": [
    {
      "id": 1,
      "parent_order_id": 123,
      "split_order_id": 124,
      "amount": 55.00,
      "payment_status": "paid",
      "payment_method": "card",
      "payment_reference": "REF123"
    }
  ],
  "total_amount": 110.00,
  "paid_amount": 55.00,
  "pending_amount": 55.00
}
```

### Update Payment Status

```http
PUT /api/v1/orders/splits/payment/{payment_id}?payment_status=paid&payment_reference=REF123
```

Updates the payment status for a split order.

### Merge Split Orders

```http
POST /api/v1/orders/splits/merge
```

Merges split orders back together.

**Request Body:**
```json
{
  "split_order_ids": [124, 125],
  "merge_reason": "Customer changed mind",
  "keep_original": true
}
```

### Split Tracking

```http
GET /api/v1/orders/{order_id}/splits/tracking
```

Gets comprehensive tracking information for split orders.

**Response:**
```json
{
  "parent_order": {
    "id": 123,
    "status": "in_progress",
    "created_at": "2024-01-20T11:00:00Z",
    "total_amount": 110.00
  },
  "splits_by_type": {
    "ticket": [...],
    "delivery": [...],
    "payment": [...]
  },
  "status_summary": {
    "total_splits": 2,
    "pending": 0,
    "in_progress": 1,
    "completed": 1,
    "cancelled": 0
  },
  "payment_summary": {
    "total_amount": 110.00,
    "paid_amount": 55.00,
    "pending_amount": 55.00
  }
}
```

## Database Schema

### New Tables

#### order_splits
```sql
CREATE TABLE order_splits (
    id INTEGER PRIMARY KEY,
    parent_order_id INTEGER NOT NULL REFERENCES orders(id),
    split_order_id INTEGER NOT NULL REFERENCES orders(id),
    split_type VARCHAR NOT NULL,
    split_reason TEXT,
    split_by INTEGER NOT NULL REFERENCES staff_members(id),
    split_metadata JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### split_payments
```sql
CREATE TABLE split_payments (
    id INTEGER PRIMARY KEY,
    parent_order_id INTEGER NOT NULL REFERENCES orders(id),
    split_order_id INTEGER NOT NULL REFERENCES orders(id),
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR,
    payment_status VARCHAR NOT NULL DEFAULT 'pending',
    payment_reference VARCHAR,
    paid_by_customer_id INTEGER REFERENCES customers(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Integration with Existing Systems

### Kitchen Display System (KDS)
- Split orders automatically route to appropriate kitchen stations
- Each split appears as a separate ticket on the KDS
- Station assignments can be configured per menu item

### POS Integration
- Split orders sync individually to POS systems
- Payment splits are tracked and reconciled
- Webhook notifications for split events

### Order Tracking
- Customers can track individual split deliveries
- Real-time status updates for each split
- Consolidated view available for parent orders

## Best Practices

### 1. Validation First
Always validate splits before execution to ensure:
- Items exist and have sufficient quantities
- Order is in a splittable state
- Amounts match for payment splits

### 2. Clear Communication
- Use descriptive split reasons
- Add notes to split items when needed
- Keep customers informed of split status

### 3. Payment Handling
- Ensure payment split amounts match order total
- Track payment methods and references
- Update payment status promptly

### 4. Status Management
- Update split order statuses independently
- Use tracking endpoint for overview
- Monitor payment collection progress

## Common Use Cases

### 1. Restaurant Table Service
```
Scenario: Table of 4 wants to split the check
Solution: Use payment split to create 4 separate payment records
```

### 2. Kitchen Efficiency
```
Scenario: Order has items from grill, salad, and dessert stations
Solution: Use ticket split to route items to appropriate stations
```

### 3. Phased Delivery
```
Scenario: Customer wants appetizers now, mains in 30 minutes
Solution: Use delivery split with different scheduled times
```

### 4. Multiple Addresses
```
Scenario: Office order going to different floors
Solution: Use delivery split with different delivery addresses
```

## Error Handling

Common errors and solutions:

### Cannot Split Completed Order
- **Error**: "Cannot split order with status completed"
- **Solution**: Only split orders in pending, in_progress, or delayed status

### Insufficient Quantity
- **Error**: "Requested quantity exceeds available"
- **Solution**: Check available quantities before splitting

### Payment Amount Mismatch
- **Error**: "Split amounts do not match order total"
- **Solution**: Ensure sum of split amounts equals order total

## Webhook Events

The following webhook events are triggered:

- `ORDER_SPLIT`: When an order is split
- `PAYMENT_UPDATED`: When split payment status changes
- `ORDER_UPDATED`: When split order status changes

## Migration Notes

For existing orders:
1. No changes required to existing order structure
2. Split functionality is additive
3. Historical orders remain unchanged
4. New tables handle split relationships

## Future Enhancements

Planned improvements:
- Automatic split suggestions based on kitchen load
- Smart payment splitting based on items ordered
- Integration with loyalty points for split payments
- Mobile app support for customer-initiated splits