# Payroll & Tax Module API Documentation

## Overview

The Payroll & Tax Module provides comprehensive RESTful APIs for managing employee payroll, tax calculations, and payment processing. This document covers all available endpoints, request/response formats, and integration guidelines.

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL](#base-url)
3. [Core Endpoints](#core-endpoints)
4. [API v1 Endpoints](#api-v1-endpoints)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Webhooks](#webhooks)
8. [Examples](#examples)

## Authentication

All API endpoints require JWT authentication. Include the token in the Authorization header:

```http
Authorization: Bearer <your-jwt-token>
```

Required permissions vary by endpoint:
- `payroll:read` - View payroll data
- `payroll:write` - Create/update payroll data
- `payroll:admin` - Administrative operations

## Base URL

```
https://api.auraconnect.com/api/payroll
```

## Core Endpoints

### Calculate Payroll

Calculate payroll for a single employee.

**POST** `/calculate`

**Request Body:**
```json
{
  "employee_id": 123,
  "pay_period_start": "2024-01-01",
  "pay_period_end": "2024-01-14",
  "hours_worked": {
    "regular": 80.0,
    "overtime": 5.0
  },
  "adjustments": {
    "bonus": 500.00,
    "reimbursements": 150.00
  },
  "deductions": {
    "retirement_401k": 300.00,
    "health_insurance": 200.00
  }
}
```

**Response:**
```json
{
  "calculation_id": "calc_20240115_123",
  "employee_id": 123,
  "pay_period": {
    "start": "2024-01-01",
    "end": "2024-01-14"
  },
  "earnings": {
    "regular_pay": 2000.00,
    "overtime_pay": 187.50,
    "bonus": 500.00,
    "reimbursements": 150.00,
    "gross_pay": 2837.50
  },
  "taxes": {
    "federal_income_tax": 425.63,
    "state_income_tax": 141.88,
    "social_security": 175.93,
    "medicare": 41.14,
    "local_tax": 0.00,
    "total_taxes": 784.58
  },
  "deductions": {
    "retirement_401k": 300.00,
    "health_insurance": 200.00,
    "total_deductions": 500.00
  },
  "net_pay": 1552.92,
  "ytd_totals": {
    "gross_pay": 5675.00,
    "net_pay": 3105.84,
    "federal_tax": 851.26,
    "state_tax": 283.76
  }
}
```

### Process Payment

Process a calculated payroll payment.

**POST** `/payments`

**Request Body:**
```json
{
  "calculation_id": "calc_20240115_123",
  "payment_method": "direct_deposit",
  "payment_date": "2024-01-19",
  "bank_details": {
    "account_number": "****1234",
    "routing_number": "****5678"
  }
}
```

**Response:**
```json
{
  "payment_id": 456,
  "status": "pending",
  "employee_id": 123,
  "gross_pay": 2837.50,
  "net_pay": 1552.92,
  "payment_date": "2024-01-19",
  "payment_method": "direct_deposit",
  "confirmation_number": "DD20240119-456"
}
```

### Configuration Management

#### Get Configuration

**GET** `/configuration/{config_type}`

**Query Parameters:**
- `location` - Filter by location (optional)
- `effective_date` - Configuration effective on date (optional)

**Response:**
```json
{
  "configurations": [
    {
      "id": 1,
      "type": "overtime_rules",
      "key": "california_overtime",
      "value": {
        "daily_threshold": 8,
        "weekly_threshold": 40,
        "daily_multiplier": 1.5,
        "double_time_threshold": 12,
        "double_time_multiplier": 2.0
      },
      "location": "california",
      "effective_date": "2024-01-01",
      "is_active": true
    }
  ]
}
```

#### Update Configuration

**PUT** `/configuration/{config_id}`

**Request Body:**
```json
{
  "value": {
    "daily_threshold": 8,
    "weekly_threshold": 40,
    "daily_multiplier": 1.5
  },
  "effective_date": "2024-02-01"
}
```

### Payment History

**GET** `/payments/history`

**Query Parameters:**
- `employee_id` - Filter by employee
- `start_date` - Period start date
- `end_date` - Period end date
- `status` - Payment status filter
- `page` - Page number (default: 1)
- `limit` - Results per page (default: 20)

**Response:**
```json
{
  "payments": [
    {
      "payment_id": 456,
      "employee_id": 123,
      "pay_period": {
        "start": "2024-01-01",
        "end": "2024-01-14"
      },
      "gross_pay": 2837.50,
      "net_pay": 1552.92,
      "payment_date": "2024-01-19",
      "status": "completed"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 156,
    "pages": 8
  }
}
```

## API v1 Endpoints

### Batch Processing

#### Create Batch Job

**POST** `/api/v1/payroll/batch/run`

**Request Body:**
```json
{
  "pay_period_start": "2024-01-01",
  "pay_period_end": "2024-01-14",
  "employee_ids": [123, 124, 125],
  "calculation_options": {
    "include_overtime": true,
    "include_benefits": true,
    "include_deductions": true,
    "use_ytd_calculations": true
  }
}
```

**Response:**
```json
{
  "job_id": "batch_20240115_001",
  "status": "queued",
  "total_employees": 3,
  "estimated_completion": "2024-01-15T10:30:00Z",
  "tracking_url": "/api/v1/payroll/batch/status/batch_20240115_001"
}
```

#### Get Batch Status

**GET** `/api/v1/payroll/batch/status/{job_id}`

**Response:**
```json
{
  "job_id": "batch_20240115_001",
  "status": "processing",
  "progress": {
    "total": 100,
    "processed": 45,
    "successful": 43,
    "failed": 2,
    "percentage": 45
  },
  "errors": [
    {
      "employee_id": 156,
      "error": "Missing timesheet data",
      "code": "MISSING_DATA"
    }
  ],
  "started_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:15:00Z"
}
```

### Webhooks

#### Subscribe to Webhook

**POST** `/api/v1/payroll/webhooks/subscribe`

**Request Body:**
```json
{
  "url": "https://example.com/payroll-webhook",
  "events": ["payment.completed", "batch.finished"],
  "secret": "webhook_secret_key",
  "active": true
}
```

**Response:**
```json
{
  "subscription_id": "sub_789",
  "url": "https://example.com/payroll-webhook",
  "events": ["payment.completed", "batch.finished"],
  "created_at": "2024-01-15T10:00:00Z",
  "status": "active"
}
```

#### Webhook Events

**Payment Completed Event:**
```json
{
  "event": "payment.completed",
  "timestamp": "2024-01-19T15:30:00Z",
  "data": {
    "payment_id": 456,
    "employee_id": 123,
    "amount": 1552.92,
    "payment_date": "2024-01-19",
    "confirmation": "DD20240119-456"
  },
  "signature": "sha256=..."
}
```

### Audit Trail

#### Get Audit Logs

**GET** `/api/v1/payroll/audit/logs`

**Query Parameters:**
- `start_date` - Filter start date
- `end_date` - Filter end date
- `user_id` - Filter by user
- `action` - Filter by action type
- `entity_type` - Filter by entity (payment, configuration, etc.)

**Response:**
```json
{
  "logs": [
    {
      "id": 1234,
      "timestamp": "2024-01-15T10:00:00Z",
      "user_id": 456,
      "action": "payment.created",
      "entity_type": "payment",
      "entity_id": "789",
      "changes": {
        "gross_pay": 2837.50,
        "net_pay": 1552.92
      },
      "ip_address": "192.168.1.100"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1234
  }
}
```

### Reports & Exports

#### Export Payments

**POST** `/api/v1/payroll/export/payments`

**Request Body:**
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "format": "csv",
  "include_details": true,
  "filters": {
    "department": ["Engineering", "Sales"],
    "location": ["california"]
  }
}
```

**Response:**
```json
{
  "export_id": "exp_20240115_001",
  "status": "processing",
  "format": "csv",
  "estimated_size": "2.5MB",
  "download_url": "/api/v1/payroll/export/download/exp_20240115_001"
}
```

#### Generate Tax Forms

**POST** `/api/v1/payroll/reports/tax-forms`

**Request Body:**
```json
{
  "year": 2023,
  "form_type": "W2",
  "employee_ids": [123, 124, 125],
  "delivery_method": "electronic"
}
```

**Response:**
```json
{
  "report_id": "w2_2023_batch001",
  "status": "generating",
  "total_forms": 3,
  "completion_url": "/api/v1/payroll/reports/status/w2_2023_batch001"
}
```

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "pay_period_start",
        "message": "Date must be in YYYY-MM-DD format"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `NOT_FOUND` | 404 | Resource not found |
| `INSUFFICIENT_PERMISSIONS` | 403 | Lacking required permissions |
| `CALCULATION_ERROR` | 400 | Payroll calculation failed |
| `PAYMENT_PROCESSING_ERROR` | 500 | Payment processing failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `WEBHOOK_DELIVERY_FAILED` | 500 | Webhook notification failed |

## Rate Limiting

API endpoints are rate limited to ensure fair usage:

- **Standard endpoints**: 100 requests per minute
- **Batch operations**: 10 requests per minute
- **Export operations**: 5 requests per minute

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1673784000
```

## Examples

### Complete Payroll Processing Flow

```python
import requests
import json
from datetime import date, timedelta

# Configuration
BASE_URL = "https://api.auraconnect.com/api/payroll"
AUTH_TOKEN = "your-jwt-token"
headers = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Calculate payroll for an employee
calculate_payload = {
    "employee_id": 123,
    "pay_period_start": "2024-01-01",
    "pay_period_end": "2024-01-14",
    "hours_worked": {
        "regular": 80.0,
        "overtime": 5.0
    }
}

response = requests.post(
    f"{BASE_URL}/calculate",
    headers=headers,
    json=calculate_payload
)
calculation = response.json()
print(f"Calculation ID: {calculation['calculation_id']}")
print(f"Net Pay: ${calculation['net_pay']}")

# 2. Process the payment
payment_payload = {
    "calculation_id": calculation['calculation_id'],
    "payment_method": "direct_deposit",
    "payment_date": "2024-01-19"
}

response = requests.post(
    f"{BASE_URL}/payments",
    headers=headers,
    json=payment_payload
)
payment = response.json()
print(f"Payment ID: {payment['payment_id']}")
print(f"Status: {payment['status']}")

# 3. Check payment status
response = requests.get(
    f"{BASE_URL}/payments/{payment['payment_id']}",
    headers=headers
)
status = response.json()
print(f"Payment Status: {status['status']}")
```

### Batch Processing Example

```python
# Process payroll for multiple employees
batch_payload = {
    "pay_period_start": "2024-01-01",
    "pay_period_end": "2024-01-14",
    "employee_ids": None,  # Process all active employees
    "calculation_options": {
        "include_overtime": True,
        "include_benefits": True,
        "include_deductions": True,
        "use_ytd_calculations": True
    }
}

# Start batch job
response = requests.post(
    f"{BASE_URL}/api/v1/payroll/batch/run",
    headers=headers,
    json=batch_payload
)
batch_job = response.json()
job_id = batch_job['job_id']

# Poll for status
import time
while True:
    response = requests.get(
        f"{BASE_URL}/api/v1/payroll/batch/status/{job_id}",
        headers=headers
    )
    status = response.json()
    
    print(f"Progress: {status['progress']['percentage']}%")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(5)  # Wait 5 seconds before next check

print(f"Batch job {status['status']}")
print(f"Processed: {status['progress']['processed']} employees")
```

### Webhook Integration Example

```python
from flask import Flask, request
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

@app.route('/payroll-webhook', methods=['POST'])
def handle_payroll_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, f"sha256={expected_sig}"):
        return "Invalid signature", 401
    
    # Process event
    event = request.json
    event_type = event['event']
    
    if event_type == 'payment.completed':
        payment_data = event['data']
        print(f"Payment completed for employee {payment_data['employee_id']}")
        # Update your system
        
    elif event_type == 'batch.finished':
        batch_data = event['data']
        print(f"Batch {batch_data['job_id']} completed")
        # Process results
    
    return "OK", 200
```

## API Versioning

The Payroll API uses URL-based versioning. The current version is v1. When breaking changes are introduced, a new version will be created while maintaining backward compatibility.

Version lifecycle:
- **Current**: v1 (fully supported)
- **Deprecated**: None
- **Sunset**: None

## Support

For API support and questions:
- Documentation: https://docs.auraconnect.com/payroll
- API Status: https://status.auraconnect.com
- Support Email: api-support@auraconnect.com
- Developer Forum: https://forum.auraconnect.com/payroll-api