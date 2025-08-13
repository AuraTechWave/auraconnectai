"""
Tests for overtime management functionality.

This module tests the overtime calculation logic, configuration management,
and API endpoints to ensure accurate and compliant overtime processing.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

from modules.staff.services.config_manager import ConfigManager, PayrollConfig
from modules.staff.services.attendance_optimizer import AttendanceOptimizer, DailyHoursSummary
from modules.staff.utils.hours_calculator import HoursCalculator, HoursBreakdown
from modules.staff.models.attendance_models import AttendanceLog
from modules.staff.models.staff_models import StaffMember


class TestConfigManager:
    """Test configuration management for overtime rules."""
    
    def test_validate_overtime_rules_valid(self):
        """Test validation of valid overtime rules."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        valid_rules = {
            'daily_threshold': 8.0,
            'weekly_threshold': 40.0,
            'overtime_multiplier': 1.5,
            'double_time_threshold': 12.0,
            'double_time_multiplier': 2.0
        }
        
        errors = config_manager.validate_overtime_rules(valid_rules)
        assert len(errors) == 0
    
    def test_validate_overtime_rules_invalid_daily_threshold(self):
        """Test validation with invalid daily threshold."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        invalid_rules = {
            'daily_threshold': 2.0,  # Too low
            'weekly_threshold': 40.0,
            'overtime_multiplier': 1.5
        }
        
        errors = config_manager.validate_overtime_rules(invalid_rules)
        assert len(errors) > 0
        assert any("Daily overtime threshold should be between 4 and 12 hours" in error for error in errors)
    
    def test_validate_overtime_rules_invalid_multiplier(self):
        """Test validation with invalid overtime multiplier."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        invalid_rules = {
            'daily_threshold': 8.0,
            'weekly_threshold': 40.0,
            'overtime_multiplier': 0.5  # Too low
        }
        
        errors = config_manager.validate_overtime_rules(invalid_rules)
        assert len(errors) > 0
        assert any("Overtime multiplier should be between 1.0 and 3.0" in error for error in errors)
    
    def test_validate_overtime_rules_double_time_less_than_overtime(self):
        """Test validation when double time threshold is less than overtime threshold."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        invalid_rules = {
            'daily_threshold': 8.0,
            'weekly_threshold': 40.0,
            'overtime_multiplier': 1.5,
            'double_time_threshold': 6.0,  # Less than daily threshold
            'double_time_multiplier': 2.0
        }
        
        errors = config_manager.validate_overtime_rules(invalid_rules)
        assert len(errors) > 0
        assert any("Double time threshold must be greater than daily overtime threshold" in error for error in errors)
    
    def test_get_overtime_rules_default(self):
        """Test getting default overtime rules."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        # Mock the get_config method to return default config
        with patch.object(config_manager, 'get_config') as mock_get_config:
            mock_config = PayrollConfig()
            mock_get_config.return_value = mock_config
            
            rules = config_manager.get_overtime_rules()
            
            assert rules['daily_threshold'] == Decimal('8.0')
            assert rules['weekly_threshold'] == Decimal('40.0')
            assert rules['overtime_multiplier'] == Decimal('1.5')
            assert rules['double_time_threshold'] == Decimal('12.0')
            assert rules['double_time_multiplier'] == Decimal('2.0')
    
    def test_config_loads_double_time_settings_from_env(self):
        """Test that double_time_threshold and double_time_multiplier load from environment variables."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        # Mock database query to return empty results
        db_mock.query.return_value.filter.return_value.all.return_value = []
        
        # Test with environment variables
        with patch.dict('os.environ', {
            'PAYROLL_DOUBLE_TIME_THRESHOLD': '14.0',
            'PAYROLL_DOUBLE_TIME_MULTIPLIER': '2.5'
        }):
            config = config_manager._load_configuration("default")
            
            assert config.double_time_threshold == Decimal('14.0')
            assert config.double_time_multiplier == Decimal('2.5')
    
    def test_config_loads_double_time_settings_from_db(self):
        """Test that double_time_threshold and double_time_multiplier load from database configuration."""
        from modules.payroll.models.payroll_configuration import PayrollConfiguration, PayrollConfigurationType
        
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        # Create mock database configurations
        db_config_threshold = Mock(spec=PayrollConfiguration)
        db_config_threshold.config_type = PayrollConfigurationType.OVERTIME_RULES
        db_config_threshold.config_key = "double_time_threshold"
        db_config_threshold.config_value = {"threshold": 14.0}
        
        db_config_multiplier = Mock(spec=PayrollConfiguration)
        db_config_multiplier.config_type = PayrollConfigurationType.OVERTIME_RULES
        db_config_multiplier.config_key = "double_time_multiplier"
        db_config_multiplier.config_value = {"multiplier": 2.5}
        
        # Mock database query
        db_mock.query.return_value.filter.return_value.all.return_value = [
            db_config_threshold,
            db_config_multiplier
        ]
        
        config = config_manager._load_configuration("default")
        
        assert config.double_time_threshold == Decimal('14.0')
        assert config.double_time_multiplier == Decimal('2.5')


class TestAttendanceOptimizer:
    """Test attendance optimization and overtime calculation."""
    
    def test_calculate_overtime_efficiently_no_overtime(self):
        """Test overtime calculation when no overtime is worked."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Create daily summaries with no overtime
        daily_summaries = [
            DailyHoursSummary(
                work_date=date(2024, 1, 1),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 1, 9, 0),
                last_check_out=datetime(2024, 1, 1, 17, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 2),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 2, 9, 0),
                last_check_out=datetime(2024, 1, 2, 17, 0)
            )
        ]
        
        result = optimizer.calculate_overtime_efficiently(daily_summaries)
        
        assert result['regular_hours'] == Decimal('16.00')
        assert result['overtime_hours'] == Decimal('0.00')
        assert result['double_time_hours'] == Decimal('0.00')
        assert result['total_hours'] == Decimal('16.00')
    
    def test_calculate_overtime_efficiently_daily_overtime(self):
        """Test overtime calculation with daily overtime."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Create daily summaries with daily overtime
        daily_summaries = [
            DailyHoursSummary(
                work_date=date(2024, 1, 1),
                total_hours=Decimal('10.0'),  # 2 hours overtime
                shifts_count=1,
                first_check_in=datetime(2024, 1, 1, 9, 0),
                last_check_out=datetime(2024, 1, 1, 19, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 2),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 2, 9, 0),
                last_check_out=datetime(2024, 1, 2, 17, 0)
            )
        ]
        
        result = optimizer.calculate_overtime_efficiently(daily_summaries)
        
        assert result['regular_hours'] == Decimal('16.00')
        assert result['overtime_hours'] == Decimal('2.00')
        assert result['double_time_hours'] == Decimal('0.00')
        assert result['total_hours'] == Decimal('18.00')
    
    def test_calculate_overtime_efficiently_weekly_overtime(self):
        """Test overtime calculation with weekly overtime."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Create daily summaries with weekly overtime
        daily_summaries = [
            DailyHoursSummary(
                work_date=date(2024, 1, 1),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 1, 9, 0),
                last_check_out=datetime(2024, 1, 1, 17, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 2),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 2, 9, 0),
                last_check_out=datetime(2024, 1, 2, 17, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 3),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 3, 9, 0),
                last_check_out=datetime(2024, 1, 3, 17, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 4),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 4, 9, 0),
                last_check_out=datetime(2024, 1, 4, 17, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 5),
                total_hours=Decimal('10.0'),  # 2 hours overtime
                shifts_count=1,
                first_check_in=datetime(2024, 1, 5, 9, 0),
                last_check_out=datetime(2024, 1, 5, 19, 0)
            )
        ]
        
        result = optimizer.calculate_overtime_efficiently(daily_summaries)
        
        # With 4 days at 8 hours and 1 day at 10 hours:
        # - Daily overtime: 2 hours on day 5 (10 - 8 = 2)
        # - Weekly total: 42 hours (also 2 hours over weekly threshold)
        # The algorithm handles overlapping daily and weekly overtime
        # by reducing regular hours when weekly overtime is calculated
        assert result['regular_hours'] == Decimal('38.00')
        assert result['overtime_hours'] == Decimal('4.00')
        assert result['double_time_hours'] == Decimal('0.00')
        assert result['total_hours'] == Decimal('42.00')
    
    def test_calculate_overtime_efficiently_double_time(self):
        """Test overtime calculation with double time."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Create daily summaries with double time
        daily_summaries = [
            DailyHoursSummary(
                work_date=date(2024, 1, 1),
                total_hours=Decimal('14.0'),  # 6 hours double time
                shifts_count=1,
                first_check_in=datetime(2024, 1, 1, 9, 0),
                last_check_out=datetime(2024, 1, 1, 23, 0)
            ),
            DailyHoursSummary(
                work_date=date(2024, 1, 2),
                total_hours=Decimal('8.0'),
                shifts_count=1,
                first_check_in=datetime(2024, 1, 2, 9, 0),
                last_check_out=datetime(2024, 1, 2, 17, 0)
            )
        ]
        
        result = optimizer.calculate_overtime_efficiently(daily_summaries)
        
        assert result['regular_hours'] == Decimal('16.00')
        assert result['overtime_hours'] == Decimal('4.00')  # 4 hours overtime (8-12)
        assert result['double_time_hours'] == Decimal('2.00')  # 2 hours double time (12-14)
        assert result['total_hours'] == Decimal('22.00')
    
    def test_calculate_overtime_efficiently_empty_data(self):
        """Test overtime calculation with empty data."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        result = optimizer.calculate_overtime_efficiently([])
        
        assert result['regular_hours'] == Decimal('0.00')
        assert result['overtime_hours'] == Decimal('0.00')
        assert result['double_time_hours'] == Decimal('0.00')
        assert result['total_hours'] == Decimal('0.00')
    
    def test_get_attendance_statistics(self):
        """Test attendance statistics calculation."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Mock the get_daily_hours_aggregated method
        with patch.object(optimizer, 'get_daily_hours_aggregated') as mock_get_daily:
            mock_get_daily.return_value = [
                DailyHoursSummary(
                    work_date=date(2024, 1, 1),
                    total_hours=Decimal('10.0'),
                    shifts_count=1,
                    first_check_in=datetime(2024, 1, 1, 9, 0),
                    last_check_out=datetime(2024, 1, 1, 19, 0)
                ),
                DailyHoursSummary(
                    work_date=date(2024, 1, 2),
                    total_hours=Decimal('8.0'),
                    shifts_count=1,
                    first_check_in=datetime(2024, 1, 2, 9, 0),
                    last_check_out=datetime(2024, 1, 2, 17, 0)
                )
            ]
            
            stats = optimizer.get_attendance_statistics(1, date(2024, 1, 1), date(2024, 1, 2))
            
            assert stats['total_days'] == 2
            assert stats['total_hours'] == Decimal('18.00')
            assert stats['average_hours_per_day'] == Decimal('9.00')
            assert stats['max_hours_in_day'] == Decimal('10.00')
            assert stats['min_hours_in_day'] == Decimal('8.00')
            assert stats['total_shifts'] == 2
            assert stats['days_with_overtime'] == 1
            assert stats['total_overtime_hours'] == Decimal('2.00')
    
    def test_batch_calculate_hours_passes_config_parameters(self):
        """Test that batch_calculate_hours_for_staff properly passes overtime configuration parameters."""
        db_mock = Mock()
        optimizer = AttendanceOptimizer(db_mock)
        
        # Mock database query results
        mock_results = [
            Mock(staff_id=1, work_date=date(2024, 1, 1), total_hours=14.0),  # 14 hours - should trigger double time
            Mock(staff_id=1, work_date=date(2024, 1, 2), total_hours=8.0),
        ]
        db_mock.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_results
        
        # Mock calculate_overtime_efficiently to verify it receives the correct parameters
        with patch.object(optimizer, 'calculate_overtime_efficiently') as mock_calc_ot:
            mock_calc_ot.return_value = {
                'regular_hours': Decimal('16.00'),
                'overtime_hours': Decimal('4.00'),
                'double_time_hours': Decimal('2.00'),
                'total_hours': Decimal('22.00')
            }
            
            # Call with custom configuration parameters
            result = optimizer.batch_calculate_hours_for_staff(
                [1], 
                date(2024, 1, 1), 
                date(2024, 1, 2),
                daily_overtime_threshold=Decimal('10.0'),  # Custom threshold
                weekly_overtime_threshold=Decimal('50.0'),  # Custom threshold
                double_time_threshold=Decimal('14.0'),  # Custom threshold
                double_time_weekly_threshold=Decimal('70.0')  # Custom threshold
            )
            
            # Verify calculate_overtime_efficiently was called with the correct parameters
            mock_calc_ot.assert_called_once()
            call_args = mock_calc_ot.call_args[0]
            assert len(call_args) == 5
            assert call_args[1] == Decimal('10.0')  # daily_overtime_threshold
            assert call_args[2] == Decimal('50.0')  # weekly_overtime_threshold
            assert call_args[3] == Decimal('14.0')  # double_time_threshold
            assert call_args[4] == Decimal('70.0')  # double_time_weekly_threshold
            
            # Verify the result
            assert 1 in result
            assert result[1]['regular_hours'] == Decimal('16.00')
            assert result[1]['overtime_hours'] == Decimal('4.00')
            assert result[1]['double_time_hours'] == Decimal('2.00')
            assert result[1]['total_hours'] == Decimal('22.00')


class TestHoursCalculator:
    """Test hours calculation utility."""
    
    def test_calculate_hours_for_period_optimized(self):
        """Test optimized hours calculation."""
        db_mock = Mock()
        calculator = HoursCalculator(db_mock)
        
        # Mock the optimizer and config manager
        with patch.object(calculator.optimizer, 'get_daily_hours_aggregated') as mock_get_daily:
            with patch.object(calculator.optimizer, 'calculate_overtime_efficiently') as mock_calc_ot:
                with patch.object(calculator.config_manager, 'get_overtime_rules') as mock_get_rules:
                    # Setup mocks
                    mock_get_daily.return_value = [
                        DailyHoursSummary(
                            work_date=date(2024, 1, 1),
                            total_hours=Decimal('8.0'),
                            shifts_count=1,
                            first_check_in=datetime(2024, 1, 1, 9, 0),
                            last_check_out=datetime(2024, 1, 1, 17, 0)
                        )
                    ]
                    
                    mock_calc_ot.return_value = {
                        'regular_hours': Decimal('8.00'),
                        'overtime_hours': Decimal('0.00'),
                        'double_time_hours': Decimal('0.00'),
                        'total_hours': Decimal('8.00')
                    }
                    
                    mock_get_rules.return_value = {
                        'daily_threshold': Decimal('8.0'),
                        'weekly_threshold': Decimal('40.0')
                    }
                    
                    result = calculator.calculate_hours_for_period(1, date(2024, 1, 1), date(2024, 1, 1))
                    
                    assert isinstance(result, HoursBreakdown)
                    assert result.regular_hours == Decimal('8.00')
                    assert result.overtime_hours == Decimal('0.00')
                    assert result.total_hours == Decimal('8.00')
    
    def test_batch_calculate_hours(self):
        """Test batch hours calculation."""
        db_mock = Mock()
        calculator = HoursCalculator(db_mock)
        
        # Mock the optimizer
        with patch.object(calculator.optimizer, 'batch_calculate_hours_for_staff') as mock_batch:
            mock_batch.return_value = {
                1: {
                    'total_hours': Decimal('40.00'),
                    'regular_hours': Decimal('40.00'),
                    'overtime_hours': Decimal('0.00')
                },
                2: {
                    'total_hours': Decimal('45.00'),
                    'regular_hours': Decimal('40.00'),
                    'overtime_hours': Decimal('5.00')
                }
            }
            
            result = calculator.batch_calculate_hours([1, 2], date(2024, 1, 1), date(2024, 1, 7))
            
            assert len(result) == 2
            assert result[1].regular_hours == Decimal('40.00')
            assert result[1].overtime_hours == Decimal('0.00')
            assert result[2].regular_hours == Decimal('40.00')
            assert result[2].overtime_hours == Decimal('5.00')


class TestOvertimeIntegration:
    """Integration tests for overtime management."""
    
    def test_end_to_end_overtime_calculation(self):
        """Test end-to-end overtime calculation workflow."""
        db_mock = Mock()
        
        # Create calculator
        calculator = HoursCalculator(db_mock)
        
        # Mock database queries using the calculator's instances
        with patch.object(calculator.optimizer, 'get_daily_hours_aggregated') as mock_get_daily:
            with patch.object(calculator.optimizer, 'calculate_overtime_efficiently') as mock_calc_ot:
                with patch.object(calculator.config_manager, 'get_overtime_rules') as mock_get_rules:
                    # Setup test data
                    daily_summaries = [
                        DailyHoursSummary(
                            work_date=date(2024, 1, 1),
                            total_hours=Decimal('10.0'),
                            shifts_count=1,
                            first_check_in=datetime(2024, 1, 1, 9, 0),
                            last_check_out=datetime(2024, 1, 1, 19, 0)
                        ),
                        DailyHoursSummary(
                            work_date=date(2024, 1, 2),
                            total_hours=Decimal('8.0'),
                            shifts_count=1,
                            first_check_in=datetime(2024, 1, 2, 9, 0),
                            last_check_out=datetime(2024, 1, 2, 17, 0)
                        )
                    ]
                    
                    mock_get_daily.return_value = daily_summaries
                    mock_calc_ot.return_value = {
                        'regular_hours': Decimal('16.00'),
                        'overtime_hours': Decimal('2.00'),
                        'double_time_hours': Decimal('0.00'),
                        'total_hours': Decimal('18.00')
                    }
                    mock_get_rules.return_value = {
                        'daily_threshold': Decimal('8.0'),
                        'weekly_threshold': Decimal('40.0')
                    }
                    
                    # Calculate hours
                    result = calculator.calculate_hours_for_period(1, date(2024, 1, 1), date(2024, 1, 2))
                    
                    # Verify results
                    assert result.regular_hours == Decimal('16.00')
                    assert result.overtime_hours == Decimal('2.00')
                    assert result.total_hours == Decimal('18.00')
                    
                    # Verify that the correct methods were called
                    mock_get_daily.assert_called_once_with(1, date(2024, 1, 1), date(2024, 1, 2))
                    mock_calc_ot.assert_called_once()
                    mock_get_rules.assert_called_once()
    
    def test_overtime_rules_validation_integration(self):
        """Test integration of overtime rules validation."""
        db_mock = Mock()
        config_manager = ConfigManager(db_mock)
        
        # Test valid rules
        valid_rules = {
            'daily_threshold': 8.0,
            'weekly_threshold': 40.0,
            'overtime_multiplier': 1.5,
            'double_time_threshold': 12.0,
            'double_time_multiplier': 2.0
        }
        
        errors = config_manager.validate_overtime_rules(valid_rules)
        assert len(errors) == 0
        
        # Test invalid rules
        invalid_rules = {
            'daily_threshold': 2.0,
            'weekly_threshold': 40.0,
            'overtime_multiplier': 1.5
        }
        
        errors = config_manager.validate_overtime_rules(invalid_rules)
        assert len(errors) > 0
        assert any("Daily overtime threshold should be between 4 and 12 hours" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])
