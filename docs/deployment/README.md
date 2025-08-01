# AuraConnect Deployment Guide

## Overview

This guide covers deploying AuraConnect to production environments. We support multiple deployment options from single-server setups to highly available Kubernetes clusters.

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Prerequisites](#prerequisites)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Platform Deployments](#cloud-platform-deployments)
6. [Database Setup](#database-setup)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Environment Configuration](#environment-configuration)
9. [Monitoring & Logging](#monitoring-logging)
10. [Backup & Recovery](#backup-recovery)
11. [Scaling Strategies](#scaling-strategies)
12. [Troubleshooting](#troubleshooting)

## Deployment Options

### Option 1: Single Server (Small Restaurants)
- **Best for**: 1-3 locations, < 100 daily orders
- **Resources**: 4 CPU, 8GB RAM, 100GB storage
- **Cost**: ~$50-100/month

### Option 2: Multi-Server (Medium Chains)
- **Best for**: 4-20 locations, < 1000 daily orders
- **Resources**: 2-3 servers, load balancer
- **Cost**: ~$300-500/month

### Option 3: Kubernetes Cluster (Large Chains)
- **Best for**: 20+ locations, high availability
- **Resources**: 3+ nodes, auto-scaling
- **Cost**: ~$1000+/month

## Prerequisites

### System Requirements

```yaml
Minimum Production Requirements:
  CPU: 4 cores
  RAM: 8 GB
  Storage: 100 GB SSD
  Network: 100 Mbps
  OS: Ubuntu 20.04+ or RHEL 8+

Recommended Production Requirements:
  CPU: 8 cores
  RAM: 16 GB
  Storage: 500 GB SSD
  Network: 1 Gbps
  Database: Dedicated PostgreSQL server
```

### Required Software

- Docker 20.10+
- Docker Compose 2.0+ (for Docker deployment)
- Kubernetes 1.24+ (for K8s deployment)
- Nginx 1.20+
- PostgreSQL 14+
- Redis 6+

## Docker Deployment

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone Repository

```bash
git clone https://github.com/AuraTechWave/auraconnectai.git
cd auraconnectai
```

### 3. Configure Environment

```bash
# Copy production environment files
cp .env.production .env
cp backend/.env.production backend/.env
cp frontend/.env.production frontend/.env

# Edit configuration
vim .env
```

Key environment variables:

```bash
# Application
ENVIRONMENT=production
DEBUG=False
SECRET_KEY=<generate-strong-secret>

# Database
DATABASE_URL=postgresql://aura:password@postgres:5432/auraconnect
DATABASE_POOL_SIZE=50

# Redis
REDIS_URL=redis://redis:6379/0

# Domain
DOMAIN=restaurant.example.com
API_URL=https://api.restaurant.example.com

# Email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USER=apikey
EMAIL_PASSWORD=<sendgrid-api-key>
```

### 4. Build and Deploy

```bash
# Build images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Create superuser
docker-compose exec backend python scripts/create_superuser.py
```

### 5. Setup Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/auraconnect
server {
    listen 80;
    server_name restaurant.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name restaurant.example.com;

    ssl_certificate /etc/letsencrypt/live/restaurant.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/restaurant.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name api.restaurant.example.com;

    ssl_certificate /etc/letsencrypt/live/api.restaurant.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.restaurant.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Kubernetes Deployment

### 1. Prepare Kubernetes Cluster

```bash
# For AWS EKS
eksctl create cluster --name auraconnect --region us-east-1 --nodes 3

# For Google GKE
gcloud container clusters create auraconnect --num-nodes=3 --zone=us-central1-a

# For local testing with minikube
minikube start --nodes 3 --cpus 4 --memory 8192
```

### 2. Install Required Tools

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Add repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

### 3. Deploy Infrastructure Components

```bash
# Create namespace
kubectl create namespace auraconnect

# Install PostgreSQL
helm install postgres bitnami/postgresql \
  --namespace auraconnect \
  --set auth.postgresPassword=secretpassword \
  --set auth.database=auraconnect \
  --set persistence.size=100Gi

# Install Redis
helm install redis bitnami/redis \
  --namespace auraconnect \
  --set auth.enabled=false \
  --set master.persistence.size=10Gi

# Install Nginx Ingress
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace auraconnect
```

### 4. Deploy Application

```bash
# Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy services
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/celery-deployment.yaml

# Apply ingress
kubectl apply -f k8s/ingress.yaml
```

Example deployment file:

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: auraconnect
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: auraconnect/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          value: "redis://redis-master:6379"
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
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: auraconnect
spec:
  selector:
    app: backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

## Cloud Platform Deployments

### AWS Deployment

```bash
# Using AWS Copilot
copilot app init auraconnect
copilot env init --name production
copilot svc deploy --name backend --env production
copilot svc deploy --name frontend --env production
```

### Google Cloud Platform

```bash
# Using Cloud Run
gcloud run deploy backend \
  --image gcr.io/project-id/auraconnect-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

gcloud run deploy frontend \
  --image gcr.io/project-id/auraconnect-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Azure Deployment

```bash
# Using Azure Container Instances
az container create \
  --resource-group auraconnect-rg \
  --name backend \
  --image auraconnect/backend:latest \
  --dns-name-label auraconnect-api \
  --ports 8000 \
  --environment-variables DATABASE_URL=$DATABASE_URL
```

## Database Setup

### PostgreSQL Configuration

```sql
-- Performance tuning
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '10MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Create database and user
CREATE DATABASE auraconnect;
CREATE USER aurauser WITH ENCRYPTED PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE auraconnect TO aurauser;

-- Enable extensions
\c auraconnect
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

### Database Migrations

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create backup before migrations
pg_dump -h localhost -U aurauser -d auraconnect > backup_$(date +%Y%m%d_%H%M%S).sql
```

## SSL/TLS Configuration

### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificates
sudo certbot --nginx -d restaurant.example.com -d api.restaurant.example.com

# Auto-renewal
sudo certbot renew --dry-run
```

### SSL Configuration for Nginx

```nginx
# Strong SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
add_header Strict-Transport-Security "max-age=63072000" always;
```

## Environment Configuration

### Production Environment Variables

```bash
# .env.production
# Application
ENVIRONMENT=production
DEBUG=False
SECRET_KEY=<use-strong-random-key>
ALLOWED_HOSTS=restaurant.example.com,api.restaurant.example.com

# Database
DATABASE_URL=postgresql://aurauser:password@db.example.com:5432/auraconnect
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://redis.example.com:6379/0
REDIS_MAX_CONNECTIONS=100

# Security
JWT_SECRET_KEY=<use-different-strong-key>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email
EMAIL_BACKEND=smtp
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid-api-key>
DEFAULT_FROM_EMAIL=noreply@restaurant.example.com

# Storage
AWS_ACCESS_KEY_ID=<aws-access-key>
AWS_SECRET_ACCESS_KEY=<aws-secret-key>
AWS_S3_BUCKET_NAME=auraconnect-assets
AWS_S3_REGION=us-east-1

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/yyy
DATADOG_API_KEY=<datadog-api-key>

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_AI_RECOMMENDATIONS=true
ENABLE_MULTI_LANGUAGE=true
```

## Monitoring & Logging

### Prometheus Setup

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  node-exporter:
    image: prom/node-exporter
    ports:
      - "9100:9100"
```

### Logging with ELK Stack

```yaml
# docker-compose.logging.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"
```

### Application Metrics

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
order_counter = Counter('orders_total', 'Total orders', ['status'])
response_time = Histogram('response_time_seconds', 'Response time')
active_users = Gauge('active_users', 'Active users')

# Use in application
@app.post("/orders")
async def create_order():
    with response_time.time():
        # Process order
        order_counter.labels(status='created').inc()
```

## Backup & Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Database backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/db_$DATE.sql.gz s3://auraconnect-backups/db/

# Redis backup
redis-cli --rdb $BACKUP_DIR/redis_$DATE.rdb
aws s3 cp $BACKUP_DIR/redis_$DATE.rdb s3://auraconnect-backups/redis/

# Clean old backups
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
```

### Restore Process

```bash
# Restore database
gunzip -c backup.sql.gz | psql -h localhost -U aurauser -d auraconnect

# Restore Redis
redis-cli --pipe < redis_backup.rdb
```

## Scaling Strategies

### Horizontal Scaling

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Database Scaling

```sql
-- Read replicas
CREATE PUBLICATION auraconnect_pub FOR ALL TABLES;

-- On replica
CREATE SUBSCRIPTION auraconnect_sub
  CONNECTION 'host=master.db.example.com dbname=auraconnect user=replicator'
  PUBLICATION auraconnect_pub;
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

```bash
# Check connectivity
psql -h db.example.com -U aurauser -d auraconnect -c "SELECT 1"

# Check connection pool
docker-compose exec backend python -c "from app.database import engine; print(engine.pool.status())"
```

#### 2. Memory Issues

```bash
# Check memory usage
docker stats

# Increase memory limits
docker update --memory="2g" --memory-swap="3g" container_name
```

#### 3. Performance Issues

```bash
# Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;

# Check slow queries
tail -f /var/log/postgresql/postgresql-*.log | grep "duration:"
```

### Health Checks

```python
# Health check endpoint
@app.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "storage": await check_storage(),
    }
    
    status = "healthy" if all(checks.values()) else "unhealthy"
    status_code = 200 if status == "healthy" else 503
    
    return JSONResponse(
        content={"status": status, "checks": checks},
        status_code=status_code
    )
```

## Security Checklist

- [ ] SSL/TLS certificates installed and auto-renewing
- [ ] Firewall rules configured (only required ports open)
- [ ] Database access restricted to application servers
- [ ] Environment variables secured (not in version control)
- [ ] Regular security updates applied
- [ ] Backup encryption enabled
- [ ] Monitoring and alerting configured
- [ ] DDoS protection enabled (CloudFlare/AWS Shield)
- [ ] WAF rules configured
- [ ] Secrets rotated regularly

## Performance Checklist

- [ ] Database indexes optimized
- [ ] Redis caching properly configured
- [ ] CDN enabled for static assets
- [ ] Gzip compression enabled
- [ ] Connection pooling configured
- [ ] Query optimization completed
- [ ] Load testing performed
- [ ] Auto-scaling configured
- [ ] Resource limits set appropriately
- [ ] Monitoring dashboards created

## Support

For deployment assistance:
- **Documentation**: https://docs.auraconnect.com/deployment
- **Support Email**: support@auratechwave.com
- **Emergency Hotline**: +1-555-AURA-911

---

*Last Updated: January 2025*