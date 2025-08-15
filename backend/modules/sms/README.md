# SMS Notification Module

Comprehensive SMS notification system with Twilio integration, template management, delivery tracking, opt-in/opt-out management, and cost tracking.

## Features

### Core Functionality
- **SMS Sending**: Send individual or bulk SMS messages
- **Provider Integration**: Twilio support with extensible architecture for other providers
- **Template Management**: Create, manage, and version SMS templates
- **Delivery Tracking**: Real-time status updates and webhook handling
- **Opt-Out Management**: TCPA-compliant opt-in/opt-out system
- **Cost Tracking**: Detailed billing and cost analysis

### Advanced Features
- **Scheduled Messages**: Schedule SMS for future delivery
- **Retry Mechanism**: Automatic retry for failed messages
- **Message Segmentation**: Automatic calculation of SMS segments
- **Unicode Support**: Handle messages with emojis and special characters
- **Batch Processing**: Efficient bulk SMS sending
- **Real-time Monitoring**: Live status dashboard

## Installation

### 1. Environment Variables

Add the following to your `.env` file:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_MESSAGING_SERVICE_SID=optional_messaging_service_sid

# Optional: Other Providers
AWS_SNS_ACCESS_KEY=your_aws_access_key
AWS_SNS_SECRET_KEY=your_aws_secret_key
AWS_SNS_REGION=us-east-1
```

### 2. Database Migration

Run the Alembic migration to create SMS tables:

```bash
cd backend
alembic upgrade head
```

### 3. Install Dependencies

```bash
pip install twilio
pip install boto3  # For AWS SNS support
```

## API Endpoints

### SMS Sending

#### Send Single SMS
```http
POST /api/v1/sms/send
Content-Type: application/json

{
  "to_number": "+1234567890",
  "message": "Your order is ready!",
  "customer_id": 123,
  "order_id": 456
}
```

#### Send SMS with Template
```http
POST /api/v1/sms/send
Content-Type: application/json

{
  "to_number": "+1234567890",
  "template_id": 1,
  "template_variables": {
    "customer_name": "John Doe",
    "order_number": "ORD-123",
    "pickup_time": "3:00 PM"
  },
  "customer_id": 123
}
```

#### Send Bulk SMS
```http
POST /api/v1/sms/send-bulk
Content-Type: application/json

{
  "batch_name": "Lunch Promotion",
  "send_immediately": true,
  "recipients": [
    {
      "to_number": "+1234567890",
      "template_id": 2,
      "template_variables": {
        "name": "John",
        "discount": "20"
      }
    },
    {
      "to_number": "+0987654321",
      "template_id": 2,
      "template_variables": {
        "name": "Jane",
        "discount": "15"
      }
    }
  ]
}
```

### Template Management

#### Create Template
```http
POST /api/v1/sms/templates
Content-Type: application/json

{
  "name": "order_ready",
  "category": "order",
  "description": "Notify customer when order is ready",
  "template_body": "Hi {{customer_name}}, your order #{{order_number}} is ready for pickup!",
  "is_active": true
}
```

#### List Templates
```http
GET /api/v1/sms/templates?category=order&is_active=true
```

#### Preview Template
```http
POST /api/v1/sms/templates/1/preview
Content-Type: application/json

{
  "customer_name": "John Doe",
  "order_number": "ORD-123"
}
```

### Opt-Out Management

#### Process Opt-Out
```http
POST /api/v1/sms/opt-out
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "opt_out_reason": "User request",
  "customer_id": 123
}
```

#### Check Opt-Out Status
```http
GET /api/v1/sms/opt-out/check/+1234567890
```

#### Process Opt-In
```http
POST /api/v1/sms/opt-out/opt-in
Content-Type: application/json

{
  "phone_number": "+1234567890"
}
```

### Cost Tracking

#### Get Cost Summary
```http
GET /api/v1/sms/costs/summary?start_date=2025-01-01&end_date=2025-01-31
```

#### Get Billing Report
```http
GET /api/v1/sms/costs/report?start_date=2025-01-01&end_date=2025-01-31
```

### Delivery Tracking

#### Get Delivery Metrics
```http
GET /api/v1/sms/delivery/metrics?start_date=2025-01-01&end_date=2025-01-31
```

#### Get Real-Time Status
```http
GET /api/v1/sms/delivery/real-time?limit=100
```

## Webhook Configuration

### Twilio Status Webhook

Configure in Twilio Console:
```
Status Callback URL: https://your-domain.com/api/v1/sms/webhooks/twilio/status
```

### Twilio Inbound SMS Webhook

Configure in Twilio Console:
```
Webhook URL: https://your-domain.com/api/v1/sms/webhooks/twilio/inbound
```

## Default Templates

The system includes default templates for common use cases:

1. **Reservation Confirmation**
   - Category: `reservation`
   - Variables: `customer_name`, `party_size`, `restaurant_name`, `date`, `time`, `confirmation_code`

2. **Reservation Reminder**
   - Category: `reminder`
   - Variables: `party_size`, `restaurant_name`, `time`

3. **Order Ready**
   - Category: `order`
   - Variables: `customer_name`, `order_number`, `restaurant_name`

4. **Order Delivered**
   - Category: `order`
   - Variables: `order_number`, `restaurant_name`

5. **Authentication Code**
   - Category: `authentication`
   - Variables: `restaurant_name`, `code`

6. **Marketing Promotion**
   - Category: `marketing`
   - Variables: `restaurant_name`, `promotion_text`, `promo_code`, `discount`

## Usage Examples

### Python Integration

```python
from modules.sms.services import SMSService
from modules.sms.schemas import SMSSendRequest
from sqlalchemy.orm import Session

# Initialize service
sms_service = SMSService(db_session)

# Send simple SMS
request = SMSSendRequest(
    to_number="+1234567890",
    message="Your table is ready!",
    customer_id=123
)
message = await sms_service.send_sms(request, user_id=1)

# Send with template
request = SMSSendRequest(
    to_number="+1234567890",
    template_id=1,
    template_variables={
        "customer_name": "John",
        "order_number": "ORD-123"
    },
    customer_id=123,
    order_id=456
)
message = await sms_service.send_sms(request, user_id=1)
```

### Integration with Other Modules

#### Reservation Module Integration
```python
from modules.sms.services import SMSService

async def send_reservation_confirmation(reservation, db: Session):
    sms_service = SMSService(db)
    
    if reservation.customer.phone:
        request = SMSSendRequest(
            to_number=reservation.customer.phone,
            template_id=get_template_id("reservation_confirmation"),
            template_variables={
                "customer_name": reservation.customer.name,
                "party_size": reservation.party_size,
                "date": reservation.date.strftime("%B %d, %Y"),
                "time": reservation.time.strftime("%I:%M %p"),
                "confirmation_code": reservation.confirmation_code
            },
            customer_id=reservation.customer_id,
            reservation_id=reservation.id
        )
        
        await sms_service.send_sms(request)
```

#### Order Module Integration
```python
from modules.sms.services import SMSService

async def notify_order_ready(order, db: Session):
    sms_service = SMSService(db)
    
    if order.customer.phone:
        request = SMSSendRequest(
            to_number=order.customer.phone,
            template_id=get_template_id("order_ready"),
            template_variables={
                "customer_name": order.customer.name,
                "order_number": order.order_number,
                "restaurant_name": "AuraConnect Restaurant"
            },
            customer_id=order.customer_id,
            order_id=order.id
        )
        
        await sms_service.send_sms(request)
```

## Compliance

### TCPA Compliance
- Automatic opt-out processing for STOP keywords
- Opt-in tracking with timestamps and methods
- Compliance export functionality
- Category-specific opt-outs

### GDPR Compliance
- Data retention policies
- Right to be forgotten support
- Audit trail for all operations
- Encrypted storage of phone numbers

## Cost Management

### Cost Optimization Tips
1. Use templates to reduce message length
2. Batch messages when possible
3. Monitor delivery rates and adjust retry logic
4. Use Unicode only when necessary (higher cost)
5. Implement time-of-day sending strategies

### Cost Tracking Features
- Real-time cost monitoring
- Cost breakdown by category
- Billing period reports
- Provider comparison
- Budget alerts (configurable)

## Monitoring and Analytics

### Key Metrics
- **Delivery Rate**: Percentage of successfully delivered messages
- **Average Delivery Time**: Time from send to delivery
- **Cost per Message**: Average cost including retries
- **Opt-Out Rate**: Percentage of recipients who opt out
- **Template Usage**: Most used templates and their performance

### Dashboard Queries
```sql
-- Daily SMS volume
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_messages,
    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
    SUM(cost_amount) as total_cost
FROM sms_messages
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Top templates by usage
SELECT 
    st.name,
    st.category,
    COUNT(sm.id) as usage_count,
    AVG(CASE WHEN sm.status = 'delivered' THEN 1 ELSE 0 END) as delivery_rate
FROM sms_templates st
LEFT JOIN sms_messages sm ON st.id = sm.template_id
WHERE sm.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY st.id, st.name, st.category
ORDER BY usage_count DESC
LIMIT 10;
```

## Troubleshooting

### Common Issues

1. **Messages not sending**
   - Check Twilio credentials in environment variables
   - Verify phone number format (E.164)
   - Check opt-out status
   - Review Twilio account balance

2. **High failure rate**
   - Verify phone numbers are valid
   - Check for carrier filtering
   - Review message content for spam triggers
   - Monitor Twilio service status

3. **Webhook not receiving updates**
   - Verify webhook URL is publicly accessible
   - Check SSL certificate validity
   - Review webhook logs
   - Test with Twilio webhook debugger

## Support

For issues or questions:
- Check the [API Documentation](/docs)
- Review [Twilio Documentation](https://www.twilio.com/docs/sms)
- Contact support@auraconnect.ai

## License

This module is part of the AuraConnect AI platform and is subject to the platform's licensing terms.