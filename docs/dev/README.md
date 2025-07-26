# Development Guide

This guide provides comprehensive information for developers working on the AuraConnect platform.

## 🛠️ Development Environment Setup

### Prerequisites
- Python 3.11 or higher
- PostgreSQL 14 or higher
- Redis 7+ (optional, for caching and job tracking)
- Docker and Docker Compose
- Git

### Local Development Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/AuraTechWave/auraconnectai.git
cd auraconnectai
```

#### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your local configuration

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Using Docker (Recommended)
```bash
# From project root
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run tests
docker-compose exec backend pytest
```

## 🏗️ Architecture Documentation

### Module Architectures
- [Order Management](architecture/order_management_architecture.md)
- [Staff Management](architecture/staff_management_architecture.md)
- [Payroll & Tax](architecture/payroll_tax_architecture.md)
- [POS Integration](architecture/pos_integration_architecture.md)
- [Menu & Inventory](architecture/menu_inventory_architecture.md)
- [Analytics & Reporting](architecture/analytics_reporting_architecture.md)
- [Customer Loyalty](architecture/customer_loyalty_architecture.md)
- [AI Customization](architecture/ai_customization_suite.md)
- [Offline Sync](architecture/offline_sync_architecture.md)
- [Regulatory Compliance](architecture/regulatory_compliance_architecture.md)
- [White Labeling](architecture/white_labeling_architecture.md)

### System Overview
- [Global Architecture Overview](architecture/global_architecture_overview.md)

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=modules --cov-report=html

# Run specific test file
pytest backend/tests/test_payroll_engine_simple.py

# Run tests in parallel
pytest -n auto

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Test Structure
```
backend/tests/
├── unit/           # Isolated unit tests
├── integration/    # API and database tests
├── e2e/           # End-to-end tests
└── fixtures/      # Shared test data
```

### Writing Tests
- Use pytest fixtures for reusable test data
- Mock external dependencies
- Test both success and failure cases
- Maintain test coverage above 90%

## 📝 Code Standards

### Python Style Guide
- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 88 characters (Black default)
- Use descriptive variable names

### Code Formatting
```bash
# Format code with Black
black backend/

# Sort imports
isort backend/

# Check code style
flake8 backend/

# Type checking
mypy backend/
```

### Git Commit Messages
Follow conventional commits:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build process or auxiliary tool changes

Example:
```
feat(payroll): Add overtime calculation for holidays

- Implement 1.5x rate for holiday work
- Add configuration for holiday dates
- Update tests for holiday scenarios
```

## 🔧 Development Tools

### VS Code Extensions
- Python
- Pylance
- Black Formatter
- GitLens
- Docker
- Thunder Client (API testing)

### Useful Commands
```bash
# Database migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1

# Docker commands
docker-compose up -d
docker-compose down
docker-compose logs -f [service]
docker-compose exec backend bash

# Database access
docker-compose exec postgres psql -U postgres auraconnect
```

## 🚀 CI/CD Pipeline

See [CI/CD Setup](CI_CD_SETUP.md) for detailed information about:
- GitHub Actions workflows
- Automated testing
- Docker image building
- Deployment strategies

## 🔍 Debugging

### Local Debugging
1. Use VS Code's Python debugger
2. Set breakpoints in code
3. Use logging instead of print statements
4. Check Docker logs for container issues

### Common Issues
- **Import errors**: Check PYTHONPATH and virtual environment
- **Database connection**: Verify DATABASE_URL in .env
- **Migration errors**: Check for model changes
- **Test failures**: Ensure test database is clean

## 📊 Performance Optimization

### Database Queries
- Use SQL aggregation for bulk operations
- Add appropriate indexes
- Use query optimization tools
- Monitor slow queries

### API Performance
- Implement caching where appropriate
- Use pagination for list endpoints
- Optimize serialization
- Profile endpoint performance

## 🔐 Security Considerations

### Development Security
- Never commit secrets to Git
- Use environment variables
- Rotate development credentials regularly
- Test with non-production data

### Code Security
- Validate all inputs
- Use parameterized queries
- Implement proper authentication
- Follow OWASP guidelines

## 📚 Additional Resources

### Internal Documentation
- [System Architecture](../ARCHITECTURE.md)
- [API Documentation](http://localhost:8000/docs)
- [Production Deployment](../../backend/PRODUCTION_DEPLOYMENT_GUIDE.md)

### External Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

<div align="center">
  Happy coding! 🚀
</div>