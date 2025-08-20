# AuraConnect AI - Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development](#local-development)
4. [Production Deployment](#production-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

## Overview

AuraConnect AI is a containerized restaurant management platform that can be deployed using Docker Compose for development or Kubernetes for production environments.

### Architecture Components
- **Backend API**: FastAPI application (Python 3.11)
- **Frontend**: React application served by Nginx
- **Database**: PostgreSQL 14
- **Cache**: Redis 7
- **Worker**: Background job processor
- **Load Balancer**: Nginx (production)

## Prerequisites

### Development Environment
- Docker Desktop 20.10+
- Docker Compose v2.0+
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- Make (optional, for automation)

### Production Environment
- Kubernetes 1.25+
- kubectl configured
- Helm 3+ (for cert-manager)
- AWS CLI (if using S3 for backups)
- Domain name with DNS control

## Local Development

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/auraconnect/auraconnectai.git
   cd auraconnectai
   ```

2. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Verify services are running**
   ```bash
   docker-compose ps
   ```

5. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - PgAdmin: http://localhost:5050 (if enabled)
   - Redis Commander: http://localhost:8081 (if enabled)

### Development Commands

```bash
# Start all services
docker-compose up -d

# Start with specific profiles
docker-compose --profile tools up -d  # Include PgAdmin and Redis Commander
docker-compose --profile development up -d  # Include Mailhog

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Execute commands in containers
docker-compose exec backend bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend pytest

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Database Management

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create a new migration
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Rollback migration
docker-compose exec backend alembic downgrade -1

# Access PostgreSQL CLI
docker-compose exec postgres psql -U auraconnect -d auraconnect
```

## Production Deployment

### Building Docker Images

1. **Build backend image**
   ```bash
   cd backend
   docker build -t auraconnect/backend:latest .
   docker tag auraconnect/backend:latest auraconnect/backend:v1.0.0
   ```

2. **Build frontend image**
   ```bash
   cd frontend
   docker build -t auraconnect/frontend:latest \
     --build-arg REACT_APP_API_URL=https://api.auraconnect.ai \
     --build-arg REACT_APP_ENVIRONMENT=production .
   docker tag auraconnect/frontend:latest auraconnect/frontend:v1.0.0
   ```

3. **Push to registry**
   ```bash
   # Using Docker Hub
   docker push auraconnect/backend:latest
   docker push auraconnect/backend:v1.0.0
   docker push auraconnect/frontend:latest
   docker push auraconnect/frontend:v1.0.0
   
   # Using AWS ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY
   docker tag auraconnect/backend:latest $ECR_REGISTRY/auraconnect/backend:latest
   docker push $ECR_REGISTRY/auraconnect/backend:latest
   ```

## Kubernetes Deployment

### Prerequisites

1. **Install cert-manager for SSL**
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
   ```

2. **Install NGINX Ingress Controller**
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx
   ```

### Deployment Steps

1. **Create namespace**
   ```bash
   kubectl apply -f kubernetes/namespace.yaml
   ```

2. **Configure secrets**
   ```bash
   # Generate secrets template
   ./scripts/manage-secrets.sh -g
   
   # Edit .env.secrets with actual values
   vim .env.secrets
   
   # Apply secrets to Kubernetes
   ./scripts/manage-secrets.sh -e production -f .env.secrets -a
   ```

3. **Apply configurations**
   ```bash
   kubectl apply -f kubernetes/configmap.yaml
   ```

4. **Deploy database and cache**
   ```bash
   kubectl apply -f kubernetes/postgres.yaml
   kubectl apply -f kubernetes/redis.yaml
   
   # Wait for them to be ready
   kubectl wait --for=condition=ready pod -l app=postgres -n auraconnect --timeout=300s
   kubectl wait --for=condition=ready pod -l app=redis -n auraconnect --timeout=300s
   ```

5. **Deploy application**
   ```bash
   kubectl apply -f kubernetes/backend.yaml
   kubectl apply -f kubernetes/frontend.yaml
   kubectl apply -f kubernetes/worker.yaml
   ```

6. **Setup SSL certificates**
   ```bash
   kubectl apply -f kubernetes/cert-manager.yaml
   ```

7. **Configure ingress**
   ```bash
   kubectl apply -f kubernetes/ingress.yaml
   ```

8. **Verify deployment**
   ```bash
   # Check pod status
   kubectl get pods -n auraconnect
   
   # Check services
   kubectl get svc -n auraconnect
   
   # Check ingress
   kubectl get ingress -n auraconnect
   
   # Check certificates
   kubectl get certificates -n auraconnect
   ```

### Scaling

```bash
# Manual scaling
kubectl scale deployment backend --replicas=5 -n auraconnect
kubectl scale deployment frontend --replicas=3 -n auraconnect

# Check HPA status
kubectl get hpa -n auraconnect

# Update HPA limits
kubectl edit hpa backend-hpa -n auraconnect
```

### Rolling Updates

```bash
# Update backend image
kubectl set image deployment/backend backend=auraconnect/backend:v1.0.1 -n auraconnect

# Check rollout status
kubectl rollout status deployment/backend -n auraconnect

# Rollback if needed
kubectl rollout undo deployment/backend -n auraconnect
```

## Monitoring & Maintenance

### Health Checks

All services include health check endpoints:
- Backend: `GET /health`
- Frontend: `GET /` (HTTP 200)
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`

### Logging

```bash
# View logs in Kubernetes
kubectl logs -f deployment/backend -n auraconnect
kubectl logs -f deployment/frontend -n auraconnect

# View logs in Docker
docker-compose logs -f backend
docker-compose logs -f frontend

# Export logs
kubectl logs deployment/backend -n auraconnect > backend.log
```

### Database Backups

```bash
# Manual backup (Docker)
./scripts/backup-restore.sh backup

# Manual backup (Kubernetes)
./scripts/backup-restore.sh -e kubernetes backup

# Backup to S3
./scripts/backup-restore.sh -s s3://my-backup-bucket backup

# Schedule automated backups
./scripts/backup-restore.sh schedule

# Restore from backup
./scripts/backup-restore.sh restore backups/backup_auraconnect_20240101_120000.sql.gz

# List available backups
./scripts/backup-restore.sh list

# Cleanup old backups
./scripts/backup-restore.sh cleanup
```

### Monitoring Metrics

The application exposes Prometheus metrics at `/metrics`:

```bash
# Backend metrics
curl http://localhost:8000/metrics

# Example metrics to monitor:
# - Request count and latency
# - Database connection pool
# - Redis operations
# - Background job queue length
# - Payment processing success rate
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed
```bash
# Check PostgreSQL pod/container
kubectl get pods -l app=postgres -n auraconnect
docker-compose ps postgres

# Check logs
kubectl logs -l app=postgres -n auraconnect
docker-compose logs postgres

# Verify credentials
kubectl get secret auraconnect-secrets -n auraconnect -o yaml
```

#### 2. Redis Connection Issues
```bash
# Test Redis connection
kubectl exec -it deployment/redis -n auraconnect -- redis-cli ping
docker-compose exec redis redis-cli ping

# Check Redis password
kubectl get secret auraconnect-secrets -n auraconnect -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d
```

#### 3. Migration Failures
```bash
# Run migrations manually
kubectl exec -it deployment/backend -n auraconnect -- alembic upgrade head
docker-compose exec backend alembic upgrade head

# Check migration history
kubectl exec -it deployment/backend -n auraconnect -- alembic history
```

#### 4. SSL Certificate Issues
```bash
# Check certificate status
kubectl describe certificate auraconnect-tls -n auraconnect

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Force certificate renewal
kubectl delete certificate auraconnect-tls -n auraconnect
kubectl apply -f kubernetes/cert-manager.yaml
```

#### 5. Frontend Not Loading
```bash
# Check nginx configuration
kubectl exec -it deployment/frontend -n auraconnect -- nginx -t

# Verify API URL configuration
kubectl exec -it deployment/frontend -n auraconnect -- env | grep REACT_APP_API_URL
```

### Debug Commands

```bash
# Get detailed pod information
kubectl describe pod <pod-name> -n auraconnect

# Execute shell in pod
kubectl exec -it <pod-name> -n auraconnect -- /bin/sh

# Port forward for debugging
kubectl port-forward deployment/backend 8000:8000 -n auraconnect

# Check resource usage
kubectl top pods -n auraconnect
kubectl top nodes

# View recent events
kubectl get events -n auraconnect --sort-by='.lastTimestamp'
```

## Security Considerations

1. **Secrets Management**
   - Never commit secrets to version control
   - Use Kubernetes secrets or external secret managers
   - Rotate secrets regularly
   - Use separate secrets for each environment

2. **Network Security**
   - Enable NetworkPolicies in Kubernetes
   - Use SSL/TLS for all external communications
   - Implement rate limiting at ingress
   - Whitelist IP addresses if possible

3. **Container Security**
   - Run containers as non-root users
   - Keep base images updated
   - Scan images for vulnerabilities
   - Use minimal base images (Alpine)

4. **Database Security**
   - Use strong passwords
   - Enable SSL for database connections
   - Regular backups with encryption
   - Restrict network access

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build and push Docker images
        run: |
          docker build -t auraconnect/backend:${{ github.sha }} ./backend
          docker build -t auraconnect/frontend:${{ github.sha }} ./frontend
          docker push auraconnect/backend:${{ github.sha }}
          docker push auraconnect/frontend:${{ github.sha }}
      
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/backend backend=auraconnect/backend:${{ github.sha }} -n auraconnect
          kubectl set image deployment/frontend frontend=auraconnect/frontend:${{ github.sha }} -n auraconnect
          kubectl rollout status deployment/backend -n auraconnect
          kubectl rollout status deployment/frontend -n auraconnect
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/auraconnect/auraconnectai/issues
- Documentation: https://docs.auraconnect.ai
- Email: support@auraconnect.ai