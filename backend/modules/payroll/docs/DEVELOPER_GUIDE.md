# Payroll Module Developer Guide

This guide provides developers with comprehensive information for working with and extending the AuraConnect Payroll Module.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Core Components](#core-components)
4. [API Development](#api-development)
5. [Service Layer](#service-layer)
6. [Data Models](#data-models)
7. [Testing](#testing)
8. [Code Examples](#code-examples)
9. [Best Practices](#best-practices)
10. [Contributing](#contributing)

## Architecture Overview

The Payroll Module follows a layered architecture pattern:

```
┌─────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                    │
├─────────────────────────────────────────────────────────┤
│                   Service Layer                          │
├─────────────────────────────────────────────────────────┤
│                   Data Access Layer                      │
├─────────────────────────────────────────────────────────┤
│                   Database (PostgreSQL)                  │
└─────────────────────────────────────────────────────────┘
```

### Key Design Patterns

- **Repository Pattern**: Data access abstraction
- **Service Pattern**: Business logic encapsulation
- **Factory Pattern**: Object creation
- **Strategy Pattern**: Tax calculation algorithms
- **Observer Pattern**: Event publishing

## Development Setup

### Prerequisites

```bash
# Install Python 3.10+
python --version  # Should show 3.10 or higher

# Install PostgreSQL
psql --version  # Should show 15.0 or higher

# Install Redis
redis-cli --version  # Should show 7.0 or higher
```

### Local Environment Setup

1. **Clone the repository**
```bash
git clone https://github.com/auraconnect/backend.git
cd backend/modules/payroll
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your local settings
```

5. **Set up database**
```bash
# Create database
createdb payroll_dev

# Run migrations
alembic upgrade head

# Seed test data
python scripts/seed_development_data.py
```

6. **Run the application**
```bash
uvicorn backend.modules.payroll.main:app --reload --port 8001
```

### Docker Development

```bash
# Build and run with Docker Compose
docker-compose -f docker-compose.dev.yml up

# Run tests in Docker
docker-compose -f docker-compose.dev.yml run --rm payroll-api pytest
```

## Core Components

### Project Structure

```
backend/modules/payroll/
├── __init__.py
├── main.py                 # FastAPI application
├── config/
│   ├── __init__.py
│   └── settings.py        # Configuration management
├── api/
│   ├── __init__.py
│   ├── routes/            # API endpoints
│   ├── dependencies.py    # Dependency injection
│   └── middleware.py      # Custom middleware
├── models/
│   ├── __init__.py
│   ├── employee_payment.py
│   ├── payroll_configuration.py
│   └── ...
├── schemas/
│   ├── __init__.py
│   ├── payment_schemas.py
│   ├── configuration_schemas.py
│   └── ...
├── services/
│   ├── __init__.py
│   ├── payroll_service.py
│   ├── tax_service.py
│   └── ...
├── repositories/
│   ├── __init__.py
│   ├── payment_repository.py
│   └── ...
├── tasks/
│   ├── __init__.py
│   ├── celery_app.py
│   └── payroll_tasks.py
├── utils/
│   ├── __init__.py
│   ├── calculations.py
│   └── validators.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── ...
```

### Configuration Management

```python
# backend/modules/payroll/config/settings.py

from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "AuraConnect Payroll"
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(5, env="DATABASE_POOL_SIZE")
    
    # Redis
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expiration_delta: int = 3600  # seconds
    
    # External Services
    tax_service_url: Optional[str] = Field(None, env="TAX_SERVICE_URL")
    staff_service_url: Optional[str] = Field(None, env="STAFF_SERVICE_URL")
    
    # Features
    enable_async_processing: bool = Field(True, env="ENABLE_ASYNC")
    batch_size: int = Field(100, env="BATCH_SIZE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton instance
settings = Settings()
```

## API Development

### Creating New Endpoints

1. **Define Schema**

```python
# backend/modules/payroll/schemas/bonus_schemas.py

from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import date
from typing import Optional, List

class BonusRequest(BaseModel):
    """Request schema for bonus payment."""
    
    employee_id: int = Field(..., description="Employee ID")
    amount: Decimal = Field(..., gt=0, description="Bonus amount")
    bonus_type: str = Field(..., description="Type of bonus")
    tax_treatment: str = Field("supplemental", description="Tax treatment")
    pay_date: Optional[date] = Field(None, description="Payment date")
    description: Optional[str] = Field(None, max_length=200)
    
    @validator('bonus_type')
    def validate_bonus_type(cls, v):
        allowed_types = ["performance", "signing", "retention", "holiday", "other"]
        if v not in allowed_types:
            raise ValueError(f"Bonus type must be one of: {allowed_types}")
        return v
    
    @validator('tax_treatment')
    def validate_tax_treatment(cls, v):
        allowed = ["regular", "supplemental"]
        if v not in allowed:
            raise ValueError(f"Tax treatment must be one of: {allowed}")
        return v
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }

class BonusResponse(BaseModel):
    """Response schema for bonus payment."""
    
    bonus_id: str
    employee_id: int
    gross_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    payment_status: str
    payment_date: date
    
    class Config:
        orm_mode = True
```

2. **Create Route**

```python
# backend/modules/payroll/api/routes/bonus_routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ...schemas.bonus_schemas import BonusRequest, BonusResponse
from ...services.bonus_service import BonusService
from ...dependencies import get_db, get_current_user, require_permission
from ...models.user import User

router = APIRouter(prefix="/bonuses", tags=["bonuses"])

@router.post("/", response_model=BonusResponse)
async def create_bonus_payment(
    bonus_request: BonusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("payroll:write"))
):
    """Process a bonus payment for an employee."""
    try:
        bonus_service = BonusService(db)
        result = await bonus_service.process_bonus(
            bonus_request=bonus_request,
            processed_by=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bonus payment"
        )

@router.get("/employee/{employee_id}", response_model=List[BonusResponse])
async def get_employee_bonuses(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("payroll:read"))
):
    """Get all bonuses for an employee."""
    bonus_service = BonusService(db)
    return await bonus_service.get_employee_bonuses(employee_id)
```

3. **Implement Service**

```python
# backend/modules/payroll/services/bonus_service.py

from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.bonus_payment import BonusPayment
from ..schemas.bonus_schemas import BonusRequest, BonusResponse
from .tax_calculation_service import TaxCalculationService
from ..repositories.bonus_repository import BonusRepository

class BonusService:
    """Service for handling bonus payments."""
    
    def __init__(self, db: Session):
        self.db = db
        self.bonus_repo = BonusRepository(db)
        self.tax_service = TaxCalculationService(db)
    
    async def process_bonus(
        self, 
        bonus_request: BonusRequest,
        processed_by: int
    ) -> BonusResponse:
        """Process a bonus payment."""
        
        # Calculate taxes
        tax_result = await self.tax_service.calculate_bonus_tax(
            employee_id=bonus_request.employee_id,
            bonus_amount=bonus_request.amount,
            tax_treatment=bonus_request.tax_treatment
        )
        
        # Create bonus payment record
        bonus_payment = BonusPayment(
            employee_id=bonus_request.employee_id,
            gross_amount=bonus_request.amount,
            federal_tax=tax_result.federal_tax,
            state_tax=tax_result.state_tax,
            social_security=tax_result.social_security,
            medicare=tax_result.medicare,
            net_amount=tax_result.net_amount,
            bonus_type=bonus_request.bonus_type,
            description=bonus_request.description,
            pay_date=bonus_request.pay_date or date.today(),
            processed_by=processed_by
        )
        
        # Save to database
        saved_bonus = await self.bonus_repo.create(bonus_payment)
        
        # Queue for payment processing
        await self._queue_payment(saved_bonus)
        
        return BonusResponse.from_orm(saved_bonus)
    
    async def get_employee_bonuses(
        self, 
        employee_id: int
    ) -> List[BonusResponse]:
        """Get all bonuses for an employee."""
        bonuses = await self.bonus_repo.find_by_employee(employee_id)
        return [BonusResponse.from_orm(b) for b in bonuses]
    
    async def _queue_payment(self, bonus: BonusPayment):
        """Queue bonus for payment processing."""
        from ..tasks.payment_tasks import process_payment_task
        process_payment_task.delay(
            payment_type="bonus",
            payment_id=str(bonus.id)
        )
```

### Dependency Injection

```python
# backend/modules/payroll/dependencies.py

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from .database import SessionLocal
from .config.settings import settings
from .models.user import User

# Security
security = HTTPBearer()

def get_db() -> Generator:
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

def require_permission(permission: str):
    """Require specific permission."""
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ):
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
    return permission_checker

# Service dependencies
def get_payroll_service(db: Session = Depends(get_db)):
    """Get payroll service instance."""
    from .services.payroll_service import PayrollService
    return PayrollService(db)

def get_tax_service(db: Session = Depends(get_db)):
    """Get tax service instance."""
    from .services.tax_calculation_service import TaxCalculationService
    return TaxCalculationService(db)
```

### Middleware

```python
# backend/modules/payroll/middleware.py

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .utils.metrics import request_duration_histogram

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {response.status_code} in {duration:.3f}s",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration": duration
            }
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(duration)
        
        # Record metrics
        request_duration_histogram.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).observe(duration)
        
        return response

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.exception(
                f"Unhandled exception: {str(e)}",
                extra={"path": request.url.path}
            )
            return Response(
                content=json.dumps({
                    "error": {
                        "message": "Internal server error",
                        "type": "INTERNAL_ERROR",
                        "request_id": request.headers.get("X-Request-ID")
                    }
                }),
                status_code=500,
                media_type="application/json"
            )
```

## Service Layer

### Service Pattern Implementation

```python
# backend/modules/payroll/services/base_service.py

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseService(ABC, Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base service class with common CRUD operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    @property
    @abstractmethod
    def model(self) -> type[ModelType]:
        """Return the model class."""
        pass
    
    async def create(self, schema: CreateSchemaType) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**schema.dict())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    async def get(self, id: int) -> Optional[ModelType]:
        """Get a record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    async def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records."""
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    async def update(
        self, 
        id: int, 
        schema: UpdateSchemaType
    ) -> Optional[ModelType]:
        """Update a record."""
        db_obj = await self.get(id)
        if not db_obj:
            return None
        
        update_data = schema.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: int) -> bool:
        """Delete a record."""
        db_obj = await self.get(id)
        if not db_obj:
            return False
        
        self.db.delete(db_obj)
        self.db.commit()
        return True
```

### Complex Service Example

```python
# backend/modules/payroll/services/payroll_calculation_service.py

from typing import Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
import logging

from ..models import EmployeePayment, PayrollConfiguration, Employee
from ..schemas import PayrollCalculationRequest, PayrollCalculationResponse
from ..utils.calculations import (
    calculate_regular_pay,
    calculate_overtime_pay,
    calculate_gross_pay,
    calculate_net_pay
)
from ..exceptions import (
    PayrollCalculationError,
    EmployeeNotFoundError,
    ConfigurationError
)

logger = logging.getLogger(__name__)

class PayrollCalculationService:
    """Service for complex payroll calculations."""
    
    def __init__(self, db: Session):
        self.db = db
        self._config_cache = {}
    
    async def calculate_payroll(
        self,
        request: PayrollCalculationRequest
    ) -> PayrollCalculationResponse:
        """Calculate complete payroll for an employee."""
        
        try:
            # Get employee data
            employee = await self._get_employee(request.employee_id)
            
            # Get configurations
            config = await self._get_payroll_config(
                employee.location,
                request.pay_period_end
            )
            
            # Calculate earnings
            earnings = await self._calculate_earnings(
                employee=employee,
                hours=request.hours_worked,
                config=config
            )
            
            # Calculate deductions
            deductions = await self._calculate_deductions(
                employee=employee,
                gross_pay=earnings.gross_pay,
                config=config
            )
            
            # Calculate taxes
            taxes = await self._calculate_taxes(
                employee=employee,
                gross_pay=earnings.gross_pay,
                ytd_income=request.ytd_income,
                config=config
            )
            
            # Calculate net pay
            net_pay = calculate_net_pay(
                gross_pay=earnings.gross_pay,
                deductions=deductions.total,
                taxes=taxes.total
            )
            
            # Create payment record
            payment = await self._create_payment_record(
                employee=employee,
                request=request,
                earnings=earnings,
                deductions=deductions,
                taxes=taxes,
                net_pay=net_pay
            )
            
            return PayrollCalculationResponse(
                payment_id=payment.id,
                employee_id=employee.id,
                earnings=earnings,
                deductions=deductions,
                taxes=taxes,
                net_pay=net_pay,
                payment_date=request.pay_date
            )
            
        except Exception as e:
            logger.error(f"Payroll calculation failed: {str(e)}")
            raise PayrollCalculationError(
                f"Failed to calculate payroll: {str(e)}"
            )
    
    async def _get_employee(self, employee_id: int) -> Employee:
        """Get employee with validation."""
        employee = self.db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.is_active == True
        ).first()
        
        if not employee:
            raise EmployeeNotFoundError(f"Employee {employee_id} not found")
        
        return employee
    
    async def _get_payroll_config(
        self,
        location: str,
        effective_date: date
    ) -> PayrollConfiguration:
        """Get payroll configuration with caching."""
        cache_key = f"{location}:{effective_date}"
        
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        config = self.db.query(PayrollConfiguration).filter(
            PayrollConfiguration.location == location,
            PayrollConfiguration.effective_date <= effective_date,
            PayrollConfiguration.is_active == True
        ).order_by(
            PayrollConfiguration.effective_date.desc()
        ).first()
        
        if not config:
            raise ConfigurationError(
                f"No payroll configuration found for {location}"
            )
        
        self._config_cache[cache_key] = config
        return config
    
    async def _calculate_earnings(
        self,
        employee: Employee,
        hours: Dict[str, Decimal],
        config: PayrollConfiguration
    ) -> EarningsResult:
        """Calculate all earnings."""
        regular_pay = calculate_regular_pay(
            employee=employee,
            regular_hours=hours.get("regular", Decimal("0"))
        )
        
        overtime_pay = Decimal("0")
        if employee.overtime_eligible:
            overtime_pay = calculate_overtime_pay(
                hourly_rate=employee.hourly_rate,
                overtime_hours=hours.get("overtime", Decimal("0")),
                overtime_rate=config.overtime_rate
            )
        
        # Add other earnings
        bonus = hours.get("bonus", Decimal("0"))
        commission = hours.get("commission", Decimal("0"))
        
        gross_pay = regular_pay + overtime_pay + bonus + commission
        
        return EarningsResult(
            regular_pay=regular_pay,
            overtime_pay=overtime_pay,
            bonus=bonus,
            commission=commission,
            gross_pay=gross_pay
        )
    
    async def _create_payment_record(
        self,
        employee: Employee,
        request: PayrollCalculationRequest,
        earnings: EarningsResult,
        deductions: DeductionsResult,
        taxes: TaxesResult,
        net_pay: Decimal
    ) -> EmployeePayment:
        """Create and save payment record."""
        payment = EmployeePayment(
            employee_id=employee.id,
            pay_period_start=request.pay_period_start,
            pay_period_end=request.pay_period_end,
            pay_date=request.pay_date,
            
            # Earnings
            regular_pay=earnings.regular_pay,
            overtime_pay=earnings.overtime_pay,
            bonus=earnings.bonus,
            commission=earnings.commission,
            gross_pay=earnings.gross_pay,
            
            # Taxes
            federal_tax=taxes.federal_tax,
            state_tax=taxes.state_tax,
            local_tax=taxes.local_tax,
            social_security=taxes.social_security,
            medicare=taxes.medicare,
            
            # Deductions
            health_insurance=deductions.health_insurance,
            retirement_401k=deductions.retirement_401k,
            
            # Net
            net_pay=net_pay,
            
            # Metadata
            created_at=datetime.utcnow(),
            created_by=request.processed_by
        )
        
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        
        return payment
```

## Data Models

### SQLAlchemy Models

```python
# backend/modules/payroll/models/employee_payment.py

from sqlalchemy import (
    Column, Integer, String, Decimal, Date, DateTime,
    ForeignKey, Boolean, Text, Enum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class PaymentStatus(enum.Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"

class EmployeePayment(Base):
    """Employee payment record."""
    
    __tablename__ = "employee_payments"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Pay period
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)
    
    # Hours
    regular_hours = Column(Decimal(5, 2), default=0)
    overtime_hours = Column(Decimal(5, 2), default=0)
    
    # Earnings
    regular_pay = Column(Decimal(10, 2), nullable=False)
    overtime_pay = Column(Decimal(10, 2), default=0)
    bonus = Column(Decimal(10, 2), default=0)
    commission = Column(Decimal(10, 2), default=0)
    other_earnings = Column(Decimal(10, 2), default=0)
    gross_pay = Column(Decimal(10, 2), nullable=False)
    
    # Taxes
    federal_tax = Column(Decimal(10, 2), nullable=False)
    state_tax = Column(Decimal(10, 2), nullable=False)
    local_tax = Column(Decimal(10, 2), default=0)
    social_security = Column(Decimal(10, 2), nullable=False)
    medicare = Column(Decimal(10, 2), nullable=False)
    additional_medicare = Column(Decimal(10, 2), default=0)
    
    # Pre-tax deductions
    health_insurance = Column(Decimal(10, 2), default=0)
    dental_insurance = Column(Decimal(10, 2), default=0)
    vision_insurance = Column(Decimal(10, 2), default=0)
    retirement_401k = Column(Decimal(10, 2), default=0)
    
    # Post-tax deductions
    garnishment_amount = Column(Decimal(10, 2), default=0)
    other_deductions = Column(Decimal(10, 2), default=0)
    
    # Net pay
    net_pay = Column(Decimal(10, 2), nullable=False)
    
    # Payment info
    payment_method = Column(String(50), default="direct_deposit")
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_reference = Column(String(100))
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    employee = relationship("Employee", back_populates="payments")
    adjustments = relationship("PaymentAdjustment", back_populates="payment")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_employee_pay_period", "employee_id", "pay_period_start", "pay_period_end"),
        Index("idx_payment_status_date", "payment_status", "pay_date"),
        Index("idx_created_at", "created_at"),
    )
    
    def __repr__(self):
        return f"<EmployeePayment(id={self.id}, employee_id={self.employee_id}, amount={self.net_pay})>"
    
    @property
    def total_deductions(self) -> Decimal:
        """Calculate total deductions."""
        return (
            self.federal_tax + self.state_tax + self.local_tax +
            self.social_security + self.medicare + self.additional_medicare +
            self.health_insurance + self.dental_insurance + self.vision_insurance +
            self.retirement_401k + self.garnishment_amount + self.other_deductions
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "pay_period": {
                "start": self.pay_period_start.isoformat(),
                "end": self.pay_period_end.isoformat()
            },
            "gross_pay": float(self.gross_pay),
            "net_pay": float(self.net_pay),
            "status": self.payment_status.value
        }
```

### Model Validation

```python
# backend/modules/payroll/models/validators.py

from sqlalchemy import event
from sqlalchemy.orm import validates
from decimal import Decimal
from datetime import date

from .employee_payment import EmployeePayment

class PaymentValidator:
    """Validation for payment models."""
    
    @validates('gross_pay', 'net_pay')
    def validate_positive_amount(self, key, value):
        """Ensure amounts are positive."""
        if value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @validates('pay_period_start', 'pay_period_end')
    def validate_pay_period(self, key, value):
        """Validate pay period dates."""
        if key == 'pay_period_end' and hasattr(self, 'pay_period_start'):
            if value < self.pay_period_start:
                raise ValueError("Pay period end must be after start")
        return value

# Attach validators
@event.listens_for(EmployeePayment, 'before_insert')
@event.listens_for(EmployeePayment, 'before_update')
def validate_payment(mapper, connection, target):
    """Validate payment before save."""
    # Verify calculations
    calculated_gross = (
        target.regular_pay + target.overtime_pay +
        target.bonus + target.commission + target.other_earnings
    )
    
    if abs(calculated_gross - target.gross_pay) > Decimal("0.01"):
        raise ValueError("Gross pay calculation mismatch")
    
    # Verify net pay
    total_deductions = target.total_deductions
    calculated_net = target.gross_pay - total_deductions
    
    if abs(calculated_net - target.net_pay) > Decimal("0.01"):
        raise ValueError("Net pay calculation mismatch")
```

## Testing

### Unit Testing

```python
# backend/modules/payroll/tests/test_payroll_service.py

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, patch

from ..services.payroll_service import PayrollService
from ..schemas import PayrollCalculationRequest
from ..exceptions import PayrollCalculationError

@pytest.fixture
def payroll_service(db_session):
    """Create payroll service instance."""
    return PayrollService(db_session)

@pytest.fixture
def sample_employee():
    """Create sample employee."""
    employee = Mock()
    employee.id = 1
    employee.hourly_rate = Decimal("25.00")
    employee.location = "california"
    employee.overtime_eligible = True
    return employee

@pytest.fixture
def calculation_request():
    """Create sample calculation request."""
    return PayrollCalculationRequest(
        employee_id=1,
        pay_period_start=date(2024, 1, 1),
        pay_period_end=date(2024, 1, 14),
        hours_worked={
            "regular": Decimal("80.0"),
            "overtime": Decimal("5.0")
        },
        pay_date=date(2024, 1, 19)
    )

class TestPayrollService:
    """Test payroll service."""
    
    async def test_calculate_payroll_success(
        self,
        payroll_service,
        sample_employee,
        calculation_request
    ):
        """Test successful payroll calculation."""
        # Mock dependencies
        with patch.object(payroll_service, '_get_employee') as mock_get_emp:
            mock_get_emp.return_value = sample_employee
            
            with patch.object(payroll_service, '_get_tax_rates') as mock_tax:
                mock_tax.return_value = {
                    "federal": Decimal("0.15"),
                    "state": Decimal("0.05"),
                    "social_security": Decimal("0.062"),
                    "medicare": Decimal("0.0145")
                }
                
                # Calculate payroll
                result = await payroll_service.calculate_payroll(
                    calculation_request
                )
                
                # Verify calculations
                assert result.gross_pay == Decimal("2187.50")  # 80*25 + 5*37.50
                assert result.net_pay > Decimal("1500.00")
                assert result.federal_tax > Decimal("0")
    
    async def test_calculate_payroll_no_overtime(
        self,
        payroll_service,
        sample_employee,
        calculation_request
    ):
        """Test payroll calculation without overtime."""
        sample_employee.overtime_eligible = False
        calculation_request.hours_worked["overtime"] = Decimal("5.0")
        
        with patch.object(payroll_service, '_get_employee') as mock_get_emp:
            mock_get_emp.return_value = sample_employee
            
            result = await payroll_service.calculate_payroll(
                calculation_request
            )
            
            # Overtime should not be calculated
            assert result.overtime_pay == Decimal("0")
    
    async def test_calculate_payroll_invalid_employee(
        self,
        payroll_service,
        calculation_request
    ):
        """Test payroll calculation with invalid employee."""
        with patch.object(payroll_service, '_get_employee') as mock_get_emp:
            mock_get_emp.side_effect = EmployeeNotFoundError("Employee not found")
            
            with pytest.raises(PayrollCalculationError):
                await payroll_service.calculate_payroll(calculation_request)
    
    @pytest.mark.parametrize("hours,expected_gross", [
        ({"regular": Decimal("40"), "overtime": Decimal("0")}, Decimal("1000.00")),
        ({"regular": Decimal("80"), "overtime": Decimal("0")}, Decimal("2000.00")),
        ({"regular": Decimal("80"), "overtime": Decimal("10")}, Decimal("2375.00")),
    ])
    async def test_various_hour_calculations(
        self,
        payroll_service,
        sample_employee,
        calculation_request,
        hours,
        expected_gross
    ):
        """Test various hour combinations."""
        calculation_request.hours_worked = hours
        
        with patch.object(payroll_service, '_get_employee') as mock_get_emp:
            mock_get_emp.return_value = sample_employee
            
            result = await payroll_service.calculate_payroll(
                calculation_request
            )
            
            assert result.gross_pay == expected_gross
```

### Integration Testing

```python
# backend/modules/payroll/tests/test_integration.py

import pytest
from httpx import AsyncClient
from datetime import date

from ..main import app

@pytest.mark.asyncio
class TestPayrollIntegration:
    """Integration tests for payroll API."""
    
    async def test_complete_payroll_flow(self, async_client: AsyncClient, auth_headers):
        """Test complete payroll processing flow."""
        
        # Step 1: Calculate payroll
        calculation_payload = {
            "employee_id": 1,
            "pay_period_start": "2024-01-01",
            "pay_period_end": "2024-01-14",
            "hours_worked": {
                "regular": 80.0,
                "overtime": 5.0
            }
        }
        
        response = await async_client.post(
            "/api/payroll/calculate",
            json=calculation_payload,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        calculation = response.json()
        assert "calculation_id" in calculation
        assert calculation["gross_pay"] > 0
        
        # Step 2: Process payment
        payment_payload = {
            "calculation_id": calculation["calculation_id"],
            "payment_method": "direct_deposit",
            "payment_date": "2024-01-19"
        }
        
        response = await async_client.post(
            "/api/payroll/payments",
            json=payment_payload,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        payment = response.json()
        assert payment["status"] == "pending"
        
        # Step 3: Verify payment in history
        response = await async_client.get(
            f"/api/payroll/payments/{payment['payment_id']}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        payment_detail = response.json()
        assert payment_detail["payment_id"] == payment["payment_id"]
    
    async def test_batch_processing(self, async_client: AsyncClient, auth_headers):
        """Test batch payroll processing."""
        
        batch_payload = {
            "pay_period_start": "2024-01-01",
            "pay_period_end": "2024-01-14",
            "employee_ids": [1, 2, 3, 4, 5]
        }
        
        # Start batch
        response = await async_client.post(
            "/api/v1/payroll/batch/run",
            json=batch_payload,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        batch = response.json()
        assert "job_id" in batch
        
        # Check status
        response = await async_client.get(
            f"/api/v1/payroll/batch/status/{batch['job_id']}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        status = response.json()
        assert status["job_id"] == batch["job_id"]
        assert "progress" in status
```

## Code Examples

### Custom Tax Calculator

```python
# backend/modules/payroll/calculators/state_tax_calculator.py

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List

class StateTaxCalculator(ABC):
    """Base class for state tax calculators."""
    
    @abstractmethod
    def calculate(
        self,
        gross_pay: Decimal,
        ytd_income: Decimal,
        filing_status: str,
        allowances: int
    ) -> Decimal:
        """Calculate state tax."""
        pass

class CaliforniaTaxCalculator(StateTaxCalculator):
    """California state tax calculator."""
    
    # 2024 tax brackets
    TAX_BRACKETS = {
        "single": [
            {"min": 0, "max": 10412, "rate": 0.01},
            {"min": 10412, "max": 24684, "rate": 0.02},
            {"min": 24684, "max": 38959, "rate": 0.04},
            {"min": 38959, "max": 54081, "rate": 0.06},
            {"min": 54081, "max": 68350, "rate": 0.08},
            {"min": 68350, "max": 349137, "rate": 0.093},
            {"min": 349137, "max": 418961, "rate": 0.103},
            {"min": 418961, "max": 698271, "rate": 0.113},
            {"min": 698271, "max": float('inf'), "rate": 0.123}
        ],
        "married_jointly": [
            # Double the single brackets
        ]
    }
    
    STANDARD_DEDUCTION = {
        "single": Decimal("5363"),
        "married_jointly": Decimal("10726")
    }
    
    PERSONAL_EXEMPTION = Decimal("154")
    
    def calculate(
        self,
        gross_pay: Decimal,
        ytd_income: Decimal,
        filing_status: str,
        allowances: int
    ) -> Decimal:
        """Calculate California state tax."""
        # Annualize income
        pay_periods = 26  # Bi-weekly
        annual_income = (ytd_income + gross_pay) * pay_periods / \
                       ((ytd_income / gross_pay) + 1)
        
        # Apply deductions
        standard_deduction = self.STANDARD_DEDUCTION.get(
            filing_status, 
            self.STANDARD_DEDUCTION["single"]
        )
        exemption_amount = self.PERSONAL_EXEMPTION * allowances
        
        taxable_income = max(
            annual_income - standard_deduction - exemption_amount,
            Decimal("0")
        )
        
        # Calculate tax
        annual_tax = self._calculate_bracket_tax(
            taxable_income,
            filing_status
        )
        
        # Calculate period tax
        period_tax = annual_tax / pay_periods
        
        return period_tax.quantize(Decimal("0.01"))
    
    def _calculate_bracket_tax(
        self,
        taxable_income: Decimal,
        filing_status: str
    ) -> Decimal:
        """Calculate tax using brackets."""
        brackets = self.TAX_BRACKETS.get(
            filing_status,
            self.TAX_BRACKETS["single"]
        )
        
        tax = Decimal("0")
        
        for bracket in brackets:
            if taxable_income <= bracket["min"]:
                break
            
            taxable_in_bracket = min(
                taxable_income - bracket["min"],
                bracket["max"] - bracket["min"]
            )
            
            tax += taxable_in_bracket * Decimal(str(bracket["rate"]))
        
        return tax

# Tax calculator factory
class TaxCalculatorFactory:
    """Factory for creating state tax calculators."""
    
    _calculators = {
        "CA": CaliforniaTaxCalculator,
        "NY": NewYorkTaxCalculator,
        "TX": TexasTaxCalculator,  # No state income tax
        # Add more states
    }
    
    @classmethod
    def create(cls, state_code: str) -> StateTaxCalculator:
        """Create tax calculator for state."""
        calculator_class = cls._calculators.get(state_code)
        if not calculator_class:
            raise ValueError(f"No tax calculator for state: {state_code}")
        return calculator_class()
```

### Background Task Processing

```python
# backend/modules/payroll/tasks/payroll_tasks.py

from celery import shared_task, Task
from celery.utils.log import get_task_logger
from typing import List, Dict
import time

from ..services.batch_payroll_service import BatchPayrollService
from ..database import SessionLocal

logger = get_task_logger(__name__)

class PayrollTask(Task):
    """Base task with database session management."""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Clean up database session."""
        if self._db is not None:
            self._db.close()
            self._db = None

@shared_task(base=PayrollTask, bind=True, max_retries=3)
def process_batch_payroll(
    self,
    job_id: str,
    employee_ids: List[int],
    pay_period_start: str,
    pay_period_end: str,
    options: Dict = None
):
    """Process payroll for multiple employees."""
    logger.info(f"Starting batch payroll job: {job_id}")
    
    try:
        service = BatchPayrollService(self.db)
        
        # Update job status
        service.update_job_status(job_id, "processing")
        
        # Process each employee
        results = []
        for i, employee_id in enumerate(employee_ids):
            try:
                result = service.process_employee(
                    employee_id=employee_id,
                    pay_period_start=pay_period_start,
                    pay_period_end=pay_period_end,
                    options=options
                )
                results.append(result)
                
                # Update progress
                progress = (i + 1) / len(employee_ids) * 100
                service.update_job_progress(job_id, progress)
                
            except Exception as e:
                logger.error(f"Failed to process employee {employee_id}: {e}")
                results.append({
                    "employee_id": employee_id,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Complete job
        service.complete_job(job_id, results)
        logger.info(f"Completed batch payroll job: {job_id}")
        
        return {
            "job_id": job_id,
            "total": len(employee_ids),
            "successful": sum(1 for r in results if r.get("status") != "failed"),
            "failed": sum(1 for r in results if r.get("status") == "failed")
        }
        
    except Exception as e:
        logger.error(f"Batch payroll job {job_id} failed: {e}")
        service.fail_job(job_id, str(e))
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@shared_task
def generate_payment_file(payment_ids: List[int], format: str = "ach"):
    """Generate payment file for bank processing."""
    logger.info(f"Generating {format} file for {len(payment_ids)} payments")
    
    with SessionLocal() as db:
        from ..services.payment_export_service import PaymentExportService
        
        service = PaymentExportService(db)
        file_path = service.generate_payment_file(
            payment_ids=payment_ids,
            format=format
        )
        
        # Queue for secure transfer
        transfer_payment_file.delay(file_path)
        
        return {
            "file_path": file_path,
            "payment_count": len(payment_ids),
            "format": format
        }

@shared_task
def send_payment_notifications(payment_ids: List[int]):
    """Send payment notifications to employees."""
    logger.info(f"Sending notifications for {len(payment_ids)} payments")
    
    with SessionLocal() as db:
        from ..services.notification_service import NotificationService
        
        service = NotificationService(db)
        results = []
        
        for payment_id in payment_ids:
            try:
                notification_id = service.send_payment_notification(payment_id)
                results.append({
                    "payment_id": payment_id,
                    "notification_id": notification_id,
                    "status": "sent"
                })
            except Exception as e:
                logger.error(f"Failed to send notification for payment {payment_id}: {e}")
                results.append({
                    "payment_id": payment_id,
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
```

### Custom Decorators

```python
# backend/modules/payroll/decorators.py

from functools import wraps
from typing import Callable
import time
import logging

from .utils.metrics import function_duration_histogram
from .exceptions import PayrollException

logger = logging.getLogger(__name__)

def timed(func: Callable) -> Callable:
    """Decorator to measure function execution time."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            function_duration_histogram.labels(
                function=func.__name__
            ).observe(duration)
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

def cached(ttl: int = 300):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key = f"{args}:{kwargs}"
            
            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if time.time() - timestamp < ttl:
                    return value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            cache[key] = (result, time.time())
            
            return result
        
        return wrapper
    return decorator

def transactional(rollback_on: tuple = (Exception,)):
    """Decorator for database transactions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'db'):
                raise ValueError("Object must have 'db' attribute")
            
            # Start transaction
            trans = self.db.begin()
            
            try:
                result = await func(self, *args, **kwargs)
                trans.commit()
                return result
            except rollback_on as e:
                trans.rollback()
                logger.error(f"Transaction rolled back: {e}")
                raise
            except Exception as e:
                trans.rollback()
                raise
        
        return wrapper
    return decorator

def audit_trail(action: str):
    """Decorator to create audit trail entries."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get user from context
            user_id = kwargs.get('user_id') or getattr(self, 'current_user_id', None)
            
            # Execute function
            result = await func(self, *args, **kwargs)
            
            # Create audit entry
            if hasattr(self, 'audit_service'):
                await self.audit_service.create_entry(
                    action=action,
                    user_id=user_id,
                    entity_type=func.__name__,
                    entity_id=getattr(result, 'id', None),
                    details={
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                )
            
            return result
        
        return wrapper
    return decorator
```

## Best Practices

### 1. Code Organization

- Keep files small and focused (< 300 lines)
- One class per file for models and services
- Group related functionality in modules
- Use clear, descriptive names

### 2. Error Handling

```python
# Good error handling example
async def process_payment(self, payment_id: int) -> PaymentResult:
    """Process a payment with proper error handling."""
    try:
        # Validate input
        if not payment_id:
            raise ValueError("Payment ID is required")
        
        # Get payment
        payment = await self.get_payment(payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")
        
        # Check status
        if payment.status != PaymentStatus.PENDING:
            raise InvalidPaymentStateError(
                f"Payment {payment_id} is not pending"
            )
        
        # Process payment
        result = await self._process_payment_internal(payment)
        
        # Update status
        payment.status = PaymentStatus.COMPLETED
        await self.db.commit()
        
        # Log success
        logger.info(f"Payment {payment_id} processed successfully")
        
        return result
        
    except PayrollException:
        # Re-raise domain exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error processing payment {payment_id}: {e}")
        
        # Wrap in domain exception
        raise PaymentProcessingError(
            f"Failed to process payment: {str(e)}"
        ) from e
```

### 3. Testing Strategy

- Unit tests for all business logic
- Integration tests for API endpoints
- Mock external dependencies
- Use fixtures for test data
- Aim for 90%+ coverage

### 4. Performance Optimization

```python
# Use bulk operations
async def process_batch_efficient(self, employee_ids: List[int]):
    """Efficient batch processing."""
    # Bad: N+1 queries
    # for emp_id in employee_ids:
    #     emp = self.db.query(Employee).filter_by(id=emp_id).first()
    #     process(emp)
    
    # Good: Single query
    employees = self.db.query(Employee).filter(
        Employee.id.in_(employee_ids)
    ).all()
    
    # Process in memory
    for emp in employees:
        process(emp)
    
    # Bulk insert
    payments = [create_payment(emp) for emp in employees]
    self.db.bulk_insert_mappings(Payment, payments)
    self.db.commit()
```

### 5. Security

- Always validate input
- Use parameterized queries
- Implement proper authentication
- Audit sensitive operations
- Encrypt sensitive data

## Contributing

### Development Workflow

1. **Create feature branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make changes**
- Write tests first (TDD)
- Implement feature
- Update documentation

3. **Run tests**
```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_your_feature.py

# Run with coverage
pytest --cov=backend.modules.payroll
```

4. **Format code**
```bash
# Format with black
black backend/modules/payroll

# Sort imports
isort backend/modules/payroll

# Lint
flake8 backend/modules/payroll
```

5. **Create pull request**
- Clear description
- Link to issue
- Include tests
- Update changelog

### Code Review Checklist

- [ ] Tests pass
- [ ] Code coverage maintained
- [ ] Documentation updated
- [ ] No security vulnerabilities
- [ ] Performance impact assessed
- [ ] Database migrations included
- [ ] API changes documented
- [ ] Error handling implemented

### Style Guide

- Follow PEP 8
- Use type hints
- Write docstrings
- Keep functions small
- Avoid deep nesting
- Use meaningful names

## Resources

### Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)

### Tools

- **API Testing**: Postman, HTTPie
- **Database**: pgAdmin, DBeaver
- **Monitoring**: Prometheus, Grafana
- **Logging**: ELK Stack

### Support

- **Slack**: #payroll-dev
- **Email**: payroll-team@auraconnect.com
- **Wiki**: https://wiki.auraconnect.com/payroll