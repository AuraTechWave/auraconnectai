# Split Bill and Tip Management Feature

## Overview

The Split Bill and Tip Management feature allows restaurant customers to split their bills among multiple participants using various methods, calculate tips, and manage tip distributions to staff.

## Key Features

### Bill Splitting Methods

1. **Equal Split** - Divide the total bill equally among all participants
2. **Percentage Split** - Split based on predefined percentages
3. **Amount Split** - Each participant pays a specific fixed amount
4. **Item Split** - Participants pay for specific items they ordered
5. **Custom Split** - Flexible custom splitting logic

### Tip Management

1. **Tip Calculation Methods**
   - Percentage of subtotal
   - Fixed amount
   - Round up to nearest dollar amount

2. **Tip Distribution Methods**
   - Equal pool distribution
   - Percentage-based distribution
   - Role-based distribution (servers, bartenders, etc.)
   - Direct assignment to specific staff

### Participant Management

- Email/SMS notifications for bill splits
- Guest access via secure tokens (no account required)
- Accept/decline participation
- Partial payment support
- Payment tracking and reconciliation

## API Endpoints

### Split Bill Endpoints

```
POST   /api/payments/splits/                 - Create a new bill split
GET    /api/payments/splits/{split_id}       - Get split details
GET    /api/payments/splits/participant/{token} - Get participant details by token
PUT    /api/payments/splits/participant/{id}/status - Update participant status
POST   /api/payments/splits/participant/{id}/pay - Process participant payment
POST   /api/payments/splits/{split_id}/cancel - Cancel a split
POST   /api/payments/splits/{split_id}/remind - Send payment reminders
```

### Tip Endpoints

```
POST   /api/payments/splits/tips/calculate   - Calculate tip amount
POST   /api/payments/splits/tips/suggestions - Get tip suggestions
POST   /api/payments/splits/{split_id}/tips/distribute - Process tip distribution
```

## Usage Examples

### Creating an Equal Split

```python
POST /api/payments/splits/
{
  "order_id": 123,
  "split_method": "equal",
  "participants": [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"}
  ],
  "tip_method": "percentage",
  "tip_value": 18
}
```

### Creating a Percentage Split

```python
POST /api/payments/splits/
{
  "order_id": 123,
  "split_method": "percentage",
  "participants": [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"}
  ],
  "split_config": {
    "percentages": {
      "alice@example.com": 60,
      "bob@example.com": 40
    }
  },
  "tip_method": "percentage",
  "tip_value": 20
}
```

### Creating an Item-Based Split

```python
POST /api/payments/splits/
{
  "order_id": 123,
  "split_method": "item",
  "participants": [
    {"name": "Alice", "email": "alice@example.com", "id": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com", "id": "bob@example.com"}
  ],
  "split_config": {
    "items": [
      {
        "item_id": 1,
        "price": 25.00,
        "quantity": 1,
        "participant_ids": ["alice@example.com"]
      },
      {
        "item_id": 2,
        "price": 30.00,
        "quantity": 1,
        "participant_ids": ["bob@example.com"]
      },
      {
        "item_id": 3,
        "price": 15.00,
        "quantity": 1,
        "participant_ids": ["alice@example.com", "bob@example.com"]
      }
    ]
  },
  "tip_method": "percentage",
  "tip_value": 18
}
```

### Processing a Participant Payment

```python
POST /api/payments/splits/participant/456/pay
{
  "gateway": "stripe",
  "amount": 35.50,
  "payment_method_id": "pm_xxx",
  "save_payment_method": false
}
```

## Database Schema

### Core Tables

1. **bill_splits** - Main split bill records
2. **split_participants** - Individual participant information
3. **payment_allocations** - Links payments to splits and participants
4. **tip_distributions** - Tip distribution configuration and history

### Key Relationships

- Orders can have multiple bill splits
- Bill splits have multiple participants
- Participants can have multiple payments
- Payments are allocated to specific splits and participants
- Tips are distributed based on configured rules

## Configuration Options

### Split Settings

- `allow_partial_payments` - Allow participants to make multiple payments
- `require_all_acceptance` - Require all participants to accept before activation
- `auto_close_on_completion` - Automatically close split when all have paid
- `send_reminders` - Enable automatic payment reminders
- `expires_in_hours` - Set expiration time for the split

### Tip Distribution Settings

- Distribution method (pool, percentage, role, direct)
- Role-based percentages
- Custom distribution rules
- Adjustment capabilities

## Security Considerations

1. **Access Control**
   - Organizers can view all participant details
   - Participants can only view their own information
   - Guest access via secure tokens

2. **Payment Security**
   - Integration with secure payment gateways
   - PCI compliance through gateway providers
   - Idempotency keys to prevent duplicate charges

3. **Data Privacy**
   - Email/phone numbers only visible to organizers
   - Secure token generation for guest access
   - Audit trail for all transactions

## Best Practices

1. **Creating Splits**
   - Always validate total amounts match
   - Set appropriate expiration times
   - Consider tax and service charge distribution

2. **Tip Management**
   - Configure default tip percentages
   - Set up role-based distribution rules
   - Regular review of tip distribution patterns

3. **Payment Processing**
   - Handle partial payments gracefully
   - Implement retry logic for failed payments
   - Send confirmation notifications

## Testing

Comprehensive test coverage includes:
- All split methods (equal, percentage, amount, item)
- Participant acceptance/decline flows
- Payment recording and reconciliation
- Tip calculation and distribution
- Edge cases and validation

Run tests with:
```bash
pytest backend/tests/test_split_bill.py -v
```

## Future Enhancements

1. **Advanced Features**
   - QR code generation for easy sharing
   - Integration with POS systems for automatic item assignment
   - Venmo/PayPal integration for peer-to-peer settlement
   - Split templates for regular groups

2. **Analytics**
   - Average split sizes and methods
   - Tip distribution analytics
   - Payment success rates
   - Popular splitting patterns

3. **Mobile App Integration**
   - Native split bill UI
   - Push notifications
   - Offline support with sync

## Support

For issues or questions related to the split bill feature:
1. Check the API documentation
2. Review test cases for examples
3. Contact the development team
4. Submit issues via the project tracker