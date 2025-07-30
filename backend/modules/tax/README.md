# Tax Services Module - Phase 2 (AUR-304)

## Overview

The Tax Services Module provides comprehensive tax management capabilities for multi-jurisdiction businesses. This module handles tax calculations, compliance, filing automation, and integration with external tax services.

## Architecture

### Core Components

1. **Tax Calculation Engine**
   - Multi-jurisdiction tax calculation
   - Rule-based tax determination
   - Exemption certificate management
   - Real-time rate lookups

2. **Tax Compliance Service**
   - Filing management and tracking
   - Automated filing generation
   - Remittance processing
   - Audit trail maintenance

3. **Tax Filing Automation**
   - Scheduled filing generation
   - Auto-submission capabilities
   - Reconciliation tools
   - Estimated payment calculations

4. **External Integrations**
   - Avalara AvaTax
   - TaxJar
   - Extensible provider framework

## Key Features

### Multi-Jurisdiction Support
- Federal, state, county, city, and special district taxes
- Nexus management
- Cross-border capabilities
- Jurisdiction hierarchy

### Tax Calculation
- Line-item level calculations
- Multiple tax types (sales, use, excise, etc.)
- Tiered and compound rates
- Tax holidays and special rules
- Shipping and handling tax

### Compliance Management
- Filing calendar and deadlines
- Document generation
- Electronic filing
- Payment tracking
- Amendment handling

### Automation
- Scheduled filing generation
- Transaction reconciliation
- Estimated tax calculations
- Bulk operations

### Reporting & Analytics
- Compliance dashboards
- Tax liability reports
- Audit trails
- Custom report templates

## Database Schema

### Core Tables

- `tax_jurisdictions` - Tax jurisdiction definitions
- `tax_rates` - Tax rates by jurisdiction and type
- `tax_rule_configurations` - Special tax rules and conditions
- `tax_exemption_certificates` - Customer exemption certificates
- `tax_nexus` - Business nexus registrations
- `tax_filings` - Tax return filings
- `tax_filing_line_items` - Filing detail lines
- `tax_remittances` - Tax payments
- `tax_audit_logs` - Comprehensive audit trail
- `tax_report_templates` - Report format templates

## API Endpoints

### Jurisdiction Management
- `POST /api/tax/jurisdictions` - Create jurisdiction
- `GET /api/tax/jurisdictions` - List jurisdictions
- `GET /api/tax/jurisdictions/{id}` - Get jurisdiction details
- `PATCH /api/tax/jurisdictions/{id}` - Update jurisdiction
- `POST /api/tax/jurisdictions/{id}/rates` - Add tax rate
- `GET /api/tax/jurisdictions/{id}/rates` - List jurisdiction rates

### Tax Calculation
- `POST /api/tax/calculations/calculate` - Calculate tax
- `POST /api/tax/calculations/validate-address` - Validate address
- `GET /api/tax/calculations/rates` - Get tax rates for location
- `POST /api/tax/calculations/exemptions` - Create exemption certificate
- `GET /api/tax/calculations/exemptions` - List exemption certificates

### Compliance & Filing
- `POST /api/tax/compliance/filings` - Create filing
- `GET /api/tax/compliance/filings` - List filings
- `PATCH /api/tax/compliance/filings/{id}` - Update filing
- `POST /api/tax/compliance/filings/{id}/submit` - Submit filing
- `POST /api/tax/compliance/filings/{id}/amend` - Amend filing
- `POST /api/tax/compliance/remittances` - Create payment
- `GET /api/tax/compliance/dashboard` - Compliance dashboard
- `POST /api/tax/compliance/reports` - Generate report

### Automation
- `POST /api/tax/compliance/automation/schedule` - Schedule automation
- `POST /api/tax/compliance/automation/generate/{nexus_id}` - Generate filing
- `POST /api/tax/compliance/automation/submit` - Auto-submit filings
- `POST /api/tax/compliance/automation/reconcile` - Reconcile accounts
- `GET /api/tax/compliance/automation/estimated-payments` - Get estimated payments

## Configuration

### Environment Variables

```bash
# Tax Service Configuration
TAX_DEFAULT_PROVIDER=internal          # Default tax calculation provider
TAX_CALCULATION_CACHE_TTL=3600        # Cache TTL in seconds

# Avalara Integration
AVALARA_ENABLED=false
AVALARA_ACCOUNT_ID=your_account_id
AVALARA_LICENSE_KEY=your_license_key
AVALARA_COMPANY_CODE=DEFAULT
AVALARA_ENVIRONMENT=sandbox

# TaxJar Integration
TAXJAR_ENABLED=false
TAXJAR_API_TOKEN=your_api_token

# Automation Settings
TAX_AUTOMATION_ENABLED=true
TAX_AUTOMATION_FREQUENCY=daily
TAX_AUTO_SUBMIT_ENABLED=false
```

### Permissions

Required permissions for tax operations:

- `tax.view` - View tax information
- `tax.calculate` - Perform tax calculations
- `tax.admin` - Manage jurisdictions and rates
- `tax.file` - Create and submit filings
- `tax.pay` - Process tax payments
- `tax.report` - Generate tax reports
- `tax.audit` - View audit logs

## Usage Examples

### Calculate Tax for a Transaction

```python
import httpx
from decimal import Decimal

# Calculate tax
response = httpx.post(
    "https://api.example.com/tax/calculations/calculate",
    json={
        "transaction_id": "ORDER-123",
        "transaction_date": "2025-01-30",
        "location": {
            "country_code": "US",
            "state_code": "CA",
            "city_name": "Los Angeles",
            "zip_code": "90001"
        },
        "line_items": [
            {
                "line_id": "item1",
                "amount": "100.00",
                "quantity": 2,
                "category": "general"
            }
        ],
        "shipping_amount": "10.00"
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

result = response.json()
print(f"Total Tax: ${result['total_tax']}")
print(f"Total Amount: ${result['total_amount']}")
```

### Create and Submit a Tax Filing

```python
# Create filing
filing_response = httpx.post(
    "https://api.example.com/tax/compliance/filings",
    json={
        "internal_reference": "CA-2025-01",
        "jurisdiction_id": 123,
        "filing_type": "sales_tax",
        "period_start": "2025-01-01",
        "period_end": "2025-01-31",
        "due_date": "2025-02-20",
        "gross_sales": "150000.00",
        "taxable_sales": "140000.00",
        "exempt_sales": "10000.00",
        "tax_collected": "11200.00",
        "line_items": [
            {
                "line_number": "1",
                "description": "Taxable sales",
                "gross_amount": "140000.00",
                "taxable_amount": "140000.00",
                "tax_rate": "8.0",
                "tax_amount": "11200.00"
            }
        ]
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

filing = filing_response.json()

# Submit filing
submit_response = httpx.post(
    f"https://api.example.com/tax/compliance/filings/{filing['id']}/submit",
    json={
        "prepared_by": "John Doe",
        "reviewed_by": "Jane Smith",
        "submission_method": "electronic"
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)
```

### Get Compliance Dashboard

```python
# Get compliance overview
dashboard = httpx.get(
    "https://api.example.com/tax/compliance/dashboard",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
).json()

print(f"Compliance Score: {dashboard['overall_compliance_score']}%")
print(f"Upcoming Deadlines: {len(dashboard['upcoming_deadlines'])}")
print(f"Overdue Filings: {len(dashboard['overdue_filings'])}")
print(f"Outstanding Balance: ${dashboard['outstanding_balance']}")

for deadline in dashboard['upcoming_deadlines']:
    print(f"- {deadline['jurisdiction']} due {deadline['due_date']}")
```

## Testing

The module includes comprehensive test coverage:

```bash
# Run all tax module tests
pytest backend/modules/tax/tests/

# Run specific test suite
pytest backend/modules/tax/tests/test_tax_calculation_engine.py
pytest backend/modules/tax/tests/test_tax_compliance_service.py

# Run with coverage
pytest backend/modules/tax/tests/ --cov=backend.modules.tax
```

## Migration

To apply the tax module database migrations:

```bash
# Create migration
alembic revision --autogenerate -m "Add enhanced tax tables"

# Apply migration
alembic upgrade head
```

## Best Practices

### Tax Calculation
1. Always validate addresses before calculating tax
2. Cache tax calculations for identical requests
3. Use exemption certificates for tax-exempt customers
4. Handle tax holidays and special rules appropriately

### Compliance
1. Set up automated filing schedules
2. Review filings before submission
3. Maintain accurate nexus information
4. Keep exemption certificates up to date
5. Regularly reconcile tax accounts

### Integration
1. Use webhook notifications for filing status updates
2. Implement retry logic for external API calls
3. Store external provider responses for audit
4. Monitor API usage and rate limits

## Troubleshooting

### Common Issues

1. **"No tax rates found"**
   - Ensure jurisdictions are properly configured
   - Check that rates are active and not expired
   - Verify location data is accurate

2. **"Filing already exists"**
   - Check for existing filings for the same period
   - Use amendment process for corrections

3. **"External provider error"**
   - Verify API credentials
   - Check provider service status
   - Review rate limits

## Support

For issues or questions:
- Internal Documentation: `/docs/tax-services`
- API Reference: `/api/docs#/Tax`
- Support Email: tax-support@example.com

## Future Enhancements

- Machine learning for tax categorization
- Blockchain audit trail
- Real-time tax rate updates
- International tax support expansion
- Advanced analytics and forecasting