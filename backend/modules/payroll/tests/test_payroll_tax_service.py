import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from ..services.payroll_tax_service import PayrollTaxService
from ..services.payroll_tax_engine import PayrollTaxEngine
from ..models.payroll_models import EmployeePayment, PayrollPolicy
from ..schemas.payroll_tax_schemas import (
    PayrollTaxServiceRequest, PayrollTaxCalculationResponse,
    TaxBreakdown, TaxRuleValidationRequest
)


class TestPayrollTaxService:
    """Test suite for PayrollTaxService."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_tax_engine(self):
        """Mock tax engine."""
        return Mock(spec=PayrollTaxEngine)
    
    @pytest.fixture
    def tax_service(self, mock_db):
        """Tax service instance with mocked dependencies."""
        with patch('backend.modules.payroll.services.payroll_tax_service.PayrollTaxEngine') as mock_engine_class:
            service = PayrollTaxService(mock_db)
            service.tax_engine = Mock(spec=PayrollTaxEngine)
            return service
    
    @pytest.fixture
    def sample_service_request(self):
        """Sample service request."""
        return PayrollTaxServiceRequest(
            employee_payment_id=None,
            staff_id=123,
            payroll_policy_id=456,
            pay_period_start=date(2025, 7, 1),
            pay_period_end=date(2025, 7, 15),
            gross_pay=Decimal('5000.00'),
            location="California",
            tenant_id=1
        )
    
    @pytest.fixture
    def sample_tax_calculation(self):
        """Sample tax calculation response."""
        return PayrollTaxCalculationResponse(
            gross_pay=Decimal('5000.00'),
            total_taxes=Decimal('1500.00'),
            net_pay=Decimal('3500.00'),
            tax_breakdown=TaxBreakdown(
                federal_tax=Decimal('1100.00'),
                state_tax=Decimal('400.00'),
                social_security_tax=Decimal('310.00'),
                medicare_tax=Decimal('72.50')
            ),
            tax_applications=[],
            calculation_date=datetime.utcnow()
        )
    
    def test_calculate_and_save_taxes_without_payment_id(
        self, tax_service, sample_service_request, sample_tax_calculation
    ):
        """Test tax calculation without saving to database."""
        # Mock tax engine calculation
        tax_service.tax_engine.calculate_payroll_taxes.return_value = sample_tax_calculation
        
        # Calculate taxes
        response = tax_service.calculate_and_save_taxes(sample_service_request)
        
        # Verify response
        assert response.employee_payment_id is None
        assert response.tax_calculation == sample_tax_calculation
        assert response.applications_saved is False
        
        # Verify tax engine was called with correct parameters
        tax_service.tax_engine.calculate_payroll_taxes.assert_called_once()
        call_args = tax_service.tax_engine.calculate_payroll_taxes.call_args[0][0]
        assert call_args.employee_id == 123
        assert call_args.location == "California"
        assert call_args.gross_pay == Decimal('5000.00')
        assert call_args.pay_date == date(2025, 7, 15)
        assert call_args.tenant_id == 1
    
    def test_calculate_and_save_taxes_with_payment_id(
        self, tax_service, sample_service_request, sample_tax_calculation
    ):
        """Test tax calculation with saving to database."""
        # Set payment ID
        sample_service_request.employee_payment_id = 789
        
        # Mock tax engine methods
        tax_service.tax_engine.calculate_payroll_taxes.return_value = sample_tax_calculation
        tax_service.tax_engine.save_tax_applications.return_value = []
        
        # Calculate taxes
        response = tax_service.calculate_and_save_taxes(sample_service_request)
        
        # Verify response
        assert response.employee_payment_id == 789
        assert response.tax_calculation == sample_tax_calculation
        assert response.applications_saved is True
        
        # Verify tax applications were saved
        tax_service.tax_engine.save_tax_applications.assert_called_once_with(
            employee_payment_id=789,
            tax_applications=sample_tax_calculation.tax_applications
        )
    
    def test_update_employee_payment_taxes_success(
        self, tax_service, mock_db, sample_tax_calculation
    ):
        """Test updating existing employee payment with tax calculations."""
        # Create mock employee payment
        mock_policy = Mock(spec=PayrollPolicy)
        mock_policy.location = "California"
        
        mock_payment = Mock(spec=EmployeePayment)
        mock_payment.id = 789
        mock_payment.staff_id = 123
        mock_payment.payroll_policy_id = 456
        mock_payment.pay_period_start = datetime(2025, 7, 1)
        mock_payment.pay_period_end = datetime(2025, 7, 15)
        mock_payment.gross_pay = Decimal('5000.00')
        mock_payment.tenant_id = 1
        mock_payment.payroll_policy = mock_policy
        mock_payment.insurance_deduction = Decimal('100.00')
        mock_payment.retirement_deduction = Decimal('200.00')
        mock_payment.other_deductions = Decimal('50.00')
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_payment
        mock_db.query.return_value = mock_query
        
        # Mock tax calculation
        tax_service.tax_engine.calculate_payroll_taxes.return_value = sample_tax_calculation
        tax_service.tax_engine.save_tax_applications.return_value = []
        
        # Update payment taxes
        response = tax_service.update_employee_payment_taxes(789)
        
        # Verify database query
        mock_db.query.assert_called_with(EmployeePayment)
        
        # Verify payment fields were updated
        assert mock_payment.federal_tax == Decimal('1100.00')
        assert mock_payment.state_tax == Decimal('400.00')
        assert mock_payment.social_security_tax == Decimal('310.00')
        assert mock_payment.medicare_tax == Decimal('72.50')
        
        # Verify total deductions calculation
        expected_total_deductions = (
            Decimal('1100.00') + Decimal('400.00') + Decimal('0.00') +  # taxes
            Decimal('310.00') + Decimal('72.50') +  # payroll taxes
            Decimal('100.00') + Decimal('200.00') + Decimal('50.00')  # other deductions
        )
        assert mock_payment.total_deductions == expected_total_deductions
        
        # Verify net pay calculation
        expected_net_pay = Decimal('5000.00') - expected_total_deductions
        assert mock_payment.net_pay == expected_net_pay
        
        # Verify database commit
        mock_db.commit.assert_called_once()
    
    def test_update_employee_payment_taxes_not_found(
        self, tax_service, mock_db
    ):
        """Test updating non-existent employee payment."""
        # Mock database query to return None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Test that ValueError is raised
        with pytest.raises(ValueError, match="Employee payment 999 not found"):
            tax_service.update_employee_payment_taxes(999)
    
    def test_validate_tax_setup_complete(self, tax_service):
        """Test tax setup validation with complete configuration."""
        # Mock jurisdiction summary
        complete_summary = {
            "federal": [{"rule_name": "Federal Income Tax", "tax_type": "FEDERAL"}],
            "state": [{"rule_name": "State Tax", "tax_type": "STATE"}],
            "local": [],
            "payroll_taxes": [
                {"rule_name": "Social Security", "tax_type": "SOCIAL_SECURITY"},
                {"rule_name": "Medicare", "tax_type": "MEDICARE"}
            ]
        }
        
        tax_service.tax_engine.get_jurisdiction_summary.return_value = complete_summary
        
        # Create validation request
        request = TaxRuleValidationRequest(
            location="California",
            pay_date=date(2025, 7, 15),
            tenant_id=1
        )
        
        # Validate setup
        response = tax_service.validate_tax_setup(request)
        
        # Verify response
        assert response.location == "California"
        assert response.total_rules == 4
        assert response.jurisdiction_summary == complete_summary
        assert len(response.missing_jurisdictions) == 0
        assert len(response.potential_issues) == 0
    
    def test_validate_tax_setup_missing_jurisdictions(self, tax_service):
        """Test tax setup validation with missing jurisdictions."""
        # Mock incomplete jurisdiction summary
        incomplete_summary = {
            "federal": [],  # Missing federal rules
            "state": [{"rule_name": "State Tax", "tax_type": "STATE"}],
            "local": [],
            "payroll_taxes": [
                {"rule_name": "Social Security", "tax_type": "SOCIAL_SECURITY"}
                # Missing Medicare
            ]
        }
        
        tax_service.tax_engine.get_jurisdiction_summary.return_value = incomplete_summary
        
        # Create validation request
        request = TaxRuleValidationRequest(
            location="Texas",
            pay_date=date(2025, 7, 15)
        )
        
        # Validate setup
        response = tax_service.validate_tax_setup(request)
        
        # Verify missing jurisdictions detected
        assert "federal" in response.missing_jurisdictions
        assert "Missing Medicare tax rule" in response.potential_issues
        assert response.total_rules == 2
    
    def test_get_effective_tax_rates(self, tax_service, sample_tax_calculation):
        """Test effective tax rate calculation."""
        # Mock tax calculation
        tax_service.tax_engine.calculate_payroll_taxes.return_value = sample_tax_calculation
        
        # Get effective rates
        rates = tax_service.get_effective_tax_rates(
            location="California",
            gross_pay=Decimal('5000.00'),
            pay_date=date(2025, 7, 15),
            tenant_id=1
        )
        
        # Verify rates
        assert rates["gross_pay"] == 5000.0
        assert rates["total_tax_rate"] == 30.0  # 1500/5000 * 100
        assert rates["federal_rate"] == 22.0    # 1100/5000 * 100
        assert rates["state_rate"] == 8.0       # 400/5000 * 100
        assert rates["social_security_rate"] == 6.2  # 310/5000 * 100
        assert rates["medicare_rate"] == 1.45   # 72.50/5000 * 100
        assert rates["net_pay_rate"] == 70.0    # 3500/5000 * 100
        assert rates["total_taxes"] == 1500.0
        assert rates["net_pay"] == 3500.0
    
    def test_get_effective_tax_rates_zero_gross_pay(self, tax_service):
        """Test effective tax rate calculation with zero gross pay."""
        rates = tax_service.get_effective_tax_rates(
            location="California",
            gross_pay=Decimal('0.00'),
            pay_date=date(2025, 7, 15)
        )
        
        # Should return empty dict for zero gross pay
        assert rates == {}
    
    def test_bulk_recalculate_taxes_success(self, tax_service, mock_db):
        """Test bulk tax recalculation for multiple employees."""
        # Create mock employee payments
        mock_payment1 = Mock(spec=EmployeePayment)
        mock_payment1.id = 101
        mock_payment1.staff_id = 201
        
        mock_payment2 = Mock(spec=EmployeePayment)
        mock_payment2.id = 102
        mock_payment2.staff_id = 202
        
        # Mock database query
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_payment1, mock_payment2]
        mock_db.query.return_value = mock_query
        
        # Mock successful updates
        with patch.object(tax_service, 'update_employee_payment_taxes') as mock_update:
            mock_update.return_value = Mock()
            
            # Perform bulk recalculation
            result = tax_service.bulk_recalculate_taxes(
                location="California",
                pay_period_start=date(2025, 7, 1),
                pay_period_end=date(2025, 7, 15),
                tenant_id=1
            )
        
        # Verify results
        assert result["total_payments"] == 2
        assert result["updated_count"] == 2
        assert result["error_count"] == 0
        assert len(result["errors"]) == 0
        
        # Verify update calls
        assert mock_update.call_count == 2
        mock_update.assert_any_call(101)
        mock_update.assert_any_call(102)
    
    def test_bulk_recalculate_taxes_with_errors(self, tax_service, mock_db):
        """Test bulk tax recalculation with some failures."""
        # Create mock employee payments
        mock_payment1 = Mock(spec=EmployeePayment)
        mock_payment1.id = 101
        mock_payment1.staff_id = 201
        
        mock_payment2 = Mock(spec=EmployeePayment)
        mock_payment2.id = 102
        mock_payment2.staff_id = 202
        
        # Mock database query
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_payment1, mock_payment2]
        mock_db.query.return_value = mock_query
        
        # Mock mixed success/failure updates
        with patch.object(tax_service, 'update_employee_payment_taxes') as mock_update:
            def side_effect(payment_id):
                if payment_id == 101:
                    return Mock()  # Success
                else:
                    raise Exception("Tax calculation failed")  # Failure
            
            mock_update.side_effect = side_effect
            
            # Perform bulk recalculation
            result = tax_service.bulk_recalculate_taxes(
                location="California",
                pay_period_start=date(2025, 7, 1),
                pay_period_end=date(2025, 7, 15)
            )
        
        # Verify results
        assert result["total_payments"] == 2
        assert result["updated_count"] == 1
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        
        # Verify error details
        error = result["errors"][0]
        assert error["employee_payment_id"] == 102
        assert error["staff_id"] == 202
        assert "Tax calculation failed" in error["error"]