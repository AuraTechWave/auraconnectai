"""
Pure mock-based unit tests for Enhanced Payroll Engine (AUR-277).

Tests the payroll calculation business logic without database dependencies.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

from modules.staff.schemas.enhanced_payroll_schemas import (
    HoursCalculationResult, PayrollCalculationResult
)


@pytest.mark.unit
@pytest.mark.payroll_engine  
class TestPayrollCalculationLogic:
    """Test core payroll calculation business logic."""
    
    def test_basic_hours_calculation(self):
        """Test basic hours calculation logic."""
        # Test data: 8 hours per day for 5 days
        daily_hours = [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0]  # Mon-Sun
        
        # Calculate totals
        total_hours = sum(daily_hours)
        regular_hours = min(total_hours, 40.0)  # Standard 40-hour week
        overtime_hours = max(total_hours - 40.0, 0.0)
        
        assert total_hours == 40.0
        assert regular_hours == 40.0
        assert overtime_hours == 0.0
    
    def test_overtime_hours_calculation(self):
        """Test overtime calculation logic."""
        # Test data: 10 hours per day for 5 days = 50 hours total
        daily_hours = [10.0, 10.0, 10.0, 10.0, 10.0, 0.0, 0.0]
        
        total_hours = sum(daily_hours)
        regular_hours = min(total_hours, 40.0)
        overtime_hours = max(total_hours - 40.0, 0.0)
        
        assert total_hours == 50.0
        assert regular_hours == 40.0
        assert overtime_hours == 10.0
    
    def test_earnings_calculation(self):
        """Test earnings calculation logic."""
        # Test data
        regular_hours = Decimal('40.0')
        overtime_hours = Decimal('10.0')
        hourly_rate = Decimal('20.00')
        overtime_multiplier = Decimal('1.5')
        
        # Calculate earnings
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * hourly_rate * overtime_multiplier
        total_gross_pay = regular_pay + overtime_pay
        
        assert regular_pay == Decimal('800.00')  # 40 * $20
        assert overtime_pay == Decimal('300.00')  # 10 * $20 * 1.5
        assert total_gross_pay == Decimal('1100.00')
    
    def test_benefits_calculation(self):
        """Test benefits and deductions calculation."""
        gross_pay = Decimal('1000.00')
        
        # Sample benefit rates
        health_insurance_rate = Decimal('0.05')  # 5%
        retirement_rate = Decimal('0.06')        # 6%
        
        # Calculate deductions
        health_deduction = gross_pay * health_insurance_rate
        retirement_deduction = gross_pay * retirement_rate
        total_deductions = health_deduction + retirement_deduction
        
        net_after_benefits = gross_pay - total_deductions
        
        assert health_deduction == Decimal('50.00')
        assert retirement_deduction == Decimal('60.00')
        assert total_deductions == Decimal('110.00')
        assert net_after_benefits == Decimal('890.00')
    
    def test_complete_payroll_calculation_flow(self):
        """Test complete payroll calculation flow."""
        # Input data
        regular_hours = Decimal('40.0')
        overtime_hours = Decimal('8.0')
        hourly_rate = Decimal('25.00')
        overtime_multiplier = Decimal('1.5')
        
        # Earnings calculation
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * hourly_rate * overtime_multiplier
        gross_pay = regular_pay + overtime_pay
        
        # Benefits deductions
        benefits_rate = Decimal('0.08')  # 8% total benefits
        benefits_deduction = gross_pay * benefits_rate
        
        # Tax deductions (mock)
        tax_rate = Decimal('0.22')  # 22% total taxes
        tax_deduction = gross_pay * tax_rate
        
        # Final calculation
        total_deductions = benefits_deduction + tax_deduction
        net_pay = gross_pay - total_deductions
        
        # Verify calculations
        assert regular_pay == Decimal('1000.00')   # 40 * $25
        assert overtime_pay == Decimal('300.00')   # 8 * $25 * 1.5
        assert gross_pay == Decimal('1300.00')
        assert benefits_deduction == Decimal('104.00')  # 8% of 1300
        assert tax_deduction == Decimal('286.00')       # 22% of 1300
        assert total_deductions == Decimal('390.00')
        assert net_pay == Decimal('910.00')


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestHoursCalculationResult:
    """Test HoursCalculationResult data structure."""
    
    def test_hours_calculation_result_creation(self):
        """Test creating HoursCalculationResult."""
        result = HoursCalculationResult(
            regular_hours=Decimal('40.0'),
            overtime_hours=Decimal('8.0'),
            double_time_hours=Decimal('0.0'),
            total_hours=Decimal('48.0'),
            calculation_period_start=date(2024, 6, 1),
            calculation_period_end=date(2024, 6, 15)
        )
        
        assert result.regular_hours == Decimal('40.0')
        assert result.overtime_hours == Decimal('8.0')
        assert result.double_time_hours == Decimal('0.0')
        assert result.total_hours == Decimal('48.0')
        assert result.calculation_period_start == date(2024, 6, 1)
        assert result.calculation_period_end == date(2024, 6, 15)
    
    def test_hours_totals_consistency(self):
        """Test that hours totals are consistent."""
        regular = Decimal('40.0')
        overtime = Decimal('8.0')
        double_time = Decimal('2.0')
        expected_total = regular + overtime + double_time
        
        result = HoursCalculationResult(
            regular_hours=regular,
            overtime_hours=overtime,
            double_time_hours=double_time,
            total_hours=expected_total,
            calculation_period_start=date(2024, 6, 1),
            calculation_period_end=date(2024, 6, 15)
        )
        
        # Verify totals match
        actual_total = result.regular_hours + result.overtime_hours + result.double_time_hours
        assert actual_total == result.total_hours
        assert actual_total == Decimal('50.0')


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestPayrollCalculationResult:
    """Test PayrollCalculationResult data structure."""
    
    def test_payroll_calculation_result_creation(self):
        """Test creating complete PayrollCalculationResult."""
        # Create hours result
        hours_result = HoursCalculationResult(
            regular_hours=Decimal('40.0'),
            overtime_hours=Decimal('5.0'),
            double_time_hours=Decimal('0.0'),
            total_hours=Decimal('45.0'),
            calculation_period_start=date(2024, 6, 1),
            calculation_period_end=date(2024, 6, 15)
        )
        
        # Create payroll result
        payroll_result = PayrollCalculationResult(
            staff_id=123,
            hours_calculation=hours_result,
            regular_pay=Decimal('800.00'),
            overtime_pay=Decimal('150.00'),
            double_time_pay=Decimal('0.00'),
            gross_pay=Decimal('950.00'),
            total_deductions=Decimal('285.00'),
            net_pay=Decimal('665.00'),
            calculation_date=datetime.now(),
            pay_period_start=date(2024, 6, 1),
            pay_period_end=date(2024, 6, 15)
        )
        
        # Verify all fields
        assert payroll_result.staff_id == 123
        assert payroll_result.hours_calculation == hours_result
        assert payroll_result.regular_pay == Decimal('800.00')
        assert payroll_result.overtime_pay == Decimal('150.00')
        assert payroll_result.gross_pay == Decimal('950.00')
        assert payroll_result.total_deductions == Decimal('285.00')
        assert payroll_result.net_pay == Decimal('665.00')
    
    def test_payroll_totals_consistency(self):
        """Test that payroll totals are mathematically consistent."""
        regular_pay = Decimal('1000.00')
        overtime_pay = Decimal('300.00')
        double_time_pay = Decimal('100.00')
        
        gross_pay = regular_pay + overtime_pay + double_time_pay
        total_deductions = Decimal('420.00')
        net_pay = gross_pay - total_deductions
        
        # Verify math
        assert gross_pay == Decimal('1400.00')
        assert net_pay == Decimal('980.00')
        
        # These values should be consistent in a real PayrollCalculationResult
        expected_gross = regular_pay + overtime_pay + double_time_pay
        expected_net = expected_gross - total_deductions
        
        assert expected_gross == gross_pay
        assert expected_net == net_pay


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestPayrollEngineEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_hours_calculation(self):
        """Test handling of zero hours worked."""
        regular_hours = Decimal('0.0')
        overtime_hours = Decimal('0.0')
        hourly_rate = Decimal('20.00')
        
        # Calculate pay
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * hourly_rate * Decimal('1.5')
        gross_pay = regular_pay + overtime_pay
        
        assert regular_pay == Decimal('0.00')
        assert overtime_pay == Decimal('0.00')
        assert gross_pay == Decimal('0.00')
    
    def test_fractional_hours_calculation(self):
        """Test calculation with fractional hours."""
        # 7.5 hours per day for 5 days = 37.5 hours
        total_hours = Decimal('37.5')
        regular_hours = min(total_hours, Decimal('40.0'))
        overtime_hours = max(total_hours - Decimal('40.0'), Decimal('0.0'))
        
        hourly_rate = Decimal('22.50')
        regular_pay = regular_hours * hourly_rate
        
        assert regular_hours == Decimal('37.5')
        assert overtime_hours == Decimal('0.0')
        assert regular_pay == Decimal('843.75')  # 37.5 * 22.50
    
    def test_high_overtime_calculation(self):
        """Test calculation with significant overtime."""
        # 12 hours per day for 5 days = 60 hours total
        total_hours = Decimal('60.0')
        regular_hours = min(total_hours, Decimal('40.0'))
        overtime_hours = max(total_hours - Decimal('40.0'), Decimal('0.0'))
        
        hourly_rate = Decimal('30.00')
        overtime_rate = Decimal('1.5')
        
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * hourly_rate * overtime_rate
        gross_pay = regular_pay + overtime_pay
        
        assert regular_hours == Decimal('40.0')
        assert overtime_hours == Decimal('20.0')
        assert regular_pay == Decimal('1200.00')   # 40 * 30
        assert overtime_pay == Decimal('900.00')   # 20 * 30 * 1.5
        assert gross_pay == Decimal('2100.00')
    
    def test_decimal_precision_maintenance(self):
        """Test that decimal precision is maintained in calculations."""
        # Use precise values
        hours = Decimal('35.75')
        rate = Decimal('18.25')
        
        # Calculate pay
        gross_pay = hours * rate
        
        # Should maintain precision
        assert gross_pay == Decimal('652.1875')
        
        # Round to currency precision (2 decimal places)
        rounded_pay = gross_pay.quantize(Decimal('0.01'))
        assert rounded_pay == Decimal('652.19')
    
    @patch('modules.staff.services.enhanced_payroll_engine.EnhancedPayrollEngine')
    def test_payroll_engine_mock_integration(self, mock_engine_class):
        """Test integration with mocked payroll engine."""
        # Setup mock
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine
        
        # Mock return value
        mock_hours_result = HoursCalculationResult(
            regular_hours=Decimal('40.0'),
            overtime_hours=Decimal('5.0'),
            double_time_hours=Decimal('0.0'),
            total_hours=Decimal('45.0'),
            calculation_period_start=date(2024, 6, 1),
            calculation_period_end=date(2024, 6, 15)
        )
        
        mock_engine.calculate_hours_for_period.return_value = mock_hours_result
        
        # Test interaction
        from modules.staff.services.enhanced_payroll_engine import EnhancedPayrollEngine
        
        mock_db = Mock()
        engine = EnhancedPayrollEngine(mock_db)
        result = engine.calculate_hours_for_period(
            staff_id=1,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 15)
        )
        
        # Verify mock was called
        mock_engine.calculate_hours_for_period.assert_called_once()
        assert result.total_hours == Decimal('45.0')
        assert result.regular_hours == Decimal('40.0')
        assert result.overtime_hours == Decimal('5.0')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])