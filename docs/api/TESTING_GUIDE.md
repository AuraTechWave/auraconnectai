# API Testing Guide

## Overview

This guide provides comprehensive instructions for testing the AuraConnect API, including unit tests, integration tests, and performance testing.

## Testing Environment Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- pytest and related packages

### Installation

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Environment Configuration

Create a `.env.test` file:

```env
DATABASE_URL=postgresql://testuser:testpass@localhost/auraconnect_test
REDIS_URL=redis://localhost:6379/1
JWT_SECRET_KEY=test-secret-key
ENVIRONMENT=test
TESTING=true
LOG_LEVEL=DEBUG
```

## Unit Testing

### Basic Test Structure

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from tests.factories import UserFactory, RestaurantFactory

client = TestClient(app)

class TestOrderAPI:
    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        """Setup test data"""
        self.user = UserFactory(role="manager")
        self.restaurant = RestaurantFactory()
        self.token = self.get_auth_token(self.user)
    
    def get_auth_token(self, user):
        """Helper to get JWT token"""
        response = client.post("/auth/login", json={
            "username": user.email,
            "password": "testpass123"
        })
        return response.json()["access_token"]
    
    def test_create_order(self):
        """Test order creation"""
        response = client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "customer_id": 1,
                "items": [
                    {"menu_item_id": 1, "quantity": 2}
                ]
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["items"]) == 1
```

### Testing Authentication

```python
class TestAuthentication:
    def test_login_success(self):
        """Test successful login"""
        user = UserFactory(email="test@example.com")
        
        response = client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "testpass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post("/auth/login", json={
            "username": "wrong@example.com",
            "password": "wrongpass"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    
    def test_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token"""
        response = client.get("/api/v1/orders")
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
```

### Testing CRUD Operations

```python
class TestMenuCRUD:
    def test_create_menu_item(self):
        """Test creating a menu item"""
        response = client.post(
            "/api/v1/menu",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "name": "Burger",
                "description": "Delicious burger",
                "price": 12.99,
                "category_id": 1
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Burger"
        assert data["price"] == 12.99
    
    def test_update_menu_item(self):
        """Test updating a menu item"""
        item = MenuItemFactory()
        
        response = client.put(
            f"/api/v1/menu/{item.id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"price": 14.99}
        )
        
        assert response.status_code == 200
        assert response.json()["price"] == 14.99
    
    def test_delete_menu_item(self):
        """Test deleting a menu item"""
        item = MenuItemFactory()
        
        response = client.delete(
            f"/api/v1/menu/{item.id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 204
        
        # Verify deletion
        response = client.get(f"/api/v1/menu/{item.id}")
        assert response.status_code == 404
```

## Integration Testing

### Database Transactions

```python
@pytest.mark.integration
class TestOrderWorkflow:
    def test_complete_order_flow(self, db_session):
        """Test complete order workflow"""
        # Create order
        order_response = client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "customer_id": 1,
                "items": [{"menu_item_id": 1, "quantity": 2}]
            }
        )
        order_id = order_response.json()["id"]
        
        # Process payment
        payment_response = client.post(
            f"/api/v1/orders/{order_id}/payment",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "payment_method": "card",
                "amount": 25.98
            }
        )
        assert payment_response.status_code == 200
        
        # Update status
        status_response = client.patch(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"status": "completed"}
        )
        assert status_response.status_code == 200
        
        # Verify final state
        order = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        ).json()
        
        assert order["status"] == "completed"
        assert order["payment_status"] == "paid"
```

### External Service Mocking

```python
from unittest.mock import patch, MagicMock

class TestPOSIntegration:
    @patch('modules.pos.square_client.SquareClient')
    def test_pos_sync(self, mock_square):
        """Test POS synchronization"""
        # Mock external API response
        mock_square.return_value.get_orders.return_value = [
            {
                "id": "sq_123",
                "total_money": {"amount": 1299, "currency": "USD"},
                "created_at": "2025-08-08T10:00:00Z"
            }
        ]
        
        response = client.post(
            "/api/v1/pos/sync",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"pos_type": "square"}
        )
        
        assert response.status_code == 200
        assert response.json()["orders_synced"] == 1
```

## Performance Testing

### Load Testing with Locust

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get token"""
        response = self.client.post("/auth/login", json={
            "username": "load_test@example.com",
            "password": "testpass123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def get_orders(self):
        """Frequently accessed endpoint"""
        self.client.get("/api/v1/orders", headers=self.headers)
    
    @task(2)
    def get_menu(self):
        """Menu listing"""
        self.client.get("/api/v1/menu", headers=self.headers)
    
    @task(1)
    def create_order(self):
        """Create new order"""
        self.client.post(
            "/api/v1/orders",
            headers=self.headers,
            json={
                "customer_id": 1,
                "items": [{"menu_item_id": 1, "quantity": 1}]
            }
        )
```

Run load test:
```bash
locust -f locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10
```

### Benchmark Critical Paths

```python
import time
import asyncio
from statistics import mean, stdev

class TestPerformance:
    @pytest.mark.benchmark
    async def test_order_creation_performance(self):
        """Benchmark order creation"""
        times = []
        
        for _ in range(100):
            start = time.time()
            
            response = await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "customer_id": 1,
                    "items": [{"menu_item_id": 1, "quantity": 2}]
                }
            )
            
            end = time.time()
            times.append(end - start)
            
            assert response.status_code == 201
        
        avg_time = mean(times)
        std_dev = stdev(times)
        
        assert avg_time < 0.1  # Should complete in under 100ms
        print(f"Average time: {avg_time:.3f}s (±{std_dev:.3f}s)")
```

## API Contract Testing

### Schema Validation

```python
from jsonschema import validate
import json

class TestAPIContracts:
    def test_order_response_schema(self):
        """Validate order response matches schema"""
        response = client.get(
            "/api/v1/orders/1",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        order_schema = {
            "type": "object",
            "required": ["id", "status", "total_amount", "items"],
            "properties": {
                "id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "confirmed", "completed"]},
                "total_amount": {"type": "number"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "menu_item_id", "quantity", "price"],
                        "properties": {
                            "id": {"type": "integer"},
                            "menu_item_id": {"type": "integer"},
                            "quantity": {"type": "integer"},
                            "price": {"type": "number"}
                        }
                    }
                }
            }
        }
        
        validate(response.json(), order_schema)
```

### Backwards Compatibility Testing

```python
class TestBackwardsCompatibility:
    def test_deprecated_endpoint_still_works(self):
        """Ensure deprecated endpoints continue to function"""
        # Old endpoint format
        response = client.get(
            "/api/v1/orders/list",  # Deprecated in favor of /api/v1/orders
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 200
        assert "X-API-Deprecated" in response.headers
        assert response.headers["X-API-Deprecated"] == "true"
```

## Security Testing

### SQL Injection Testing

```python
class TestSecurity:
    def test_sql_injection_prevention(self):
        """Test SQL injection is prevented"""
        malicious_input = "1' OR '1'='1"
        
        response = client.get(
            f"/api/v1/orders/{malicious_input}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 422  # Invalid input format
    
    def test_xss_prevention(self):
        """Test XSS prevention in API"""
        xss_payload = "<script>alert('XSS')</script>"
        
        response = client.post(
            "/api/v1/menu",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "name": xss_payload,
                "price": 10.00
            }
        )
        
        # Should accept but escape on output
        assert response.status_code == 201
        assert response.json()["name"] == xss_payload  # Stored as-is
        
        # When rendered, should be escaped (test in frontend)
```

### Rate Limiting Testing

```python
class TestRateLimiting:
    def test_rate_limit_enforcement(self):
        """Test rate limiting is enforced"""
        # Make requests up to the limit
        for i in range(100):
            response = client.get(
                "/api/v1/menu",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 429:
                # Rate limit hit
                assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
                assert "Retry-After" in response.headers
                break
        else:
            pytest.fail("Rate limit not enforced after 100 requests")
```

## Mocking Strategies

### Database Mocking

```python
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = MagicMock(spec=Session)
    yield db

def test_with_mock_db(mock_db):
    """Test using mocked database"""
    from modules.orders.service import OrderService
    
    service = OrderService(mock_db)
    mock_db.query.return_value.filter.return_value.first.return_value = Order(id=1)
    
    order = service.get_order(1)
    assert order.id == 1
```

### Time-based Testing

```python
from freezegun import freeze_time

class TestTimeBasedFeatures:
    @freeze_time("2025-08-08 10:00:00")
    def test_happy_hour_pricing(self):
        """Test time-based pricing"""
        response = client.get(
            "/api/v1/menu",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # During happy hour, prices should be discounted
        items = response.json()
        for item in items:
            if item["happy_hour_eligible"]:
                assert item["current_price"] < item["regular_price"]
```

## Test Data Management

### Factories

```python
import factory
from factory.alchemy import SQLAlchemyModelFactory
from modules.orders.models import Order

class OrderFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Order
        sqlalchemy_session_persistence = "commit"
    
    customer_id = factory.Faker("random_int", min=1, max=100)
    status = "pending"
    total_amount = factory.Faker("pydecimal", left_digits=3, right_digits=2)
    
    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            for item in extracted:
                self.items.append(item)
```

### Fixtures

```python
@pytest.fixture
def sample_restaurant(db_session):
    """Create a sample restaurant"""
    restaurant = Restaurant(
        name="Test Restaurant",
        address="123 Test St",
        phone="+1234567890"
    )
    db_session.add(restaurant)
    db_session.commit()
    return restaurant

@pytest.fixture
def authenticated_client(client, sample_user):
    """Client with authentication headers"""
    token = get_auth_token(sample_user)
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
```

## Continuous Integration

### GitHub Actions Test Workflow

```yaml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r backend/requirements.txt
        pip install -r backend/requirements-dev.txt
    
    - name: Run tests
      run: |
        cd backend
        pytest -v --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Use Fixtures**: Share common setup code
3. **Mock External Services**: Don't depend on external APIs
4. **Test Edge Cases**: Include boundary conditions
5. **Performance Benchmarks**: Set and monitor performance targets
6. **Security Testing**: Include security checks in CI/CD
7. **Documentation**: Document test scenarios and expected behaviors

## Debugging Tips

### Verbose Output
```bash
pytest -vv --tb=short
```

### Run Specific Tests
```bash
pytest tests/test_orders.py::TestOrderAPI::test_create_order
```

### Debug with PDB
```python
def test_complex_scenario():
    import pdb; pdb.set_trace()
    # Test code here
```

### Check Test Coverage
```bash
pytest --cov=modules --cov-report=html
open htmlcov/index.html
```