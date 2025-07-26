# AuraConnect – Enterprise Restaurant Management Platform

<div align="center">
  <img src="docs/assets/AuraConnect_Architecture_ColorCoded.png" alt="AuraConnect Architecture" width="600">
  
  **A comprehensive, AI-integrated restaurant management system built with modern architecture**
  
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
  [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org)
  [![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
</div>

## 🎯 Overview

AuraConnect is a production-ready restaurant management platform that integrates:
- **Order Management** - Real-time order processing with kitchen integration
- **Staff & Payroll** - Comprehensive employee management with automated payroll
- **Tax Compliance** - Multi-jurisdiction tax calculation and reporting
- **POS Integration** - Seamless integration with major POS systems
- **Analytics & Insights** - AI-powered business intelligence

## 🏗️ Architecture

### Core Technologies
- **Backend**: FastAPI (Python 3.11+) with async/await support
- **Database**: PostgreSQL with Alembic migrations
- **Authentication**: JWT-based with refresh token rotation
- **Task Queue**: Background job processing with persistent tracking
- **Caching**: Redis for performance optimization
- **Container**: Docker & Docker Compose for development and deployment

### Key Modules

#### 📦 Order Management
- Real-time order processing with WebSocket support
- Kitchen display system integration
- Dynamic pricing and fraud detection
- Payment reconciliation engine
- Webhook system for external integrations

#### 👥 Staff & Payroll
- Attendance tracking with SQL-optimized aggregation
- Enhanced payroll engine with configurable business rules
- Multi-jurisdiction tax calculation
- Automated benefit proration
- Comprehensive audit trails

#### 💰 Tax Services
- IRS-compliant tax calculations
- Social Security and Medicare cap handling
- State and local tax support
- Year-to-date tracking
- Tax form generation (W-2, 1099)

#### 🔌 POS Integration
- Square, Clover, Toast adapter system
- Real-time sync with conflict resolution
- Offline-first architecture
- Automatic retry mechanisms

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis (optional, for caching)
- Docker & Docker Compose

### Development Setup

```bash
# Clone the repository
git clone https://github.com/AuraTechWave/auraconnectai.git
cd auraconnectai

# Set up Python environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt

# Set up environment variables
cp backend/.env.example backend/.env
# Edit .env with your configuration

# Run database migrations
cd backend
alembic upgrade head

# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Setup

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run tests
docker-compose exec backend pytest
```

## 🔐 Security

### Environment Variables
```bash
# Required for production
JWT_SECRET_KEY=your-256-bit-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
ENVIRONMENT=production

# Security features
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["https://your-domain.com"]
```

### Authentication
- JWT tokens with type validation (access/refresh)
- Role-based access control (RBAC)
- Tenant isolation for multi-restaurant support
- Automatic token refresh mechanism

## 📊 API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### Payroll Processing
```http
POST /api/v1/payrolls/run
{
  "staff_ids": [1, 2, 3],
  "pay_period_start": "2024-01-01",
  "pay_period_end": "2024-01-15"
}
```

#### Order Management
```http
POST /api/v1/orders
{
  "items": [...],
  "customer_id": 123,
  "special_instructions": "No onions"
}
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=modules --cov-report=html

# Run specific test suite
pytest backend/tests/test_payroll_engine_simple.py -v
```

### Test Coverage
- ✅ Unit tests for business logic
- ✅ Integration tests for API endpoints
- ✅ Performance tests for SQL optimization
- ✅ Mock-based tests for external services

## 🚢 Deployment

### Production Checklist
- [ ] Set secure JWT_SECRET_KEY
- [ ] Configure production database
- [ ] Enable Redis for caching
- [ ] Set up SSL certificates
- [ ] Configure monitoring (Prometheus/Grafana)
- [ ] Set up log aggregation
- [ ] Configure backup strategy

### Deployment Options
- **Docker Swarm**: Production-ready orchestration
- **Kubernetes**: For large-scale deployments
- **Railway/Render**: Quick cloud deployment
- **AWS ECS**: Managed container service

## 📈 Performance Optimizations

### Implemented Optimizations
- **SQL Aggregation**: Batch processing for attendance calculations
- **Connection Pooling**: Optimized database connections
- **Redis Caching**: For frequently accessed data
- **Async Processing**: Non-blocking I/O operations
- **Job Queue**: Background task processing

### Monitoring
- Health check endpoint: `/health`
- Metrics endpoint: `/metrics`
- Performance tracking with configurable thresholds

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards
- **Python**: Black formatter, flake8 linter
- **Type Hints**: Required for all new code
- **Tests**: Required for all features
- **Documentation**: API endpoints must be documented

## 📄 License

This project is proprietary software owned by AuraTechWave. All rights reserved.

## 🔗 Links

- [API Documentation](http://localhost:8000/docs)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [Deployment Guide](backend/PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Contributing Guidelines](CONTRIBUTING.md)

---

<div align="center">
  Built with ❤️ by AuraTechWave
</div>