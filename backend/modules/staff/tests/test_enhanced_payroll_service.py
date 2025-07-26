"""
Unit tests for the Enhanced Payroll Service.

Tests cover:
- Single staff payroll processing
- Batch payroll processing
- Payroll summary generation
- Employee payment history
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from ..services.enhanced_payroll_service import EnhancedPayrollService
from ..services.enhanced_payroll_engine import HoursBreakdown, EarningsBreakdown, DeductionsBreakdown
from ..models.payroll_models import Payroll
from ..schemas.payroll_schemas import PayrollResponse, PayrollBreakdown
from ...payroll.models.payroll_models import EmployeePayment


class TestEnhancedPayrollService:
    """Test suite for Enhanced Payroll Service."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def payroll_service(self, mock_db):
        """Create a payroll service instance with mocked dependencies."""
        with patch('modules.staff.services.enhanced_payroll_service.EnhancedPayrollEngine'):
            return EnhancedPayrollService(mock_db)
    
    @pytest.fixture
    def sample_payroll_calculation(self):
        """Create a sample payroll calculation result."""
        return {
            'staff_id': 1,
            'pay_period_start': date(2024, 1, 15),
            'pay_period_end': date(2024, 1, 29),
            'hours_breakdown': HoursBreakdown(
                regular_hours=Decimal('40.00'),
                overtime_hours=Decimal('8.00')
            ),
            'earnings_breakdown': EarningsBreakdown(
                regular_pay=Decimal('600.00'),
                overtime_pay=Decimal('180.00'),
                bonus=Decimal('50.00')
            ),
            'deductions_breakdown': DeductionsBreakdown(
                federal_tax=Decimal('125.00'),
                state_tax=Decimal('42.00'),
                health_insurance=Decimal('55.20')
            ),
            'gross_pay': Decimal('830.00'),
            'total_deductions': Decimal('222.20'),
            'net_pay': Decimal('607.80'),
            'policy': Mock()
        }
    
    @pytest.fixture
    def sample_payroll_record(self):
        """Create a sample Payroll database record."""
        return Payroll(
            id=1,
            staff_id=1,
            period="2024-01",
            gross_pay=830.00,
            deductions=222.20,
            net_pay=607.80,
            created_at=datetime(2024, 1, 31, 10, 0, 0)
        )
    
    @pytest.mark.asyncio
    async def test_process_payroll_for_staff_new_record(
        self, 
        payroll_service, 
        mock_db, 
        sample_payroll_calculation,
        sample_payroll_record
    ):
        """Test processing payroll for staff with new payroll record."""
        # Mock the engine computation
        payroll_service.engine.compute_comprehensive_payroll = AsyncMock(
            return_value=sample_payroll_calculation
        )
        payroll_service.engine.create_employee_payment_record = AsyncMock(
            return_value=Mock(spec=EmployeePayment)
        )
        
        # Mock database operations for new record
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        with patch('modules.staff.services.enhanced_payroll_service.Payroll', return_value=sample_payroll_record):
            result = await payroll_service.process_payroll_for_staff(
                staff_id=1,
                pay_period_start=date(2024, 1, 15),
                pay_period_end=date(2024, 1, 29)
            )
        
        assert isinstance(result, PayrollResponse)
        assert result.staff_id == 1
        assert result.period == "2024-01"
        assert result.gross_pay == 830.00
        assert result.deductions == 222.20
        assert result.net_pay == 607.80
        assert isinstance(result.breakdown, PayrollBreakdown)
    
    @pytest.mark.asyncio
    async def test_process_payroll_for_staff_existing_record(
        self, 
        payroll_service, 
        mock_db, 
        sample_payroll_calculation,
        sample_payroll_record
    ):
        """Test processing payroll for staff with existing payroll record."""
        # Mock the engine computation
        payroll_service.engine.compute_comprehensive_payroll = AsyncMock(
            return_value=sample_payroll_calculation
        )
        payroll_service.engine.create_employee_payment_record = AsyncMock(
            return_value=Mock(spec=EmployeePayment)
        )
        
        # Mock database operations for existing record
        mock_db.query.return_value.filter.return_value.first.return_value = sample_payroll_record
        mock_db.commit.return_value = None
        
        result = await payroll_service.process_payroll_for_staff(
            staff_id=1,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        assert isinstance(result, PayrollResponse)
        assert result.staff_id == 1
        # Verify the record was updated
        assert sample_payroll_record.gross_pay == 830.00
        assert sample_payroll_record.deductions == 222.20
        assert sample_payroll_record.net_pay == 607.80
    
    @pytest.mark.asyncio
    async def test_process_payroll_batch_success(self, payroll_service):
        """Test successful batch payroll processing."""
        # Mock successful processing for multiple staff
        mock_payroll_response = Mock(spec=PayrollResponse)
        mock_payroll_response.staff_id = 1
        
        payroll_service.process_payroll_for_staff = AsyncMock(return_value=mock_payroll_response)
        
        staff_ids = [1, 2, 3]
        results = await payroll_service.process_payroll_batch(
            staff_ids=staff_ids,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        assert len(results) == 3
        assert all(isinstance(result, PayrollResponse) for result in results)
        assert payroll_service.process_payroll_for_staff.call_count == 3
    
    @pytest.mark.asyncio
    async def test_process_payroll_batch_with_errors(self, payroll_service, capsys):
        """Test batch payroll processing with some failures."""
        # Mock mixed success/failure
        def mock_process_side_effect(staff_id, *args, **kwargs):
            if staff_id == 2:
                raise ValueError("Staff not found")
            return Mock(spec=PayrollResponse)
        
        payroll_service.process_payroll_for_staff = AsyncMock(side_effect=mock_process_side_effect)
        
        staff_ids = [1, 2, 3]
        results = await payroll_service.process_payroll_batch(
            staff_ids=staff_ids,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        # Should return 2 successful results (staff 1 and 3)
        assert len(results) == 2
        
        # Should print error information
        captured = capsys.readouterr()
        assert "Payroll batch processing errors" in captured.out
    
    @pytest.mark.asyncio
    async def test_get_payroll_summary_with_data(self, payroll_service, mock_db):
        """Test getting payroll summary with employee payment data."""
        # Mock employee payment records
        mock_payments = [
            Mock(
                gross_amount=Decimal('800.00'),
                net_amount=Decimal('600.00'),
                federal_tax_amount=Decimal('120.00'),
                state_tax_amount=Decimal('40.00'),
                local_tax_amount=Decimal('0.00'),
                social_security_amount=Decimal('50.00'),
                medicare_amount=Decimal('12.00'),
                health_insurance_amount=Decimal('55.00'),
                retirement_amount=Decimal('25.00'),
                other_deductions_amount=Decimal('10.00'),
                regular_hours=Decimal('40.00'),
                overtime_hours=Decimal('5.00')
            ),
            Mock(
                gross_amount=Decimal('600.00'),
                net_amount=Decimal('450.00'),
                federal_tax_amount=Decimal('90.00'),
                state_tax_amount=Decimal('30.00'),
                local_tax_amount=Decimal('0.00'),
                social_security_amount=Decimal('37.50'),
                medicare_amount=Decimal('9.00'),
                health_insurance_amount=Decimal('55.00'),
                retirement_amount=Decimal('25.00'),
                other_deductions_amount=Decimal('10.00'),
                regular_hours=Decimal('35.00'),
                overtime_hours=Decimal('0.00')
            )
        ]
        
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_payments
        
        summary = await payroll_service.get_payroll_summary(
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        assert summary['total_employees'] == 2
        assert summary['total_gross_pay'] == Decimal('1400.00')
        assert summary['total_net_pay'] == Decimal('1050.00')
        assert summary['total_deductions'] == Decimal('350.00')
        assert summary['total_tax_deductions'] == Decimal('388.50')
        assert summary['total_benefit_deductions'] == Decimal('180.00')
        assert summary['average_hours_per_employee'] == Decimal('40.00')  # (45 + 35) / 2
    
    @pytest.mark.asyncio
    async def test_get_payroll_summary_no_data(self, payroll_service, mock_db):
        """Test getting payroll summary with no employee payment data."""
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        
        summary = await payroll_service.get_payroll_summary(
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        assert summary['total_employees'] == 0
        assert summary['total_gross_pay'] == Decimal('0.00')
        assert summary['total_net_pay'] == Decimal('0.00')
        assert summary['total_deductions'] == Decimal('0.00')
        assert summary['average_hours_per_employee'] == Decimal('0.00')
    
    def test_create_payroll_breakdown(self, payroll_service, sample_payroll_calculation):
        """Test creating PayrollBreakdown from payroll calculation."""
        breakdown = payroll_service._create_payroll_breakdown(sample_payroll_calculation)
        
        assert isinstance(breakdown, PayrollBreakdown)
        assert breakdown.hours_worked == 40.00
        assert breakdown.overtime_hours == 8.00
        assert breakdown.gross_earnings == 830.00
        assert breakdown.tax_deductions == 167.00  # federal + state
        assert breakdown.total_deductions == 222.20
    
    @pytest.mark.asyncio
    async def test_get_employee_payment_history(self, payroll_service, mock_db):
        """Test getting employee payment history."""
        mock_payments = [
            Mock(
                id=1,
                pay_period_start=date(2024, 1, 15),
                pay_period_end=date(2024, 1, 29),
                gross_amount=Decimal('800.00'),
                net_amount=Decimal('600.00'),
                regular_hours=Decimal('40.00'),
                overtime_hours=Decimal('5.00'),
                processed_at=datetime(2024, 1, 30, 10, 0, 0)
            ),
            Mock(
                id=2,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                gross_amount=Decimal('750.00'),
                net_amount=Decimal('565.00'),
                regular_hours=Decimal('38.00'),
                overtime_hours=Decimal('2.00'),
                processed_at=datetime(2024, 1, 16, 10, 0, 0)
            )
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_payments
        
        history = await payroll_service.get_employee_payment_history(staff_id=1, limit=2)
        
        assert len(history) == 2
        assert history[0]['id'] == 1
        assert history[0]['gross_amount'] == Decimal('800.00')
        assert history[0]['net_amount'] == Decimal('600.00')
        assert history[1]['id'] == 2
    
    @pytest.mark.asyncio
    async def test_get_employee_payment_history_with_tenant_filter(self, payroll_service, mock_db):
        """Test getting employee payment history with tenant filtering."""
        mock_payments = [Mock(id=1)]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_payments
        
        await payroll_service.get_employee_payment_history(staff_id=1, tenant_id=123)
        
        # Verify tenant filter was applied
        filter_calls = mock_query.filter.call_args_list
        assert len(filter_calls) == 2  # One for staff_id, one for tenant_id
    
    @pytest.mark.asyncio
    async def test_recalculate_payroll(self, payroll_service, mock_db):
        """Test recalculating payroll for a staff member."""
        # Mock existing payment record
        existing_payment = Mock(spec=EmployeePayment)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_payment
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None
        
        # Mock the recalculation
        mock_response = Mock(spec=PayrollResponse)
        payroll_service.process_payroll_for_staff = AsyncMock(return_value=mock_response)
        
        result = await payroll_service.recalculate_payroll(
            staff_id=1,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        # Verify existing record was deleted
        mock_db.delete.assert_called_once_with(existing_payment)
        mock_db.commit.assert_called_once()
        
        # Verify new calculation was performed
        payroll_service.process_payroll_for_staff.assert_called_once()
        assert result == mock_response
    
    @pytest.mark.asyncio
    async def test_recalculate_payroll_no_existing_record(self, payroll_service, mock_db):
        """Test recalculating payroll when no existing record exists."""
        # Mock no existing payment record
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock the calculation
        mock_response = Mock(spec=PayrollResponse)
        payroll_service.process_payroll_for_staff = AsyncMock(return_value=mock_response)
        
        result = await payroll_service.recalculate_payroll(
            staff_id=1,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        # Verify no delete was attempted
        mock_db.delete.assert_not_called()
        
        # Verify calculation was still performed
        payroll_service.process_payroll_for_staff.assert_called_once()
        assert result == mock_response


class TestPayrollServiceErrorHandling:
    """Test error handling and edge cases for payroll service."""
    
    @pytest.fixture
    def payroll_service(self):
        """Create payroll service for error testing."""
        mock_db = Mock(spec=Session)
        with patch('modules.staff.services.enhanced_payroll_service.EnhancedPayrollEngine'):
            return EnhancedPayrollService(mock_db)
    
    @pytest.mark.asyncio
    async def test_process_payroll_engine_error(self, payroll_service):
        """Test handling engine computation errors."""
        payroll_service.engine.compute_comprehensive_payroll = AsyncMock(
            side_effect=ValueError("Invalid staff ID")
        )
        
        with pytest.raises(ValueError, match="Invalid staff ID"):
            await payroll_service.process_payroll_for_staff(
                staff_id=999,
                pay_period_start=date(2024, 1, 15),
                pay_period_end=date(2024, 1, 29)
            )
    
    @pytest.mark.asyncio
    async def test_get_payroll_summary_with_none_values(self, payroll_service, mock_db):
        """Test payroll summary calculation with None values in database."""
        # Mock payments with None values for optional fields
        mock_payments = [
            Mock(
                gross_amount=Decimal('800.00'),
                net_amount=Decimal('600.00'),
                federal_tax_amount=None,
                state_tax_amount=Decimal('40.00'),
                local_tax_amount=None,
                social_security_amount=None,
                medicare_amount=None,
                health_insurance_amount=Decimal('55.00'),
                retirement_amount=None,
                other_deductions_amount=None,
                regular_hours=Decimal('40.00'),
                overtime_hours=None
            )
        ]
        
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_payments
        
        summary = await payroll_service.get_payroll_summary(
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29)
        )
        
        # Should handle None values gracefully
        assert summary['total_employees'] == 1
        assert summary['total_gross_pay'] == Decimal('800.00')
        assert summary['total_tax_deductions'] == Decimal('40.00')  # Only state tax
        assert summary['total_benefit_deductions'] == Decimal('55.00')  # Only health insurance
    
    def test_create_payroll_breakdown_with_minimal_data(self, payroll_service):
        """Test creating breakdown with minimal payroll calculation data."""
        minimal_calc = {
            'hours_breakdown': HoursBreakdown(
                regular_hours=Decimal('20.00'),
                overtime_hours=Decimal('0.00')
            ),
            'earnings_breakdown': EarningsBreakdown(
                regular_pay=Decimal('300.00'),
                overtime_pay=Decimal('0.00')
            ),
            'deductions_breakdown': DeductionsBreakdown(
                federal_tax=Decimal('60.00')
            ),
            'policy': Mock(
                base_hourly_rate=Decimal('15.00'),
                overtime_multiplier=Decimal('1.5')
            )
        }
        
        breakdown = payroll_service._create_payroll_breakdown(minimal_calc)
        
        assert breakdown.hours_worked == 20.00
        assert breakdown.hourly_rate == 15.00
        assert breakdown.overtime_hours == 0.00
        assert breakdown.gross_earnings == 300.00
        assert breakdown.tax_deductions == 60.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])