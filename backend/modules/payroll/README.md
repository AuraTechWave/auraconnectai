# Payroll Module - Phase 3: Payroll Engine (AUR-305)

## Overview

The Payroll Module provides comprehensive payroll processing capabilities for the AuraConnect platform. This module implements Phase 3 of the payroll system, featuring a complete payroll engine with tax calculations, configuration management, and payment tracking.

## Architecture

### Core Components

1. **Payroll Engine**
   - Enhanced payroll calculation engine
   - Integration with attendance and hours tracking
   - Multi-rate support (regular, overtime, double-time)
   - Policy-based deductions

2. **Tax Engine**
   - Multi-jurisdiction tax calculations
   - Federal, state, and local tax support
   - Social Security and Medicare calculations
   - Tax rule management with effective dates

3. **Configuration Service**
   - Database-driven payroll configurations
   - Staff pay policies
   - Overtime rules by jurisdiction
   - Role-based pay rates

4. **Payment Management**
   - Employee payment record tracking
   - Payment history and analytics
   - Export capabilities
   - Audit trail

## API Endpoints

### Base URL
All payroll endpoints are prefixed with `/api/payroll`

### Tax Calculation Endpoints

#### Calculate Payroll Taxes
```http
POST /api/payroll/tax/calculate
```

Calculate taxes for a given gross amount:
```json
{
  "gross_amount": "1000.00",
  "pay_date": "2025-01-30",
  "location": "CA",
  "employee_id": 123,
  "year_to_date_gross": "50000.00"
}
```

#### Calculate and Save Taxes
```http
POST /api/payroll/tax/calculate-and-save
```

Calculate taxes and save with audit trail:
```json
{
  "employee_id": 123,
  "gross_amount": "1000.00",
  "pay_period_start": "2025-01-15",
  "pay_period_end": "2025-01-29",
  "location": "CA",
  "tenant_id": 1
}
```

#### Get Tax Rules
```http
GET /api/payroll/tax/rules?location=CA&tax_type=STATE
```

Query parameters:
- `location` - Filter by jurisdiction
- `tax_type` - Filter by tax type (FEDERAL, STATE, LOCAL, etc.)
- `status` - Filter by status (ACTIVE, INACTIVE)
- `effective_date` - Get rules effective on date

#### Get Effective Tax Rates
```http
GET /api/payroll/tax/effective-rates?location=CA&gross_amount=1000.00
```

### Configuration Management Endpoints

#### Payroll Configurations
```http
GET /api/payroll/config/payroll-configs
POST /api/payroll/config/payroll-configs
```

#### Staff Pay Policies
```http
GET /api/payroll/config/pay-policies?staff_id=123
POST /api/payroll/config/pay-policies
PUT /api/payroll/config/pay-policies/{staff_id}
```

Create/update pay policy:
```json
{
  "staff_id": 123,
  "base_hourly_rate": "25.00",
  "overtime_multiplier": "1.5",
  "location": "CA",
  "health_insurance": "150.00",
  "retirement_401k_percentage": "6.0"
}
```

#### Overtime Rules
```http
GET /api/payroll/config/overtime-rules?location=CA
POST /api/payroll/config/overtime-rules
```

#### Role-Based Pay Rates
```http
GET /api/payroll/config/role-pay-rates?role_name=manager
POST /api/payroll/config/role-pay-rates
```

### Payment Management Endpoints

#### Get Payment History
```http
GET /api/payroll/payments/history/{employee_id}
```

Query parameters:
- `start_date` - Filter from date
- `end_date` - Filter to date
- `status` - Filter by payment status
- `limit` - Max records (default: 50)
- `offset` - Pagination offset

#### Get Payment Details
```http
GET /api/payroll/payments/{payment_id}
```

Returns complete payment breakdown including:
- Hours worked (regular, overtime, etc.)
- Earnings breakdown
- Tax deductions
- Benefit deductions
- Net pay calculation

#### Get Payment Summary
```http
GET /api/payroll/payments/summary/by-period?start_date=2025-01-01&end_date=2025-01-31
```

#### Update Payment Status
```http
PUT /api/payroll/payments/{payment_id}/status
```

Update payment status:
```json
{
  "status": "PAID",
  "payment_method": "Direct Deposit",
  "payment_reference": "DD123456"
}
```

#### Export Payment Data
```http
POST /api/payroll/payments/export
```

Export request:
```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "employee_ids": [123, 456],
  "format": "csv",
  "include_details": true
}
```

### Health Check
```http
GET /api/payroll/health
```

## Database Schema

### Core Tables

- `tax_rules` - Tax calculation rules
- `employee_payments` - Payment records
- `employee_payment_tax_applications` - Tax calculation audit trail
- `payroll_configurations` - System configurations
- `staff_pay_policies` - Individual staff pay policies
- `overtime_rules` - Jurisdiction-specific overtime rules
- `role_based_pay_rates` - Pay rates by role
- `payroll_job_tracking` - Background job tracking

## Integration with Other Modules

### Staff Module Integration
The payroll module integrates with the staff module for:
- Employee data and profiles
- Attendance and hours tracking
- Enhanced payroll routes (legacy integration)

### Tax Module Integration
Leverages the tax module for:
- Tax jurisdiction management
- Tax rate lookups
- Compliance tracking

## Configuration

### Environment Variables
```bash
# Payroll Configuration
PAYROLL_DEFAULT_LOCATION=US
PAYROLL_CALCULATION_PRECISION=2
PAYROLL_MAX_BATCH_SIZE=100

# Tax Configuration
TAX_CALCULATION_CACHE_TTL=3600
TAX_RULE_REFRESH_INTERVAL=86400
```

### Required Permissions
- `payroll.view` - View payroll information
- `payroll.calculate` - Perform calculations
- `payroll.write` - Create/update configurations
- `payroll.admin` - Full administrative access

## Usage Examples

### Calculate Payroll for Employee
```python
import httpx

# Calculate payroll taxes
response = httpx.post(
    "http://localhost:8000/api/payroll/tax/calculate",
    json={
        "gross_amount": "2500.00",
        "pay_date": "2025-01-30",
        "location": "CA",
        "employee_id": 123
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

result = response.json()
print(f"Total taxes: ${result['total_employee_taxes']}")
```

### Configure Staff Pay Policy
```python
# Create pay policy
policy_response = httpx.post(
    "http://localhost:8000/api/payroll/config/pay-policies",
    json={
        "staff_id": 123,
        "base_hourly_rate": "25.00",
        "overtime_multiplier": "1.5",
        "health_insurance": "200.00",
        "retirement_401k_percentage": "6.0"
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)
```

### Get Payment History
```python
# Get employee payment history
history = httpx.get(
    "http://localhost:8000/api/payroll/payments/history/123?limit=10",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
).json()

for payment in history['payments']:
    print(f"Period: {payment['pay_period_start']} - {payment['pay_period_end']}")
    print(f"Net Pay: ${payment['net_amount']}")
```

## Testing

Run the test suite:
```bash
# Run all payroll tests
pytest backend/modules/payroll/tests/ -v

# Run specific test file
pytest backend/modules/payroll/tests/test_payroll_routes.py -v

# Run with coverage
pytest backend/modules/payroll/tests/ --cov=backend.modules.payroll
```

## Migration Notes

### From Enhanced Payroll Routes
The payroll module now provides dedicated API endpoints. Applications using the staff module's enhanced payroll routes can migrate to use the new endpoints:

- `/payrolls/run` → `/api/payroll/tax/calculate-and-save`
- `/payrolls/{staff_id}` → `/api/payroll/payments/history/{employee_id}`
- `/payrolls/rules` → `/api/payroll/tax/rules`

## Performance Considerations

- Tax calculations are optimized with caching
- Batch operations support up to 100 employees
- Payment queries use database indexes for fast retrieval
- Configuration lookups are cached in memory

## Rate Limiting

The payroll module implements rate limiting to prevent abuse and ensure fair usage:

### Export Endpoints
- **Limit**: 3 concurrent export requests per user
- **Window**: 5 minutes
- **Error**: 429 Too Many Requests

### Calculation Endpoints
- **Limit**: 100 requests per minute per user
- **Window**: 1 minute sliding window
- **Error**: 429 Too Many Requests

### Configuration Updates
- **Limit**: 50 updates per hour per user
- **Window**: 1 hour rolling window
- **Error**: 429 Too Many Requests

## Error Response Format

All API errors follow a standardized format:

```json
{
  "error": "ValidationError",
  "message": "Invalid request parameters",
  "code": "PAYROLL_VALIDATION_ERROR",
  "details": [
    {
      "field": "gross_amount",
      "message": "Must be a positive number",
      "code": "INVALID_AMOUNT"
    }
  ],
  "timestamp": "2025-01-30T12:00:00Z",
  "request_id": "req_123abc"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PAYROLL_INVALID_AMOUNT` | 422 | Invalid monetary amount |
| `PAYROLL_INVALID_DATE_RANGE` | 422 | Start date after end date |
| `PAYROLL_NO_PAY_POLICY` | 404 | No active pay policy found |
| `PAYROLL_PAYMENT_ALREADY_PROCESSED` | 400 | Cannot modify processed payment |
| `PAYROLL_TAX_CALCULATION_FAILED` | 400 | Tax calculation error |
| `PAYROLL_CONFIG_NOT_FOUND` | 404 | Configuration not found |
| `PAYROLL_DATABASE_ERROR` | 500 | Database operation failed |
| `PAYROLL_INSUFFICIENT_PERMISSIONS` | 403 | Insufficient permissions |
| `PAYROLL_RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |

### Error Response Examples

#### Validation Error
```http
POST /api/payroll/tax/calculate
{
  "gross_amount": "invalid",
  "pay_date": "2025-01-30"
}

Response: 422 Unprocessable Entity
{
  "error": "ValidationError",
  "message": "Invalid request parameters",
  "code": "PAYROLL_VALIDATION_ERROR",
  "details": [
    {
      "field": "gross_amount",
      "message": "value is not a valid decimal",
      "code": "type_error.decimal"
    }
  ],
  "timestamp": "2025-01-30T12:00:00Z"
}
```

#### Not Found Error
```http
GET /api/payroll/payments/details/99999

Response: 404 Not Found
{
  "error": "NotFound",
  "message": "Payment with ID 99999 not found",
  "code": "PAYROLL_RECORD_NOT_FOUND",
  "timestamp": "2025-01-30T12:00:00Z"
}
```

#### Business Rule Violation
```http
PUT /api/payroll/payments/123/status
{
  "status": "PENDING"
}

Response: 400 Bad Request
{
  "error": "InvalidTransition",
  "message": "Cannot change status of a paid payment",
  "code": "PAYROLL_PAYMENT_ALREADY_PROCESSED",
  "timestamp": "2025-01-30T12:00:00Z"
}
```

#### Rate Limit Exceeded
```http
POST /api/payroll/payments/export

Response: 429 Too Many Requests
{
  "error": "RateLimitExceeded",
  "message": "Too many export requests. Please wait for existing exports to complete.",
  "code": "PAYROLL_RATE_LIMIT_EXCEEDED",
  "timestamp": "2025-01-30T12:00:00Z",
  "retry_after": 300
}
```

## Future Enhancements

- GraphQL API support
- Real-time payroll analytics
- Advanced reporting templates
- Integration with accounting systems
- Multi-currency support
- Automated compliance reporting