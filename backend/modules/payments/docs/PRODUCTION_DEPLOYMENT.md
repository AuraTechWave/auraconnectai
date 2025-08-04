# Payment System Production Deployment Guide

This guide covers deploying and operating the payment system in production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Deployment Steps](#deployment-steps)
5. [Monitoring Setup](#monitoring-setup)
6. [Security Checklist](#security-checklist)
7. [Operational Procedures](#operational-procedures)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Services

- PostgreSQL 14+ with SSL enabled
- Redis 6+ with Redis Sentinel or Cluster
- Prometheus + AlertManager
- Container orchestration (Kubernetes/Docker Swarm)
- Load balancer with SSL termination
- Log aggregation system (ELK/Splunk)

### Required Access

- Payment gateway API credentials (production)
- SSL certificates for domains
- Access to monitoring systems
- PagerDuty/Slack webhook URLs

## Environment Configuration

### 1. Environment Variables

Create a `.env.production` file:

```bash
# Application Environment
PAYMENT_ENVIRONMENT=production
PAYMENT_REDIS_URL=rediss://:<password>@redis-cluster.internal:6379/0
DATABASE_URL=postgresql://user:pass@db-master.internal:5432/auraconnect?sslmode=require

# Redis Configuration
PAYMENT_REDIS_MAX_CONNECTIONS=100
PAYMENT_REDIS_SOCKET_TIMEOUT=5
PAYMENT_WEBHOOK_WORKER_CONCURRENCY=20

# Gateway Configuration
PAYMENT_GATEWAY_TIMEOUT_SECONDS=30
PAYMENT_GATEWAY_CONNECT_TIMEOUT=10

# Security
PAYMENT_MAX_PAYMENT_AMOUNT=50000.00
PAYMENT_MIN_PAYMENT_AMOUNT=1.00
PAYMENT_WEBHOOK_SIGNATURE_TOLERANCE_SECONDS=300

# Monitoring
PAYMENT_PROMETHEUS_ENABLED=true
PAYMENT_PROMETHEUS_PORT=8001
PAYMENT_ALERT_PAYMENT_FAILURE_THRESHOLD=0.02  # 2% for production
PAYMENT_ALERT_GATEWAY_LATENCY_THRESHOLD=3.0   # 3 seconds
PAYMENT_ALERT_WEBHOOK_BACKLOG_THRESHOLD=50
```

### 2. Gateway Credentials

Store gateway credentials securely:

```bash
# Using Kubernetes Secrets
kubectl create secret generic payment-gateway-creds \
  --from-literal=stripe_secret_key='sk_live_...' \
  --from-literal=stripe_webhook_secret='whsec_...' \
  --from-literal=square_access_token='...' \
  --from-literal=paypal_client_secret='...'
```

## Infrastructure Setup

### 1. Database Setup

```sql
-- Create payment database and user
CREATE USER payment_service WITH ENCRYPTED PASSWORD 'secure_password';
CREATE DATABASE payments OWNER payment_service;

-- Enable SSL
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/etc/postgresql/server.crt';
ALTER SYSTEM SET ssl_key_file = '/etc/postgresql/server.key';

-- Run migrations
alembic upgrade head
```

### 2. Redis Cluster Setup

```yaml
# redis-cluster.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-cluster-config
data:
  redis.conf: |
    port 6379
    cluster-enabled yes
    cluster-config-file nodes.conf
    cluster-node-timeout 5000
    appendonly yes
    requirepass ${REDIS_PASSWORD}
    maxmemory 2gb
    maxmemory-policy allkeys-lru
```

### 3. Load Balancer Configuration

```nginx
# nginx.conf
upstream payment_api {
    least_conn;
    server payment-api-1:8000 max_fails=3 fail_timeout=30s;
    server payment-api-2:8000 max_fails=3 fail_timeout=30s;
    server payment-api-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name payments.company.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # Rate limiting for payment endpoints
    limit_req_zone $binary_remote_addr zone=payment_limit:10m rate=10r/s;
    
    location /api/v1/payments/ {
        limit_req zone=payment_limit burst=20 nodelay;
        proxy_pass http://payment_api;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Webhook endpoints (no auth required)
    location /api/v1/payments/webhook/ {
        proxy_pass http://payment_api;
        proxy_read_timeout 10s;
        proxy_connect_timeout 5s;
    }
}
```

## Deployment Steps

### 1. API Service Deployment

```yaml
# payment-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
    spec:
      containers:
      - name: payment-api
        image: company/payment-api:v1.0.0
        ports:
        - containerPort: 8000
        - containerPort: 8001  # Prometheus metrics
        env:
        - name: PAYMENT_ENVIRONMENT
          value: "production"
        envFrom:
        - secretRef:
            name: payment-gateway-creds
        - configMapRef:
            name: payment-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
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

### 2. Webhook Worker Deployment

```yaml
# webhook-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-webhook-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-webhook-worker
  template:
    metadata:
      labels:
        app: payment-webhook-worker
    spec:
      containers:
      - name: webhook-worker
        image: company/payment-api:v1.0.0
        command: ["python", "-m", "workers.payment_webhook_worker"]
        env:
        - name: PAYMENT_ENVIRONMENT
          value: "production"
        envFrom:
        - secretRef:
            name: payment-gateway-creds
        - configMapRef:
            name: payment-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### 3. Database Migration Job

```yaml
# migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: payment-db-migration
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migration
        image: company/payment-api:v1.0.0
        command: ["alembic", "upgrade", "head"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
```

## Monitoring Setup

### 1. Prometheus Configuration

```yaml
# prometheus-config.yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - '/etc/prometheus/rules/payment_alerts.yml'

scrape_configs:
  - job_name: 'payment-api'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: payment-api
      - source_labels: [__address__]
        action: replace
        regex: ([^:]+)(?::\\d+)?
        replacement: $1:8001
        target_label: __address__
        
  - job_name: 'payment-webhook-worker'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: payment-webhook-worker
```

### 2. Grafana Dashboard

Import the payment system dashboard:

```bash
# Import dashboard
curl -X POST http://grafana.internal/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @payment-dashboard.json
```

### 3. AlertManager Setup

```bash
# Deploy AlertManager with payment alerts
kubectl create configmap alertmanager-config \
  --from-file=alertmanager.yml=monitoring/alertmanager.yml

kubectl apply -f alertmanager-deployment.yaml
```

## Security Checklist

- [ ] All API endpoints require authentication (except webhooks)
- [ ] SSL/TLS enabled for all connections
- [ ] Database connections use SSL
- [ ] Redis connections use AUTH and SSL
- [ ] API keys stored in secrets management
- [ ] Webhook signatures verified
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Security headers enabled
- [ ] Audit logging enabled
- [ ] PCI compliance requirements met
- [ ] Regular security scans scheduled

## Operational Procedures

### 1. Health Checks

```bash
# Check API health
curl https://payments.company.com/health

# Check worker health
curl http://worker-1.internal:8001/metrics | grep worker_health

# Check Redis connectivity
redis-cli -h redis-cluster.internal --tls ping
```

### 2. Scaling

```bash
# Scale API pods
kubectl scale deployment payment-api --replicas=5

# Scale webhook workers
kubectl scale deployment payment-webhook-worker --replicas=3
```

### 3. Gateway Configuration Updates

```bash
# Update gateway config via API
curl -X PUT https://payments.company.com/api/v1/admin/gateways/stripe/config \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fee_percentage": 2.9, "fee_fixed": 0.30}'
```

### 4. Maintenance Mode

```bash
# Enable maintenance mode
kubectl set env deployment/payment-api MAINTENANCE_MODE=true

# Disable maintenance mode
kubectl set env deployment/payment-api MAINTENANCE_MODE=false
```

## Troubleshooting

### Common Issues

#### 1. High Payment Failure Rate

```bash
# Check recent errors
kubectl logs -l app=payment-api --tail=100 | grep ERROR

# Check gateway status
curl https://payments.company.com/api/v1/admin/gateways/status

# Verify gateway credentials
kubectl get secret payment-gateway-creds -o yaml
```

#### 2. Webhook Processing Delays

```bash
# Check webhook queue size
redis-cli -h redis-cluster.internal --tls llen payment_webhooks

# Check worker logs
kubectl logs -l app=payment-webhook-worker --tail=100

# Scale workers if needed
kubectl scale deployment payment-webhook-worker --replicas=4
```

#### 3. Database Connection Issues

```bash
# Check connection pool
curl http://payment-api-1:8001/metrics | grep db_connections

# Verify SSL certificates
openssl s_client -connect db-master.internal:5432 -starttls postgres
```

### Emergency Procedures

#### Payment Gateway Failover

```bash
# Disable failing gateway
curl -X POST https://payments.company.com/api/v1/admin/gateways/stripe/disable \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Enable backup gateway
curl -X POST https://payments.company.com/api/v1/admin/gateways/square/enable \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### Emergency Rollback

```bash
# Rollback deployment
kubectl rollout undo deployment payment-api

# Rollback database migration
alembic downgrade -1
```

## Monitoring Dashboards

### Key Metrics to Monitor

1. **Business Metrics**
   - Payment success rate (target: >95%)
   - Average payment amount
   - Refund rate
   - Gateway distribution

2. **Performance Metrics**
   - API response time (p95 < 1s)
   - Gateway latency (p95 < 5s)
   - Queue processing time
   - Database query time

3. **Infrastructure Metrics**
   - CPU/Memory usage
   - Redis connection pool
   - Database connections
   - Network latency

### Alert Response Playbook

| Alert | Severity | Response Time | Action |
|-------|----------|---------------|---------|
| PaymentGatewayUnavailable | Critical | Immediate | Page on-call, check gateway status |
| HighPaymentFailureRate | Critical | 5 minutes | Check recent deployments, gateway status |
| WebhookProcessingBacklog | Warning | 30 minutes | Scale workers, check for errors |
| HighGatewayLatency | Warning | 30 minutes | Check gateway status page |

## Post-Deployment Verification

```bash
# Run smoke tests
./scripts/smoke-test-production.sh

# Verify metrics collection
curl http://localhost:8001/metrics | grep payment_

# Test payment flow
./scripts/test-payment-flow.sh --env production

# Verify webhook processing
./scripts/test-webhook-delivery.sh --gateway stripe
```

## Maintenance Schedule

- **Daily**: Review error logs and metrics
- **Weekly**: Check gateway fee reconciliation
- **Monthly**: Security scan and certificate renewal check
- **Quarterly**: Load testing and capacity planning