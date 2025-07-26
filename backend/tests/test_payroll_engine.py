"""
Comprehensive unit tests for Enhanced Payroll Engine (AUR-277).

Tests cover:
- Hours calculation and aggregation
- Earnings calculations with multiple rates
- Benefit deductions with configurable factors
- Tax integration and deductions
- Policy-based calculations
- Error handling and edge cases
"""

import pytest
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from ..modules.staff.services.enhanced_payroll_engine import (
    EnhancedPayrollEngine, StaffPayPolicy, HoursBreakdown, 
    EarningsBreakdown, DeductionsBreakdown
)
from ..modules.staff.models.staff_models import StaffMember, Role
from ..modules.staff.models.attendance_models import AttendanceLog
from ..modules.staff.enums.staff_enums import StaffStatus
from ..modules.payroll.services.payroll_configuration_service import PayrollConfigurationService
from ..modules.payroll.models.payroll_configuration import StaffPayPolicy as DBStaffPayPolicy


class TestEnhancedPayrollEngine:
    """Unit tests for EnhancedPayrollEngine core functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_config_service(self):
        """Create mock configuration service."""
        return Mock(spec=PayrollConfigurationService)
    
    @pytest.fixture
    def payroll_engine(self, mock_db_session):
        """Create EnhancedPayrollEngine instance."""
        engine = EnhancedPayrollEngine(mock_db_session)
        # Mock the config service that gets created in __init__
        engine.config_service = Mock(spec=PayrollConfigurationService)
        return engine
    
    @pytest.fixture
    def sample_staff_member(self):
        """Create sample staff member."""
        role = Role(id=1, name="server", permissions="basic")
        return StaffMember(
            id=1,
            name="John Doe",
            email="john@example.com",
            role_id=1,
            role=role,
            status=StaffStatus.ACTIVE
        )
    
    @pytest.fixture
    def sample_pay_policy(self):
        """Create sample pay policy."""
        return StaffPayPolicy(
            base_hourly_rate=Decimal('18.50'),
            overtime_multiplier=Decimal('1.5'),
            regular_hours_threshold=Decimal('40.0'),
            location="Restaurant Main",
            health_insurance=Decimal('150.00'),
            dental_insurance=Decimal('25.00'),
            retirement_contribution=Decimal('100.00'),
            parking_fee=Decimal('50.00')
        )
    
    @pytest.fixture
    def sample_attendance_logs(self):
        """Create sample attendance logs for testing."""
        logs = []
        base_date = date(2024, 6, 1)
        
        # Create 10 working days (2 weeks)
        for day in range(14):
            work_date = base_date + timedelta(days=day)
            # Skip weekends
            if work_date.weekday() < 5:
                check_in = datetime.combine(work_date, datetime.min.time().replace(hour=9))
                check_out = datetime.combine(work_date, datetime.min.time().replace(hour=17))
                
                log = AttendanceLog(
                    id=day + 1,
                    staff_id=1,
                    check_in=check_in,
                    check_out=check_out
                )
                logs.append(log)
        
        return logs


class TestHoursCalculation:
    """Test hours calculation functionality."""
    
    def test_calculate_hours_for_period_basic(self, payroll_engine, mock_db_session, sample_attendance_logs):
        """Test basic hours calculation for a pay period."""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = sample_attendance_logs
        mock_db_session.query.return_value = mock_query
        
        # Mock SQL aggregation query
        mock_aggregation_query = Mock()
        mock_aggregation_result = [
            Mock(day=1, total_hours=8.0),
            Mock(day=2, total_hours=8.0),
            Mock(day=3, total_hours=8.0),
            Mock(day=4, total_hours=8.0),
            Mock(day=5, total_hours=8.0),
            Mock(day=8, total_hours=8.0),
            Mock(day=9, total_hours=8.0),
            Mock(day=10, total_hours=8.0),
            Mock(day=11, total_hours=8.0),
            Mock(day=12, total_hours=8.0)
        ]
        mock_aggregation_query.all.return_value = mock_aggregation_result
        mock_db_session.query.return_value = mock_aggregation_query
        
        start_date = date(2024, 6, 1)
        end_date = date(2024, 6, 15)
        
        hours = payroll_engine.calculate_hours_for_period(1, start_date, end_date)
        
        # Should return proper hours breakdown
        assert isinstance(hours, HoursBreakdown)
        assert hours.regular_hours == Decimal('40.00')  # 40 hours regular
        assert hours.overtime_hours == Decimal('40.00')  # 40 hours overtime (80 total - 40 regular)
        
        # Verify database was called with SQL aggregation
        mock_db_session.query.assert_called()
    
    def test_calculate_hours_for_period_no_overtime(self, payroll_engine, mock_db_session):
        """Test hours calculation with no overtime."""
        # Mock 30 hours total (no overtime)
        mock_aggregation_result = [
            Mock(day=1, total_hours=6.0),
            Mock(day=2, total_hours=6.0),
            Mock(day=3, total_hours=6.0),
            Mock(day=4, total_hours=6.0),
            Mock(day=5, total_hours=6.0)
        ]
        
        mock_query = Mock()
        mock_query.all.return_value = mock_aggregation_result
        mock_db_session.query.return_value = mock_query
        
        hours = payroll_engine.calculate_hours_for_period(1, date(2024, 6, 1), date(2024, 6, 8))
        
        assert hours.regular_hours == Decimal('30.00')
        assert hours.overtime_hours == Decimal('0.00')
    
    def test_calculate_hours_for_period_extensive_overtime(self, payroll_engine, mock_db_session):
        """Test hours calculation with extensive overtime."""
        # Mock 60 hours total (20 hours overtime)
        mock_aggregation_result = [
            Mock(day=1, total_hours=12.0),  # 4 hours overtime per day
            Mock(day=2, total_hours=12.0),
            Mock(day=3, total_hours=12.0),
            Mock(day=4, total_hours=12.0),
            Mock(day=5, total_hours=12.0)
        ]
        
        mock_query = Mock()
        mock_query.all.return_value = mock_aggregation_result
        mock_db_session.query.return_value = mock_query
        
        hours = payroll_engine.calculate_hours_for_period(1, date(2024, 6, 1), date(2024, 6, 8))
        
        assert hours.regular_hours == Decimal('40.00')
        assert hours.overtime_hours == Decimal('20.00')
    
    def test_calculate_hours_for_period_no_attendance(self, payroll_engine, mock_db_session):
        """Test hours calculation with no attendance records."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        hours = payroll_engine.calculate_hours_for_period(1, date(2024, 6, 1), date(2024, 6, 8))
        
        assert hours.regular_hours == Decimal('0.00')
        assert hours.overtime_hours == Decimal('0.00')


class TestEarningsCalculation:
    """Test earnings calculation functionality."""
    
    def test_calculate_earnings_regular_only(self, payroll_engine, sample_pay_policy):
        """Test earnings calculation with only regular hours."""
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        
        assert isinstance(earnings, EarningsBreakdown)
        expected_regular = Decimal('40.00') * Decimal('18.50')  # $740
        assert earnings.regular_pay == expected_regular
        assert earnings.overtime_pay == Decimal('0.00')
        assert earnings.gross_pay == expected_regular
    
    def test_calculate_earnings_with_overtime(self, payroll_engine, sample_pay_policy):
        """Test earnings calculation with overtime hours."""
        hours = HoursBreakdown(
            regular_hours=Decimal('40.00'),
            overtime_hours=Decimal('10.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        
        expected_regular = Decimal('40.00') * Decimal('18.50')  # $740
        expected_overtime = Decimal('10.00') * (Decimal('18.50') * Decimal('1.5'))  # $277.50
        expected_gross = expected_regular + expected_overtime  # $1017.50
        
        assert earnings.regular_pay == expected_regular
        assert earnings.overtime_pay == expected_overtime
        assert earnings.gross_pay == expected_gross
    
    def test_calculate_earnings_precision(self, payroll_engine, sample_pay_policy):
        """Test earnings calculation with decimal precision."""
        hours = HoursBreakdown(
            regular_hours=Decimal('37.5'),  # 37.5 hours
            overtime_hours=Decimal('2.25')  # 2.25 hours overtime
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        
        # Verify precision is maintained
        expected_regular = (Decimal('37.5') * Decimal('18.50')).quantize(Decimal('0.01'))
        expected_overtime = (Decimal('2.25') * Decimal('18.50') * Decimal('1.5')).quantize(Decimal('0.01'))
        
        assert earnings.regular_pay == expected_regular
        assert earnings.overtime_pay == expected_overtime
    
    def test_calculate_earnings_zero_hours(self, payroll_engine, sample_pay_policy):
        """Test earnings calculation with zero hours."""
        hours = HoursBreakdown(
            regular_hours=Decimal('0.00'),
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        
        assert earnings.regular_pay == Decimal('0.00')
        assert earnings.overtime_pay == Decimal('0.00')
        assert earnings.gross_pay == Decimal('0.00')


class TestBenefitDeductions:
    """Test benefit deductions calculation."""
    
    def test_apply_benefit_deductions_basic(self, payroll_engine, sample_pay_policy):
        """Test basic benefit deductions calculation."""
        # Mock config service to return proration factor
        payroll_engine.config_service.get_benefit_proration_factor.return_value = Decimal('0.46')
        
        deductions = DeductionsBreakdown()
        
        result = payroll_engine.apply_benefit_deductions(deductions, sample_pay_policy, tenant_id=1)
        
        # Verify proration factor was used
        expected_health = sample_pay_policy.health_insurance * Decimal('0.46')
        expected_dental = sample_pay_policy.dental_insurance * Decimal('0.46')
        expected_retirement = sample_pay_policy.retirement_contribution * Decimal('0.46')
        expected_parking = sample_pay_policy.parking_fee * Decimal('0.46')
        
        assert result.health_insurance == expected_health.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        assert result.dental_insurance == expected_dental.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        assert result.retirement_contribution == expected_retirement.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        assert result.parking_fee == expected_parking.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Verify config service was called
        payroll_engine.config_service.get_benefit_proration_factor.assert_called_once_with(
            location=sample_pay_policy.location,
            tenant_id=1
        )
    
    def test_apply_benefit_deductions_custom_proration(self, payroll_engine, sample_pay_policy):
        """Test benefit deductions with custom proration factor."""
        # Mock different proration factor
        payroll_engine.config_service.get_benefit_proration_factor.return_value = Decimal('0.50')
        
        deductions = DeductionsBreakdown()
        result = payroll_engine.apply_benefit_deductions(deductions, sample_pay_policy)
        
        # Should use custom factor (0.50 instead of default 0.46)
        expected_health = sample_pay_policy.health_insurance * Decimal('0.50')
        assert result.health_insurance == expected_health.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def test_apply_benefit_deductions_zero_benefits(self, payroll_engine):
        """Test benefit deductions with zero benefit amounts."""
        zero_policy = StaffPayPolicy(
            base_hourly_rate=Decimal('15.00'),
            overtime_multiplier=Decimal('1.5'),
            regular_hours_threshold=Decimal('40.0'),
            location="Test",
            health_insurance=Decimal('0.00'),
            dental_insurance=Decimal('0.00'),
            retirement_contribution=Decimal('0.00'),
            parking_fee=Decimal('0.00')
        )
        
        payroll_engine.config_service.get_benefit_proration_factor.return_value = Decimal('0.46')
        
        deductions = DeductionsBreakdown()
        result = payroll_engine.apply_benefit_deductions(deductions, zero_policy)
        
        assert result.health_insurance == Decimal('0.00')
        assert result.dental_insurance == Decimal('0.00')
        assert result.retirement_contribution == Decimal('0.00')
        assert result.parking_fee == Decimal('0.00')


class TestStaffPayPolicyRetrieval:
    """Test staff pay policy retrieval with configuration service."""
    
    def test_get_staff_pay_policy_from_database(self, payroll_engine, mock_db_session, sample_staff_member):
        """Test retrieving staff pay policy from database configuration."""
        # Mock database query for staff
        mock_staff_query = Mock()
        mock_staff_query.filter.return_value.first.return_value = sample_staff_member
        mock_db_session.query.return_value = mock_staff_query
        
        # Mock configuration service response
        mock_db_policy = DBStaffPayPolicy(
            staff_id=1,
            location="Restaurant Main",
            base_hourly_rate=Decimal('20.00'),
            overtime_multiplier=Decimal('1.5'),
            weekly_overtime_threshold=Decimal('40.0'),
            health_insurance_monthly=Decimal('175.00'),
            dental_insurance_monthly=Decimal('30.00'),
            retirement_contribution_monthly=Decimal('125.00'),
            parking_fee_monthly=Decimal('60.00')
        )
        
        payroll_engine.config_service.get_staff_pay_policy_from_db.return_value = mock_db_policy
        
        policy = payroll_engine.get_staff_pay_policy(1, "Restaurant Main")
        
        # Verify policy was retrieved from database
        assert isinstance(policy, StaffPayPolicy)
        assert policy.base_hourly_rate == Decimal('20.00')
        assert policy.health_insurance == Decimal('175.00')
        assert policy.location == "Restaurant Main"
        
        # Verify config service was called
        payroll_engine.config_service.get_staff_pay_policy_from_db.assert_called_once_with(1, "Restaurant Main")
    
    def test_get_staff_pay_policy_fallback_to_role_rates(self, payroll_engine, mock_db_session, sample_staff_member):
        """Test fallback to role-based rates when no specific policy exists."""
        # Mock database query for staff
        mock_staff_query = Mock()
        mock_staff_query.filter.return_value.first.return_value = sample_staff_member
        mock_db_session.query.return_value = mock_staff_query
        
        # Mock no specific policy found
        payroll_engine.config_service.get_staff_pay_policy_from_db.return_value = None
        
        # Mock role-based rate
        mock_role_rate = Mock()
        mock_role_rate.default_hourly_rate = Decimal('16.00')
        mock_role_rate.overtime_multiplier = Decimal('1.5')
        payroll_engine.config_service.get_role_based_pay_rate.return_value = mock_role_rate
        
        policy = payroll_engine.get_staff_pay_policy(1)
        
        # Should fallback to role-based rate
        assert policy.base_hourly_rate == Decimal('16.00')
        payroll_engine.config_service.get_role_based_pay_rate.assert_called_once_with(
            role_name="server",
            location="restaurant_main"
        )
    
    def test_get_staff_pay_policy_final_fallback(self, payroll_engine, mock_db_session, sample_staff_member):
        """Test final fallback when no configuration is found."""
        # Mock database query for staff
        mock_staff_query = Mock()
        mock_staff_query.filter.return_value.first.return_value = sample_staff_member
        mock_db_session.query.return_value = mock_staff_query
        
        # Mock no policies found
        payroll_engine.config_service.get_staff_pay_policy_from_db.return_value = None
        payroll_engine.config_service.get_role_based_pay_rate.return_value = None
        
        policy = payroll_engine.get_staff_pay_policy(1)
        
        # Should use hardcoded fallback rates
        assert isinstance(policy, StaffPayPolicy)
        assert policy.base_hourly_rate == Decimal('12.00')  # Server rate from fallback
        assert policy.overtime_multiplier == Decimal('1.5')
    
    def test_get_staff_pay_policy_staff_not_found(self, payroll_engine, mock_db_session):
        """Test error handling when staff member is not found."""
        # Mock no staff found
        mock_staff_query = Mock()
        mock_staff_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_staff_query
        
        with pytest.raises(ValueError, match="Staff member with ID 999 not found"):
            payroll_engine.get_staff_pay_policy(999)


class TestTaxIntegration:
    """Test integration with tax calculation services."""
    
    @pytest.fixture
    def mock_tax_service(self):
        """Create mock tax service."""
        return Mock()
    
    def test_calculate_tax_deductions_success(self, payroll_engine, mock_tax_service):
        """Test successful tax deductions calculation."""
        # Mock tax service
        payroll_engine.tax_service = mock_tax_service
        
        # Mock tax response
        mock_tax_response = Mock()
        mock_tax_response.total_taxes = Decimal('300.00')
        mock_tax_response.federal_tax = Decimal('220.00')
        mock_tax_response.state_tax = Decimal('80.00')
        mock_tax_response.local_tax = Decimal('0.00')
        mock_tax_response.social_security_tax = Decimal('0.00')
        mock_tax_response.medicare_tax = Decimal('0.00')
        mock_tax_response.unemployment_tax = Decimal('0.00')
        
        mock_tax_service.calculate_comprehensive_taxes.return_value = mock_tax_response
        
        gross_pay = Decimal('1000.00')
        deductions = payroll_engine.calculate_tax_deductions_with_breakdown(
            gross_pay, "California", tenant_id=1
        )
        
        assert isinstance(deductions, DeductionsBreakdown)
        assert deductions.federal_tax == Decimal('220.00')
        assert deductions.state_tax == Decimal('80.00')
        
        # Verify tax service was called
        mock_tax_service.calculate_comprehensive_taxes.assert_called_once()
    
    def test_calculate_tax_deductions_fallback_on_error(self, payroll_engine, mock_tax_service):
        """Test fallback tax calculation when tax service fails."""
        # Mock tax service to raise exception
        payroll_engine.tax_service = mock_tax_service
        payroll_engine.tax_service.calculate_comprehensive_taxes.side_effect = Exception("Tax service unavailable")
        
        # Mock config service for tax approximation
        mock_breakdown = {
            "federal_tax": Decimal('0.22'),
            "state_tax": Decimal('0.08'),
            "local_tax": Decimal('0.02'),
            "social_security": Decimal('0.062'),
            "medicare": Decimal('0.0145'),
            "unemployment": Decimal('0.006')
        }
        payroll_engine.config_service.get_tax_approximation_breakdown.return_value = mock_breakdown
        
        gross_pay = Decimal('1000.00')
        deductions = payroll_engine._calculate_tax_approximation(gross_pay, "California", tenant_id=1)
        
        # Should use approximation values
        assert deductions.federal_tax == Decimal('220.00')  # 22% of $1000
        assert deductions.state_tax == Decimal('80.00')     # 8% of $1000
        assert deductions.social_security == Decimal('62.00')  # 6.2% of $1000


class TestComprehensivePayrollCalculation:
    """Test complete payroll calculation workflow."""
    
    def test_compute_comprehensive_payroll_complete_workflow(self, payroll_engine, mock_db_session, sample_staff_member):
        """Test complete payroll calculation workflow."""
        # Mock all dependencies
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_staff_member
        
        # Mock hours calculation
        with patch.object(payroll_engine, 'calculate_hours_for_period') as mock_hours:
            mock_hours.return_value = HoursBreakdown(
                regular_hours=Decimal('40.00'),
                overtime_hours=Decimal('5.00')
            )
            
            # Mock policy retrieval
            with patch.object(payroll_engine, 'get_staff_pay_policy') as mock_policy:
                mock_policy.return_value = StaffPayPolicy(
                    base_hourly_rate=Decimal('20.00'),
                    overtime_multiplier=Decimal('1.5'),
                    regular_hours_threshold=Decimal('40.0'),
                    location="Test Location",
                    health_insurance=Decimal('150.00'),
                    dental_insurance=Decimal('25.00'),
                    retirement_contribution=Decimal('100.00'),
                    parking_fee=Decimal('50.00')
                )
                
                # Mock tax calculation
                with patch.object(payroll_engine, 'calculate_tax_deductions') as mock_tax:
                    mock_tax.return_value = DeductionsBreakdown(
                        federal_tax=Decimal('200.00'),
                        state_tax=Decimal('75.00')
                    )
                    
                    # Mock benefit deductions
                    payroll_engine.config_service.get_benefit_proration_factor.return_value = Decimal('0.46')
                    
                    # Execute comprehensive payroll calculation
                    result = payroll_engine.compute_comprehensive_payroll(
                        staff_id=1,
                        pay_period_start=date(2024, 6, 1),
                        pay_period_end=date(2024, 6, 15),
                        tenant_id=1
                    )
                    
                    # Verify result structure
                    assert 'staff_id' in result
                    assert 'hours_breakdown' in result
                    assert 'earnings_breakdown' in result
                    assert 'deductions_breakdown' in result
                    assert 'net_pay' in result
                    
                    # Verify calculations
                    earnings = result['earnings_breakdown']
                    assert earnings.regular_pay == Decimal('800.00')  # 40 * $20
                    assert earnings.overtime_pay == Decimal('150.00')  # 5 * $20 * 1.5
                    assert earnings.gross_pay == Decimal('950.00')
                    
                    # Verify net pay calculation
                    assert isinstance(result['net_pay'], Decimal)
                    assert result['net_pay'] > Decimal('0.00')


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_staff_id(self, payroll_engine, mock_db_session):
        """Test handling of invalid staff ID."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Staff member with ID 999 not found"):
            payroll_engine.get_staff_pay_policy(999)
    
    def test_negative_hours_handling(self, payroll_engine, sample_pay_policy):
        """Test handling of negative hours (should be prevented at database level)."""
        # This tests the model's ability to handle edge cases gracefully
        hours = HoursBreakdown(
            regular_hours=Decimal('0.00'),  # Ensure non-negative
            overtime_hours=Decimal('0.00')
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        assert earnings.gross_pay >= Decimal('0.00')
    
    def test_very_large_numbers(self, payroll_engine, sample_pay_policy):
        """Test handling of very large hour amounts."""
        hours = HoursBreakdown(
            regular_hours=Decimal('1000.00'),  # 1000 hours
            overtime_hours=Decimal('500.00')   # 500 overtime hours
        )
        
        earnings = payroll_engine.calculate_earnings(hours, sample_pay_policy)
        
        # Should handle large numbers correctly
        expected_regular = Decimal('1000.00') * sample_pay_policy.base_hourly_rate
        expected_overtime = Decimal('500.00') * sample_pay_policy.base_hourly_rate * sample_pay_policy.overtime_multiplier
        
        assert earnings.regular_pay == expected_regular
        assert earnings.overtime_pay == expected_overtime
        assert earnings.gross_pay == expected_regular + expected_overtime


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=modules.staff.services"])