# API Error Code Registry

This document provides a comprehensive list of all error codes returned by the AuraConnect API.

## Error Response Format

All errors follow this standard format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    },
    "request_id": "req_xyz789",
    "timestamp": "2025-08-08T12:00:00Z"
  }
}
```

## Error Codes by Category

### Authentication Errors (1000-1099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `AUTH_INVALID_CREDENTIALS` | 401 | Invalid username or password | Verify credentials are correct |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT token has expired | Refresh token or re-authenticate |
| `AUTH_TOKEN_INVALID` | 401 | JWT token is malformed or invalid | Re-authenticate |
| `AUTH_INSUFFICIENT_PERMISSIONS` | 403 | User lacks required permissions | Check user roles and permissions |
| `AUTH_ACCOUNT_LOCKED` | 423 | Account locked due to failed attempts | Wait 30 minutes or contact admin |
| `AUTH_EMAIL_NOT_VERIFIED` | 403 | Email verification required | Verify email address |
| `AUTH_REFRESH_TOKEN_INVALID` | 401 | Refresh token invalid or expired | Re-authenticate |

### Validation Errors (2000-2099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `VALIDATION_REQUIRED_FIELD` | 400 | Required field missing | Include all required fields |
| `VALIDATION_INVALID_FORMAT` | 400 | Field format invalid | Check field format requirements |
| `VALIDATION_INVALID_TYPE` | 400 | Field type mismatch | Use correct data type |
| `VALIDATION_OUT_OF_RANGE` | 400 | Value outside allowed range | Check min/max constraints |
| `VALIDATION_DUPLICATE_ENTRY` | 409 | Duplicate unique value | Use different value |
| `VALIDATION_INVALID_ENUM` | 400 | Invalid enum value | Use allowed enum values |
| `VALIDATION_INVALID_DATE` | 400 | Invalid date format | Use ISO 8601 format |

### Business Logic Errors (3000-3099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `ORDER_INVALID_STATUS_TRANSITION` | 400 | Invalid order status change | Check allowed transitions |
| `ORDER_ALREADY_COMPLETED` | 409 | Order already completed | Cannot modify completed orders |
| `INVENTORY_INSUFFICIENT_STOCK` | 409 | Not enough inventory | Check stock levels |
| `PAYMENT_INSUFFICIENT_FUNDS` | 402 | Payment failed - insufficient funds | Use different payment method |
| `PAYMENT_ALREADY_REFUNDED` | 409 | Payment already refunded | Check refund status |
| `SCHEDULE_CONFLICT` | 409 | Schedule overlap detected | Choose different time |
| `RECIPE_CIRCULAR_DEPENDENCY` | 400 | Circular recipe dependency | Remove circular reference |

### Resource Errors (4000-4099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `RESOURCE_NOT_FOUND` | 404 | Requested resource not found | Verify resource ID |
| `RESOURCE_DELETED` | 410 | Resource has been deleted | Resource no longer available |
| `RESOURCE_LOCKED` | 423 | Resource temporarily locked | Retry after delay |
| `RESOURCE_QUOTA_EXCEEDED` | 429 | Resource limit exceeded | Upgrade plan or wait |

### Integration Errors (5000-5099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `POS_CONNECTION_FAILED` | 503 | Cannot connect to POS system | Check POS configuration |
| `POS_SYNC_FAILED` | 502 | POS synchronization failed | Retry or check logs |
| `PAYMENT_GATEWAY_ERROR` | 502 | Payment gateway error | Try different gateway |
| `EMAIL_SEND_FAILED` | 503 | Email service unavailable | Retry later |
| `SMS_SEND_FAILED` | 503 | SMS service unavailable | Retry later |

### System Errors (9000-9099)

| Code | HTTP Status | Description | Resolution |
|------|-------------|-------------|------------|
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error | Contact support |
| `DATABASE_ERROR` | 503 | Database connection error | Retry later |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily down | Check status page |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Wait and retry |
| `MAINTENANCE_MODE` | 503 | System under maintenance | Check maintenance schedule |

## Rate Limiting Headers

When rate limited, responses include:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1628856000
Retry-After: 60
```

## Common Resolution Steps

### Authentication Issues
1. Verify API credentials are correct
2. Check token expiration
3. Ensure proper permissions assigned
4. Verify account is active

### Validation Issues
1. Check API documentation for field requirements
2. Verify data types match schema
3. Ensure enum values are from allowed list
4. Validate date formats are ISO 8601

### Resource Issues
1. Verify resource ID exists
2. Check resource hasn't been deleted
3. Ensure you have access permissions
4. Verify resource isn't locked by another process

### Integration Issues
1. Check third-party service status
2. Verify API keys and credentials
3. Check network connectivity
4. Review integration logs

## Error Handling Best Practices

1. **Always check error codes** - Don't rely on HTTP status alone
2. **Log request_id** - Include in support tickets
3. **Implement exponential backoff** - For 429 and 503 errors
4. **Handle errors gracefully** - Show user-friendly messages
5. **Monitor error rates** - Set up alerts for error spikes

## Support

For persistent errors, contact support with:
- Error code
- Request ID
- Timestamp
- Request details (without sensitive data)