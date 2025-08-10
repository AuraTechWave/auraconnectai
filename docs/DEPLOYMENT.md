# Deployment Guide - AuraConnect

**Version: 1.0.0** | Last Updated: January 2025

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [AWS Deployment](#aws-deployment)
6. [Railway Deployment](#railway-deployment)
7. [Database Migration Strategy](#database-migration-strategy)
8. [Environment Configuration](#environment-configuration)
9. [Monitoring & Logging](#monitoring--logging)
10. [Rollback Procedures](#rollback-procedures)
11. [Production Best Practices](#production-best-practices)

## Deployment Overview

AuraConnect supports multiple deployment strategies to accommodate different infrastructure requirements and scale.

### Deployment Options

| Platform | Best For | Complexity | Cost |
|----------|----------|------------|------|
| Docker Compose | Small-medium deployments | Low | $ |
| Kubernetes | Large scale, multi-region | High | $$$ |
| AWS ECS/Fargate | AWS-native deployments | Medium | $$ |
| Railway | Quick deployments, startups | Low | $ |

## Pre-Deployment Checklist

### Security Checklist
- [ ] All secrets in environment variables
- [ ] SSL certificates configured
- [ ] Database backups enabled
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] JWT secrets rotated
- [ ] Admin credentials changed

### Performance Checklist
- [ ] Database indexes created
- [ ] Redis caching configured
- [ ] Static assets CDN ready
- [ ] Image optimization complete
- [ ] Gzip compression enabled
- [ ] Connection pooling configured

### Monitoring Checklist
- [ ] Logging configured
- [ ] Error tracking enabled
- [ ] Health checks implemented
- [ ] Metrics collection setup
- [ ] Alerts configured
- [ ] Backup verification

## Docker Deployment

### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - static_volume:/app/static
    depends_on:
      - backend
      - frontend
    restart: always

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    volumes:
      - static_volume:/app/static
    depends_on:
      - db
      - redis
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        - REACT_APP_API_URL=${REACT_APP_API_URL}
    restart: always

  db:
    image: postgres:14-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: always
    command: >
      postgres
      -c shared_buffers=256MB
      -c max_connections=200
      -c effective_cache_size=1GB

  redis:
    image: redis:6-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: always

  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A tasks worker --loglevel=info
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - redis
      - db
    restart: always

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A tasks beat --loglevel=info
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - redis
      - db
    restart: always

volumes:
  postgres_data:
  redis_data:
  static_volume:
```

### Backend Dockerfile (Production)

```dockerfile
# backend/Dockerfile.prod
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run gunicorn
CMD ["gunicorn", "main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### Frontend Dockerfile (Production)

```dockerfile
# frontend/Dockerfile.prod
# Build stage
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build arguments
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built files from builder
COPY --from=builder /app/build /usr/share/nginx/html

# Add security headers
RUN echo 'add_header X-Frame-Options "SAMEORIGIN" always;' >> /etc/nginx/conf.d/security.conf && \
    echo 'add_header X-Content-Type-Options "nosniff" always;' >> /etc/nginx/conf.d/security.conf && \
    echo 'add_header X-XSS-Protection "1; mode=block" always;' >> /etc/nginx/conf.d/security.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Deployment Commands

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Backup database
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres auraconnect > backup.sql
```

## Kubernetes Deployment

### Kubernetes Architecture

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: auraconnect
```

### Backend Deployment

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
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: jwt-secret
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
---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  namespace: auraconnect
spec:
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### Database StatefulSet

```yaml
# k8s/postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: auraconnect
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:14-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: auraconnect
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secrets
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secrets
              key: password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

### Ingress Configuration

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auraconnect-ingress
  namespace: auraconnect
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.auraconnect.com
    - app.auraconnect.com
    secretName: auraconnect-tls
  rules:
  - host: api.auraconnect.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: backend-service
            port:
              number: 80
  - host: app.auraconnect.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: auraconnect
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

### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets
kubectl create secret generic app-secrets \
  --from-literal=database-url=$DATABASE_URL \
  --from-literal=jwt-secret=$JWT_SECRET_KEY \
  -n auraconnect

# Deploy all resources
kubectl apply -f k8s/

# Check deployment status
kubectl get all -n auraconnect

# View logs
kubectl logs -f deployment/backend -n auraconnect

# Scale deployment
kubectl scale deployment backend --replicas=5 -n auraconnect
```

## AWS Deployment

### AWS Architecture

```
┌─────────────────┐
│   CloudFront    │
└────────┬────────┘
         │
┌────────┴────────┐
│   ALB (HTTPS)   │
└────────┬────────┘
         │
┌────────┴────────┐
│   ECS Fargate   │
│  ┌───────────┐  │
│  │  Backend  │  │
│  │  Service  │  │
│  └───────────┘  │
└────────┬────────┘
         │
┌────────┴────────┐
│      RDS        │
│   PostgreSQL    │
└─────────────────┘
```

### Terraform Configuration

```hcl
# terraform/main.tf
provider "aws" {
  region = var.aws_region
}

# VPC
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "auraconnect-vpc"
  cidr = "10.0.0.0/16"
  
  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  
  enable_nat_gateway = true
  enable_vpn_gateway = true
  
  tags = {
    Environment = "production"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier = "auraconnect-db"
  
  engine         = "postgres"
  engine_version = "14.7"
  instance_class = "db.t3.medium"
  
  allocated_storage     = 100
  storage_encrypted     = true
  storage_type         = "gp3"
  
  db_name  = "auraconnect"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  multi_az               = true
  deletion_protection    = true
  
  tags = {
    Name        = "auraconnect-db"
    Environment = "production"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "auraconnect-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "auraconnect-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  
  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        }
      ]
      
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.db_url.arn
        },
        {
          name      = "JWT_SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.jwt_secret.arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "backend" {
  name            = "auraconnect-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 3
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.backend.id]
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
  
  health_check_grace_period_seconds = 60
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "auraconnect-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets           = module.vpc.public_subnets
  
  enable_deletion_protection = true
  enable_http2              = true
  
  tags = {
    Name        = "auraconnect-alb"
    Environment = "production"
  }
}
```

### AWS Deployment Script

```bash
#!/bin/bash
# deploy-aws.sh

# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REPOSITORY
docker build -t auraconnect-backend ./backend
docker tag auraconnect-backend:latest $ECR_REPOSITORY:latest
docker push $ECR_REPOSITORY:latest

# Update ECS service
aws ecs update-service \
  --cluster auraconnect-cluster \
  --service auraconnect-backend \
  --force-new-deployment

# Run database migrations
aws ecs run-task \
  --cluster auraconnect-cluster \
  --task-definition auraconnect-migration \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_IDS],securityGroups=[$SECURITY_GROUP_ID]}"
```

## Railway Deployment

### Railway Configuration

```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "./backend/Dockerfile.prod"

[deploy]
startCommand = "gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[environments.production]
ENVIRONMENT = "production"
```

### Railway Deployment Steps

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Link to GitHub repo
railway link

# Add PostgreSQL plugin
railway add postgresql

# Add Redis plugin
railway add redis

# Set environment variables
railway variables set JWT_SECRET_KEY=$JWT_SECRET_KEY
railway variables set STRIPE_API_KEY=$STRIPE_API_KEY

# Deploy
railway up

# Run migrations
railway run alembic upgrade head

# View logs
railway logs
```

## Database Migration Strategy

### Safe Migration Process

```python
# scripts/safe_migrate.py
import sys
import time
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

def safe_migrate():
    """Perform safe database migration with backup"""
    
    # 1. Create backup
    print("Creating database backup...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = 'auraconnect'
            AND pid <> pg_backend_pid()
        """))
        
        backup_name = f"backup_{int(time.time())}.sql"
        os.system(f"pg_dump {DATABASE_URL} > backups/{backup_name}")
    
    # 2. Run migration
    print("Running migrations...")
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.upgrade(alembic_cfg, "head")
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Migration failed: {e}")
        print(f"Restore backup with: psql {DATABASE_URL} < backups/{backup_name}")
        sys.exit(1)
    
    # 3. Verify migration
    print("Verifying migration...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        print(f"Current database version: {version}")

if __name__ == "__main__":
    safe_migrate()
```

### Zero-Downtime Migration

```bash
# Blue-Green deployment for migrations

# 1. Create new database
createdb auraconnect_new

# 2. Restore from production
pg_dump auraconnect | psql auraconnect_new

# 3. Run migrations on new database
DATABASE_URL=postgresql://localhost/auraconnect_new alembic upgrade head

# 4. Switch application to new database
# Update environment variable and restart services

# 5. Keep old database for rollback
# After verification, drop old database
```

## Environment Configuration

### Production Environment Variables

```bash
# .env.production
# Core Settings
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
ALLOWED_HOSTS=api.auraconnect.com,app.auraconnect.com

# Database
DATABASE_URL=postgresql://user:pass@rds.amazonaws.com:5432/auraconnect
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=100
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://:<password>@redis.auraconnect.com:6379/0
REDIS_MAX_CONNECTIONS=100

# Email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid-api-key>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@auraconnect.com

# Storage
AWS_ACCESS_KEY_ID=<aws-access-key>
AWS_SECRET_ACCESS_KEY=<aws-secret-key>
AWS_STORAGE_BUCKET_NAME=auraconnect-assets
AWS_S3_REGION_NAME=us-east-1

# Monitoring
SENTRY_DSN=https://<key>@sentry.io/<project>
NEW_RELIC_LICENSE_KEY=<new-relic-key>

# Feature Flags
ENABLE_ANALYTICS=True
ENABLE_AI_RECOMMENDATIONS=True
MAINTENANCE_MODE=False
```

### Secrets Management

```python
# core/secrets.py
import boto3
from functools import lru_cache

class SecretsManager:
    def __init__(self):
        self.client = boto3.client('secretsmanager')
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret from AWS Secrets Manager"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise

secrets_manager = SecretsManager()

# Usage
DATABASE_URL = secrets_manager.get_secret("auraconnect/database-url")
```

## Monitoring & Logging

### Logging Configuration

```python
# core/logging_config.py
import logging
import json
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Configure structured logging for production"""
    
    # JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        'logs/auraconnect.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Suppress noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
```

### Health Checks

```python
# core/health.py
from fastapi import APIRouter, Response, status
from sqlalchemy import text
import redis

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@router.get("/ready")
async def readiness_check(response: Response):
    """Detailed readiness check"""
    checks = {
        "database": False,
        "redis": False,
        "migrations": False
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except:
        pass
    
    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = True
    except:
        pass
    
    # Check migrations
    try:
        result = db.execute(text("SELECT version_num FROM alembic_version"))
        if result.scalar():
            checks["migrations"] = True
    except:
        pass
    
    # Set response status
    if not all(checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": "ready" if all(checks.values()) else "not ready",
        "checks": checks
    }
```

### Monitoring Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml
      - loki_data:/loki

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - ./promtail-config.yaml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml

volumes:
  prometheus_data:
  grafana_data:
  loki_data:
```

## Rollback Procedures

### Automated Rollback

```bash
#!/bin/bash
# rollback.sh

DEPLOYMENT_ID=$1
PREVIOUS_VERSION=$2

echo "Starting rollback to version $PREVIOUS_VERSION..."

# 1. Tag current version as failed
docker tag auraconnect:latest auraconnect:failed-$DEPLOYMENT_ID

# 2. Restore previous version
docker tag auraconnect:$PREVIOUS_VERSION auraconnect:latest

# 3. Update services
docker-compose -f docker-compose.prod.yml up -d --no-deps backend

# 4. Verify health
sleep 30
HEALTH_CHECK=$(curl -s http://localhost:8000/health | jq -r .status)

if [ "$HEALTH_CHECK" != "healthy" ]; then
    echo "Rollback failed! Health check not passing"
    exit 1
fi

echo "Rollback completed successfully"

# 5. Optional: Rollback database if needed
# psql $DATABASE_URL < backups/backup_$PREVIOUS_VERSION.sql
```

### Database Rollback

```python
# scripts/db_rollback.py
from alembic import command
from alembic.config import Config
import sys

def rollback_migration(steps=1):
    """Rollback database migration by N steps"""
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        # Downgrade by N steps
        command.downgrade(alembic_cfg, f"-{steps}")
        print(f"Successfully rolled back {steps} migration(s)")
    except Exception as e:
        print(f"Rollback failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rollback_migration(steps)
```

## Production Best Practices

### 1. Security Hardening

```nginx
# nginx/security.conf
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

# Hide nginx version
server_tokens off;

# Limit request size
client_max_body_size 10M;

# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;
```

### 2. Performance Optimization

```python
# Caching configuration
from functools import lru_cache
import redis
import pickle

redis_client = redis.from_url(settings.REDIS_URL)

def cache_result(ttl=3600):
    """Cache function results in Redis"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(
                cache_key,
                ttl,
                pickle.dumps(result)
            )
            
            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl=300)
def get_menu_items(restaurant_id: int):
    return db.query(MenuItem).filter_by(restaurant_id=restaurant_id).all()
```

### 3. Backup Strategy

```bash
#!/bin/bash
# backup.sh

# Configuration
BACKUP_DIR="/backups"
S3_BUCKET="auraconnect-backups"
RETENTION_DAYS=30

# Create backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/auraconnect_$TIMESTAMP.sql"

# Dump database
pg_dump $DATABASE_URL > $BACKUP_FILE

# Compress
gzip $BACKUP_FILE

# Upload to S3
aws s3 cp "$BACKUP_FILE.gz" "s3://$S3_BUCKET/postgres/"

# Clean old backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Clean old S3 backups
aws s3 ls "s3://$S3_BUCKET/postgres/" | \
  awk '{print $4}' | \
  while read -r file; do
    if [[ $(aws s3api head-object --bucket $S3_BUCKET --key "postgres/$file" | \
      jq -r '.LastModified' | \
      xargs -I {} date -d {} +%s) -lt $(date -d "$RETENTION_DAYS days ago" +%s) ]]; then
      aws s3 rm "s3://$S3_BUCKET/postgres/$file"
    fi
  done
```

### 4. Deployment Checklist

```markdown
## Pre-Deployment
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Backup created
- [ ] Rollback plan ready

## Deployment
- [ ] Tag release version
- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Deploy to production (canary/blue-green)
- [ ] Monitor metrics

## Post-Deployment
- [ ] Verify all services healthy
- [ ] Check error rates
- [ ] Monitor performance metrics
- [ ] Test critical user flows
- [ ] Update status page
```

---

*For deployment support, contact the DevOps team at devops@auratechwave.com*