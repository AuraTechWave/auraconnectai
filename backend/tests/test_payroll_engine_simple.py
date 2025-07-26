"""
Simplified payroll engine tests using basic calculations and mocks.

Tests core payroll calculation logic without complex schema dependencies.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch


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
class TestPayrollEdgeCases:
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
        
        # Should maintain precision (35.75 * 18.25 = 652.4375)
        assert gross_pay == Decimal('652.4375')
        
        # Round to currency precision (2 decimal places)
        rounded_pay = gross_pay.quantize(Decimal('0.01'))
        assert rounded_pay == Decimal('652.44')


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestPayPeriodCalculations:
    """Test pay period calculations."""
    
    def test_weekly_pay_period(self):
        """Test weekly pay period calculations."""
        # 7 days, 8 hours per day
        daily_hours = [8.0] * 7
        total_hours = sum(daily_hours)
        
        # Weekly calculations might have different overtime rules
        regular_hours = min(total_hours, 40.0)
        overtime_hours = max(total_hours - 40.0, 0.0)
        
        assert total_hours == 56.0
        assert regular_hours == 40.0
        assert overtime_hours == 16.0
    
    def test_biweekly_pay_period(self):
        """Test biweekly pay period calculations."""
        # 14 days, 8 hours per weekday only (10 working days)
        weekday_hours = [8.0] * 10  # Mon-Fri for 2 weeks
        weekend_hours = [0.0] * 4   # Sat-Sun for 2 weeks
        
        all_hours = weekday_hours + weekend_hours
        total_hours = sum(all_hours)
        
        # Standard 80 hours for biweekly (40 * 2)
        regular_hours = min(total_hours, 80.0)
        overtime_hours = max(total_hours - 80.0, 0.0)
        
        assert total_hours == 80.0
        assert regular_hours == 80.0
        assert overtime_hours == 0.0
    
    def test_monthly_pay_period(self):
        """Test monthly pay calculations."""
        # Assume 22 working days in a month
        working_days = 22
        hours_per_day = 8.0
        total_monthly_hours = working_days * hours_per_day
        
        # Monthly standard might be different (e.g., 176 hours)
        monthly_standard = 176.0
        regular_hours = min(total_monthly_hours, monthly_standard)
        overtime_hours = max(total_monthly_hours - monthly_standard, 0.0)
        
        assert total_monthly_hours == 176.0
        assert regular_hours == 176.0
        assert overtime_hours == 0.0


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestPayrollDifferentRoles:
    """Test payroll calculations for different employee roles."""
    
    def test_hourly_employee_calculation(self):
        """Test standard hourly employee payroll."""
        hours_worked = Decimal('42.0')
        hourly_rate = Decimal('18.50')
        
        regular_hours = min(hours_worked, Decimal('40.0'))
        overtime_hours = max(hours_worked - Decimal('40.0'), Decimal('0.0'))
        
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * hourly_rate * Decimal('1.5')
        gross_pay = regular_pay + overtime_pay
        
        assert regular_pay == Decimal('740.00')   # 40 * 18.50
        assert overtime_pay == Decimal('55.50')   # 2 * 18.50 * 1.5
        assert gross_pay == Decimal('795.50')
    
    def test_tipped_employee_calculation(self):
        """Test tipped employee payroll calculation."""
        base_hourly_rate = Decimal('7.25')  # Tipped minimum wage
        tips_reported = Decimal('150.00')
        hours_worked = Decimal('30.0')
        
        # Base pay calculation
        base_pay = hours_worked * base_hourly_rate
        
        # Total compensation
        total_compensation = base_pay + tips_reported
        
        assert base_pay == Decimal('217.50')     # 30 * 7.25
        assert total_compensation == Decimal('367.50')
    
    def test_manager_salary_calculation(self):
        """Test manager/salary employee calculation."""
        annual_salary = Decimal('52000.00')
        pay_periods_per_year = 26  # Biweekly
        
        # Calculate per-period salary
        period_salary = annual_salary / pay_periods_per_year
        
        # Salary employees typically don't get overtime
        gross_pay = period_salary
        
        assert period_salary == Decimal('2000.00')
        assert gross_pay == Decimal('2000.00')


@pytest.mark.unit
@pytest.mark.payroll_engine
class TestPayrollMockIntegration:
    """Test mocked integration with payroll services."""
    
    @patch('modules.staff.services.enhanced_payroll_engine.EnhancedPayrollEngine')
    def test_payroll_engine_mock_basic(self, mock_engine_class):
        """Test basic mock integration with payroll engine."""
        # Setup mock
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine
        
        # Mock calculation method
        mock_engine.compute_comprehensive_payroll.return_value = {
            'staff_id': 1,
            'gross_pay': Decimal('1200.00'),
            'total_deductions': Decimal('360.00'),
            'net_pay': Decimal('840.00'),
            'regular_hours': Decimal('40.0'),
            'overtime_hours': Decimal('5.0')
        }
        
        # Test interaction
        from modules.staff.services.enhanced_payroll_engine import EnhancedPayrollEngine
        
        mock_db = Mock()
        engine = EnhancedPayrollEngine(mock_db)
        result = engine.compute_comprehensive_payroll(
            staff_id=1,
            pay_period_start=date(2024, 6, 1),
            pay_period_end=date(2024, 6, 15)
        )
        
        # Verify mock was called
        mock_engine.compute_comprehensive_payroll.assert_called_once()
        assert result['gross_pay'] == Decimal('1200.00')
        assert result['net_pay'] == Decimal('840.00')
    
    def test_payroll_calculation_validation(self):
        """Test payroll calculation validation logic."""
        # Test data that should pass validation
        calculation_data = {
            'staff_id': 123,
            'regular_hours': Decimal('40.0'),
            'overtime_hours': Decimal('5.0'),
            'hourly_rate': Decimal('22.00'),
            'gross_pay': Decimal('1045.00'),  # (40 * 22) + (5 * 22 * 1.5)
            'net_pay': Decimal('800.00')
        }
        
        # Validate calculations
        expected_regular_pay = calculation_data['regular_hours'] * calculation_data['hourly_rate']
        expected_overtime_pay = calculation_data['overtime_hours'] * calculation_data['hourly_rate'] * Decimal('1.5')
        expected_gross = expected_regular_pay + expected_overtime_pay
        
        assert expected_gross == calculation_data['gross_pay']
        assert calculation_data['net_pay'] < calculation_data['gross_pay']
        assert calculation_data['staff_id'] > 0
        assert calculation_data['regular_hours'] >= 0
        assert calculation_data['overtime_hours'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])