"""
Comprehensive unit tests for the Enhanced Payroll Engine.

Tests cover:
- Hours calculation accuracy
- Earnings computation with various pay rates
- Tax integration with the tax services
- Benefit deduction application
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from ..services.enhanced_payroll_engine import (
    EnhancedPayrollEngine, StaffPayPolicy, HoursBreakdown, 
    EarningsBreakdown, DeductionsBreakdown
)
from ..models.attendance_models import AttendanceLog
from ..models.staff_models import StaffMember, Role
from ...payroll.schemas.payroll_tax_schemas import (
    PayrollTaxServiceResponse, TaxBreakdown, TaxApplicationDetail
)
from ...payroll.models.payroll_models import EmployeePayment, TaxRule


class TestEnhancedPayrollEngine:
    """Test suite for Enhanced Payroll Engine."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def payroll_engine(self, mock_db):
        """Create a payroll engine instance with mocked dependencies."""
        with patch('modules.staff.services.enhanced_payroll_engine.PayrollTaxEngine'), \
             patch('modules.staff.services.enhanced_payroll_engine.PayrollTaxService'):
            return EnhancedPayrollEngine(mock_db)
    
    @pytest.fixture
    def sample_staff_member(self):
        """Create a sample staff member with role."""
        role = Role(id=1, name="server", permissions="basic")
        staff = StaffMember(
            id=1,
            name="John Doe",
            email="john@example.com",
            phone="555-1234",
            role_id=1,
            status="active"
        )
        staff.role = role
        return staff
    
    @pytest.fixture
    def sample_attendance_logs(self):
        """Create sample attendance logs for testing."""
        base_date = date(2024, 1, 15)
        logs = []
        
        # Regular 8-hour days for 5 days (40 hours total)
        for i in range(5):
            work_date = base_date + timedelta(days=i)
            check_in = datetime.combine(work_date, datetime.strptime("09:00", "%H:%M").time())
            check_out = datetime.combine(work_date, datetime.strptime("17:00", "%H:%M").time())
            
            log = AttendanceLog(
                id=i + 1,
                staff_id=1,
                check_in=check_in,
                check_out=check_out
            )
            logs.append(log)
        
        return logs
    
    @pytest.fixture
    def overtime_attendance_logs(self):
        """Create attendance logs with overtime hours."""
        base_date = date(2024, 1, 15)
        logs = []
        
        # 5 days with 10 hours each (50 hours total, 10 overtime)
        for i in range(5):
            work_date = base_date + timedelta(days=i)
            check_in = datetime.combine(work_date, datetime.strptime("08:00", "%H:%M").time())
            check_out = datetime.combine(work_date, datetime.strptime("18:00", "%H:%M").time())
            
            log = AttendanceLog(
                id=i + 1,
                staff_id=1,
                check_in=check_in,
                check_out=check_out
            )
            logs.append(log)
        
        return logs
    
    def test_get_staff_pay_policy_default_rate(self, payroll_engine, mock_db, sample_staff_member):
        """Test getting staff pay policy with default rate."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_staff_member
        
        policy = payroll_engine.get_staff_pay_policy(1)
        
        assert isinstance(policy, StaffPayPolicy)
        assert policy.base_hourly_rate == Decimal('12.00')  # Server rate
        assert policy.overtime_multiplier == Decimal('1.5')
        assert policy.regular_hours_threshold == Decimal('40.0')
        assert policy.health_insurance == Decimal('120.00')
    
    def test_get_staff_pay_policy_manager_rate(self, payroll_engine, mock_db):
        """Test getting staff pay policy for manager role."""
        role = Role(id=2, name="manager", permissions="admin")
        staff = StaffMember(id=2, name="Jane Manager", role_id=2)
        staff.role = role
        
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        
        policy = payroll_engine.get_staff_pay_policy(2)
        
        assert policy.base_hourly_rate == Decimal('25.00')  # Manager rate
    
    def test_get_staff_pay_policy_staff_not_found(self, payroll_engine, mock_db):
        """Test getting staff pay policy when staff member doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Staff member with ID 999 not found"):
            payroll_engine.get_staff_pay_policy(999)
    
    def test_calculate_hours_regular_time_only(self, payroll_engine, mock_db, sample_attendance_logs):
        """Test calculating hours with regular time only."""
        mock_db.query.return_value.filter.return_value.all.return_value = sample_attendance_logs
        
        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 22)
        
        hours = payroll_engine.calculate_hours_for_period(1, start_date, end_date)
        
        assert isinstance(hours, HoursBreakdown)
        assert hours.regular_hours == Decimal('40.00')
        assert hours.overtime_hours == Decimal('0.00')
    
    def test_calculate_hours_with_overtime(self, payroll_engine, mock_db, overtime_attendance_logs):
        """Test calculating hours with overtime."""
        mock_db.query.return_value.filter.return_value.all.return_value = overtime_attendance_logs
        
        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 22)
        
        hours = payroll_engine.calculate_hours_for_period(1, start_date, end_date)
        
        assert hours.regular_hours == Decimal('40.00')
        assert hours.overtime_hours == Decimal('10.00')
    
    def test_calculate_hours_no_attendance(self, payroll_engine, mock_db):
        """Test calculating hours with no attendance records."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 22)
        
        hours = payroll_engine.calculate_hours_for_period(1, start_date, end_date)
        
        assert hours.regular_hours == Decimal('0.00')
        assert hours.overtime_hours == Decimal('0.00')
    
    def test_calculate_earnings_regular_hours_only(self, payroll_engine):
        """Test calculating earnings with regular hours only."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('15.00'))
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert isinstance(earnings, EarningsBreakdown)
        assert earnings.regular_pay == Decimal('600.00')  # 40 * $15
        assert earnings.overtime_pay == Decimal('0.00')
        assert earnings.gross_pay == Decimal('600.00')
    
    def test_calculate_earnings_with_overtime(self, payroll_engine):
        """Test calculating earnings with overtime hours."""
        policy = StaffPayPolicy(
            base_hourly_rate=Decimal('15.00'),
            overtime_multiplier=Decimal('1.5')
        )
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('10.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert earnings.regular_pay == Decimal('600.00')  # 40 * $15
        assert earnings.overtime_pay == Decimal('225.00')  # 10 * $15 * 1.5
        assert earnings.gross_pay == Decimal('825.00')
    
    def test_calculate_earnings_with_all_pay_types(self, payroll_engine):
        """Test calculating earnings with all pay types."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('20.00'))
        hours = HoursBreakdown(
            regular_hours=Decimal('32.00'),
            overtime_hours=Decimal('5.00'),
            double_time_hours=Decimal('2.00'),
            holiday_hours=Decimal('8.00'),
            sick_hours=Decimal('4.00'),
            vacation_hours=Decimal('8.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert earnings.regular_pay == Decimal('640.00')  # 32 * $20
        assert earnings.overtime_pay == Decimal('150.00')  # 5 * $20 * 1.5
        assert earnings.double_time_pay == Decimal('80.00')  # 2 * $20 * 2
        assert earnings.holiday_pay == Decimal('240.00')  # 8 * $20 * 1.5
        assert earnings.sick_pay == Decimal('80.00')  # 4 * $20
        assert earnings.vacation_pay == Decimal('160.00')  # 8 * $20
        assert earnings.gross_pay == Decimal('1350.00')
    
    @pytest.mark.asyncio
    async def test_calculate_tax_deductions(self, payroll_engine):
        """Test calculating tax deductions using tax service."""
        # Mock tax service response
        mock_tax_detail = Mock()
        mock_tax_detail.tax_rule.tax_type.value = 'federal'
        mock_tax_detail.calculated_amount = Decimal('120.00')
        
        mock_tax_breakdown = Mock()
        mock_tax_breakdown.tax_applications = [mock_tax_detail]
        
        mock_tax_response = Mock()
        mock_tax_response.tax_breakdown = mock_tax_breakdown
        
        payroll_engine.tax_service.calculate_and_save_taxes = AsyncMock(return_value=mock_tax_response)
        
        deductions = await payroll_engine.calculate_tax_deductions(
            staff_id=1,
            gross_pay=Decimal('600.00'),
            pay_date=date(2024, 1, 31),
            location="restaurant_main"
        )
        
        assert isinstance(deductions, DeductionsBreakdown)
        assert deductions.federal_tax == Decimal('120.00')
        assert deductions.total_tax_deductions == Decimal('120.00')
    
    def test_apply_benefit_deductions(self, payroll_engine):
        """Test applying benefit deductions based on policy."""
        policy = StaffPayPolicy(
            base_hourly_rate=Decimal('15.00'),
            health_insurance=Decimal('120.00'),
            dental_insurance=Decimal('25.00'),
            retirement_contribution=Decimal('50.00'),
            parking_fee=Decimal('15.00')
        )
        
        deductions = DeductionsBreakdown()
        updated_deductions = payroll_engine.apply_benefit_deductions(deductions, policy)
        
        # Benefits are prorated for bi-weekly pay (monthly * 0.46)
        assert updated_deductions.health_insurance == Decimal('55.20')  # 120 * 0.46
        assert updated_deductions.dental_insurance == Decimal('11.50')  # 25 * 0.46
        assert updated_deductions.retirement_contribution == Decimal('23.00')  # 50 * 0.46
        assert updated_deductions.parking_fee == Decimal('6.90')  # 15 * 0.46
    
    @pytest.mark.asyncio
    async def test_compute_comprehensive_payroll(self, payroll_engine, mock_db, sample_staff_member, sample_attendance_logs):
        """Test comprehensive payroll computation integration."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_staff_member
        mock_db.query.return_value.filter.return_value.all.return_value = sample_attendance_logs
        
        # Mock tax service
        mock_tax_response = Mock()
        mock_tax_response.tax_breakdown.tax_applications = []
        payroll_engine.tax_service.calculate_and_save_taxes = AsyncMock(return_value=mock_tax_response)
        
        result = await payroll_engine.compute_comprehensive_payroll(
            staff_id=1,
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 29),
        )
        
        assert result['staff_id'] == 1
        assert isinstance(result['hours_breakdown'], HoursBreakdown)
        assert isinstance(result['earnings_breakdown'], EarningsBreakdown)
        assert isinstance(result['deductions_breakdown'], DeductionsBreakdown)
        assert result['gross_pay'] > Decimal('0')
        assert result['net_pay'] <= result['gross_pay']
    
    @pytest.mark.asyncio
    async def test_create_employee_payment_record(self, payroll_engine, mock_db):
        """Test creating EmployeePayment record from payroll calculation."""
        payroll_calc = {
            'staff_id': 1,
            'pay_period_start': date(2024, 1, 15),
            'pay_period_end': date(2024, 1, 29),
            'hours_breakdown': HoursBreakdown(
                regular_hours=Decimal('40.00'),
                overtime_hours=Decimal('5.00')
            ),
            'earnings_breakdown': EarningsBreakdown(
                regular_pay=Decimal('600.00'),
                overtime_pay=Decimal('112.50'),
                bonus=Decimal('50.00'),
                commission=Decimal('25.00')
            ),
            'deductions_breakdown': DeductionsBreakdown(
                federal_tax=Decimal('120.00'),
                state_tax=Decimal('40.00'),
                health_insurance=Decimal('55.20')
            ),
            'gross_pay': Decimal('787.50'),
            'total_deductions': Decimal('215.20'),
            'net_pay': Decimal('572.30')
        }
        
        # Mock database operations
        mock_payment = Mock()
        mock_payment.id = 1
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        with patch('modules.staff.services.enhanced_payroll_engine.EmployeePayment', return_value=mock_payment):
            result = await payroll_engine.create_employee_payment_record(payroll_calc)
        
        assert result == mock_payment
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_deductions_breakdown_totals(self):
        """Test DeductionsBreakdown total calculations."""
        deductions = DeductionsBreakdown(
            federal_tax=Decimal('100.00'),
            state_tax=Decimal('30.00'),
            social_security=Decimal('50.00'),
            health_insurance=Decimal('55.20'),
            dental_insurance=Decimal('11.50'),
            garnishments=Decimal('25.00')
        )
        
        assert deductions.total_tax_deductions == Decimal('180.00')
        assert deductions.total_benefit_deductions == Decimal('66.70')
        assert deductions.total_other_deductions == Decimal('25.00')
        assert deductions.total_deductions == Decimal('271.70')
    
    def test_earnings_breakdown_gross_pay(self):
        """Test EarningsBreakdown gross pay calculation."""
        earnings = EarningsBreakdown(
            regular_pay=Decimal('600.00'),
            overtime_pay=Decimal('150.00'),
            bonus=Decimal('100.00'),
            commission=Decimal('50.00'),
            holiday_pay=Decimal('120.00')
        )
        
        assert earnings.gross_pay == Decimal('1020.00')
    
    def test_staff_pay_policy_defaults(self):
        """Test StaffPayPolicy default values."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('15.00'))
        
        assert policy.overtime_multiplier == Decimal('1.5')
        assert policy.regular_hours_threshold == Decimal('40.0')
        assert policy.location == "default"
        assert policy.health_insurance == Decimal('0.00')


class TestPayrollEngineEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def payroll_engine(self):
        """Create payroll engine for edge case testing."""
        mock_db = Mock(spec=Session)
        with patch('modules.staff.services.enhanced_payroll_engine.PayrollTaxEngine'), \
             patch('modules.staff.services.enhanced_payroll_engine.PayrollTaxService'):
            return EnhancedPayrollEngine(mock_db)
    
    def test_zero_hours_calculation(self, payroll_engine):
        """Test earnings calculation with zero hours."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('15.00'))
        hours = HoursBreakdown(
            regular_hours=Decimal('0.00'),
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert earnings.regular_pay == Decimal('0.00')
        assert earnings.overtime_pay == Decimal('0.00')
        assert earnings.gross_pay == Decimal('0.00')
    
    def test_very_high_overtime_hours(self, payroll_engine):
        """Test calculation with unusually high overtime hours."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('20.00'))
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('30.00')  # Very high overtime
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert earnings.regular_pay == Decimal('800.00')  # 40 * $20
        assert earnings.overtime_pay == Decimal('900.00')  # 30 * $20 * 1.5
        assert earnings.gross_pay == Decimal('1700.00')
    
    def test_fractional_hours_precision(self, payroll_engine):
        """Test calculation with fractional hours maintains precision."""
        policy = StaffPayPolicy(base_hourly_rate=Decimal('15.75'))
        hours = HoursBreakdown(
            regular_hours=Decimal('37.25'),
            overtime_hours=Decimal('2.75')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        assert earnings.regular_pay == Decimal('586.69')  # 37.25 * 15.75
        assert earnings.overtime_pay == Decimal('64.97')  # 2.75 * 15.75 * 1.5
        assert earnings.gross_pay == Decimal('651.66')
    
    def test_minimum_wage_compliance(self, payroll_engine):
        """Test that payroll respects minimum wage constraints."""
        # This would be implemented based on jurisdiction requirements
        policy = StaffPayPolicy(base_hourly_rate=Decimal('7.25'))  # Federal minimum
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, policy)
        
        # Should calculate correctly even at minimum wage
        assert earnings.regular_pay == Decimal('290.00')
        assert earnings.gross_pay == Decimal('290.00')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])