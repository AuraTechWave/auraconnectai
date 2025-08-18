# Secret Management Guide for AuraConnect

This guide explains how to properly manage secrets and credentials in AuraConnect deployments.

## Overview

AuraConnect uses a fail-safe approach to secret management that prevents hardcoded credentials from reaching production. All sensitive configuration values must be provided through environment variables.

## Required Secrets

### Critical Secrets (Required for all environments)

1. **JWT_SECRET_KEY**
   - Used for signing JWT tokens
   - Must be a strong, random string (minimum 32 characters)
   - Example generation: `openssl rand -hex 32`

2. **DATABASE_URL**
   - PostgreSQL connection string
   - Format: `postgresql://username:password@host:port/database`
   - Example: `postgresql://aura_user:secure_password@db.example.com:5432/auraconnect`

### Production-Only Required Secrets

3. **SESSION_SECRET**
   - Used for session encryption
   - Must be different from JWT_SECRET_KEY
   - Example generation: `openssl rand -hex 32`

4. **REDIS_URL**
   - Redis connection string for caching and session storage
   - Format: `redis://[:password]@host:port/db`
   - Example: `redis://:redis_password@redis.example.com:6379/0`

### Optional Secrets (Recommended for production)

5. **TWILIO_ACCOUNT_SID** and **TWILIO_AUTH_TOKEN**
   - Required for SMS notifications
   - Obtain from Twilio dashboard

6. **SMTP_USERNAME** and **SMTP_PASSWORD**
   - Required for email notifications
   - Use app-specific passwords where available

## Environment Setup

### Development Environment

Create a `.env` file in the backend directory:

```bash
# Development .env file
ENVIRONMENT=development
JWT_SECRET_KEY=dev-jwt-secret-change-for-production
DATABASE_URL=postgresql://dev_user:dev_password@localhost:5432/auraconnect_dev
REDIS_URL=redis://localhost:6379
```

### Production Environment

**NEVER commit production secrets to version control!**

#### Using Environment Variables

```bash
export ENVIRONMENT=production
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export SESSION_SECRET=$(openssl rand -hex 32)
export DATABASE_URL="postgresql://prod_user:prod_password@db.example.com:5432/auraconnect"
export REDIS_URL="redis://:redis_password@redis.example.com:6379/0"
```

#### Using systemd (Ubuntu/Debian)

Create `/etc/systemd/system/auraconnect.service.d/override.conf`:

```ini
[Service]
Environment="ENVIRONMENT=production"
Environment="JWT_SECRET_KEY=your-secure-jwt-secret"
Environment="SESSION_SECRET=your-secure-session-secret"
Environment="DATABASE_URL=postgresql://..."
Environment="REDIS_URL=redis://..."
```

#### Using Docker

```yaml
# docker-compose.yml
services:
  backend:
    image: auraconnect/backend
    environment:
      - ENVIRONMENT=production
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - SESSION_SECRET=${SESSION_SECRET}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
```

```bash
# .env file (for docker-compose, NOT committed)
JWT_SECRET_KEY=your-secure-jwt-secret
SESSION_SECRET=your-secure-session-secret
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
```

## Secret Management Solutions

### AWS Secrets Manager

```python
# Example: Fetch secrets from AWS Secrets Manager
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Set environment variables from AWS Secrets
secrets = get_secret('auraconnect/production')
os.environ['JWT_SECRET_KEY'] = secrets['jwt_secret_key']
os.environ['DATABASE_URL'] = secrets['database_url']
```

### HashiCorp Vault

```bash
# Store secrets in Vault
vault kv put secret/auraconnect/production \
  jwt_secret_key="..." \
  database_url="..." \
  redis_url="..."

# Retrieve and export
export JWT_SECRET_KEY=$(vault kv get -field=jwt_secret_key secret/auraconnect/production)
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: auraconnect-secrets
type: Opaque
data:
  jwt-secret-key: <base64-encoded-secret>
  database-url: <base64-encoded-url>
  redis-url: <base64-encoded-url>
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auraconnect-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        envFrom:
        - secretRef:
            name: auraconnect-secrets
```

## Security Best Practices

1. **Never commit secrets to version control**
   - Use `.gitignore` to exclude `.env` files
   - Scan commits for accidentally included secrets

2. **Use strong, unique secrets**
   - Minimum 32 characters for keys
   - Use cryptographically secure random generators

3. **Rotate secrets regularly**
   - Implement secret rotation for production
   - Update secrets without downtime using rolling deployments

4. **Limit secret access**
   - Use principle of least privilege
   - Separate secrets by environment

5. **Monitor secret usage**
   - Log authentication failures
   - Alert on suspicious access patterns

## Validation

The application performs automatic secret validation at startup:

1. **Development Mode**: Warns about missing secrets but continues
2. **Production Mode**: Fails fast if required secrets are missing

### Manual Validation

```bash
# Check if all required secrets are set
python -c "from backend.core.secrets import validate_all_secrets; validate_all_secrets()"
```

## Troubleshooting

### "CRITICAL SECURITY ERROR: Required secret 'JWT_SECRET_KEY' is not set"

**Solution**: Ensure the JWT_SECRET_KEY environment variable is set before starting the application.

### "Secret contains dangerous default value"

**Solution**: The application detected a development default in production. Generate a new secure secret.

### Application won't start in production

**Check**:
1. All required environment variables are set
2. No development defaults are used
3. Database and Redis connections are valid

## CI/CD Integration

### GitHub Actions

```yaml
- name: Deploy to Production
  env:
    JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    REDIS_URL: ${{ secrets.REDIS_URL }}
    SESSION_SECRET: ${{ secrets.SESSION_SECRET }}
  run: |
    # Deploy script
```

### GitLab CI

```yaml
deploy:
  stage: deploy
  variables:
    JWT_SECRET_KEY: $JWT_SECRET_KEY
    DATABASE_URL: $DATABASE_URL
  script:
    - # Deploy commands
```

## Conclusion

Proper secret management is critical for production security. Always:

- Use environment variables for secrets
- Never hardcode credentials
- Validate secrets at startup
- Use secret management tools in production
- Monitor and rotate secrets regularly

For questions or issues, contact the security team.