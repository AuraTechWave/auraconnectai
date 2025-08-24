# Email Notification System

## Overview
The AuraConnect Email Notification System provides comprehensive email functionality including transactional emails, templates, tracking, and multi-provider support.

## Features

### 1. Email Service Providers
- **SendGrid Integration**: Full support for SendGrid API including webhooks
- **AWS SES Integration**: Complete AWS Simple Email Service support
- **Provider Abstraction**: Easy switching between providers via configuration
- **Automatic Failover**: Retry logic with provider switching on failure

### 2. Email Templates
- **Jinja2 Templating**: Dynamic content with variable substitution
- **Pre-built Templates**: Order confirmations, password resets, reservations
- **Template Management**: CRUD operations via API
- **Template Caching**: Improved performance with configurable TTL

### 3. Email Tracking
- **Delivery Status**: Track sent, delivered, opened, clicked, bounced
- **Real-time Updates**: Webhook processing for instant status updates
- **Analytics Dashboard**: View email performance metrics
- **Bounce Handling**: Automatic suppression of invalid addresses

### 4. Unsubscribe Management
- **One-Click Unsubscribe**: Secure token-based unsubscribe links
- **Category Management**: Users can unsubscribe from specific email types
- **Compliance**: GDPR and CAN-SPAM compliant

### 5. Order Emails
- **Order Confirmation**: Sent immediately after order placement
- **Order Ready**: Notification when order is ready for pickup
- **Order Cancelled**: Automatic notification on cancellation
- **Order Receipt**: Detailed receipt with payment information

### 6. Authentication Emails
- **Password Reset**: Secure token-based password reset flow
- **Welcome Email**: New user registration confirmation
- **Account Verification**: Email address verification

### 7. Reservation Emails
- **Reservation Confirmation**: Booking details with confirmation code
- **Reservation Reminder**: Sent 24 hours before reservation
- **Reservation Modification**: Updates on changes
- **Reservation Cancellation**: Confirmation of cancellation

## Configuration

### Environment Variables

```bash
# Email Provider Settings
EMAIL_DEFAULT_PROVIDER=sendgrid  # Options: sendgrid, aws_ses
EMAIL_FROM_ADDRESS=noreply@yourestaurant.com
EMAIL_FROM_NAME="Your Restaurant Name"

# SendGrid Settings (if using SendGrid)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_WEBHOOK_SECRET=your-webhook-secret

# AWS SES Settings (if using AWS SES)
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-1
SES_CONFIGURATION_SET=your-configuration-set

# General Email Settings
EMAIL_MAX_RETRY_ATTEMPTS=3
EMAIL_RETRY_DELAY_MINUTES=5
EMAIL_BATCH_SIZE=50
EMAIL_RATE_LIMIT_PER_MINUTE=100

# Restaurant Information
RESTAURANT_NAME="Your Restaurant"
RESTAURANT_ADDRESS="123 Main St, City, State 12345"
RESTAURANT_PHONE="(555) 123-4567"
RESTAURANT_EMAIL=info@yourestaurant.com
RESTAURANT_WEBSITE=https://www.yourestaurant.com

# URLs
FRONTEND_URL=http://localhost:3000
APP_URL=http://localhost:8000
```

## API Endpoints

### Send Email
```http
POST /api/v1/email/send
Authorization: Bearer {token}
Content-Type: application/json

{
  "to_email": "customer@example.com",
  "subject": "Your Order Confirmation",
  "template_name": "order_confirmation",
  "variables": {
    "order_id": "ORD-123",
    "customer_name": "John Doe",
    "total": 45.99
  }
}
```

### Template Management
```http
# List templates
GET /api/v1/email/templates

# Create template
POST /api/v1/email/templates
{
  "name": "special_offer",
  "subject": "Special Offer for You!",
  "body_html": "<h1>Hello {{customer_name}}</h1>...",
  "body_text": "Hello {{customer_name}}...",
  "category": "marketing"
}

# Update template
PUT /api/v1/email/templates/{template_id}

# Delete template
DELETE /api/v1/email/templates/{template_id}
```

### Email Tracking
```http
# Get email status
GET /api/v1/email/messages/{message_id}

# List emails with filters
GET /api/v1/email/messages?status=delivered&date_from=2024-01-01

# Get email analytics
GET /api/v1/email/analytics?start_date=2024-01-01&end_date=2024-01-31
```

### Webhook Endpoints
```http
# SendGrid webhook
POST /api/v1/email/webhooks/sendgrid

# AWS SES webhook
POST /api/v1/email/webhooks/ses
```

### Unsubscribe Management
```http
# Process unsubscribe
GET /api/v1/email/unsubscribe/{token}

# List unsubscribes
GET /api/v1/email/unsubscribes

# Re-subscribe user
POST /api/v1/email/resubscribe
{
  "email": "customer@example.com",
  "categories": ["marketing", "updates"]
}
```

## Usage Examples

### Send Order Confirmation
```python
from modules.email.services.order_email_service import OrderEmailService

# In your order creation endpoint
order_email_service = OrderEmailService(db)
await order_email_service.send_order_confirmation(order_id=123)
```

### Send Password Reset
```python
from modules.email.services.auth_email_service import AuthEmailService

# In your password reset endpoint
auth_email_service = AuthEmailService(db)
await auth_email_service.send_password_reset_email(user_id=456)
```

### Send Custom Email
```python
from modules.email.services.email_service import EmailService
from modules.email.schemas.email_schemas import EmailSendRequest

email_service = EmailService(db)

request = EmailSendRequest(
    to_email="customer@example.com",
    subject="Special Offer",
    template_name="marketing_offer",
    variables={
        "customer_name": "John",
        "discount_code": "SAVE20",
        "expiry_date": "2024-12-31"
    },
    category="marketing"
)

email_message = await email_service.send_email(request, user_id=789)
```

## Database Schema

The email system uses the following main tables:
- `email_messages`: Stores all sent emails with status tracking
- `email_templates`: Email template definitions
- `email_attachments`: File attachments for emails
- `email_unsubscribes`: Unsubscribe preferences
- `email_bounces`: Bounce and complaint tracking

## Security Considerations

1. **Webhook Verification**: All webhooks are verified using provider-specific signatures
2. **Token Security**: Unsubscribe tokens are cryptographically secure
3. **Rate Limiting**: Built-in rate limiting to prevent abuse
4. **Input Validation**: All email addresses and content are validated
5. **HTML Sanitization**: Email content is sanitized to prevent XSS

## Monitoring

### Health Check
```http
GET /api/v1/email/health
```

Response:
```json
{
  "status": "healthy",
  "provider": "sendgrid",
  "emails_sent_today": 156,
  "emails_queued": 3,
  "last_error": null
}
```

### Metrics
- Delivery rate
- Open rate
- Click rate
- Bounce rate
- Unsubscribe rate

## Troubleshooting

### Common Issues

1. **Emails not sending**
   - Check provider API keys in environment variables
   - Verify FROM address is verified with provider
   - Check rate limits

2. **Webhooks not updating status**
   - Verify webhook URLs are publicly accessible
   - Check webhook secrets match configuration
   - Review webhook logs for errors

3. **Templates not rendering**
   - Ensure all required variables are provided
   - Check Jinja2 syntax in templates
   - Verify template exists and is active

## Migration

To create the email tables, run:
```bash
alembic upgrade head
```

To seed initial templates:
```bash
python scripts/seed_email_templates.py
```

## Testing

Run the email module tests:
```bash
pytest modules/email/tests/ -v
```

## Future Enhancements

1. **A/B Testing**: Test different subject lines and content
2. **Scheduled Emails**: Send emails at optimal times
3. **Email Campaigns**: Multi-step email sequences
4. **Advanced Analytics**: Cohort analysis and revenue attribution
5. **Multi-language Support**: Localized email templates