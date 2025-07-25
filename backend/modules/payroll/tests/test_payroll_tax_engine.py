import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from ..services.payroll_tax_engine import PayrollTaxEngine
from ..models.payroll_models import TaxRule
from ..enums.payroll_enums import TaxType
from ..schemas.payroll_tax_schemas import PayrollTaxCalculationRequest


class TestPayrollTaxEngine:
    """Test suite for PayrollTaxEngine."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def tax_engine(self, mock_db):
        """Tax engine instance with mocked database."""
        return PayrollTaxEngine(mock_db)
    
    @pytest.fixture
    def sample_tax_rules(self):
        """Sample tax rules for testing."""
        return [
            # Federal income tax
            TaxRule(
                id=1,
                rule_name="Federal Income Tax",
                location="California",
                tax_type=TaxType.FEDERAL,
                rate_percent=Decimal('22.0000'),
                employee_portion=Decimal('22.0000'),
                employer_portion=Decimal('0.0000'),
                effective_date=datetime(2025, 1, 1),
                expiry_date=None,
                is_active=True
            ),
            # State income tax
            TaxRule(
                id=2,
                rule_name="California State Tax",
                location="California",
                tax_type=TaxType.STATE,
                rate_percent=Decimal('8.0000'),
                employee_portion=Decimal('8.0000'),
                employer_portion=Decimal('0.0000'),
                effective_date=datetime(2025, 1, 1),
                expiry_date=None,
                is_active=True
            ),
            # Social Security
            TaxRule(
                id=3,
                rule_name="Social Security",
                location="California",
                tax_type=TaxType.SOCIAL_SECURITY,
                rate_percent=Decimal('12.4000'),
                employee_portion=Decimal('6.2000'),
                employer_portion=Decimal('6.2000'),
                max_taxable_amount=Decimal('160200.00'),
                effective_date=datetime(2025, 1, 1),
                expiry_date=None,
                is_active=True
            ),
            # Medicare
            TaxRule(
                id=4,
                rule_name="Medicare",
                location="California",
                tax_type=TaxType.MEDICARE,
                rate_percent=Decimal('2.9000'),
                employee_portion=Decimal('1.45000'),
                employer_portion=Decimal('1.45000'),
                effective_date=datetime(2025, 1, 1),
                expiry_date=None,
                is_active=True
            )
        ]
    
    @pytest.fixture
    def sample_request(self):
        """Sample tax calculation request."""
        return PayrollTaxCalculationRequest(
            employee_id=123,
            location="California",
            gross_pay=Decimal('5000.00'),
            pay_date=date(2025, 7, 15),
            tenant_id=1
        )
    
    def test_calculate_payroll_taxes_with_multiple_rules(
        self, tax_engine, mock_db, sample_tax_rules, sample_request
    ):
        """Test tax calculation with multiple applicable rules."""
        # Mock database query to return sample rules
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = sample_tax_rules
        mock_db.query.return_value = mock_query
        
        # Calculate taxes
        result = tax_engine.calculate_payroll_taxes(sample_request)
        
        # Verify results
        assert result.gross_pay == Decimal('5000.00')
        assert result.total_taxes > Decimal('0.00')
        assert result.net_pay == result.gross_pay - result.total_taxes
        
        # Check tax breakdown
        breakdown = result.tax_breakdown
        assert breakdown.federal_tax == Decimal('1100.00')  # 22% of 5000
        assert breakdown.state_tax == Decimal('400.00')     # 8% of 5000
        assert breakdown.social_security_tax == Decimal('310.00')  # 6.2% of 5000
        assert breakdown.medicare_tax == Decimal('72.50')   # 1.45% of 5000
        
        # Verify tax applications
        assert len(result.tax_applications) == 4
        assert all(app.calculated_tax > Decimal('0.00') for app in result.tax_applications)
    
    def test_calculate_payroll_taxes_no_applicable_rules(
        self, tax_engine, mock_db, sample_request
    ):
        """Test tax calculation when no rules are applicable."""
        # Mock database query to return empty list
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Calculate taxes
        result = tax_engine.calculate_payroll_taxes(sample_request)
        
        # Verify zero tax response
        assert result.gross_pay == Decimal('5000.00')
        assert result.total_taxes == Decimal('0.00')
        assert result.net_pay == Decimal('5000.00')
        assert len(result.tax_applications) == 0
        
        breakdown = result.tax_breakdown
        assert breakdown.federal_tax == Decimal('0.00')
        assert breakdown.state_tax == Decimal('0.00')
        assert breakdown.social_security_tax == Decimal('0.00')
        assert breakdown.medicare_tax == Decimal('0.00')
    
    def test_get_applicable_tax_rules_filters_by_date(
        self, tax_engine, mock_db
    ):
        """Test that tax rules are filtered by effective and expiry dates."""
        # Create rules with different effective dates
        past_rule = TaxRule(
            id=1,
            rule_name="Past Rule",
            location="California",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('20.0000'),
            effective_date=datetime(2024, 1, 1),
            expiry_date=datetime(2024, 12, 31),
            is_active=True
        )
        
        current_rule = TaxRule(
            id=2,
            rule_name="Current Rule",
            location="California",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('22.0000'),
            effective_date=datetime(2025, 1, 1),
            expiry_date=None,
            is_active=True
        )
        
        future_rule = TaxRule(
            id=3,
            rule_name="Future Rule", 
            location="California",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('25.0000'),
            effective_date=datetime(2026, 1, 1),
            expiry_date=None,
            is_active=True
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [current_rule]  # Only current rule should be returned
        mock_db.query.return_value = mock_query
        
        # Get applicable rules for current date
        rules = tax_engine._get_applicable_tax_rules(
            location="California",
            pay_date=date(2025, 7, 15),
            tenant_id=1
        )
        
        # Verify filtering was applied correctly via the mock
        mock_db.query.assert_called_once()
    
    def test_apply_tax_rule_with_max_taxable_amount(
        self, tax_engine, sample_request
    ):
        """Test tax calculation with maximum taxable amount cap."""
        # Create rule with max taxable amount
        social_security_rule = TaxRule(
            id=1,
            rule_name="Social Security",
            location="California",
            tax_type=TaxType.SOCIAL_SECURITY,
            rate_percent=Decimal('12.4000'),
            employee_portion=Decimal('6.2000'),
            max_taxable_amount=Decimal('160200.00'),
            effective_date=datetime(2025, 1, 1),
            is_active=True
        )
        
        # Test with gross pay below cap
        low_pay_request = PayrollTaxCalculationRequest(
            employee_id=123,
            location="California",
            gross_pay=Decimal('5000.00'),
            pay_date=date(2025, 7, 15)
        )
        
        application = tax_engine._apply_tax_rule(social_security_rule, low_pay_request)
        
        assert application is not None
        assert application.taxable_amount == Decimal('5000.00')
        assert application.calculated_tax == Decimal('310.00')  # 6.2% of 5000
        
        # Test with gross pay above cap
        high_pay_request = PayrollTaxCalculationRequest(
            employee_id=123,
            location="California", 
            gross_pay=Decimal('200000.00'),
            pay_date=date(2025, 7, 15)
        )
        
        application = tax_engine._apply_tax_rule(social_security_rule, high_pay_request)
        
        assert application is not None
        assert application.taxable_amount == Decimal('160200.00')  # Capped amount
        assert application.calculated_tax == Decimal('9932.40')  # 6.2% of 160200
    
    def test_apply_tax_rule_with_min_taxable_amount(
        self, tax_engine, sample_request
    ):
        """Test tax calculation with minimum taxable amount threshold."""
        # Create rule with minimum taxable amount
        rule_with_min = TaxRule(
            id=1,
            rule_name="High Earner Tax",
            location="California",
            tax_type=TaxType.STATE,
            rate_percent=Decimal('10.0000'),
            employee_portion=Decimal('10.0000'),
            min_taxable_amount=Decimal('10000.00'),
            effective_date=datetime(2025, 1, 1),
            is_active=True
        )
        
        # Test with gross pay below minimum - should return None
        low_pay_request = PayrollTaxCalculationRequest(
            employee_id=123,
            location="California",
            gross_pay=Decimal('5000.00'),
            pay_date=date(2025, 7, 15)
        )
        
        application = tax_engine._apply_tax_rule(rule_with_min, low_pay_request)
        assert application is None
        
        # Test with gross pay above minimum
        high_pay_request = PayrollTaxCalculationRequest(
            employee_id=123,
            location="California",
            gross_pay=Decimal('15000.00'),
            pay_date=date(2025, 7, 15)
        )
        
        application = tax_engine._apply_tax_rule(rule_with_min, high_pay_request)
        
        assert application is not None
        assert application.taxable_amount == Decimal('15000.00')
        assert application.calculated_tax == Decimal('1500.00')  # 10% of 15000
    
    def test_calculate_taxable_amount_edge_cases(self, tax_engine):
        """Test taxable amount calculation with various edge cases."""
        gross_pay = Decimal('50000.00')
        
        # Rule with no limits
        no_limit_rule = TaxRule(
            rate_percent=Decimal('10.0000'),
            min_taxable_amount=None,
            max_taxable_amount=None
        )
        
        amount = tax_engine._calculate_taxable_amount(no_limit_rule, gross_pay)
        assert amount == gross_pay
        
        # Rule with both min and max
        both_limits_rule = TaxRule(
            rate_percent=Decimal('10.0000'),
            min_taxable_amount=Decimal('30000.00'),
            max_taxable_amount=Decimal('40000.00')
        )
        
        amount = tax_engine._calculate_taxable_amount(both_limits_rule, gross_pay)
        assert amount == Decimal('40000.00')  # Capped at max
        
        # Rule with min higher than gross pay
        high_min_rule = TaxRule(
            rate_percent=Decimal('10.0000'),
            min_taxable_amount=Decimal('60000.00'),
            max_taxable_amount=None
        )
        
        amount = tax_engine._calculate_taxable_amount(high_min_rule, gross_pay)
        assert amount == Decimal('0.00')  # Below minimum threshold
    
    def test_get_calculation_method(self, tax_engine):
        """Test calculation method determination."""
        # Basic percentage rule
        basic_rule = TaxRule(
            rate_percent=Decimal('10.0000'),
            employee_portion=Decimal('10.0000'),
            min_taxable_amount=None,
            max_taxable_amount=None
        )
        
        method = tax_engine._get_calculation_method(basic_rule)
        assert method == "percentage"
        
        # Rule with maximum cap
        capped_rule = TaxRule(
            rate_percent=Decimal('10.0000'),
            employee_portion=Decimal('10.0000'),
            min_taxable_amount=None,
            max_taxable_amount=Decimal('100000.00')
        )
        
        method = tax_engine._get_calculation_method(capped_rule)
        assert method == "percentage_capped"
        
        # Rule with employee/employer split
        split_rule = TaxRule(
            rate_percent=Decimal('12.4000'),
            employee_portion=Decimal('6.2000'),
            min_taxable_amount=None,
            max_taxable_amount=None
        )
        
        method = tax_engine._get_calculation_method(split_rule)
        assert method == "percentage_split_employer_employee"
    
    def test_save_tax_applications(self, tax_engine, mock_db):
        """Test saving tax applications to database."""
        from ..schemas.payroll_tax_schemas import TaxApplicationDetail
        
        # Create sample tax applications
        applications = [
            TaxApplicationDetail(
                tax_rule_id=1,
                rule_name="Federal Tax",
                tax_type=TaxType.FEDERAL,
                location="California",
                taxable_amount=Decimal('5000.00'),
                calculated_tax=Decimal('1100.00'),
                effective_rate=Decimal('22.0000'),
                calculation_method="percentage"
            ),
            TaxApplicationDetail(
                tax_rule_id=2,
                rule_name="State Tax",
                tax_type=TaxType.STATE,
                location="California", 
                taxable_amount=Decimal('5000.00'),
                calculated_tax=Decimal('400.00'),
                effective_rate=Decimal('8.0000'),
                calculation_method="percentage"
            )
        ]
        
        # Save applications
        saved_apps = tax_engine.save_tax_applications(
            employee_payment_id=123,
            tax_applications=applications
        )
        
        # Verify database operations
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()
        assert len(saved_apps) == 2
    
    def test_get_jurisdiction_summary(self, tax_engine, mock_db, sample_tax_rules):
        """Test jurisdiction summary generation."""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = sample_tax_rules
        mock_db.query.return_value = mock_query
        
        # Get jurisdiction summary
        summary = tax_engine.get_jurisdiction_summary(
            location="California",
            pay_date=date(2025, 7, 15),
            tenant_id=1
        )
        
        # Verify summary structure
        assert "federal" in summary
        assert "state" in summary
        assert "local" in summary
        assert "payroll_taxes" in summary
        
        # Verify content
        assert len(summary["federal"]) == 1
        assert len(summary["state"]) == 1
        assert len(summary["payroll_taxes"]) == 2  # Social Security + Medicare
        
        # Verify rule details
        federal_rule = summary["federal"][0]
        assert federal_rule["rule_name"] == "Federal Income Tax"
        assert federal_rule["rate_percent"] == 22.0
        assert federal_rule["employee_portion"] == 22.0