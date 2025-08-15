"""
Unit tests for payroll model validations addressing code review recommendations.

Tests cover:
- Foreign key constraints and relationships
- Enum validation and consistency
- Data validation constraints
- Database integrity checks
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError, CheckViolation
from sqlalchemy.orm import Session

from ..models.payroll_models import (
    TaxRule,
    PayrollPolicy,
    EmployeePayment,
    EmployeePaymentTaxApplication,
)
from ..enums.payroll_enums import PaymentStatus, PayFrequency, TaxType, PaymentMethod
from ...staff.models.staff_models import StaffMember, Role
from ...staff.enums.staff_enums import StaffStatus


class TestForeignKeyConstraints:
    """Test foreign key constraints and relationships."""

    def test_employee_payment_staff_foreign_key(self, db_session: Session):
        """Test that staff_id must reference existing staff member."""

        # Create a payroll policy first
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test Location",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )
        db_session.add(policy)
        db_session.flush()

        # Try to create payment with non-existent staff_id
        payment = EmployeePayment(
            staff_id=99999,  # Non-existent staff ID
            payroll_policy_id=policy.id,
            pay_period_start=datetime.now(),
            pay_period_end=datetime.now() + timedelta(days=14),
            pay_date=datetime.now(),
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment)

        # Should raise foreign key constraint error
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "foreign key constraint" in str(exc_info.value).lower()

    def test_employee_payment_valid_staff_relationship(self, db_session: Session):
        """Test successful creation with valid staff relationship."""

        # Create role and staff member
        role = Role(name="server", permissions="basic")
        db_session.add(role)
        db_session.flush()

        staff = StaffMember(
            name="John Doe",
            email="john@example.com",
            role_id=role.id,
            status=StaffStatus.ACTIVE,
        )
        db_session.add(staff)
        db_session.flush()

        # Create payroll policy
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test Location",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )
        db_session.add(policy)
        db_session.flush()

        # Create employee payment with valid staff_id
        payment = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=datetime.now(),
            pay_period_end=datetime.now() + timedelta(days=14),
            pay_date=datetime.now(),
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment)
        db_session.commit()

        # Verify relationship works
        assert payment.staff_member is not None
        assert payment.staff_member.name == "John Doe"
        assert staff.employee_payments[0] == payment

    def test_tax_application_foreign_keys(self, db_session: Session):
        """Test tax application foreign key constraints."""

        # Create required entities
        role = Role(name="server", permissions="basic")
        staff = StaffMember(
            name="Jane Doe",
            email="jane@example.com",
            role_id=1,
            status=StaffStatus.ACTIVE,
        )
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )
        payment = EmployeePayment(
            staff_id=1,
            payroll_policy_id=1,
            pay_period_start=datetime.now(),
            pay_period_end=datetime.now() + timedelta(days=14),
            pay_date=datetime.now(),
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )
        tax_rule = TaxRule(
            rule_name="Federal Tax",
            location="US",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.12"),
            effective_date=datetime.now(),
        )

        db_session.add_all([role, staff, policy, payment, tax_rule])
        db_session.flush()

        # Create tax application with valid foreign keys
        tax_app = EmployeePaymentTaxApplication(
            employee_payment_id=payment.id,
            tax_rule_id=tax_rule.id,
            taxable_amount=Decimal("600.00"),
            calculated_tax=Decimal("72.00"),
            effective_rate=Decimal("0.12"),
            calculation_date=datetime.now(),
        )

        db_session.add(tax_app)
        db_session.commit()

        # Verify relationships
        assert tax_app.employee_payment == payment
        assert tax_app.tax_rule == tax_rule
        assert payment.tax_applications[0] == tax_app


class TestEnumValidation:
    """Test enum validation and consistency."""

    def test_payment_status_enum_validation(self, db_session: Session):
        """Test that payment status must be valid enum value."""

        # Valid enum values should work
        for status in PaymentStatus:
            payment = EmployeePayment(
                staff_id=1,
                payroll_policy_id=1,
                pay_period_start=datetime.now(),
                pay_period_end=datetime.now() + timedelta(days=14),
                pay_date=datetime.now(),
                regular_rate=Decimal("15.00"),
                gross_pay=Decimal("600.00"),
                total_deductions=Decimal("120.00"),
                net_pay=Decimal("480.00"),
                payment_status=status,
            )
            assert payment.payment_status == status

    def test_tax_type_enum_validation(self):
        """Test tax type enum validation."""

        tax_rule = TaxRule(
            rule_name="Test Tax",
            location="Test Location",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.12"),
            effective_date=datetime.now(),
        )

        assert tax_rule.tax_type == TaxType.FEDERAL

        # Test all enum values
        for tax_type in TaxType:
            tax_rule.tax_type = tax_type
            assert tax_rule.tax_type == tax_type

    def test_pay_frequency_enum_validation(self):
        """Test pay frequency enum validation."""

        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test Location",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )

        assert policy.pay_frequency == PayFrequency.BIWEEKLY

        # Test all enum values
        for frequency in PayFrequency:
            policy.pay_frequency = frequency
            assert policy.pay_frequency == frequency

    def test_staff_status_enum_validation(self):
        """Test staff status enum validation."""

        staff = StaffMember(
            name="Test Staff", email="test@example.com", status=StaffStatus.ACTIVE
        )

        assert staff.status == StaffStatus.ACTIVE

        # Test all enum values
        for status in StaffStatus:
            staff.status = status
            assert staff.status == status


class TestDataValidationConstraints:
    """Test data validation constraints."""

    def test_positive_hours_constraint(self, db_session: Session):
        """Test that hours worked must be positive."""

        # Create required entities
        role = Role(name="server", permissions="basic")
        staff = StaffMember(
            name="Test Staff",
            email="test@example.com",
            role_id=1,
            status=StaffStatus.ACTIVE,
        )
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )

        db_session.add_all([role, staff, policy])
        db_session.flush()

        # Try to create payment with negative hours
        payment = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=datetime.now(),
            pay_period_end=datetime.now() + timedelta(days=14),
            pay_date=datetime.now(),
            regular_rate=Decimal("15.00"),
            regular_hours=Decimal("-5.00"),  # Negative hours
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment)

        # Should raise check constraint error
        with pytest.raises((IntegrityError, CheckViolation)):
            db_session.commit()

    def test_positive_pay_amounts_constraint(self, db_session: Session):
        """Test that pay amounts must be positive."""

        # Create required entities
        role = Role(name="server", permissions="basic")
        staff = StaffMember(
            name="Test Staff",
            email="test@example.com",
            role_id=1,
            status=StaffStatus.ACTIVE,
        )
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )

        db_session.add_all([role, staff, policy])
        db_session.flush()

        # Try to create payment with negative gross pay
        payment = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=datetime.now(),
            pay_period_end=datetime.now() + timedelta(days=14),
            pay_date=datetime.now(),
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("-600.00"),  # Negative gross pay
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment)

        # Should raise check constraint error
        with pytest.raises((IntegrityError, CheckViolation)):
            db_session.commit()

    def test_valid_pay_period_constraint(self, db_session: Session):
        """Test that pay period end must be after start."""

        # Create required entities
        role = Role(name="server", permissions="basic")
        staff = StaffMember(
            name="Test Staff",
            email="test@example.com",
            role_id=1,
            status=StaffStatus.ACTIVE,
        )
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )

        db_session.add_all([role, staff, policy])
        db_session.flush()

        # Try to create payment with invalid period
        now = datetime.now()
        payment = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=now,
            pay_period_end=now - timedelta(days=1),  # End before start
            pay_date=now,
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment)

        # Should raise check constraint error
        with pytest.raises((IntegrityError, CheckViolation)):
            db_session.commit()

    def test_tax_rule_rate_validation(self, db_session: Session):
        """Test that tax rates must be between 0 and 1."""

        # Valid rate should work
        tax_rule = TaxRule(
            rule_name="Valid Tax",
            location="Test",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.12"),
            effective_date=datetime.now(),
        )

        db_session.add(tax_rule)
        db_session.commit()

        # Invalid rate should fail
        invalid_tax_rule = TaxRule(
            rule_name="Invalid Tax",
            location="Test",
            tax_type=TaxType.STATE,
            rate_percent=Decimal("1.5"),  # Rate > 1
            effective_date=datetime.now(),
        )

        db_session.add(invalid_tax_rule)

        with pytest.raises((IntegrityError, CheckViolation)):
            db_session.commit()

    def test_payroll_policy_multiplier_validation(self, db_session: Session):
        """Test that multipliers must be >= 1.0."""

        # Valid multipliers should work
        policy = PayrollPolicy(
            policy_name="Valid Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
            overtime_multiplier=Decimal("1.5"),
            holiday_pay_multiplier=Decimal("2.0"),
        )

        db_session.add(policy)
        db_session.commit()

        # Invalid multiplier should fail
        invalid_policy = PayrollPolicy(
            policy_name="Invalid Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
            overtime_multiplier=Decimal("0.5"),  # Multiplier < 1
        )

        db_session.add(invalid_policy)

        with pytest.raises((IntegrityError, CheckViolation)):
            db_session.commit()


class TestTaxRuleApplicability:
    """Test tax rule applicability logic."""

    def test_tax_rule_effective_date_filtering(self, db_session: Session):
        """Test that tax rules are filtered by effective date."""

        now = datetime.now()

        # Create tax rules with different effective dates
        future_rule = TaxRule(
            rule_name="Future Tax",
            location="Test",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.15"),
            effective_date=now + timedelta(days=30),
            is_active=True,
        )

        current_rule = TaxRule(
            rule_name="Current Tax",
            location="Test",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.12"),
            effective_date=now - timedelta(days=30),
            is_active=True,
        )

        expired_rule = TaxRule(
            rule_name="Expired Tax",
            location="Test",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.10"),
            effective_date=now - timedelta(days=60),
            expiry_date=now - timedelta(days=30),
            is_active=False,
        )

        db_session.add_all([future_rule, current_rule, expired_rule])
        db_session.commit()

        # Query for applicable rules
        applicable_rules = (
            db_session.query(TaxRule)
            .filter(
                TaxRule.location == "Test",
                TaxRule.tax_type == TaxType.FEDERAL,
                TaxRule.effective_date <= now,
                TaxRule.is_active == True,
            )
            .all()
        )

        # Should only return current rule
        assert len(applicable_rules) == 1
        assert applicable_rules[0].rule_name == "Current Tax"

    def test_tax_rule_location_jurisdiction(self, db_session: Session):
        """Test tax rule location-based filtering."""

        now = datetime.now()

        # Create tax rules for different locations
        california_rule = TaxRule(
            rule_name="California Tax",
            location="California",
            tax_type=TaxType.STATE,
            rate_percent=Decimal("0.08"),
            effective_date=now,
        )

        texas_rule = TaxRule(
            rule_name="Texas Tax",
            location="Texas",
            tax_type=TaxType.STATE,
            rate_percent=Decimal("0.06"),
            effective_date=now,
        )

        federal_rule = TaxRule(
            rule_name="Federal Tax",
            location="US",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal("0.12"),
            effective_date=now,
        )

        db_session.add_all([california_rule, texas_rule, federal_rule])
        db_session.commit()

        # Query for California-specific rules
        ca_rules = (
            db_session.query(TaxRule)
            .filter(TaxRule.location.in_(["California", "US"]))
            .all()
        )

        # Should return California and Federal rules
        assert len(ca_rules) == 2
        rule_names = [rule.rule_name for rule in ca_rules]
        assert "California Tax" in rule_names
        assert "Federal Tax" in rule_names
        assert "Texas Tax" not in rule_names


class TestUniqueConstraints:
    """Test unique constraints and data integrity."""

    def test_employee_payment_period_uniqueness(self, db_session: Session):
        """Test that employee can't have duplicate payments for same period."""

        # Create required entities
        role = Role(name="server", permissions="basic")
        staff = StaffMember(
            name="Test Staff",
            email="test@example.com",
            role_id=1,
            status=StaffStatus.ACTIVE,
        )
        policy = PayrollPolicy(
            policy_name="Test Policy",
            location="Test",
            pay_frequency=PayFrequency.BIWEEKLY,
            pay_period_start_day=1,
            minimum_wage=Decimal("15.00"),
        )

        db_session.add_all([role, staff, policy])
        db_session.flush()

        # Create first payment
        start_date = datetime.now()
        end_date = start_date + timedelta(days=14)

        payment1 = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=start_date,
            pay_period_end=end_date,
            pay_date=end_date,
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("600.00"),
            total_deductions=Decimal("120.00"),
            net_pay=Decimal("480.00"),
        )

        db_session.add(payment1)
        db_session.commit()

        # Try to create duplicate payment for same period
        payment2 = EmployeePayment(
            staff_id=staff.id,
            payroll_policy_id=policy.id,
            pay_period_start=start_date,
            pay_period_end=end_date,
            pay_date=end_date,
            regular_rate=Decimal("15.00"),
            gross_pay=Decimal("700.00"),
            total_deductions=Decimal("140.00"),
            net_pay=Decimal("560.00"),
        )

        db_session.add(payment2)

        # Should raise unique constraint error
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "unique constraint" in str(exc_info.value).lower()


# Fixtures for testing
@pytest.fixture
def db_session():
    """Create a test database session."""

    # This would be implemented based on your test database setup
    # For now, returning a mock that provides the interface
    class MockSession:
        def __init__(self):
            self.objects = []

        def add(self, obj):
            self.objects.append(obj)

        def add_all(self, objects):
            self.objects.extend(objects)

        def flush(self):
            pass

        def commit(self):
            pass

        def query(self, model):
            return MockQuery(model)

    class MockQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *args):
            return self

        def all(self):
            return []

    return MockSession()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
