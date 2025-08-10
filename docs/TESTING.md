# Testing Guide - AuraConnect

**Version: 1.0.0** | Last Updated: January 2025

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Backend Testing](#backend-testing)
3. [Frontend Testing](#frontend-testing)
4. [Mobile Testing](#mobile-testing)
5. [Integration Testing](#integration-testing)
6. [Performance Testing](#performance-testing)
7. [Security Testing](#security-testing)
8. [Test Data Management](#test-data-management)
9. [CI/CD Testing](#cicd-testing)
10. [Testing Best Practices](#testing-best-practices)

## Testing Overview

AuraConnect follows a comprehensive testing strategy to ensure code quality, reliability, and performance across all components.

### Testing Pyramid

```
         /\
        /  \    E2E Tests (10%)
       /    \   - Critical user flows
      /      \  - Payment processes
     /--------\ Integration Tests (30%)
    /          \- API endpoints
   /            \- Database operations
  /--------------\Unit Tests (60%)
 /                \- Business logic
/                  \- Utilities
```

### Test Coverage Goals

- **Overall**: 80% minimum
- **Critical paths**: 95% minimum
- **New code**: 90% minimum

## Backend Testing

### Setup

```bash
# Install test dependencies
cd backend
pip install -r requirements-test.txt

# Create test database
createdb auraconnect_test

# Set test environment
export ENVIRONMENT=test
export DATABASE_URL=postgresql://localhost/auraconnect_test
```

### Running Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=modules --cov-report=html

# Run specific module
pytest modules/orders/tests/

# Run specific test
pytest modules/orders/tests/test_order_service.py::test_create_order

# Run with verbose output
pytest -v

# Run tests in parallel
pytest -n 4

# Run only marked tests
pytest -m "unit"
pytest -m "integration"
pytest -m "slow"
```

### Writing Backend Tests

#### Unit Test Example

```python
# modules/orders/tests/test_order_service.py
import pytest
from unittest.mock import Mock, patch
from modules.orders.services import OrderService
from modules.orders.models import Order

class TestOrderService:
    @pytest.fixture
    def order_service(self):
        return OrderService()
    
    @pytest.fixture
    def mock_db(self):
        with patch('modules.orders.services.get_db') as mock:
            yield mock
    
    def test_create_order_success(self, order_service, mock_db):
        # Arrange
        order_data = {
            "customer_id": 1,
            "items": [{"menu_item_id": 1, "quantity": 2}],
            "total": 25.99
        }
        
        # Act
        result = order_service.create_order(order_data)
        
        # Assert
        assert result.customer_id == 1
        assert result.total == 25.99
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_create_order_invalid_customer(self, order_service):
        # Arrange
        order_data = {"customer_id": -1, "items": []}
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid customer"):
            order_service.create_order(order_data)
```

#### Integration Test Example

```python
# modules/orders/tests/test_order_api.py
import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import Base, engine
from core.auth import create_access_token

class TestOrderAPI:
    @pytest.fixture(scope="class")
    def client(self):
        # Setup test database
        Base.metadata.create_all(bind=engine)
        
        with TestClient(app) as c:
            yield c
        
        # Cleanup
        Base.metadata.drop_all(bind=engine)
    
    @pytest.fixture
    def auth_headers(self):
        token = create_access_token({"sub": "test@example.com"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_create_order_endpoint(self, client, auth_headers):
        # Arrange
        order_data = {
            "customer_id": 1,
            "items": [
                {"menu_item_id": 1, "quantity": 2, "price": 12.99}
            ]
        }
        
        # Act
        response = client.post(
            "/api/v1/orders",
            json=order_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == 1
        assert len(data["items"]) == 1
        assert "id" in data
    
    @pytest.mark.parametrize("invalid_data,expected_error", [
        ({"customer_id": None}, "customer_id is required"),
        ({"items": []}, "items cannot be empty"),
        ({"items": [{"quantity": -1}]}, "quantity must be positive")
    ])
    def test_create_order_validation(self, client, auth_headers, invalid_data, expected_error):
        response = client.post(
            "/api/v1/orders",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert expected_error in response.json()["detail"][0]["msg"]
```

### Database Testing

```python
# conftest.py - Shared test fixtures
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.config import settings

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(settings.DATABASE_TEST_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_db(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    
    yield session
    
    session.rollback()
    session.close()

@pytest.fixture
def factory():
    """Factory for creating test data"""
    from tests.factories import Factory
    return Factory()
```

### Mocking External Services

```python
# Test with mocked external services
class TestPaymentService:
    @patch('stripe.Charge.create')
    def test_process_payment(self, mock_stripe):
        # Arrange
        mock_stripe.return_value = Mock(
            id="ch_test123",
            status="succeeded"
        )
        
        # Act
        result = PaymentService.process_payment(
            amount=2500,
            token="tok_test123"
        )
        
        # Assert
        assert result.charge_id == "ch_test123"
        assert result.status == "succeeded"
        mock_stripe.assert_called_once_with(
            amount=2500,
            currency="usd",
            source="tok_test123"
        )
```

## Frontend Testing

### Setup

```bash
# Install dependencies
cd frontend
npm install --save-dev @testing-library/react @testing-library/jest-dom
npm install --save-dev @testing-library/user-event jest-environment-jsdom

# Configure Jest
# jest.config.js
module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
```

### Running Frontend Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm test -- --watch

# Run specific test file
npm test OrderForm.test.tsx

# Update snapshots
npm test -- -u
```

### Writing Frontend Tests

#### Component Test Example

```typescript
// components/orders/OrderForm.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OrderForm } from './OrderForm';
import { OrderService } from '../../services/OrderService';

// Mock the service
jest.mock('../../services/OrderService');

describe('OrderForm', () => {
  const mockOnSubmit = jest.fn();
  
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  test('renders form fields correctly', () => {
    render(<OrderForm onSubmit={mockOnSubmit} />);
    
    expect(screen.getByLabelText('Customer')).toBeInTheDocument();
    expect(screen.getByLabelText('Items')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit Order' })).toBeInTheDocument();
  });
  
  test('validates required fields', async () => {
    const user = userEvent.setup();
    render(<OrderForm onSubmit={mockOnSubmit} />);
    
    // Try to submit empty form
    await user.click(screen.getByRole('button', { name: 'Submit Order' }));
    
    // Check for validation errors
    expect(screen.getByText('Customer is required')).toBeInTheDocument();
    expect(screen.getByText('At least one item is required')).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });
  
  test('submits form with valid data', async () => {
    const user = userEvent.setup();
    (OrderService.getCustomers as jest.Mock).mockResolvedValue([
      { id: 1, name: 'John Doe' }
    ]);
    
    render(<OrderForm onSubmit={mockOnSubmit} />);
    
    // Fill form
    await user.selectOptions(screen.getByLabelText('Customer'), '1');
    await user.click(screen.getByText('Add Item'));
    await user.type(screen.getByLabelText('Quantity'), '2');
    
    // Submit
    await user.click(screen.getByRole('button', { name: 'Submit Order' }));
    
    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        customer_id: 1,
        items: [{ menu_item_id: 1, quantity: 2 }]
      });
    });
  });
});
```

#### Hook Test Example

```typescript
// hooks/useAuth.test.tsx
import { renderHook, act } from '@testing-library/react';
import { useAuth } from './useAuth';
import { AuthService } from '../services/AuthService';

jest.mock('../services/AuthService');

describe('useAuth', () => {
  test('login success flow', async () => {
    const mockUser = { id: 1, email: 'test@example.com' };
    (AuthService.login as jest.Mock).mockResolvedValue({
      user: mockUser,
      token: 'test-token'
    });
    
    const { result } = renderHook(() => useAuth());
    
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    
    await act(async () => {
      await result.current.login('test@example.com', 'password');
    });
    
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
  });
  
  test('logout clears user data', () => {
    const { result } = renderHook(() => useAuth());
    
    act(() => {
      result.current.logout();
    });
    
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem('token')).toBeNull();
  });
});
```

### Snapshot Testing

```typescript
// components/MenuItem.test.tsx
import React from 'react';
import { render } from '@testing-library/react';
import { MenuItem } from './MenuItem';

describe('MenuItem', () => {
  test('matches snapshot', () => {
    const item = {
      id: 1,
      name: 'Burger',
      price: 12.99,
      description: 'Delicious burger'
    };
    
    const { container } = render(<MenuItem item={item} />);
    expect(container).toMatchSnapshot();
  });
});
```

## Mobile Testing

### React Native Testing

```bash
# Setup
cd mobile
npm install --save-dev @testing-library/react-native
npm install --save-dev jest @types/jest

# Run tests
npm test
npm test -- --coverage
```

#### Mobile Component Test

```typescript
// screens/OrderScreen.test.tsx
import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { OrderScreen } from './OrderScreen';
import { NavigationContainer } from '@react-navigation/native';

describe('OrderScreen', () => {
  const renderWithNavigation = (component: React.ReactElement) => {
    return render(
      <NavigationContainer>
        {component}
      </NavigationContainer>
    );
  };
  
  test('displays order list', async () => {
    const { getByText, getByTestId } = renderWithNavigation(<OrderScreen />);
    
    await waitFor(() => {
      expect(getByText('Order #1001')).toBeTruthy();
      expect(getByText('Order #1002')).toBeTruthy();
    });
  });
  
  test('navigates to order details on press', async () => {
    const { getByText } = renderWithNavigation(<OrderScreen />);
    
    const orderItem = await waitFor(() => getByText('Order #1001'));
    fireEvent.press(orderItem);
    
    // Verify navigation occurred
    await waitFor(() => {
      expect(getByText('Order Details')).toBeTruthy();
    });
  });
});
```

## Integration Testing

### API Integration Tests

```python
# tests/integration/test_order_workflow.py
import pytest
from datetime import datetime

class TestOrderWorkflow:
    """Test complete order workflow from creation to completion"""
    
    @pytest.mark.integration
    def test_complete_order_flow(self, client, auth_headers, test_db):
        # 1. Create customer
        customer_response = client.post(
            "/api/v1/customers",
            json={"name": "John Doe", "email": "john@example.com"},
            headers=auth_headers
        )
        customer_id = customer_response.json()["id"]
        
        # 2. Create order
        order_response = client.post(
            "/api/v1/orders",
            json={
                "customer_id": customer_id,
                "items": [{"menu_item_id": 1, "quantity": 2}]
            },
            headers=auth_headers
        )
        order_id = order_response.json()["id"]
        
        # 3. Process payment
        payment_response = client.post(
            f"/api/v1/orders/{order_id}/payment",
            json={
                "amount": 25.99,
                "payment_method": "card",
                "token": "tok_test123"
            },
            headers=auth_headers
        )
        assert payment_response.status_code == 200
        
        # 4. Update order status
        status_response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "completed"},
            headers=auth_headers
        )
        assert status_response.status_code == 200
        
        # 5. Verify final state
        order_response = client.get(
            f"/api/v1/orders/{order_id}",
            headers=auth_headers
        )
        order = order_response.json()
        assert order["status"] == "completed"
        assert order["payment_status"] == "paid"
```

### Database Integration Tests

```python
# tests/integration/test_inventory_deduction.py
@pytest.mark.integration
class TestInventoryDeduction:
    def test_inventory_deduction_on_order(self, test_db):
        # Setup: Create inventory items
        inventory = InventoryItem(
            name="Beef Patty",
            quantity=100,
            unit="pieces"
        )
        test_db.add(inventory)
        test_db.commit()
        
        # Create order with recipe
        order = Order(
            customer_id=1,
            items=[
                OrderItem(
                    menu_item_id=1,  # Burger
                    quantity=5
                )
            ]
        )
        test_db.add(order)
        test_db.commit()
        
        # Process inventory deduction
        InventoryService.deduct_for_order(order.id)
        
        # Verify inventory was reduced
        test_db.refresh(inventory)
        assert inventory.quantity == 95  # 5 burgers * 1 patty each
```

## Performance Testing

### Load Testing with Locust

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class RestaurantUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def view_menu(self):
        self.client.get("/api/v1/menu/items", headers=self.headers)
    
    @task(2)
    def view_orders(self):
        self.client.get("/api/v1/orders", headers=self.headers)
    
    @task(1)
    def create_order(self):
        self.client.post("/api/v1/orders", json={
            "customer_id": 1,
            "items": [{"menu_item_id": 1, "quantity": 1}]
        }, headers=self.headers)
```

### Running Performance Tests

```bash
# Install Locust
pip install locust

# Run load test
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Run with specific parameters
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless
```

### Database Query Performance

```python
# tests/performance/test_query_performance.py
import time
import pytest

class TestQueryPerformance:
    @pytest.mark.performance
    def test_order_list_performance(self, test_db):
        # Create test data
        for i in range(1000):
            order = Order(customer_id=1, total=100.00)
            test_db.add(order)
        test_db.commit()
        
        # Measure query time
        start_time = time.time()
        
        orders = test_db.query(Order)\
            .filter(Order.created_at >= datetime.now())\
            .order_by(Order.created_at.desc())\
            .limit(50)\
            .all()
        
        query_time = time.time() - start_time
        
        # Assert performance threshold
        assert query_time < 0.1  # Should complete in under 100ms
        assert len(orders) == 50
```

## Security Testing

### SQL Injection Testing

```python
# tests/security/test_sql_injection.py
class TestSQLInjection:
    @pytest.mark.security
    def test_sql_injection_prevention(self, client, auth_headers):
        # Attempt SQL injection
        malicious_input = "1'; DROP TABLE orders; --"
        
        response = client.get(
            f"/api/v1/orders?customer_id={malicious_input}",
            headers=auth_headers
        )
        
        # Should handle safely
        assert response.status_code in [200, 422]  # OK or validation error
        
        # Verify tables still exist
        response = client.get("/api/v1/orders", headers=auth_headers)
        assert response.status_code == 200
```

### Authentication Testing

```python
# tests/security/test_authentication.py
class TestAuthentication:
    def test_expired_token_rejected(self, client):
        # Create expired token
        expired_token = create_access_token(
            data={"sub": "test@example.com"},
            expires_delta=timedelta(minutes=-1)
        )
        
        response = client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert "Token expired" in response.json()["detail"]
    
    def test_invalid_token_rejected(self, client):
        response = client.get(
            "/api/v1/orders",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401
```

## Test Data Management

### Test Factories

```python
# tests/factories.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from modules.orders.models import Order, OrderItem

class OrderFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Order
        sqlalchemy_session_persistence = "commit"
    
    customer_id = factory.Sequence(lambda n: n)
    status = "pending"
    total = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    
    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            for item in extracted:
                self.items.append(item)

class OrderItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = OrderItem
    
    menu_item_id = factory.Sequence(lambda n: n)
    quantity = factory.Faker('random_int', min=1, max=5)
    price = factory.Faker('pydecimal', left_digits=2, right_digits=2, positive=True)
```

### Seed Data Scripts

```python
# scripts/seed_test_data.py
import click
from tests.factories import OrderFactory, CustomerFactory

@click.command()
@click.option('--orders', default=10, help='Number of orders to create')
@click.option('--customers', default=5, help='Number of customers to create')
def seed_test_data(orders, customers):
    """Seed test database with sample data"""
    
    # Create customers
    customer_list = []
    for _ in range(customers):
        customer = CustomerFactory()
        customer_list.append(customer)
    
    # Create orders
    for _ in range(orders):
        customer = random.choice(customer_list)
        OrderFactory(customer_id=customer.id)
    
    click.echo(f"Created {customers} customers and {orders} orders")

if __name__ == '__main__':
    seed_test_data()
```

## CI/CD Testing

### GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
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
        cd backend
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run migrations
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/auraconnect_test
      run: |
        cd backend
        alembic upgrade head
    
    - name: Run tests with coverage
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/auraconnect_test
        REDIS_URL: redis://localhost:6379/0
      run: |
        cd backend
        pytest --cov=modules --cov-report=xml --cov-report=html
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
  
  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    
    - name: Install dependencies
      run: |
        cd frontend
        npm ci
    
    - name: Run tests
      run: |
        cd frontend
        npm test -- --coverage --watchAll=false
    
    - name: Run linting
      run: |
        cd frontend
        npm run lint
```

## Testing Best Practices

### 1. Test Organization

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Multi-component tests
├── e2e/              # End-to-end scenarios
├── performance/      # Load and stress tests
├── security/         # Security-focused tests
├── fixtures/         # Shared test data
├── factories/        # Test data factories
└── conftest.py       # Shared pytest configuration
```

### 2. Test Naming Conventions

```python
# Use descriptive test names
def test_order_creation_with_valid_data_succeeds():
    pass

def test_order_creation_with_invalid_customer_raises_error():
    pass

def test_order_total_calculation_includes_tax_and_tips():
    pass
```

### 3. Test Independence

```python
# Bad - Tests depend on each other
class TestOrder:
    order_id = None
    
    def test_create_order(self):
        self.order_id = create_order()
    
    def test_update_order(self):
        update_order(self.order_id)  # Fails if first test fails

# Good - Independent tests
class TestOrder:
    def test_create_order(self):
        order_id = create_order()
        assert order_id is not None
    
    def test_update_order(self):
        order_id = create_order()  # Setup own data
        result = update_order(order_id)
        assert result.status == "updated"
```

### 4. Mock External Dependencies

```python
# Always mock external services in unit tests
@patch('requests.post')
def test_send_notification(mock_post):
    mock_post.return_value.status_code = 200
    
    result = NotificationService.send_sms("+1234567890", "Test message")
    
    assert result == True
    mock_post.assert_called_once()
```

### 5. Use Test Markers

```python
# Mark tests for easy filtering
@pytest.mark.slow
@pytest.mark.integration
def test_full_payroll_processing():
    # Long-running test
    pass

@pytest.mark.unit
@pytest.mark.fast
def test_calculate_tax():
    # Quick unit test
    pass

# Run only fast tests: pytest -m "fast"
# Skip slow tests: pytest -m "not slow"
```

### 6. Continuous Testing

```bash
# Watch mode for development
pytest-watch

# Pre-commit hooks
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

*For more testing resources, visit our [Developer Portal](https://docs.auraconnect.com/testing).*