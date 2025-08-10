# Contributing to AuraConnect

**Version: 1.0.0** | Last Updated: January 2025

Thank you for your interest in contributing to AuraConnect! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Testing Requirements](#testing-requirements)
8. [Documentation Standards](#documentation-standards)
9. [Issue Guidelines](#issue-guidelines)
10. [Community](#community)

## Code of Conduct

### Our Pledge

We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Expected Behavior

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/auraconnectai.git
   cd auraconnectai
   ```

3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/AuraTechWave/auraconnectai.git
   ```

4. Set up your development environment:
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   
   # Frontend
   cd ../frontend
   npm install
   ```

### Development Setup

1. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

2. Create a branch for your work:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/AUR-XXX-brief-description
   ```

## Development Workflow

### 1. Branch Naming Convention

Use descriptive branch names following this pattern:
- `feature/AUR-XXX-feature-name` - New features
- `fix/AUR-XXX-bug-description` - Bug fixes
- `docs/AUR-XXX-what-changed` - Documentation updates
- `refactor/AUR-XXX-what-changed` - Code refactoring
- `test/AUR-XXX-what-tests` - Test additions/changes
- `chore/AUR-XXX-what-task` - Maintenance tasks

Where `AUR-XXX` is the Linear issue number.

### 2. Development Process

1. **Always work on a fresh branch**:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/AUR-XXX-new-feature
   ```

2. **Keep your branch updated**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

3. **Make atomic commits** - Each commit should represent one logical change

4. **Write tests** - All new features must include tests

5. **Update documentation** - Keep docs in sync with code changes

## Coding Standards

### Python (Backend)

We follow PEP 8 with some modifications:

```python
# Good example
from typing import List, Optional
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from modules.orders.models import Order
from modules.orders.schemas import OrderCreate, OrderResponse


class OrderService:
    """Service class for order operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_order(
        self,
        order_data: OrderCreate,
        user_id: int
    ) -> OrderResponse:
        """
        Create a new order.
        
        Args:
            order_data: Order creation data
            user_id: ID of the user creating the order
            
        Returns:
            Created order response
            
        Raises:
            HTTPException: If order creation fails
        """
        try:
            order = Order(
                user_id=user_id,
                **order_data.dict()
            )
            self.db.add(order)
            self.db.commit()
            self.db.refresh(order)
            
            return OrderResponse.from_orm(order)
            
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create order: {str(e)}"
            )
```

#### Python Style Rules

1. **Line length**: 88 characters (Black default)
2. **Imports**: Group in order - stdlib, third-party, local
3. **Type hints**: Required for all function signatures
4. **Docstrings**: Google style for all public functions/classes
5. **Error handling**: Always use specific exceptions
6. **Async/await**: Prefer async for I/O operations

### TypeScript/JavaScript (Frontend)

We use ESLint and Prettier for consistent formatting:

```typescript
// Good example
import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

import { OrderService } from '@/services/OrderService';
import { OrderList } from '@/components/orders/OrderList';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

interface OrdersPageProps {
  restaurantId: number;
}

export const OrdersPage: React.FC<OrdersPageProps> = ({ restaurantId }) => {
  const [filter, setFilter] = useState<string>('all');
  
  const {
    data: orders,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['orders', restaurantId, filter],
    queryFn: () => OrderService.getOrders(restaurantId, filter),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
  
  useEffect(() => {
    // Set up WebSocket connection for real-time updates
    const ws = OrderService.connectWebSocket(restaurantId);
    
    ws.on('orderUpdate', () => {
      refetch();
    });
    
    return () => {
      ws.disconnect();
    };
  }, [restaurantId, refetch]);
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  
  return (
    <div className="orders-page">
      <h1>Orders</h1>
      <OrderList 
        orders={orders}
        onFilterChange={setFilter}
        currentFilter={filter}
      />
    </div>
  );
};
```

#### Frontend Style Rules

1. **Components**: Functional components with TypeScript
2. **State management**: React hooks, Context, or Zustand
3. **Styling**: CSS modules or styled-components
4. **File naming**: PascalCase for components, camelCase for utilities
5. **Props**: Always define interfaces for component props
6. **Error boundaries**: Wrap major sections

### SQL and Database

```sql
-- Good example
-- Create index for frequently queried columns
CREATE INDEX idx_orders_restaurant_status_created 
ON orders(restaurant_id, status, created_at DESC)
WHERE deleted_at IS NULL;

-- Use meaningful names and comments
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
    special_instructions TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure no duplicate items in same order
    UNIQUE(order_id, menu_item_id)
);

-- Add table comment
COMMENT ON TABLE order_items IS 'Individual items within customer orders';
```

## Commit Guidelines

We follow the Conventional Commits specification:

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **test**: Test additions or changes
- **chore**: Maintenance tasks
- **perf**: Performance improvements

### Examples

```bash
# Feature
git commit -m "feat(orders): add bulk order export functionality

- Add CSV export for order reports
- Include filters for date range and status
- Add progress indicator for large exports

Closes AUR-123"

# Bug fix
git commit -m "fix(auth): resolve token refresh race condition

Multiple simultaneous requests were causing token refresh failures.
Implemented mutex to ensure single refresh operation.

Fixes AUR-456"

# Documentation
git commit -m "docs(api): update order endpoint documentation

- Add missing response examples
- Clarify required permissions
- Update rate limit information"
```

### Commit Best Practices

1. **Atomic commits**: One logical change per commit
2. **Present tense**: "add feature" not "added feature"
3. **Line length**: 50 chars for subject, 72 for body
4. **Reference issues**: Include issue numbers
5. **Explain why**: Body should explain the reasoning

## Pull Request Process

### 1. Before Creating a PR

- [ ] All tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] Commits are clean and well-described
- [ ] Branch is up to date with main

### 2. PR Template

```markdown
## Description
Brief description of changes and why they're needed.

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #(issue number)

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] My code follows the project style guidelines
- [ ] I have performed a self-review
- [ ] I have added tests that prove my fix/feature works
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
```

### 3. PR Review Process

1. **Automated checks** must pass:
   - CI/CD pipeline
   - Code coverage maintained
   - Linting passes

2. **Code review** requirements:
   - At least 1 approval for minor changes
   - 2 approvals for major features
   - Core team approval for breaking changes

3. **Review checklist**:
   - [ ] Code quality and style
   - [ ] Test coverage
   - [ ] Performance impact
   - [ ] Security considerations
   - [ ] Documentation completeness

### 4. Merging

- PRs are merged using "Squash and merge"
- Delete branch after merge
- Ensure Linear issue is updated

## Testing Requirements

### Minimum Test Coverage

- **New features**: 90% coverage required
- **Bug fixes**: Include regression tests
- **Overall project**: Maintain 80% coverage

### Test Types Required

1. **Unit tests** for all business logic
2. **Integration tests** for API endpoints
3. **E2E tests** for critical user flows

### Example Test Structure

```python
# test_order_service.py
import pytest
from unittest.mock import Mock, patch

from modules.orders.services import OrderService
from modules.orders.exceptions import InsufficientStockError


class TestOrderService:
    """Test cases for OrderService."""
    
    @pytest.fixture
    def order_service(self, db_session):
        """Create OrderService instance with test database."""
        return OrderService(db_session)
    
    @pytest.fixture
    def sample_order_data(self):
        """Sample order data for testing."""
        return {
            "customer_id": 1,
            "items": [
                {"menu_item_id": 1, "quantity": 2},
                {"menu_item_id": 2, "quantity": 1}
            ]
        }
    
    def test_create_order_success(
        self,
        order_service,
        sample_order_data,
        mock_inventory_service
    ):
        """Test successful order creation."""
        # Arrange
        mock_inventory_service.check_availability.return_value = True
        
        # Act
        order = order_service.create_order(sample_order_data)
        
        # Assert
        assert order.id is not None
        assert order.status == "pending"
        assert len(order.items) == 2
        mock_inventory_service.reserve_items.assert_called_once()
    
    def test_create_order_insufficient_stock(
        self,
        order_service,
        sample_order_data,
        mock_inventory_service
    ):
        """Test order creation fails with insufficient stock."""
        # Arrange
        mock_inventory_service.check_availability.return_value = False
        
        # Act & Assert
        with pytest.raises(InsufficientStockError):
            order_service.create_order(sample_order_data)
```

## Documentation Standards

### Code Documentation

1. **Module level**: Describe purpose and main exports
2. **Class level**: Explain responsibility and usage
3. **Function level**: Document parameters, returns, and exceptions
4. **Complex logic**: Add inline comments

### API Documentation

```python
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

router = APIRouter()

@router.get(
    "/orders",
    response_model=List[OrderResponse],
    summary="List orders",
    description="""
    Retrieve a paginated list of orders with optional filters.
    
    **Permissions required**: `orders.view`
    
    **Rate limit**: 100 requests per minute
    """,
    responses={
        200: {
            "description": "List of orders",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "customer_id": 123,
                            "total": 45.99,
                            "status": "completed"
                        }
                    ]
                }
            }
        },
        403: {"description": "Insufficient permissions"}
    }
)
async def list_orders(
    restaurant_id: int = Query(..., description="Restaurant ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, le=100, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: User = Depends(get_current_user)
):
    """List orders with pagination and filters."""
    pass
```

### README Updates

Always update relevant README files when:
- Adding new features
- Changing setup procedures
- Modifying API endpoints
- Adding dependencies

## Issue Guidelines

### Creating Issues

Use issue templates for:
- Bug reports
- Feature requests
- Documentation improvements

### Issue Template Example

```markdown
## Bug Report

### Description
Clear description of the bug

### Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Environment
- OS: [e.g., Ubuntu 20.04]
- Browser: [e.g., Chrome 91]
- Version: [e.g., 1.2.3]

### Screenshots
If applicable

### Additional Context
Any other relevant information
```

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature request
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed
- `priority:high`: High priority
- `priority:medium`: Medium priority
- `priority:low`: Low priority

## Community

### Communication Channels

- **GitHub Discussions**: General discussions and questions
- **Discord**: Real-time chat and support
- **Linear**: Project management and issue tracking

### Getting Help

1. Check existing documentation
2. Search closed issues
3. Ask in Discord #help channel
4. Create a detailed issue

### Recognition

Contributors are recognized in:
- Release notes
- Contributors page
- Annual contributor spotlight

---

**Thank you for contributing to AuraConnect! Your efforts help make restaurant management better for everyone.**
