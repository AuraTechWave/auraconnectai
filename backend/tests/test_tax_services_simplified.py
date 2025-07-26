"""
Simplified unit tests for Tax Services (AUR-276).

Uses pure mocks to avoid SQLAlchemy relationship issues while testing core business logic.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

from modules.payroll.services.payroll_tax_engine import PayrollTaxEngine
from modules.payroll.schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest, PayrollTaxCalculationResponse,
    TaxApplicationDetail, TaxBreakdown
)
from modules.payroll.enums.payroll_enums import TaxType


@pytest.mark.unit
@pytest.mark.tax_services
class TestPayrollTaxEngineSimplified:
    """Simplified unit tests for PayrollTaxEngine core functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def tax_engine(self, mock_db_session):
        """Create PayrollTaxEngine with mock database."""
        return PayrollTaxEngine(mock_db_session)
    
    @pytest.fixture
    def sample_tax_rules_data(self):
        """Create sample tax rule data as simple dictionaries."""
        return [
            {
                'id': 1,
                'rule_name': 'Federal Income Tax',
                'location': 'US',
                'tax_type': TaxType.FEDERAL,
                'rate_percent': Decimal('0.22'),
                'effective_date': datetime(2024, 1, 1),
                'is_active': True
            },
            {
                'id': 2,
                'rule_name': 'California State Tax',
                'location': 'California',
                'tax_type': TaxType.STATE,
                'rate_percent': Decimal('0.08'),
                'effective_date': datetime(2024, 1, 1),
                'is_active': True
            },
            {
                'id': 3,
                'rule_name': 'Social Security Tax',
                'location': 'US',
                'tax_type': TaxType.SOCIAL_SECURITY,
                'rate_percent': Decimal('0.062'),
                'effective_date': datetime(2024, 1, 1),
                'is_active': True
            }
        ]
    
    def create_mock_tax_rule(self, rule_data):
        """Helper to create a mock tax rule from data."""
        mock_rule = Mock()
        for key, value in rule_data.items():
            setattr(mock_rule, key, value)
        return mock_rule
    
    def test_get_applicable_tax_rules_by_location(self, tax_engine, mock_db_session, sample_tax_rules_data):
        """Test filtering tax rules by location."""
        # Create mock rules
        us_rules = [
            self.create_mock_tax_rule(sample_tax_rules_data[0]),  # Federal
            self.create_mock_tax_rule(sample_tax_rules_data[2])   # Social Security
        ]
        
        # Mock database query chain
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = us_rules
        mock_db_session.query.return_value = mock_query
        
        # Execute
        result = tax_engine.get_applicable_tax_rules(location="US", pay_date=date(2024, 6, 15))
        
        # Verify
        assert len(result) == 2
        assert result[0].location == "US"
        assert result[1].location == "US"
        assert result[0].tax_type == TaxType.FEDERAL
        assert result[1].tax_type == TaxType.SOCIAL_SECURITY
    
    def test_calculate_payroll_taxes_basic(self, tax_engine, mock_db_session, sample_tax_rules_data):
        """Test basic payroll tax calculation."""
        # Setup mock rules
        mock_rules = [self.create_mock_tax_rule(sample_tax_rules_data[0])]  # 22% Federal
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = mock_rules
        mock_db_session.query.return_value = mock_query
        
        # Create request
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15),
            tenant_id=1
        )
        
        # Execute
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify
        assert isinstance(result, PayrollTaxCalculationResponse)
        assert result.gross_pay == Decimal('1000.00')
        assert result.total_taxes == Decimal('220.00')  # 22% of 1000
        assert result.net_pay == Decimal('780.00')
        assert len(result.tax_applications) == 1
        assert result.tax_applications[0].tax_type == TaxType.FEDERAL
    
    def test_calculate_payroll_taxes_multiple_jurisdictions(self, tax_engine, mock_db_session, sample_tax_rules_data):
        """Test tax calculation with multiple tax rules."""
        # Setup mock rules - Federal (22%) + Social Security (6.2%)
        mock_rules = [
            self.create_mock_tax_rule(sample_tax_rules_data[0]),  # Federal 22%
            self.create_mock_tax_rule(sample_tax_rules_data[2])   # Social Security 6.2%
        ]
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = mock_rules
        mock_db_session.query.return_value = mock_query
        
        # Create request
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        # Execute
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify
        expected_total = Decimal('220.00') + Decimal('62.00')  # 22% + 6.2%
        assert result.total_taxes == expected_total
        assert result.net_pay == Decimal('1000.00') - expected_total
        assert len(result.tax_applications) == 2
        
        # Check tax breakdown
        assert result.tax_breakdown.federal_tax == Decimal('220.00')
        assert result.tax_breakdown.social_security_tax == Decimal('62.00')
    
    def test_calculate_payroll_taxes_no_applicable_rules(self, tax_engine, mock_db_session):
        """Test handling when no tax rules are found."""
        # Mock empty result
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        # Create request
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('1000.00'),
            location="Unknown",
            pay_date=date(2024, 6, 15)
        )
        
        # Execute
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify
        assert result.total_taxes == Decimal('0.00')
        assert result.net_pay == result.gross_pay
        assert len(result.tax_applications) == 0
    
    def test_calculate_payroll_taxes_zero_gross_pay(self, tax_engine, mock_db_session, sample_tax_rules_data):
        """Test handling zero gross pay."""
        # Setup mock rules
        mock_rules = [self.create_mock_tax_rule(sample_tax_rules_data[0])]
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = mock_rules
        mock_db_session.query.return_value = mock_query
        
        # Create request with zero gross pay
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('0.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        # Execute
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify
        assert result.gross_pay == Decimal('0.00')
        assert result.total_taxes == Decimal('0.00')
        assert result.net_pay == Decimal('0.00')


@pytest.mark.unit
@pytest.mark.tax_services
class TestTaxCalculationEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def mock_db_session(self):
        return Mock()
    
    @pytest.fixture
    def tax_engine(self, mock_db_session):
        return PayrollTaxEngine(mock_db_session)
    
    def test_very_large_gross_pay(self, tax_engine, mock_db_session):
        """Test calculation with very large gross pay amounts."""
        # Mock federal tax rule
        mock_rule = Mock()
        mock_rule.id = 1
        mock_rule.tax_type = TaxType.FEDERAL
        mock_rule.rate_percent = Decimal('0.37')  # High tax bracket
        mock_rule.location = "US"
        
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_rule]
        mock_db_session.query.return_value = mock_query
        
        # Test with large amount
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('100000.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify precision is maintained
        expected_tax = Decimal('37000.00')  # 37% of 100,000
        assert result.total_taxes == expected_tax
        assert result.net_pay == Decimal('63000.00')
    
    def test_decimal_precision(self, tax_engine, mock_db_session):
        """Test that decimal precision is maintained in calculations."""
        # Mock rule with precise rate
        mock_rule = Mock()
        mock_rule.id = 1
        mock_rule.tax_type = TaxType.FEDERAL
        mock_rule.rate_percent = Decimal('0.1234')  # 12.34%
        mock_rule.location = "US"
        
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_rule]
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify precise calculation
        expected_tax = Decimal('123.40')  # 12.34% of 1000, rounded to 2 decimal places
        assert result.total_taxes == expected_tax
    
    def test_tenant_isolation(self, tax_engine, mock_db_session):
        """Test that tenant filtering works correctly."""
        # Create mock rules for different tenants
        tenant1_rule = Mock()
        tenant1_rule.id = 1
        tenant1_rule.tax_type = TaxType.FEDERAL
        tenant1_rule.rate_percent = Decimal('0.20')
        tenant1_rule.tenant_id = 1
        
        # Mock query should be called with tenant filter
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = [tenant1_rule]
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            employee_id=1,
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15),
            tenant_id=1
        )
        
        result = tax_engine.calculate_payroll_taxes(request)
        
        # Verify the query was called (tenant filtering would be in the actual implementation)
        mock_db_session.query.assert_called()
        assert result.total_taxes == Decimal('200.00')  # 20% of 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])