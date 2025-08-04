# Payment Gateway Integration Module

This module provides a unified payment processing system that supports multiple payment gateways (Stripe, Square, PayPal) with a consistent API interface.

## Features

- **Multi-Gateway Support**: Seamlessly switch between Stripe, Square, and PayPal
- **Unified API**: Consistent interface across all payment gateways
- **Payment Processing**: Create, capture, and cancel payments
- **Refund Management**: Full and partial refunds with reason tracking
- **Saved Payment Methods**: Store customer payment methods for future use
- **Webhook Handling**: Automatic processing of gateway webhooks
- **Idempotency**: Built-in idempotency support for safe retries
- **PCI Compliance**: Secure handling of payment data

## Architecture

```
payments/
├── models/          # Database models
├── gateways/        # Gateway adapters
├── services/        # Business logic
├── api/            # REST endpoints
└── schemas/        # Pydantic schemas
```

## Configuration

### 1. Database Setup

Run the migration to create payment tables:

```bash
cd backend
alembic upgrade head
```

### 2. Gateway Configuration

Configure payment gateways in the database via the `payment_gateway_configs` table:

#### Stripe Configuration
```json
{
  "publishable_key": "pk_test_...",
  "secret_key": "sk_test_...",
  "webhook_secret": "whsec_..."
}
```

#### Square Configuration
```json
{
  "application_id": "sandbox-...",
  "access_token": "...",
  "location_id": "...",
  "webhook_signature_key": "..."
}
```

#### PayPal Configuration
```json
{
  "client_id": "...",
  "client_secret": "...",
  "webhook_id": "..."
}
```

## API Endpoints

### Payment Operations

#### Create Payment
```http
POST /api/v1/payments/create
Content-Type: application/json

{
  "order_id": 123,
  "gateway": "stripe",
  "amount": 99.99,
  "currency": "USD",
  "payment_method_id": "pm_xxx",  // Optional - for saved payment methods
  "save_payment_method": false,
  "return_url": "https://example.com/success"  // For PayPal redirects
}
```

#### Capture Payment
```http
POST /api/v1/payments/{payment_id}/capture
Content-Type: application/json

{
  "amount": 99.99  // Optional - for partial capture
}
```

#### Cancel Payment
```http
POST /api/v1/payments/{payment_id}/cancel
Content-Type: application/json

{
  "reason": "Customer requested cancellation"
}
```

#### Get Payment Details
```http
GET /api/v1/payments/{payment_id}
```

### Refund Operations

#### Create Refund
```http
POST /api/v1/payments/{payment_id}/refund
Content-Type: application/json

{
  "amount": 50.00,  // Optional - omit for full refund
  "reason": "Product returned"
}
```

#### Get Refund Details
```http
GET /api/v1/payments/refunds/{refund_id}
```

### Payment Methods

#### Save Payment Method
```http
POST /api/v1/payments/methods/save
Content-Type: application/json

{
  "customer_id": 456,
  "gateway": "stripe",
  "payment_method_token": "pm_xxx",
  "set_as_default": true
}
```

#### List Payment Methods
```http
GET /api/v1/payments/methods/list?gateway=stripe
```

#### Delete Payment Method
```http
DELETE /api/v1/payments/methods/{method_id}
```

### Gateway Information

#### Get Available Gateways
```http
GET /api/v1/payments/gateways/available
```

### Webhooks

#### Handle Gateway Webhook
```http
POST /api/v1/payments/webhook/{gateway}
```

Webhook endpoints are public and use signature verification for security.

## Usage Examples

### Python Service Usage

```python
from modules.payments.services import payment_service
from modules.payments.models import PaymentGateway

# Create a payment
payment = await payment_service.create_payment(
    db=db,
    order_id=123,
    gateway=PaymentGateway.STRIPE,
    amount=Decimal("99.99"),
    currency="USD"
)

# Process refund
refund = await payment_service.create_refund(
    db=db,
    payment_id=payment.id,
    amount=Decimal("50.00"),
    reason="Partial refund requested"
)

# Save payment method
payment_method = await payment_service.save_payment_method(
    db=db,
    customer_id=456,
    gateway=PaymentGateway.STRIPE,
    payment_method_token="pm_xxx"
)
```

### Frontend Integration

#### Stripe

```javascript
// Load Stripe.js
const stripe = Stripe('pk_test_...');

// Create payment method
const { error, paymentMethod } = await stripe.createPaymentMethod({
  type: 'card',
  card: cardElement,
});

// Send to backend
const response = await fetch('/api/v1/payments/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    order_id: 123,
    gateway: 'stripe',
    payment_method_id: paymentMethod.id
  })
});
```

#### Square

```javascript
// Initialize Square Web Payments SDK
const payments = Square.payments(applicationId, locationId);
const card = await payments.card();
await card.attach('#card-container');

// Generate token
const { token } = await card.tokenize();

// Send to backend
const response = await fetch('/api/v1/payments/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    order_id: 123,
    gateway: 'square',
    payment_method_id: token
  })
});
```

#### PayPal

```javascript
// PayPal returns to your return_url after approval
const response = await fetch('/api/v1/payments/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    order_id: 123,
    gateway: 'paypal',
    return_url: 'https://example.com/success'
  })
});

// Redirect user to PayPal
if (response.requires_action) {
  window.location.href = response.action_url;
}
```

## Webhook Configuration

### Stripe
1. Go to Stripe Dashboard > Webhooks
2. Add endpoint: `https://yourdomain.com/api/v1/payments/webhook/stripe`
3. Select events: `payment_intent.*`, `charge.refunded`, `charge.dispute.*`
4. Copy webhook secret to configuration

### Square
1. Go to Square Dashboard > Webhooks
2. Add endpoint: `https://yourdomain.com/api/v1/payments/webhook/square`
3. Subscribe to: `payment.created`, `payment.updated`, `refund.*`
4. Copy signature key to configuration

### PayPal
1. Go to PayPal Developer > Webhooks
2. Add webhook: `https://yourdomain.com/api/v1/payments/webhook/paypal`
3. Select events: All payment and refund events
4. Copy webhook ID to configuration

## Security Considerations

1. **API Keys**: Store all API keys securely (use environment variables or secrets management)
2. **Webhook Verification**: Always verify webhook signatures
3. **PCI Compliance**: Never store raw card details - use gateway tokens
4. **Idempotency**: Use idempotency keys for payment creation
5. **HTTPS**: Always use HTTPS in production
6. **Rate Limiting**: Implement rate limiting on payment endpoints

## Error Handling

The system provides detailed error responses:

```json
{
  "detail": "Payment creation failed",
  "error_code": "card_declined",
  "error_message": "Your card was declined"
}
```

Common error codes:
- `payment_error`: Generic payment failure
- `invalid_request`: Invalid parameters
- `card_declined`: Card was declined
- `insufficient_funds`: Not enough funds
- `gateway_error`: Gateway communication error

## Testing

### Test Cards

#### Stripe
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- 3D Secure: `4000 0025 0000 3155`

#### Square (Sandbox)
- Success: `4111 1111 1111 1111`
- Decline: `4000 0000 0000 0002`

#### PayPal (Sandbox)
- Use sandbox buyer accounts

### Running Tests

```bash
cd backend
pytest modules/payments/tests/ -v
```

## Monitoring

Monitor payment operations via:
- Application logs
- Payment gateway dashboards
- Database payment_webhooks table for webhook history
- Prometheus metrics (if configured)

## Support

For issues or questions:
1. Check gateway-specific documentation
2. Review error logs
3. Check webhook processing status
4. Contact the development team

## License

This module is part of the AuraConnect platform and follows the same license terms.