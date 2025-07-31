# Payroll Module Deployment Guide

This guide provides comprehensive instructions for deploying the Payroll & Tax Module in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Application Deployment](#application-deployment)
5. [Infrastructure Requirements](#infrastructure-requirements)
6. [Monitoring and Logging](#monitoring-and-logging)
7. [Security Configuration](#security-configuration)
8. [Backup and Recovery](#backup-and-recovery)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **PostgreSQL**: 15.0 or higher
- **Redis**: 7.0 or higher
- **Docker**: 20.10 or higher (for containerized deployment)
- **Kubernetes**: 1.25 or higher (for K8s deployment)

### Required Services

- PostgreSQL database server
- Redis server (for caching and background tasks)
- SMTP server (for email notifications)
- Object storage (S3-compatible) for document storage

### Python Dependencies

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-dev python3-pip
sudo apt-get install -y postgresql-client libpq-dev
sudo apt-get install -y redis-tools

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r backend/requirements.txt
pip install -r backend/modules/payroll/requirements.txt
```

## Environment Setup

### Environment Variables

Create a `.env` file with the following configuration:

```bash
# Application Settings
APP_NAME=AuraConnect-Payroll
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here

# Database Configuration
DATABASE_URL=postgresql://payroll_user:password@localhost:5432/payroll_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password
REDIS_SSL=true

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Tax Service Configuration
TAX_SERVICE_URL=https://api.auraconnect.com/tax
TAX_SERVICE_API_KEY=tax-service-api-key

# Staff Service Configuration
STAFF_SERVICE_URL=https://api.auraconnect.com/staff
STAFF_SERVICE_API_KEY=staff-service-api-key

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=notifications@auraconnect.com
SMTP_PASSWORD=smtp-password
SMTP_USE_TLS=true

# Storage Configuration
S3_BUCKET_NAME=auraconnect-payroll
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_REGION=us-west-2
S3_ENDPOINT_URL=https://s3.amazonaws.com

# Security Settings
JWT_SECRET_KEY=jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DELTA=3600

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
LOG_LEVEL=INFO
ENABLE_METRICS=true
METRICS_PORT=9090
```

### Directory Structure

```
/opt/auraconnect/
├── backend/
│   ├── modules/
│   │   └── payroll/
│   │       ├── alembic/
│   │       ├── api/
│   │       ├── models/
│   │       ├── services/
│   │       ├── tasks/
│   │       └── config/
│   ├── logs/
│   ├── temp/
│   └── static/
├── scripts/
├── config/
└── docker/
```

## Database Configuration

### 1. Create Database and User

```sql
-- Connect as superuser
CREATE USER payroll_user WITH PASSWORD 'secure_password';
CREATE DATABASE payroll_db OWNER payroll_user;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE payroll_db TO payroll_user;
GRANT CREATE ON SCHEMA public TO payroll_user;

-- Create extensions
\c payroll_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

### 2. Run Migrations

```bash
# Set database URL
export DATABASE_URL=postgresql://payroll_user:password@localhost:5432/payroll_db

# Run migrations
cd backend/modules/payroll
alembic upgrade head

# Verify migrations
alembic current
```

### 3. Create Indexes

```sql
-- Performance indexes for payroll queries
CREATE INDEX idx_employee_payments_employee_date 
    ON employee_payments(employee_id, pay_period_start, pay_period_end);

CREATE INDEX idx_employee_payments_status 
    ON employee_payments(status) 
    WHERE status IN ('pending', 'processing');

CREATE INDEX idx_payroll_configurations_active 
    ON payroll_configurations(config_type, location, is_active) 
    WHERE is_active = true;

CREATE INDEX idx_audit_logs_timestamp 
    ON payroll_audit_logs(created_at DESC);

-- Full-text search indexes
CREATE INDEX idx_audit_logs_search 
    ON payroll_audit_logs 
    USING gin(to_tsvector('english', action || ' ' || details));
```

### 4. Seed Initial Data

```bash
# Run seed script
python scripts/seed_payroll_data.py

# This creates:
# - Default tax configurations
# - Overtime rules by state
# - Standard deduction types
# - Role-based pay rates
```

## Application Deployment

### Docker Deployment

#### 1. Build Docker Image

```dockerfile
# Dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY backend/requirements.txt backend/
COPY backend/modules/payroll/requirements.txt backend/modules/payroll/

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir -r backend/modules/payroll/requirements.txt

# Copy application code
COPY backend/ backend/
COPY scripts/ scripts/

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Create non-root user
RUN useradd -m -u 1000 payroll && chown -R payroll:payroll /app
USER payroll

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "backend.modules.payroll.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  payroll-api:
    build: .
    container_name: payroll-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://payroll_user:password@postgres:5432/payroll_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
      - ./temp:/app/temp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build: .
    container_name: payroll-celery-worker
    command: celery -A backend.modules.payroll.tasks.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://payroll_user:password@postgres:5432/payroll_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  celery-beat:
    build: .
    container_name: payroll-celery-beat
    command: celery -A backend.modules.payroll.tasks.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://payroll_user:password@postgres:5432/payroll_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: payroll-postgres
    environment:
      - POSTGRES_DB=payroll_db
      - POSTGRES_USER=payroll_user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: payroll-redis
    command: redis-server --requirepass redis_password
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: payroll-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - payroll-api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

#### 1. ConfigMap

```yaml
# payroll-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: payroll-config
  namespace: auraconnect
data:
  APP_NAME: "AuraConnect-Payroll"
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  DATABASE_POOL_SIZE: "20"
  REDIS_URL: "redis://redis-service:6379/0"
```

#### 2. Secret

```yaml
# payroll-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: payroll-secret
  namespace: auraconnect
type: Opaque
stringData:
  DATABASE_URL: "postgresql://payroll_user:password@postgres-service:5432/payroll_db"
  SECRET_KEY: "your-secret-key"
  JWT_SECRET_KEY: "jwt-secret-key"
  REDIS_PASSWORD: "redis-password"
```

#### 3. Deployment

```yaml
# payroll-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payroll-api
  namespace: auraconnect
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payroll-api
  template:
    metadata:
      labels:
        app: payroll-api
    spec:
      containers:
      - name: payroll-api
        image: auraconnect/payroll:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: payroll-config
        - secretRef:
            name: payroll-secret
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### 4. Service

```yaml
# payroll-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: payroll-service
  namespace: auraconnect
spec:
  selector:
    app: payroll-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

#### 5. Ingress

```yaml
# payroll-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: payroll-ingress
  namespace: auraconnect
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.auraconnect.com
    secretName: payroll-tls
  rules:
  - host: api.auraconnect.com
    http:
      paths:
      - path: /api/payroll
        pathType: Prefix
        backend:
          service:
            name: payroll-service
            port:
              number: 80
```

## Infrastructure Requirements

### Compute Resources

| Environment | API Servers | Workers | CPU | Memory | Storage |
|-------------|-------------|---------|-----|---------|---------|
| Development | 1 | 1 | 2 cores | 4GB | 20GB |
| Staging | 2 | 2 | 4 cores | 8GB | 50GB |
| Production | 3+ | 4+ | 8 cores | 16GB | 100GB |

### Database Requirements

- **PostgreSQL**: 
  - Version: 15+
  - Storage: 100GB minimum
  - IOPS: 3000 minimum
  - Connections: 100 max
  - Backup: Daily with 30-day retention

### Redis Requirements

- **Memory**: 4GB minimum
- **Persistence**: AOF enabled
- **Replication**: Master-slave setup
- **Backup**: Daily snapshots

## Monitoring and Logging

### 1. Application Metrics

```python
# Prometheus metrics endpoint
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
payroll_calculations = Counter(
    'payroll_calculations_total',
    'Total payroll calculations',
    ['status']
)

calculation_duration = Histogram(
    'payroll_calculation_duration_seconds',
    'Payroll calculation duration'
)

active_batch_jobs = Gauge(
    'payroll_batch_jobs_active',
    'Number of active batch jobs'
)
```

### 2. Logging Configuration

```python
# logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        },
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'json',
            'filename': '/app/logs/payroll.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'json',
            'filename': '/app/logs/payroll_error.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file', 'error_file']
    }
}
```

### 3. Health Check Endpoints

```python
# health.py
from fastapi import APIRouter, status
from sqlalchemy import text

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Basic health check."""
    return {"status": "healthy"}

@router.get("/ready")
async def readiness_check(
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Detailed readiness check."""
    checks = {
        "database": False,
        "redis": False,
        "celery": False
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    
    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = True
    except Exception:
        pass
    
    # Check Celery
    try:
        from backend.modules.payroll.tasks import celery_app
        stats = celery_app.control.inspect().stats()
        if stats:
            checks["celery"] = True
    except Exception:
        pass
    
    all_healthy = all(checks.values())
    return {
        "status": "ready" if all_healthy else "not ready",
        "checks": checks
    }
```

### 4. Monitoring Stack

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'payroll-api'
    static_configs:
      - targets: ['payroll-api:9090']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

## Security Configuration

### 1. SSL/TLS Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.auraconnect.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location /api/payroll {
        proxy_pass http://payroll-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. API Security

```python
# security.py
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token."""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
```

### 3. Database Security

```sql
-- Row-level security
ALTER TABLE employee_payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON employee_payments
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant')::int);

-- Audit triggers
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO payroll_audit_logs (
        table_name,
        operation,
        user_id,
        changed_data,
        created_at
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_setting('app.current_user')::int,
        to_jsonb(NEW),
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_employee_payments
    AFTER INSERT OR UPDATE OR DELETE ON employee_payments
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
```

## Backup and Recovery

### 1. Database Backup

```bash
#!/bin/bash
# backup.sh

# Configuration
DB_NAME="payroll_db"
DB_USER="payroll_user"
BACKUP_DIR="/backup/postgres"
S3_BUCKET="auraconnect-backups"
RETENTION_DAYS=30

# Create backup
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/payroll_$DATE.sql.gz"

pg_dump -U $DB_USER -d $DB_NAME | gzip > $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE s3://$S3_BUCKET/payroll/postgres/

# Clean old backups
find $BACKUP_DIR -name "payroll_*.sql.gz" -mtime +$RETENTION_DAYS -delete
aws s3 ls s3://$S3_BUCKET/payroll/postgres/ | while read -r line; do
    createDate=$(echo $line | awk '{print $1" "$2}')
    createDate=$(date -d "$createDate" +%s)
    olderThan=$(date -d "$RETENTION_DAYS days ago" +%s)
    if [[ $createDate -lt $olderThan ]]; then
        fileName=$(echo $line | awk '{print $4}')
        aws s3 rm s3://$S3_BUCKET/payroll/postgres/$fileName
    fi
done
```

### 2. Recovery Procedure

```bash
#!/bin/bash
# restore.sh

# Download backup from S3
BACKUP_DATE=$1
aws s3 cp s3://$S3_BUCKET/payroll/postgres/payroll_$BACKUP_DATE.sql.gz /tmp/

# Restore database
gunzip -c /tmp/payroll_$BACKUP_DATE.sql.gz | psql -U $DB_USER -d $DB_NAME

# Verify restoration
psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM employee_payments;"
```

### 3. Disaster Recovery Plan

1. **RTO (Recovery Time Objective)**: 4 hours
2. **RPO (Recovery Point Objective)**: 1 hour

**Recovery Steps:**
1. Provision new infrastructure
2. Restore database from latest backup
3. Restore Redis data if available
4. Update DNS to point to new infrastructure
5. Verify all services are operational
6. Resume batch processing from last checkpoint

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection
psql -U payroll_user -d payroll_db -c "SELECT 1;"

# Check connection pool
SELECT count(*) FROM pg_stat_activity WHERE datname = 'payroll_db';
```

#### 2. Redis Connection Issues

```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check Redis memory
redis-cli info memory

# Clear Redis cache if needed
redis-cli FLUSHDB
```

#### 3. Celery Worker Issues

```bash
# Check Celery workers
celery -A backend.modules.payroll.tasks.celery_app inspect active

# Check Celery queues
celery -A backend.modules.payroll.tasks.celery_app inspect reserved

# Purge queue if needed
celery -A backend.modules.payroll.tasks.celery_app purge
```

#### 4. Performance Issues

```sql
-- Find slow queries
SELECT 
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
WHERE query LIKE '%payroll%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Analyze tables
ANALYZE employee_payments;
ANALYZE payroll_configurations;
```

### Debug Mode

Enable debug logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG
export DEBUG=true

# Or in Docker
docker run -e LOG_LEVEL=DEBUG -e DEBUG=true payroll-api
```

### Support Contacts

- **DevOps Team**: devops@auraconnect.com
- **Database Admin**: dba@auraconnect.com
- **On-Call**: +1-555-PAYROLL (729-7655)
- **Slack**: #payroll-support

## Post-Deployment Checklist

- [ ] All services are running and healthy
- [ ] Database migrations completed successfully
- [ ] Redis is accessible and configured
- [ ] Celery workers are processing tasks
- [ ] SSL certificates are valid
- [ ] Monitoring dashboards are active
- [ ] Backup jobs are scheduled
- [ ] Log rotation is configured
- [ ] Security scans completed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team notified of deployment