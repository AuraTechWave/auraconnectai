# backend/modules/payroll/tests/test_payroll_configuration_service.py

"""
Unit tests for PayrollConfigurationService.

Tests configuration management, business rules, and settings retrieval.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import (
    PayrollConfiguration,
    StaffPayPolicy,
    OvertimeRule,
    TaxBreakdownApproximation,
    RoleBasedPayRate,
    PayrollConfigurationType,
)
from ..exceptions import PayrollConfigurationError, PayrollNotFoundError


class TestPayrollConfigurationService:
    """Test PayrollConfigurationService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance with mock db."""
        return PayrollConfigurationService(mock_db)

    def test_get_configuration_success(self, service, mock_db):
        """Test successful configuration retrieval."""
        # Setup
        mock_config = Mock(spec=PayrollConfiguration)
        mock_config.config_value = {
            "daily_threshold": 8,
            "weekly_threshold": 40,
            "overtime_multiplier": 1.5,
        }
        mock_config.is_active = True

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_config

        # Execute
        result = service.get_configuration(
            config_type=PayrollConfigurationType.OVERTIME_RULES,
            config_key="standard_overtime",
            location="california",
        )

        # Verify
        assert result == mock_config.config_value
        assert mock_db.query.called

    def test_get_configuration_not_found(self, service, mock_db):
        """Test configuration not found error."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        # Execute and verify
        with pytest.raises(PayrollConfigurationError) as exc_info:
            service.get_configuration(
                config_type=PayrollConfigurationType.TAX_APPROXIMATION,
                config_key="invalid_key",
            )

        assert "not found" in str(exc_info.value).lower()

    def test_get_staff_pay_policy(self, service, mock_db):
        """Test staff pay policy retrieval."""
        # Setup
        staff_id = 123
        location = "new_york"
        effective_date = date.today()

        mock_policy = Mock(spec=StaffPayPolicy)
        mock_policy.base_hourly_rate = Decimal("25.00")
        mock_policy.overtime_multiplier = Decimal("1.5")
        mock_policy.health_insurance_monthly = Decimal("200.00")
        mock_policy.benefit_proration_factor = Decimal("0.2308")  # Semi-monthly

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_policy

        # Execute
        result = service.get_staff_pay_policy(staff_id, location, effective_date)

        # Verify
        assert result["base_rate"] == Decimal("25.00")
        assert result["overtime_multiplier"] == Decimal("1.5")
        assert result["health_insurance"] == Decimal("200.00")
        assert result["benefit_proration_factor"] == Decimal("0.2308")

    def test_get_staff_pay_policy_not_found(self, service, mock_db):
        """Test staff pay policy not found."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        # Execute and verify
        with pytest.raises(PayrollNotFoundError) as exc_info:
            service.get_staff_pay_policy(999, "unknown")

        assert "Pay policy" in str(exc_info.value)

    def test_get_overtime_rules(self, service, mock_db):
        """Test overtime rules retrieval."""
        # Setup
        jurisdiction = "california"

        mock_rules = [
            Mock(
                daily_threshold_hours=Decimal("8.0"),
                daily_overtime_multiplier=Decimal("1.5"),
                weekly_threshold_hours=Decimal("40.0"),
                weekly_overtime_multiplier=Decimal("1.5"),
                precedence=1,
            ),
            Mock(
                daily_threshold_hours=Decimal("12.0"),
                daily_overtime_multiplier=Decimal("2.0"),
                weekly_threshold_hours=None,
                weekly_overtime_multiplier=None,
                precedence=2,
            ),
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_rules

        # Execute
        result = service.get_overtime_rules(jurisdiction)

        # Verify
        assert len(result) == 2
        assert result[0]["daily_threshold"] == 8.0
        assert result[0]["daily_multiplier"] == 1.5
        assert result[1]["daily_threshold"] == 12.0
        assert result[1]["daily_multiplier"] == 2.0

    def test_get_tax_approximation_rules(self, service, mock_db):
        """Test tax approximation rules retrieval."""
        # Setup
        location = "california"

        mock_rule = Mock(spec=TaxBreakdownApproximation)
        mock_rule.federal_tax_percentage = Decimal("0.22")
        mock_rule.state_tax_percentage = Decimal("0.093")
        mock_rule.local_tax_percentage = Decimal("0.01")
        mock_rule.social_security_percentage = Decimal("0.062")
        mock_rule.medicare_percentage = Decimal("0.0145")

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_rule

        # Execute
        result = service.get_tax_approximation_rules(location)

        # Verify
        assert result["federal_percentage"] == 0.22
        assert result["state_percentage"] == 0.093
        assert result["local_percentage"] == 0.01
        assert result["social_security_percentage"] == 0.062
        assert result["medicare_percentage"] == 0.0145

    def test_get_role_based_pay_rate(self, service, mock_db):
        """Test role-based pay rate retrieval."""
        # Setup
        role = "supervisor"
        location = "new_york"

        mock_rate = Mock(spec=RoleBasedPayRate)
        mock_rate.default_hourly_rate = Decimal("35.00")
        mock_rate.minimum_hourly_rate = Decimal("30.00")
        mock_rate.maximum_hourly_rate = Decimal("45.00")
        mock_rate.overtime_eligible = True
        mock_rate.overtime_multiplier = Decimal("1.5")

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_rate

        # Execute
        result = service.get_role_based_pay_rate(role, location)

        # Verify
        assert result["default_rate"] == 35.00
        assert result["min_rate"] == 30.00
        assert result["max_rate"] == 45.00
        assert result["overtime_eligible"] is True
        assert result["overtime_multiplier"] == 1.5

    def test_get_role_based_pay_rate_fallback(self, service, mock_db):
        """Test role-based pay rate with fallback to default."""
        # Setup - no specific rate found
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        # Execute
        result = service.get_role_based_pay_rate("unknown_role", "unknown_location")

        # Verify fallback values
        assert result["default_rate"] == 15.00
        assert result["min_rate"] == 15.00
        assert result["max_rate"] == 50.00
        assert result["overtime_eligible"] is True
        assert result["overtime_multiplier"] == 1.5

    def test_get_all_active_configurations(self, service, mock_db):
        """Test retrieving all active configurations."""
        # Setup
        mock_configs = [
            Mock(
                config_type=PayrollConfigurationType.OVERTIME_RULES,
                config_key="standard",
                config_value={"threshold": 40},
                location="default",
            ),
            Mock(
                config_type=PayrollConfigurationType.TAX_APPROXIMATION,
                config_key="rates",
                config_value={"federal": 0.22},
                location="california",
            ),
        ]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_configs

        # Execute
        result = service.get_all_active_configurations()

        # Verify
        assert len(result) == 2
        assert result[0]["type"] == "overtime_rules"
        assert result[0]["key"] == "standard"
        assert result[1]["type"] == "tax_approximation"
        assert result[1]["key"] == "rates"

    def test_create_configuration(self, service, mock_db):
        """Test creating new configuration."""
        # Setup
        config_data = {
            "config_type": PayrollConfigurationType.BENEFIT_PRORATION,
            "config_key": "monthly_to_biweekly",
            "config_value": {"factor": 0.4615},
            "description": "Monthly to bi-weekly proration",
            "location": "default",
            "effective_date": datetime.utcnow(),
        }

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Execute
        result = service.create_configuration(config_data)

        # Verify
        assert mock_db.add.called
        assert mock_db.commit.called
        args = mock_db.add.call_args[0][0]
        assert isinstance(args, PayrollConfiguration)
        assert args.config_key == "monthly_to_biweekly"

    def test_update_configuration(self, service, mock_db):
        """Test updating existing configuration."""
        # Setup
        config_id = 1
        mock_config = Mock(spec=PayrollConfiguration)
        mock_config.id = config_id

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_config
        mock_db.commit = Mock()

        update_data = {
            "config_value": {"factor": 0.5},
            "description": "Updated description",
        }

        # Execute
        result = service.update_configuration(config_id, update_data)

        # Verify
        assert mock_config.config_value == {"factor": 0.5}
        assert mock_config.description == "Updated description"
        assert mock_db.commit.called

    def test_deactivate_configuration(self, service, mock_db):
        """Test deactivating configuration."""
        # Setup
        config_id = 1
        mock_config = Mock(spec=PayrollConfiguration)
        mock_config.is_active = True

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_config
        mock_db.commit = Mock()

        # Execute
        service.deactivate_configuration(config_id)

        # Verify
        assert mock_config.is_active is False
        assert mock_config.expiry_date is not None
        assert mock_db.commit.called
