# Getting Started with AuraConnect

Welcome to AuraConnect! This guide will help you get up and running with the platform quickly. Whether you're setting up a development environment or deploying to production, we'll walk you through each step.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start with Docker](#quick-start-with-docker)
3. [Local Development Setup](#local-development-setup)
4. [Understanding the Architecture](#understanding-the-architecture)
5. [First Steps](#first-steps)
6. [Common Tasks](#common-tasks)
7. [Troubleshooting](#troubleshooting)
8. [Next Steps](#next-steps)

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL2
- **Memory**: Minimum 8GB RAM (16GB recommended)
- **Storage**: At least 10GB free space
- **CPU**: 4+ cores recommended

### Software Requirements

- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Python**: Version 3.11+
- **Node.js**: Version 18+ (for frontend)
- **PostgreSQL**: Version 14+ (if running locally)
- **Redis**: Version 6+ (if running locally)
- **Git**: For version control

## Quick Start with Docker

The fastest way to get started is using Docker Compose, which sets up the entire stack automatically.

### 1. Clone the Repository

```bash
git clone https://github.com/AuraTechWave/auraconnectai.git
cd auraconnectai
```

### 2. Configure Environment

```bash
# Copy example environment files
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit .env files with your settings
# At minimum, update:
# - DATABASE_URL
# - REDIS_URL
# - JWT_SECRET_KEY
# - API_KEYS for external services
```

### 3. Start All Services

```bash
# Build and start all services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Initialize the Database

```bash
# Run database migrations
docker-compose exec backend alembic upgrade head

# Load demo data (optional)
docker-compose exec backend python scripts/seed_demo_data.py
```

### 5. Access the Application

- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Admin Portal**: http://localhost:3000/admin
- **PgAdmin**: http://localhost:5050 (if enabled)
- **Redis Commander**: http://localhost:8081 (if enabled)

### Default Credentials

```
Admin User:
- Email: admin@auraconnect.com
- Password: admin123

Demo Restaurant:
- Email: demo@restaurant.com
- Password: demo123
```

## Local Development Setup

For active development, you may prefer running services locally.

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install
```

### 2. Database Setup

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Or install locally:
# PostgreSQL: https://www.postgresql.org/download/
# Redis: https://redis.io/download

# Create database
createdb auraconnect

# Run migrations
alembic upgrade head

# Seed data (optional)
python scripts/seed_demo_data.py
```

### 3. Start Backend Services

```bash
# Start main API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# In separate terminals, start other services:
# Orders service
cd modules/orders && uvicorn main:app --reload --port 8002

# Menu service
cd modules/menu && uvicorn main:app --reload --port 8001

# Start Celery worker (for background tasks)
celery -A tasks worker --loglevel=info

# Start Celery beat (for scheduled tasks)
celery -A tasks beat --loglevel=info
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# The app will be available at http://localhost:3000
```

## Understanding the Architecture

AuraConnect uses a microservices architecture:

```
┌───────────────────────┐
│   Frontend (React)   │
└──────────┬───────────┘
            │
┌──────────┴───────────┐
│   API Gateway (Nginx) │
└──────────┬───────────┘
            │
┌───────────┴────────────┐
│    Backend Services    │
│ ┌───────┐ ┌────────┐  │
│ │ Auth   │ │ Orders │  │
│ └───────┘ └────────┘  │
│ ┌───────┐ ┌────────┐  │
│ │ Menu   │ │ Staff  │  │
│ └───────┘ └────────┘  │
└───────────┬────────────┘
            │
┌───────────┴────────────┐
│   Data & Infrastructure │
│ ┌──────────┐ ┌───────┐ │
│ │PostgreSQL│ │ Redis │ │
│ └──────────┘ └───────┘ │
└─────────────────────────┘
```

### Key Services

- **Auth Service**: Handles authentication and authorization
- **Orders Service**: Manages order processing
- **Menu Service**: Handles menu items and pricing
- **Staff Service**: Employee management and scheduling
- **Payroll Service**: Payroll processing and tax calculations

## First Steps

### 1. Create Your First Restaurant

```python
# Using the API
import requests

headers = {"Authorization": "Bearer <admin_token>"}

restaurant_data = {
    "name": "My Restaurant",
    "timezone": "America/New_York",
    "currency": "USD",
    "locations": [
        {
            "name": "Main Street",
            "address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "phone": "(555) 123-4567"
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/restaurants",
    json=restaurant_data,
    headers=headers
)
```

### 2. Set Up Menu Categories

```python
categories = [
    {"name": "Appetizers", "display_order": 1},
    {"name": "Main Courses", "display_order": 2},
    {"name": "Desserts", "display_order": 3},
    {"name": "Beverages", "display_order": 4}
]

for category in categories:
    response = requests.post(
        "http://localhost:8001/api/v1/menu/categories",
        json=category,
        headers=headers
    )
```

### 3. Add Your First Employee

```python
employee_data = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@myrestaurant.com",
    "role": "manager",
    "location_ids": [1],
    "hourly_rate": "25.00"
}

response = requests.post(
    "http://localhost:8005/api/v1/staff/employees",
    json=employee_data,
    headers=headers
)
```

## Common Tasks

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# With coverage
pytest tests/ --cov=modules --cov-report=html

# Frontend tests
cd frontend
npm test
npm run test:coverage
```

### Database Operations

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Database backup
pg_dump auraconnect > backup.sql

# Restore database
psql auraconnect < backup.sql
```

### Monitoring Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# With timestamps
docker-compose logs -f --timestamps

# Last 100 lines
docker-compose logs --tail=100
```

### Clearing Cache

```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Or using Python
python -c "import redis; redis.Redis().flushall()"
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

#### 2. Database Connection Error

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection
psql -h localhost -U postgres -d auraconnect

# Reset database
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

#### 3. Redis Connection Error

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli ping
# Should return: PONG
```

#### 4. Frontend Build Issues

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG=True
export LOG_LEVEL=DEBUG

# Run with verbose output
uvicorn main:app --reload --log-level debug
```

## Configuration Options

### Environment Variables

```bash
# Core Settings
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/auraconnect
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Settings
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# External Services
STRIPE_API_KEY=sk_test_...
TWILIO_ACCOUNT_SID=AC...
SENDGRID_API_KEY=SG...

# Feature Flags
ENABLE_ANALYTICS=True
ENABLE_AI_RECOMMENDATIONS=False
```

### Service Ports

| Service | Default Port | Environment Variable |
|---------|--------------|--------------------|
| Main API | 8000 | API_PORT |
| Menu Service | 8001 | MENU_SERVICE_PORT |
| Orders Service | 8002 | ORDERS_SERVICE_PORT |
| Frontend | 3000 | FRONTEND_PORT |
| PostgreSQL | 5432 | POSTGRES_PORT |
| Redis | 6379 | REDIS_PORT |

## Development Tips

### 1. Use the API Documentation

The interactive API docs at http://localhost:8000/docs are your best friend. You can:
- Explore all endpoints
- Try API calls directly
- View request/response schemas
- Download OpenAPI spec

### 2. Enable Hot Reload

For faster development:
```bash
# Backend
uvicorn main:app --reload

# Frontend
npm run dev
```

### 3. Use Docker Volumes

For persistent development data:
```yaml
# docker-compose.override.yml
services:
  postgres:
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
  redis:
    volumes:
      - ./data/redis:/data
```

### 4. VS Code Extensions

Recommended extensions:
- Python
- Pylance
- ESLint
- Prettier
- Docker
- PostgreSQL
- Thunder Client (API testing)

## Next Steps

1. **Explore the Modules**
   - [Orders Module](../modules/orders/README.md)
   - [Menu Module](../modules/menu/README.md)
   - [Staff Module](../modules/staff/README.md)

2. **Learn the Architecture**
   - [Architecture Overview](../architecture/README.md)
   - [API Design Guide](../api/design-guide.md)
   - [Database Schema](../modules/README.md)

3. **Set Up Your Restaurant**
   - Configure locations
   - Import menu items
   - Add staff members
   - Set up payment processing

4. **Deploy to Production**
   - [Deployment Guide](../deployment/README.md)
   - [Security Checklist](../guides/security.md)
   - [Performance Tuning](../guides/performance.md)

## Getting Help

- **Documentation**: https://docs.auraconnect.com
- **API Reference**: http://localhost:8000/docs
- **GitHub Issues**: https://github.com/AuraTechWave/auraconnectai/issues
- **Discord Community**: https://discord.gg/auraconnect
- **Email Support**: support@auratechwave.com

---

*Happy coding! Welcome to the AuraConnect community!* 🚀