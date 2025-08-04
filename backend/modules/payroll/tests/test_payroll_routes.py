# backend/modules/payroll/tests/test_payroll_routes.py

"""
Unit tests for payroll module API routes.

Tests cover:
- Tax calculation endpoints
- Configuration management endpoints
- Payment history and details endpoints
- Authentication and authorization
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from ....app.main import app
from core.database import get_db
from ..models.payroll_models import TaxRule, EmployeePayment
from ..enums.payroll_enums import TaxRuleType, TaxRuleStatus, PaymentStatus


# Test client
client = TestClient(app)


# Mock database session
@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    yield db


# Mock authentication
@pytest.fixture
def mock_auth_headers():
    """Mock authentication headers"""
    return {"Authorization": "Bearer test_token"}


# Override database dependency
def override_get_db():
    """Override database dependency for testing"""
    db = Mock()
    try:
        yield db
    finally:
        pass


app.dependency_overrides[get_db] = override_get_db


class TestTaxCalculationRoutes:
    """Test cases for tax calculation endpoints"""
    
    @patch('backend.modules.payroll.routes.tax_calculation_routes.require_payroll_access')
    @patch('backend.modules.payroll.routes.tax_calculation_routes.PayrollTaxEngine')
    def test_calculate_payroll_taxes_success(self, mock_tax_engine, mock_auth):
        """Test successful tax calculation"""
        # Mock authentication
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock tax engine response
        mock_engine_instance = Mock()
        mock_tax_engine.return_value = mock_engine_instance
        mock_engine_instance.calculate_taxes.return_value = Mock(
            federal_tax=Decimal('100.00'),
            state_tax=Decimal('50.00'),
            local_tax=Decimal('10.00'),
            social_security_employee=Decimal('62.00'),
            medicare_employee=Decimal('14.50'),
            total_employee_taxes=Decimal('236.50')
        )
        
        # Make request
        response = client.post(
            "/api/payroll/tax/calculate",
            json={
                "gross_amount": "1000.00",
                "pay_date": "2025-01-30",
                "location": "CA",
                "employee_id": 123
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "federal_tax" in data
        assert "state_tax" in data
        assert "total_employee_taxes" in data
    
    @patch('backend.modules.payroll.routes.tax_calculation_routes.require_payroll_access')
    @patch('backend.modules.payroll.routes.tax_calculation_routes.PayrollTaxEngine')
    def test_calculate_payroll_taxes_invalid_input(self, mock_tax_engine, mock_auth):
        """Test tax calculation with invalid input"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Make request with invalid gross amount
        response = client.post(
            "/api/payroll/tax/calculate",
            json={
                "gross_amount": "invalid",
                "pay_date": "2025-01-30",
                "location": "CA"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('backend.modules.payroll.routes.tax_calculation_routes.require_payroll_access')
    def test_get_tax_rules_success(self, mock_auth):
        """Test getting tax rules"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock database query
        with patch('backend.modules.payroll.routes.tax_calculation_routes.Session') as mock_session:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [
                Mock(
                    id=1,
                    tax_type=TaxRuleType.FEDERAL,
                    location="US",
                    rate=Decimal('0.22'),
                    cap_amount=None,
                    employer_rate=None,
                    description="Federal income tax",
                    effective_date=date(2025, 1, 1),
                    expiry_date=None,
                    status=TaxRuleStatus.ACTIVE,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            ]
            
            # Make request
            response = client.get(
                "/api/payroll/tax/rules?location=US&tax_type=FEDERAL",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0
    
    @patch('backend.modules.payroll.routes.tax_calculation_routes.require_payroll_access')
    def test_get_effective_tax_rates(self, mock_auth):
        """Test getting effective tax rates"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        with patch('backend.modules.payroll.routes.tax_calculation_routes.PayrollTaxEngine') as mock_engine:
            mock_engine_instance = Mock()
            mock_engine.return_value = mock_engine_instance
            
            # Mock tax rules
            mock_engine_instance.get_applicable_tax_rules.return_value = [
                Mock(tax_type=TaxRuleType.FEDERAL, rate=Decimal('0.22')),
                Mock(tax_type=TaxRuleType.STATE, rate=Decimal('0.05')),
                Mock(tax_type=TaxRuleType.SOCIAL_SECURITY, rate=Decimal('0.062'))
            ]
            
            # Mock tax calculation
            mock_engine_instance.calculate_taxes.return_value = Mock(
                federal_tax=Decimal('220.00'),
                state_tax=Decimal('50.00'),
                local_tax=Decimal('0.00'),
                social_security_employee=Decimal('62.00'),
                medicare_employee=Decimal('14.50'),
                total_employee_taxes=Decimal('346.50')
            )
            
            # Make request
            response = client.get(
                "/api/payroll/tax/effective-rates?location=CA&gross_amount=1000.00",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "effective_rates" in data
            assert "estimated_taxes" in data


class TestConfigurationRoutes:
    """Test cases for configuration management endpoints"""
    
    @patch('backend.modules.payroll.routes.configuration_routes.require_payroll_write')
    def test_get_payroll_configurations(self, mock_auth):
        """Test getting payroll configurations"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        with patch('backend.modules.payroll.routes.configuration_routes.PayrollConfigurationService') as mock_service:
            mock_service_instance = Mock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.get_all_payroll_configurations.return_value = [
                Mock(
                    id=1,
                    tenant_id=1,
                    config_key="overtime_threshold",
                    config_value="40",
                    is_active=True
                )
            ]
            
            response = client.get(
                "/api/payroll/config/payroll-configs",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    @patch('backend.modules.payroll.routes.configuration_routes.require_payroll_write')
    def test_create_staff_pay_policy(self, mock_auth):
        """Test creating staff pay policy"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock database
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('backend.modules.payroll.routes.configuration_routes.get_db', return_value=mock_db):
            response = client.post(
                "/api/payroll/config/pay-policies",
                json={
                    "staff_id": 123,
                    "base_hourly_rate": "25.00",
                    "overtime_multiplier": "1.5",
                    "location": "CA",
                    "health_insurance": "150.00"
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
    
    @patch('backend.modules.payroll.routes.configuration_routes.require_payroll_write')
    def test_update_staff_pay_policy(self, mock_auth):
        """Test updating staff pay policy"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock existing policy
        mock_policy = Mock()
        mock_policy.id = 1
        mock_policy.staff_id = 123
        mock_policy.base_hourly_rate = Decimal('20.00')
        
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_policy
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('backend.modules.payroll.routes.configuration_routes.get_db', return_value=mock_db):
            response = client.put(
                "/api/payroll/config/pay-policies/123",
                json={
                    "base_hourly_rate": "25.00",
                    "health_insurance": "200.00"
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200


class TestPaymentRoutes:
    """Test cases for payment management endpoints"""
    
    @patch('backend.modules.payroll.routes.payment_routes.require_payroll_access')
    def test_get_employee_payment_history(self, mock_auth):
        """Test getting employee payment history"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock payments
        mock_payments = [
            Mock(
                id=1,
                employee_id=123,
                pay_period_start=date(2025, 1, 1),
                pay_period_end=date(2025, 1, 15),
                gross_amount=Decimal('2000.00'),
                net_amount=Decimal('1500.00'),
                regular_hours=Decimal('80.00'),
                overtime_hours=Decimal('10.00'),
                status=PaymentStatus.PAID,
                processed_at=datetime.utcnow(),
                paid_at=datetime.utcnow()
            )
        ]
        
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = mock_payments
        
        with patch('backend.modules.payroll.routes.payment_routes.get_db', return_value=mock_db):
            response = client.get(
                "/api/payroll/payments/history/123",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["employee_id"] == 123
            assert "summary" in data
            assert "payments" in data
    
    @patch('backend.modules.payroll.routes.payment_routes.require_payroll_access')
    def test_get_payment_details(self, mock_auth):
        """Test getting payment details"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock payment
        mock_payment = Mock(
            id=1,
            employee_id=123,
            pay_period_start=date(2025, 1, 1),
            pay_period_end=date(2025, 1, 15),
            gross_amount=Decimal('2000.00'),
            net_amount=Decimal('1500.00'),
            regular_hours=Decimal('80.00'),
            overtime_hours=Decimal('10.00'),
            double_time_hours=Decimal('0.00'),
            holiday_hours=Decimal('0.00'),
            sick_hours=Decimal('0.00'),
            vacation_hours=Decimal('0.00'),
            regular_pay=Decimal('1600.00'),
            overtime_pay=Decimal('400.00'),
            double_time_pay=Decimal('0.00'),
            holiday_pay=Decimal('0.00'),
            sick_pay=Decimal('0.00'),
            vacation_pay=Decimal('0.00'),
            bonus_pay=Decimal('0.00'),
            commission_pay=Decimal('0.00'),
            other_earnings=Decimal('0.00'),
            federal_tax_amount=Decimal('300.00'),
            state_tax_amount=Decimal('100.00'),
            local_tax_amount=Decimal('20.00'),
            social_security_amount=Decimal('124.00'),
            medicare_amount=Decimal('29.00'),
            unemployment_amount=Decimal('10.00'),
            health_insurance_amount=Decimal('150.00'),
            dental_insurance_amount=Decimal('25.00'),
            vision_insurance_amount=Decimal('10.00'),
            retirement_401k_amount=Decimal('100.00'),
            life_insurance_amount=Decimal('20.00'),
            disability_insurance_amount=Decimal('15.00'),
            parking_fee_amount=Decimal('50.00'),
            garnishment_amount=Decimal('0.00'),
            loan_repayment_amount=Decimal('0.00'),
            other_deductions=Decimal('0.00'),
            status=PaymentStatus.PAID,
            payment_method="Direct Deposit",
            payment_reference="DD123456",
            processed_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            tenant_id=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_payment
        mock_query.all.return_value = []  # No tax applications for simplicity
        
        with patch('backend.modules.payroll.routes.payment_routes.get_db', return_value=mock_db):
            response = client.get(
                "/api/payroll/payments/1",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["employee_id"] == 123
            assert "hours" in data
            assert "earnings" in data
            assert "deductions" in data
    
    @patch('backend.modules.payroll.routes.payment_routes.require_payroll_write')
    def test_update_payment_status(self, mock_auth):
        """Test updating payment status"""
        mock_auth.return_value = Mock(id=1, email="test@example.com")
        
        # Mock payment
        mock_payment = Mock(
            id=1,
            status=PaymentStatus.PENDING,
            paid_at=None,
            payment_method=None,
            payment_reference=None,
            updated_at=datetime.utcnow()
        )
        
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_payment
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('backend.modules.payroll.routes.payment_routes.get_db', return_value=mock_db):
            response = client.put(
                "/api/payroll/payments/1/status",
                json={
                    "status": "PAID",
                    "payment_method": "Direct Deposit",
                    "payment_reference": "DD789"
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            # Verify status was updated
            assert mock_payment.status == PaymentStatus.PAID


class TestPayrollHealthCheck:
    """Test health check endpoint"""
    
    def test_payroll_health_check(self):
        """Test payroll module health check"""
        response = client.get("/api/payroll/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["module"] == "payroll"
        assert "timestamp" in data