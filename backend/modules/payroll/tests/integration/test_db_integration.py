# backend/modules/payroll/tests/integration/test_db_integration.py

"""
Database integration tests with real PostgreSQL.

These tests use a real database connection to verify
actual SQL queries and transactions.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ...models.employee_payment import EmployeePayment
from ...models.payroll_configuration import (
    PayrollConfiguration,
    StaffPayPolicy,
    PayrollConfigurationType
)
from ...services.payroll_service import PayrollService
from ...services.payroll_configuration_service import PayrollConfigurationService
from ....staff.models.staff import Staff
from core.database import Base


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    # Use TEST_DATABASE_URL if available, otherwise default
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test_user:test_password@localhost:5433/payroll_test"
    )
    engine = create_engine(database_url)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Clean up
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    
    # Begin a transaction
    session.begin()
    
    yield session
    
    # Rollback the transaction
    session.rollback()
    session.close()


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database operations with real PostgreSQL."""
    
    def test_create_employee_payment(self, db_session):
        """Test creating an employee payment record."""
        # Create payment
        payment = EmployeePayment(
            employee_id=1,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 14),
            pay_date=date(2024, 1, 19),
            regular_hours=Decimal("80.0"),
            overtime_hours=Decimal("5.0"),
            regular_pay=Decimal("2000.00"),
            overtime_pay=Decimal("187.50"),
            gross_pay=Decimal("2187.50"),
            federal_tax=Decimal("328.13"),
            state_tax=Decimal("87.50"),
            social_security=Decimal("135.63"),
            medicare=Decimal("31.72"),
            net_pay=Decimal("1604.52")
        )
        
        db_session.add(payment)
        db_session.flush()
        
        # Verify
        assert payment.id is not None
        saved_payment = db_session.query(EmployeePayment).filter_by(
            id=payment.id
        ).first()
        assert saved_payment is not None
        assert saved_payment.gross_pay == Decimal("2187.50")
    
    def test_payroll_configuration_crud(self, db_session):
        """Test CRUD operations on payroll configuration."""
        service = PayrollConfigurationService(db_session)
        
        # Create configuration
        config_data = {
            "config_type": PayrollConfigurationType.OVERTIME_RULES,
            "config_key": "california_overtime",
            "config_value": {
                "daily_threshold": 8,
                "weekly_threshold": 40,
                "daily_multiplier": 1.5,
                "weekly_multiplier": 1.5
            },
            "description": "California overtime rules",
            "location": "california",
            "effective_date": datetime.utcnow()
        }
        
        config = service.create_configuration(config_data)
        assert config.id is not None
        
        # Read configuration
        retrieved = service.get_configuration(
            config_type=PayrollConfigurationType.OVERTIME_RULES,
            config_key="california_overtime",
            location="california"
        )
        assert retrieved["daily_threshold"] == 8
        
        # Update configuration
        update_data = {
            "config_value": {
                "daily_threshold": 8,
                "weekly_threshold": 40,
                "daily_multiplier": 1.5,
                "weekly_multiplier": 1.5,
                "double_time_threshold": 12,
                "double_time_multiplier": 2.0
            }
        }
        updated = service.update_configuration(config.id, update_data)
        assert "double_time_threshold" in updated.config_value
        
        # Deactivate configuration
        service.deactivate_configuration(config.id)
        deactivated = db_session.query(PayrollConfiguration).filter_by(
            id=config.id
        ).first()
        assert deactivated.is_active is False
    
    def test_staff_pay_policy_with_history(self, db_session):
        """Test pay policy with historical tracking."""
        # Create initial policy
        policy1 = StaffPayPolicy(
            staff_id=1,
            base_hourly_rate=Decimal("25.00"),
            overtime_eligible=True,
            overtime_multiplier=Decimal("1.5"),
            health_insurance_monthly=Decimal("400.00"),
            retirement_match_percentage=Decimal("0.04"),
            effective_date=date(2023, 1, 1),
            created_by=1
        )
        db_session.add(policy1)
        
        # Create updated policy
        policy2 = StaffPayPolicy(
            staff_id=1,
            base_hourly_rate=Decimal("27.50"),  # Raise
            overtime_eligible=True,
            overtime_multiplier=Decimal("1.5"),
            health_insurance_monthly=Decimal("400.00"),
            retirement_match_percentage=Decimal("0.05"),  # Increased match
            effective_date=date(2024, 1, 1),
            created_by=1
        )
        db_session.add(policy2)
        
        # Set expiry on old policy
        policy1.expiry_date = date(2023, 12, 31)
        
        db_session.flush()
        
        # Query current policy
        current_policy = db_session.query(StaffPayPolicy).filter(
            StaffPayPolicy.staff_id == 1,
            StaffPayPolicy.is_active == True,
            StaffPayPolicy.effective_date <= date.today()
        ).order_by(StaffPayPolicy.effective_date.desc()).first()
        
        assert current_policy.base_hourly_rate == Decimal("27.50")
        
        # Query historical policy
        historical_policy = db_session.query(StaffPayPolicy).filter(
            StaffPayPolicy.staff_id == 1,
            StaffPayPolicy.effective_date <= date(2023, 6, 1),
            StaffPayPolicy.expiry_date >= date(2023, 6, 1)
        ).first()
        
        assert historical_policy.base_hourly_rate == Decimal("25.00")
    
    def test_payment_query_performance(self, db_session):
        """Test payment query performance with indexes."""
        # Create multiple payments
        for i in range(100):
            payment = EmployeePayment(
                employee_id=(i % 10) + 1,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                pay_date=date(2024, 1, 19),
                gross_pay=Decimal("2500.00"),
                net_pay=Decimal("1875.00")
            )
            db_session.add(payment)
        
        db_session.flush()
        
        # Test indexed query (should be fast)
        import time
        start_time = time.time()
        
        payments = db_session.query(EmployeePayment).filter(
            EmployeePayment.employee_id == 5,
            EmployeePayment.pay_period_start >= date(2024, 1, 1),
            EmployeePayment.pay_period_end <= date(2024, 1, 31)
        ).all()
        
        query_time = time.time() - start_time
        
        assert len(payments) == 10
        assert query_time < 0.1  # Should be very fast with indexes
    
    def test_transaction_rollback(self, db_session):
        """Test transaction rollback on error."""
        service = PayrollService(db_session)
        
        # Start creating a payment
        payment = EmployeePayment(
            employee_id=1,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 14),
            gross_pay=Decimal("2500.00")
        )
        db_session.add(payment)
        db_session.flush()
        
        payment_id = payment.id
        
        # Simulate an error that should trigger rollback
        try:
            # This should fail due to missing required fields
            invalid_payment = EmployeePayment(
                employee_id=None,  # Required field
                gross_pay=Decimal("1000.00")
            )
            db_session.add(invalid_payment)
            db_session.flush()
        except Exception:
            db_session.rollback()
        
        # Verify the first payment was also rolled back
        rolled_back = db_session.query(EmployeePayment).filter_by(
            id=payment_id
        ).first()
        assert rolled_back is None