# AuraConnect Production Security Hardening

This document describes the security hardening measures implemented for production deployment.

## Overview

The following security enhancements have been implemented to ensure the application meets production security requirements:

1. **Debug Endpoint Protection**
2. **Webhook Signature Validation**
3. **Comprehensive Audit Logging**
4. **Enhanced Rate Limiting**
5. **Security Headers**
6. **API Version Security**

## 1. Debug Endpoint Protection

### Implementation
- All debug endpoints are now protected by the `@protect_debug_endpoint` decorator
- Debug endpoints return 404 in production unless explicitly enabled
- Configuration via environment variables:
  - `DEBUG_ENDPOINTS_ENABLED=true` - Enable debug endpoints in production (not recommended)
  - `DEBUG_ENDPOINTS_WHITELIST=endpoint1,endpoint2` - Whitelist specific endpoints

### Example
```python
@app.get("/debug/token")
@protect_debug_endpoint(allowed_envs=["development"])
async def debug_token(...):
    # This endpoint is only accessible in development
```

## 2. Webhook Signature Validation

### Implementation
- HMAC-SHA256 signature validation for all incoming webhooks
- Timestamp validation to prevent replay attacks
- Per-source webhook secrets
- Comprehensive validation logging

### Configuration
Set webhook secrets via environment variables:
```bash
WEBHOOK_SECRET_SQUARE=your-square-webhook-secret
WEBHOOK_SECRET_TOAST=your-toast-webhook-secret
WEBHOOK_SECRET_CLOVER=your-clover-webhook-secret
WEBHOOK_SECRET_STRIPE=your-stripe-webhook-secret
WEBHOOK_SECRET_TWILIO=your-twilio-webhook-secret
```

### Usage
```python
from core.webhook_security import validate_webhook_signature

@app.post("/webhooks/square")
async def handle_square_webhook(
    request: Request,
    _: None = Depends(lambda req: validate_webhook_signature(req, "square"))
):
    # Webhook is validated before reaching this point
```

## 3. Comprehensive Audit Logging

### Features
- Logs all sensitive operations to both database and files
- Tracks user actions, IP addresses, and request metadata
- Automatic log rotation and retention
- Sanitizes sensitive data before logging

### Monitored Operations
- User creation/deletion
- Role changes
- Payment processing
- Payroll operations
- Settings updates
- Data import/export

### Log Location
- Production: `/var/log/auraconnect/audit/`
- Development: `./logs/audit/`

## 4. Enhanced Rate Limiting

### Authentication Endpoints
- Login: 5 attempts per 5 minutes
- Registration: 3 attempts per hour
- Password reset: 3 attempts per hour
- Token refresh: 10 attempts per 10 minutes

### Features
- Per-IP and per-user rate limiting
- Exponential backoff for repeated failures
- Redis-based distributed rate limiting
- Automatic failure tracking

### Configuration
```python
RATE_LIMIT_CONFIG = {
    "auth_endpoints": {
        "login": {"requests": 5, "window": 300},
        "register": {"requests": 3, "window": 3600},
        # ...
    }
}
```

## 5. Security Headers

### Applied Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy` (production only)
- `Strict-Transport-Security` (production/staging only)

### Implementation
Security headers are automatically applied by the `SecurityMiddleware` to all responses.

## 6. API Version Security

### Features
- Deprecation warnings for old API versions
- Automatic blocking of disabled API versions
- Version tracking in audit logs

### Configuration
```python
DEPRECATED_API_VERSIONS = {"v1"}  # Versions to warn about
DISABLED_API_VERSIONS = set()     # Versions to block
```

## Environment Variables

### Required for Production
```bash
# Environment
ENVIRONMENT=production
DEBUG_ENDPOINTS_ENABLED=false

# Database
DATABASE_URL=postgresql://user:pass@host/db

# Redis (for rate limiting)
REDIS_URL=redis://host:6379/0

# JWT Secret
JWT_SECRET_KEY=your-strong-secret-key

# Webhook Secrets
WEBHOOK_SECRET_SQUARE=...
WEBHOOK_SECRET_TOAST=...
# etc.
```

## Security Checklist

Before deploying to production, ensure:

- [ ] `ENVIRONMENT=production` is set
- [ ] All webhook secrets are configured
- [ ] Redis is configured for rate limiting
- [ ] Audit log directory has proper permissions
- [ ] JWT secret is strong and unique
- [ ] Database SSL is enabled
- [ ] HTTPS is enforced at load balancer
- [ ] Debug endpoints are disabled
- [ ] Log aggregation is configured

## Monitoring

### Key Metrics to Monitor
1. Failed authentication attempts
2. Rate limit violations
3. Webhook validation failures
4. Unusual API usage patterns
5. Audit log anomalies

### Recommended Alerts
- More than 10 failed login attempts from same IP in 5 minutes
- Webhook validation failure rate > 5%
- Any access to disabled API versions
- Unusual spike in sensitive operations

## Testing Security Features

### Rate Limiting Test
```bash
# Test login rate limiting
for i in {1..10}; do
  curl -X POST http://localhost:8000/auth/login \
    -d "username=test&password=wrong"
done
# Should get 429 after 5 attempts
```

### Webhook Signature Test
```python
import hmac
import hashlib
import time

secret = "your-webhook-secret"
body = '{"test": "data"}'
timestamp = str(int(time.time()))

signature = hmac.new(
    secret.encode(),
    f"{timestamp}.{body}".encode(),
    hashlib.sha256
).hexdigest()

# Send with headers:
# X-Webhook-Signature: {signature}
# X-Webhook-Timestamp: {timestamp}
```

## Incident Response

If a security incident is detected:

1. Check audit logs for suspicious activity
2. Review rate limit violations
3. Check webhook validation failures
4. Analyze access patterns
5. Rotate affected secrets
6. Update security rules as needed

## Maintenance

### Regular Tasks
- Review audit logs weekly
- Rotate webhook secrets quarterly
- Update rate limit rules based on usage patterns
- Archive old audit logs monthly
- Review deprecated API usage

### Security Updates
- Keep dependencies updated
- Monitor security advisories
- Perform regular security scans
- Conduct penetration testing annually