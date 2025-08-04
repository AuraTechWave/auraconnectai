# Refund Processing API Documentation

## Overview

The AuraConnect refund processing system provides a comprehensive solution for handling customer refund requests with automated approval workflows, configurable policies, and detailed audit trails.

## Key Features

- **16 Standard Refund Reason Codes** categorized into 5 main categories
- **Automated Approval Workflow** based on configurable thresholds
- **Refund Policies** per restaurant with customizable rules
- **Complete Audit Trail** for compliance and tracking
- **RESTful API** with proper permission controls

## API Endpoints

### Create Refund Request

Create a new refund request for a customer order.

```
POST /api/v1/payments/refunds/request
```

**Request Body:**
```json
{
  "order_id": 123,
  "payment_id": 456,
  "requested_amount": 25.50,
  "reason_code": "cold_food",
  "reason_details": "Food arrived cold and had to be reheated",
  "refund_items": [
    {
      "item_id": 789,
      "quantity": 1,
      "amount": 15.00,
      "reason": "Main dish was cold"
    }
  ],
  "priority": "normal"
}
```

**Response:**
```json
{
  "id": 1,
  "request_number": "REF-2025-0001",
  "order_id": 123,
  "payment_id": 456,
  "requested_amount": 25.50,
  "reason_code": "cold_food",
  "category": "quality_issue",
  "approval_status": "auto_approved",
  "created_at": "2025-08-04T12:00:00Z"
}
```

### List Refund Requests

Get a paginated list of refund requests with filtering options.

```
GET /api/v1/payments/refunds/requests
```

**Query Parameters:**
- `status` - Filter by approval status (pending_approval, approved, rejected, auto_approved)
- `category` - Filter by category (order_issue, quality_issue, service_issue, payment_issue, other)
- `customer_id` - Filter by customer (staff only)
- `order_id` - Filter by order (staff only)
- `priority` - Filter by priority (urgent, high, normal, low)
- `date_from` - Start date for filtering
- `date_to` - End date for filtering
- `offset` - Pagination offset
- `limit` - Results per page (max 100)

### Get Refund Request Details

```
GET /api/v1/payments/refunds/requests/{request_id}
```

### Approve Refund Request

**Requires Permission:** `refunds.approve`

```
POST /api/v1/payments/refunds/requests/{request_id}/approve
```

**Request Body:**
```json
{
  "notes": "Approved per customer service policy",
  "process_immediately": true
}
```

### Reject Refund Request

**Requires Permission:** `refunds.approve`

```
POST /api/v1/payments/refunds/requests/{request_id}/reject
```

**Request Body:**
```json
{
  "reason": "Outside refund window - order placed 10 days ago"
}
```

### Process Refund

Manually process an approved refund request.

**Requires Permission:** `refunds.process`

```
POST /api/v1/payments/refunds/requests/{request_id}/process
```

### Get Refund Reasons

Get all available refund reasons and their categories.

```
GET /api/v1/payments/refunds/reasons
```

**Response:**
```json
{
  "reasons": [
    {
      "code": "order_cancelled",
      "display_name": "Order Cancelled",
      "category": "order_issue"
    },
    // ... more reasons
  ],
  "categories": [
    {
      "code": "order_issue",
      "display_name": "Order Issue"
    },
    // ... more categories
  ]
}
```

## Refund Reason Codes

### Order Issues
- `order_cancelled` - Customer cancelled the order
- `order_mistake` - Wrong order was prepared
- `wrong_items` - Received incorrect items
- `missing_items` - Some items were missing

### Quality Issues
- `food_quality` - Food quality was poor
- `cold_food` - Food arrived cold
- `incorrect_preparation` - Food not prepared as requested

### Service Issues
- `long_wait` - Excessive wait time
- `poor_service` - Poor customer service

### Payment Issues
- `duplicate_charge` - Charged multiple times
- `overcharge` - Charged more than expected
- `price_dispute` - Disagreement on pricing

### Other
- `customer_request` - General customer request
- `goodwill` - Goodwill gesture
- `test_refund` - Test transaction
- `other` - Other reason

## Refund Policies

Each restaurant can configure their own refund policy with the following settings:

- **Auto-Approval**: Enable automatic approval for refunds under a threshold
- **Auto-Approval Threshold**: Maximum amount for automatic approval
- **Refund Window**: Time limit for refund requests (in hours)
- **Partial Refunds**: Allow partial refunds
- **Notifications**: Configure customer and manager notifications

### Create/Update Refund Policy

**Requires Permission:** `refunds.manage_policies`

```
POST /api/v1/payments/refunds/policies?restaurant_id=1
```

**Request Body:**
```json
{
  "name": "Standard Refund Policy",
  "description": "Default policy with 7-day window",
  "auto_approve_enabled": true,
  "auto_approve_threshold": 50.00,
  "refund_window_hours": 168,
  "allow_partial_refunds": true,
  "require_reason": true,
  "notify_customer": true,
  "notify_manager": true
}
```

### Get Restaurant Policy

```
GET /api/v1/payments/refunds/policies/{restaurant_id}
```

## Permissions

The following permissions control access to refund functionality:

- `refunds.create` - Create refund requests (customers have this by default)
- `refunds.view` - View refund requests
- `refunds.approve` - Approve or reject refund requests
- `refunds.process` - Process approved refunds
- `refunds.view_statistics` - View refund statistics and reports
- `refunds.manage_policies` - Create and update refund policies

## Workflow

1. **Customer creates refund request** with reason code and details
2. **System checks refund policy**:
   - If amount <= auto-approval threshold, status = `auto_approved`
   - Otherwise, status = `pending_approval`
3. **Manager reviews pending requests** and approves/rejects
4. **Approved refunds are processed** either automatically or manually
5. **Notifications sent** to customer and relevant staff
6. **Audit trail updated** at each step

## Error Responses

Common error responses:

- `400 Bad Request` - Invalid request data or business rule violation
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Business logic conflict (e.g., refund already processed)
- `500 Internal Server Error` - Server error

Example error response:
```json
{
  "detail": "Refund amount exceeds original payment amount"
}
```

## Integration Notes

- All monetary amounts are in the restaurant's configured currency
- Timestamps are in UTC
- The refund system integrates with the payment gateway for processing
- Audit logs track all actions for compliance