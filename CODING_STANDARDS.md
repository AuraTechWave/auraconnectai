# AuraConnect AI Coding Standards

## Table of Contents
1. [General Principles](#general-principles)
2. [Python Standards](#python-standards)
3. [JavaScript/TypeScript Standards](#javascripttypescript-standards)
4. [Database Standards](#database-standards)
5. [API Standards](#api-standards)
6. [Testing Standards](#testing-standards)
7. [Documentation Standards](#documentation-standards)
8. [Version Control Standards](#version-control-standards)

## General Principles

### Core Values
- **Consistency**: Code should look like it was written by a single person
- **Readability**: Code is read more often than it's written
- **Simplicity**: Favor simple, clear solutions over clever ones
- **Maintainability**: Write code that's easy to modify and extend
- **Performance**: Optimize for readability first, performance when measured

## Python Standards

### Code Style
We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with the following specifications:

#### Naming Conventions
```python
# Classes: PascalCase
class UserProfile:
    pass

# Functions and variables: snake_case
def calculate_total_price(base_price: float, tax_rate: float) -> float:
    total_amount = base_price * (1 + tax_rate)
    return total_amount

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30

# Private methods/attributes: leading underscore
class Service:
    def _internal_method(self):
        pass
    
    def __init__(self):
        self._private_attribute = None

# Module-level private: leading underscore
_internal_helper = lambda x: x * 2
```

#### Import Organization
```python
# Standard library imports
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

# Third-party imports
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session

# Local application imports
from core.database import get_db
from modules.auth.models import User
from modules.auth.services import AuthService
```

#### Type Hints
Always use type hints for function signatures and class attributes:
```python
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

def process_order(
    order_id: int,
    items: List[Dict[str, Any]],
    customer_id: Optional[int] = None,
    discount: float = 0.0
) -> Dict[str, Union[float, str, datetime]]:
    """Process an order and return order details."""
    pass
```

### Async/Sync Patterns

#### When to Use Async
- I/O-bound operations (database queries, API calls, file operations)
- Operations that can benefit from concurrency
- WebSocket connections and real-time features

```python
# Async function for I/O operations
async def get_user_orders(user_id: int, db: Session) -> List[Order]:
    """Fetch user orders asynchronously."""
    query = select(Order).where(Order.user_id == user_id)
    result = await db.execute(query)
    return result.scalars().all()

# Sync function for CPU-bound operations
def calculate_order_total(items: List[OrderItem]) -> float:
    """Calculate order total synchronously."""
    return sum(item.price * item.quantity for item in items)
```

#### Async Best Practices
```python
# Good: Use async context managers
async with aiofiles.open('file.txt', 'r') as f:
    content = await f.read()

# Good: Batch async operations
results = await asyncio.gather(
    fetch_user(user_id),
    fetch_orders(user_id),
    fetch_preferences(user_id)
)

# Bad: Blocking calls in async functions
async def bad_example():
    time.sleep(1)  # Don't use blocking sleep
    requests.get(url)  # Don't use blocking HTTP calls
```

### Error Handling

#### Standard Error Handling Pattern
```python
from typing import Optional, Union
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    """Base exception for service layer."""
    pass

class NotFoundError(ServiceError):
    """Resource not found."""
    pass

class ValidationError(ServiceError):
    """Validation error."""
    pass

def get_user_by_id(user_id: int, db: Session) -> Optional[User]:
    """
    Fetch user by ID with proper error handling.
    
    Raises:
        NotFoundError: If user not found
        ServiceError: For other database errors
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise NotFoundError(f"User with ID {user_id} not found")
        return user
    except NotFoundError:
        raise  # Re-raise our custom exceptions
    except Exception as e:
        logger.error(f"Database error fetching user {user_id}: {str(e)}")
        raise ServiceError(f"Failed to fetch user: {str(e)}")

# In API endpoints
@router.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    try:
        return get_user_by_id(user_id, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Logging Standards

#### Logging Levels
```python
import logging
from typing import Any

logger = logging.getLogger(__name__)

# DEBUG: Detailed diagnostic information
logger.debug(f"Processing item: {item_id} with options: {options}")

# INFO: General informational messages
logger.info(f"Order {order_id} processed successfully")

# WARNING: Warning messages for potentially harmful situations
logger.warning(f"Retry attempt {attempt}/{max_attempts} for order {order_id}")

# ERROR: Error messages for failures that should be investigated
logger.error(f"Failed to process payment for order {order_id}: {error}")

# CRITICAL: Critical issues that require immediate attention
logger.critical(f"Database connection lost: {connection_string}")
```

#### Structured Logging
```python
# Use structured logging for better searchability
logger.info(
    "Order processed",
    extra={
        "order_id": order_id,
        "customer_id": customer_id,
        "total": total_amount,
        "processing_time": processing_time
    }
)
```

## JavaScript/TypeScript Standards

### TypeScript Configuration
```typescript
// Use strict TypeScript settings
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "esModuleInterop": true
  }
}
```

### Naming Conventions
```typescript
// Interfaces: PascalCase with 'I' prefix (optional, but be consistent)
interface IUserProfile {
  id: number;
  email: string;
}

// Types: PascalCase
type OrderStatus = 'pending' | 'completed' | 'cancelled';

// Classes: PascalCase
class OrderService {
  // Private members: underscore prefix
  private _apiClient: ApiClient;
  
  // Methods: camelCase
  async fetchOrders(userId: number): Promise<Order[]> {
    return this._apiClient.get(`/users/${userId}/orders`);
  }
}

// Functions and variables: camelCase
const calculateTotalPrice = (items: OrderItem[]): number => {
  return items.reduce((sum, item) => sum + item.price, 0);
};

// Constants: UPPER_SNAKE_CASE
const MAX_RETRY_ATTEMPTS = 3;
const API_BASE_URL = 'https://api.auraconnect.ai';

// React components: PascalCase
const UserDashboard: React.FC<Props> = ({ user }) => {
  // Hooks: use prefix
  const [isLoading, setIsLoading] = useState(false);
  const userData = useUserData(user.id);
  
  return <div>{/* component JSX */}</div>;
};
```

### React Best Practices
```tsx
// Functional components with TypeScript
interface UserCardProps {
  user: User;
  onSelect?: (user: User) => void;
  className?: string;
}

export const UserCard: React.FC<UserCardProps> = ({ 
  user, 
  onSelect, 
  className = '' 
}) => {
  // Use early returns for conditional rendering
  if (!user) {
    return <EmptyState message="No user data" />;
  }
  
  // Extract complex logic into functions
  const handleClick = useCallback(() => {
    onSelect?.(user);
  }, [user, onSelect]);
  
  return (
    <div className={`user-card ${className}`} onClick={handleClick}>
      {/* component content */}
    </div>
  );
};
```

## Database Standards

### SQL Query Formatting
```sql
-- Use uppercase for SQL keywords
SELECT 
    u.id,
    u.email,
    u.created_at,
    COUNT(o.id) AS order_count
FROM 
    users u
    LEFT JOIN orders o ON u.id = o.user_id
WHERE 
    u.is_active = TRUE
    AND u.created_at >= '2024-01-01'
GROUP BY 
    u.id, u.email, u.created_at
HAVING 
    COUNT(o.id) > 0
ORDER BY 
    order_count DESC
LIMIT 100;
```

### SQLAlchemy ORM Standards
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    # Primary keys first
    id = Column(Integer, primary_key=True, index=True)
    
    # Required fields
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False)
    
    # Optional fields
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes and constraints defined explicitly
    __table_args__ = (
        Index('idx_users_email_active', 'email', 'is_active'),
        CheckConstraint('char_length(email) >= 3', name='check_email_length'),
    )
```

### Database Migration Standards
```python
"""Add user preferences table

Revision ID: abc123
Revises: def456
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'abc123'
down_revision = 'def456'

def upgrade():
    """Apply migration."""
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('theme', sa.String(50), default='light'),
        sa.Column('notifications_enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # Create indexes after table creation
    op.create_index('idx_user_preferences_user_id', 'user_preferences', ['user_id'])

def downgrade():
    """Revert migration."""
    op.drop_index('idx_user_preferences_user_id', 'user_preferences')
    op.drop_table('user_preferences')
```

## API Standards

### RESTful Endpoint Naming
```python
# Use plural nouns for collections
GET    /api/v1/users           # List users
POST   /api/v1/users           # Create user
GET    /api/v1/users/{id}      # Get specific user
PUT    /api/v1/users/{id}      # Update user
DELETE /api/v1/users/{id}      # Delete user

# Use sub-resources for relationships
GET    /api/v1/users/{id}/orders    # Get user's orders
POST   /api/v1/orders/{id}/items    # Add item to order

# Use query parameters for filtering
GET    /api/v1/orders?status=pending&limit=10&offset=0
```

### Request/Response Models
```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

# Request models
class UserCreateRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=100)

# Response models
class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True  # Enable ORM model compatibility

# Pagination response
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool
```

### API Error Responses
```python
from fastapi import HTTPException
from typing import Dict, Any

class APIError(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Standard error responses
ERROR_RESPONSES = {
    400: {"description": "Bad Request", "model": APIError},
    401: {"description": "Unauthorized", "model": APIError},
    403: {"description": "Forbidden", "model": APIError},
    404: {"description": "Not Found", "model": APIError},
    422: {"description": "Validation Error", "model": APIError},
    500: {"description": "Internal Server Error", "model": APIError},
}
```

## Testing Standards

### Test Organization
```
tests/
├── unit/                  # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/          # Integration tests
│   ├── test_api.py
│   ├── test_database.py
│   └── test_cache.py
├── e2e/                  # End-to-end tests
│   └── test_workflows.py
├── fixtures/             # Test fixtures
│   └── users.py
└── conftest.py          # Pytest configuration
```

### Test Naming and Structure
```python
import pytest
from unittest.mock import Mock, patch
from typing import Generator

class TestUserService:
    """Test cases for UserService."""
    
    @pytest.fixture
    def mock_db(self) -> Generator[Mock, None, None]:
        """Provide mock database session."""
        with patch('modules.users.services.get_db') as mock:
            yield mock.return_value
    
    def test_create_user_success(self, mock_db):
        """Test successful user creation."""
        # Arrange
        user_data = {"email": "test@example.com", "username": "testuser"}
        expected_user = User(**user_data, id=1)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        # Act
        result = UserService.create_user(user_data, mock_db)
        
        # Assert
        assert result.email == user_data["email"]
        assert result.username == user_data["username"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_user_duplicate_email(self, mock_db):
        """Test user creation with duplicate email."""
        # Arrange
        user_data = {"email": "existing@example.com", "username": "newuser"}
        mock_db.add.side_effect = IntegrityError("Duplicate email", None, None)
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserService.create_user(user_data, mock_db)
        
        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    @pytest.mark.parametrize("invalid_email", [
        "notanemail",
        "@example.com",
        "user@",
        "user @example.com"
    ])
    def test_create_user_invalid_email(self, invalid_email, mock_db):
        """Test user creation with invalid email formats."""
        user_data = {"email": invalid_email, "username": "testuser"}
        
        with pytest.raises(ValidationError) as exc_info:
            UserService.create_user(user_data, mock_db)
        
        assert "Invalid email" in str(exc_info.value)
```

### Test Coverage Requirements
- Minimum 80% code coverage for new code
- Critical paths must have 100% coverage
- Include edge cases and error conditions
- Test both success and failure scenarios

## Documentation Standards

### Docstring Format (Google Style)
```python
def calculate_discount(
    base_price: float,
    discount_percentage: float,
    max_discount: Optional[float] = None
) -> float:
    """
    Calculate the discounted price based on percentage.
    
    Args:
        base_price: The original price before discount.
        discount_percentage: The discount percentage (0-100).
        max_discount: Optional maximum discount amount allowed.
    
    Returns:
        The final price after applying the discount.
    
    Raises:
        ValueError: If discount_percentage is not between 0 and 100.
        ValueError: If base_price is negative.
    
    Example:
        >>> calculate_discount(100.0, 20.0)
        80.0
        >>> calculate_discount(100.0, 50.0, max_discount=30.0)
        70.0
    """
    if base_price < 0:
        raise ValueError("Base price cannot be negative")
    if not 0 <= discount_percentage <= 100:
        raise ValueError("Discount percentage must be between 0 and 100")
    
    discount = base_price * (discount_percentage / 100)
    if max_discount is not None:
        discount = min(discount, max_discount)
    
    return base_price - discount
```

### API Documentation
```python
from fastapi import APIRouter, Depends, Query
from typing import List

router = APIRouter()

@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users",
    description="Retrieve a paginated list of users with optional filtering",
    response_description="List of users matching the criteria",
    responses=ERROR_RESPONSES
)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name and email"),
    db: Session = Depends(get_db)
) -> List[UserResponse]:
    """
    Retrieve users with pagination and filtering.
    
    This endpoint supports:
    - Pagination via skip/limit parameters
    - Filtering by active status
    - Text search in name and email fields
    """
    return UserService.list_users(db, skip, limit, is_active, search)
```

## Version Control Standards

### Branch Naming
```bash
# Feature branches
feature/AUR-123-add-user-authentication

# Bug fix branches
fix/AUR-456-fix-payment-calculation

# Hotfix branches (production fixes)
hotfix/AUR-789-critical-security-patch

# Release branches
release/v1.2.0
```

### Commit Message Format
```bash
# Format: <type>(<scope>): <subject>
#
# Types:
# - feat: New feature
# - fix: Bug fix
# - docs: Documentation changes
# - style: Code style changes (formatting, etc.)
# - refactor: Code refactoring
# - test: Test additions or fixes
# - chore: Build process or auxiliary tool changes

# Examples:
feat(auth): Add JWT token refresh endpoint
fix(orders): Correct tax calculation for international orders
docs(api): Update REST API documentation for v2
refactor(database): Optimize user query performance
test(payments): Add unit tests for payment service
```

### Pull Request Guidelines
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
```

## Code Review Checklist

### Functionality
- [ ] Code accomplishes the intended goal
- [ ] Edge cases are handled
- [ ] Error handling is appropriate
- [ ] No obvious bugs

### Code Quality
- [ ] Follows naming conventions
- [ ] No code duplication
- [ ] Functions are focused and single-purpose
- [ ] Complex logic is well-commented
- [ ] No commented-out code

### Performance
- [ ] No unnecessary database queries
- [ ] Efficient algorithms used
- [ ] Proper use of caching where appropriate
- [ ] No memory leaks

### Security
- [ ] Input validation is proper
- [ ] No SQL injection vulnerabilities
- [ ] Sensitive data is not logged
- [ ] Authentication/authorization checks in place

### Testing
- [ ] Adequate test coverage
- [ ] Tests are meaningful
- [ ] Edge cases are tested
- [ ] Mocks are used appropriately

### Documentation
- [ ] Functions have docstrings
- [ ] Complex logic is explained
- [ ] API changes are documented
- [ ] README updated if needed

## Enforcement

These standards are enforced through:

1. **Automated Tools**:
   - `ruff` for Python linting
   - `black` for Python formatting
   - `isort` for import sorting
   - `mypy` for type checking
   - `eslint` for JavaScript/TypeScript
   - `prettier` for JS/TS formatting

2. **Pre-commit Hooks**:
   - Automatically run formatters and linters
   - Prevent commits that violate standards
   - Run tests for modified code

3. **CI/CD Pipeline**:
   - Run full test suite
   - Check code coverage
   - Perform security scanning
   - Validate documentation

4. **Code Reviews**:
   - Peer review for all changes
   - Use the code review checklist
   - Require approval before merging

## Adoption Timeline

1. **Phase 1** (Immediate): 
   - Apply to all new code
   - Configure tools and hooks

2. **Phase 2** (1-2 weeks):
   - Update critical modules
   - Fix high-priority violations

3. **Phase 3** (1 month):
   - Complete codebase migration
   - All code meets standards

## Questions and Updates

For questions about these standards or to propose changes:
1. Open a discussion in the team channel
2. Create a pull request with proposed changes
3. Get team consensus before updating

Last Updated: 2025-01-15
Version: 1.0.0