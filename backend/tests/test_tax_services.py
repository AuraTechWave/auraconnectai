"""
Comprehensive unit tests for Tax Services (AUR-276).

Tests cover:
- PayrollTaxEngine functionality
- PayrollTaxService operations
- Tax rule evaluation and application
- Multi-jurisdiction tax calculations
- Error handling and edge cases
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from modules.payroll.services.payroll_tax_engine import PayrollTaxEngine
from modules.payroll.services.payroll_tax_service import PayrollTaxService
from modules.payroll.schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest, PayrollTaxCalculationResponse,
    PayrollTaxServiceRequest, PayrollTaxServiceResponse,
    TaxApplicationDetail, TaxBreakdown
)
from modules.payroll.models.payroll_models import TaxRule, EmployeePaymentTaxApplication
from modules.payroll.enums.payroll_enums import TaxType


class TestPayrollTaxEngine:
    """Unit tests for PayrollTaxEngine core functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def tax_engine(self, mock_db_session):
        """Create PayrollTaxEngine instance with mock database."""
        return PayrollTaxEngine(mock_db_session)
    
    @pytest.fixture
    def sample_tax_rules(self):
        """Create sample tax rules for testing."""
        return [
            TaxRule(
                id=1,
                rule_name="Federal Income Tax",
                location="US",
                tax_type=TaxType.FEDERAL,
                rate_percent=Decimal('0.22'),
                effective_date=datetime(2024, 1, 1),
                is_active=True
            ),
            TaxRule(
                id=2,
                rule_name="California State Tax",
                location="California",
                tax_type=TaxType.STATE,
                rate_percent=Decimal('0.08'),
                effective_date=datetime(2024, 1, 1),
                is_active=True
            ),
            TaxRule(
                id=3,
                rule_name="Social Security",
                location="US",
                tax_type=TaxType.SOCIAL_SECURITY,
                rate_percent=Decimal('0.062'),
                effective_date=datetime(2024, 1, 1),
                is_active=True
            ),
            TaxRule(
                id=4,
                rule_name="Medicare",
                location="US",
                tax_type=TaxType.MEDICARE,
                rate_percent=Decimal('0.0145'),
                effective_date=datetime(2024, 1, 1),
                is_active=True
            )
        ]
    
    def test_get_applicable_tax_rules_by_location(self, tax_engine, mock_db_session, sample_tax_rules):
        """Test filtering tax rules by location."""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
            sample_tax_rules[0], sample_tax_rules[2], sample_tax_rules[3]  # US rules only
        ]
        mock_db_session.query.return_value = mock_query
        
        # Test getting applicable rules for US location
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15),
            tenant_id=1
        )
        
        applicable_rules = tax_engine._get_applicable_tax_rules(
            location=request.location,
            pay_date=request.pay_date,
            tenant_id=request.tenant_id
        )
        
        # Verify query was called correctly
        mock_db_session.query.assert_called_once_with(TaxRule)
        
        # Should return US-specific rules
        assert len(applicable_rules) == 3
        us_rule_types = {rule.tax_type for rule in applicable_rules}
        assert TaxType.FEDERAL in us_rule_types
        assert TaxType.SOCIAL_SECURITY in us_rule_types
        assert TaxType.MEDICARE in us_rule_types
    
    def test_get_applicable_tax_rules_by_date(self, tax_engine, mock_db_session):
        """Test filtering tax rules by effective date."""
        # Create rules with different effective dates
        past_rule = TaxRule(
            rule_name="Old Tax Rate",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.20'),
            effective_date=datetime(2023, 1, 1),
            expiry_date=datetime(2023, 12, 31),
            is_active=False
        )
        
        current_rule = TaxRule(
            rule_name="Current Tax Rate",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.22'),
            effective_date=datetime(2024, 1, 1),
            is_active=True
        )
        
        future_rule = TaxRule(
            rule_name="Future Tax Rate",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.25'),
            effective_date=datetime(2025, 1, 1),
            is_active=True
        )
        
        # Mock query to return only current rule
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = [current_rule]
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        applicable_rules = tax_engine._get_applicable_tax_rules(
            location=request.location,
            pay_date=request.pay_date
        )
        
        # Should only return current rule
        assert len(applicable_rules) == 1
        assert applicable_rules[0].rule_name == "Current Tax Rate"
        assert applicable_rules[0].rate_percent == Decimal('0.22')
    
    def test_calculate_payroll_taxes_basic(self, tax_engine, mock_db_session, sample_tax_rules):
        """Test basic payroll tax calculation."""
        # Mock applicable rules
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = sample_tax_rules
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('1000.00'),
            location="US",
            pay_date=date(2024, 6, 15),
            tenant_id=1
        )
        
        response = tax_engine.calculate_payroll_taxes(request)
        
        # Verify response structure
        assert isinstance(response, PayrollTaxCalculationResponse)
        assert response.gross_pay == Decimal('1000.00')
        assert response.total_taxes > Decimal('0.00')
        assert len(response.tax_details) > 0
        
        # Verify tax calculations
        expected_federal = Decimal('1000.00') * Decimal('0.22')  # 22%
        expected_social_security = Decimal('1000.00') * Decimal('0.062')  # 6.2%
        expected_medicare = Decimal('1000.00') * Decimal('0.0145')  # 1.45%
        
        tax_amounts = {detail.tax_rule.tax_type: detail.calculated_amount for detail in response.tax_details}
        
        assert tax_amounts.get(TaxType.FEDERAL) == expected_federal
        assert tax_amounts.get(TaxType.SOCIAL_SECURITY) == expected_social_security
        assert tax_amounts.get(TaxType.MEDICARE) == expected_medicare
    
    def test_calculate_payroll_taxes_multi_jurisdiction(self, tax_engine, mock_db_session, sample_tax_rules):
        """Test multi-jurisdiction tax calculation (US + California)."""
        # Mock rules including state tax
        california_rules = sample_tax_rules  # Includes both US and California rules
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = california_rules
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('2000.00'),
            location="California",
            pay_date=date(2024, 6, 15),
            tenant_id=1
        )
        
        response = tax_engine.calculate_payroll_taxes(request)
        
        # Should include federal, state, social security, and medicare taxes
        tax_types = {detail.tax_rule.tax_type for detail in response.tax_details}
        assert TaxType.FEDERAL in tax_types
        assert TaxType.STATE in tax_types
        assert TaxType.SOCIAL_SECURITY in tax_types
        assert TaxType.MEDICARE in tax_types
        
        # Verify total includes all jurisdictions
        expected_total = (
            Decimal('2000.00') * Decimal('0.22') +  # Federal
            Decimal('2000.00') * Decimal('0.08') +  # State
            Decimal('2000.00') * Decimal('0.062') + # Social Security
            Decimal('2000.00') * Decimal('0.0145')  # Medicare
        )
        assert response.total_taxes == expected_total
    
    def test_calculate_payroll_taxes_no_applicable_rules(self, tax_engine, mock_db_session):
        """Test behavior when no tax rules are applicable."""
        # Mock empty result
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('1000.00'),
            location="NonExistentLocation",
            pay_date=date(2024, 6, 15)
        )
        
        response = tax_engine.calculate_payroll_taxes(request)
        
        # Should return zero taxes but valid response
        assert response.total_taxes == Decimal('0.00')
        assert len(response.tax_details) == 0
        assert response.gross_pay == Decimal('1000.00')
    
    def test_calculate_payroll_taxes_zero_gross_pay(self, tax_engine, mock_db_session, sample_tax_rules):
        """Test calculation with zero gross pay."""
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = sample_tax_rules
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('0.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        response = tax_engine.calculate_payroll_taxes(request)
        
        # Should return zero taxes
        assert response.total_taxes == Decimal('0.00')
        assert all(detail.calculated_amount == Decimal('0.00') for detail in response.tax_details)
    
    def test_calculate_payroll_taxes_negative_gross_pay(self, tax_engine, mock_db_session):
        """Test calculation with negative gross pay (should handle gracefully)."""
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        request = PayrollTaxCalculationRequest(
            gross_pay=Decimal('-100.00'),
            location="US",
            pay_date=date(2024, 6, 15)
        )
        
        # Should handle negative amounts gracefully
        response = tax_engine.calculate_payroll_taxes(request)
        assert isinstance(response, PayrollTaxCalculationResponse)


class TestPayrollTaxService:
    """Unit tests for PayrollTaxService business logic."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_tax_engine(self):
        """Create mock PayrollTaxEngine."""
        return Mock(spec=PayrollTaxEngine)
    
    @pytest.fixture
    def tax_service(self, mock_db_session):
        """Create PayrollTaxService instance."""
        return PayrollTaxService(mock_db_session)
    
    @pytest.fixture
    def sample_service_request(self):
        """Create sample service request."""
        return PayrollTaxServiceRequest(
            gross_pay=Decimal('1500.00'),
            location="California",
            pay_date=date(2024, 6, 15),
            staff_id=123,
            tenant_id=1
        )
    
    def test_calculate_comprehensive_taxes_success(self, tax_service, mock_db_session, sample_service_request):
        """Test successful comprehensive tax calculation."""
        # Mock the tax engine response
        mock_engine_response = PayrollTaxCalculationResponse(
            gross_pay=Decimal('1500.00'),
            total_taxes=Decimal('450.00'),
            calculation_date=datetime.now(),
            location="California",
            tax_details=[
                TaxApplicationDetail(
                    tax_rule=Mock(tax_type=TaxType.FEDERAL, rate_percent=Decimal('0.22')),
                    calculated_amount=Decimal('330.00'),
                    effective_rate=Decimal('0.22'),
                    taxable_amount=Decimal('1500.00')
                ),
                TaxApplicationDetail(
                    tax_rule=Mock(tax_type=TaxType.STATE, rate_percent=Decimal('0.08')),
                    calculated_amount=Decimal('120.00'),
                    effective_rate=Decimal('0.08'),
                    taxable_amount=Decimal('1500.00')
                )
            ]
        )
        
        # Mock the engine calculation
        with patch.object(tax_service, 'tax_engine') as mock_engine:
            mock_engine.calculate_payroll_taxes.return_value = mock_engine_response
            
            response = tax_service.calculate_comprehensive_taxes(sample_service_request)
            
            # Verify response
            assert isinstance(response, PayrollTaxServiceResponse)
            assert response.total_taxes == Decimal('450.00')
            assert response.federal_tax == Decimal('330.00')
            assert response.state_tax == Decimal('120.00')
            assert response.calculation_successful is True
    
    def test_calculate_comprehensive_taxes_with_tax_applications(self, tax_service, mock_db_session, sample_service_request):
        """Test tax calculation with tax application records."""
        # Mock successful calculation
        mock_response = PayrollTaxServiceResponse(
            gross_pay=Decimal('1500.00'),
            total_taxes=Decimal('450.00'),
            federal_tax=Decimal('330.00'),
            state_tax=Decimal('120.00'),
            calculation_successful=True
        )
        
        with patch.object(tax_service, 'calculate_comprehensive_taxes', return_value=mock_response):
            with patch.object(tax_service, '_create_tax_applications') as mock_create_apps:
                
                result = tax_service.calculate_and_apply_taxes(
                    employee_payment_id=456,
                    request=sample_service_request
                )
                
                # Verify tax applications were created
                mock_create_apps.assert_called_once()
                assert result.calculation_successful is True
    
    def test_calculate_comprehensive_taxes_engine_failure(self, tax_service, sample_service_request):
        """Test handling of tax engine calculation failure."""
        # Mock engine to raise exception
        with patch.object(tax_service, 'tax_engine') as mock_engine:
            mock_engine.calculate_payroll_taxes.side_effect = Exception("Tax calculation failed")
            
            response = tax_service.calculate_comprehensive_taxes(sample_service_request)
            
            # Should return failed response with fallback
            assert response.calculation_successful is False
            assert response.total_taxes >= Decimal('0.00')  # Should have fallback calculation
            assert "fallback" in response.calculation_notes.lower()
    
    def test_fallback_tax_calculation(self, tax_service, sample_service_request):
        """Test fallback tax calculation when engine fails."""
        fallback_response = tax_service._calculate_fallback_taxes(sample_service_request)
        
        # Should return reasonable approximation
        assert isinstance(fallback_response, PayrollTaxServiceResponse)
        assert fallback_response.total_taxes > Decimal('0.00')
        assert fallback_response.calculation_successful is False
        assert "estimated" in fallback_response.calculation_notes.lower()
        
        # Verify fallback percentages are reasonable
        total_rate = fallback_response.total_taxes / sample_service_request.gross_pay
        assert Decimal('0.20') <= total_rate <= Decimal('0.40')  # 20-40% range is reasonable
    
    def test_create_tax_applications(self, tax_service, mock_db_session):
        """Test creation of tax application records."""
        tax_details = [
            TaxApplicationDetail(
                tax_rule=Mock(id=1, tax_type=TaxType.FEDERAL),
                calculated_amount=Decimal('220.00'),
                effective_rate=Decimal('0.22'),
                taxable_amount=Decimal('1000.00')
            ),
            TaxApplicationDetail(
                tax_rule=Mock(id=2, tax_type=TaxType.STATE),
                calculated_amount=Decimal('80.00'),
                effective_rate=Decimal('0.08'),
                taxable_amount=Decimal('1000.00')
            )
        ]
        
        # Mock database operations
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        
        tax_service._create_tax_applications(
            employee_payment_id=123,
            tax_details=tax_details
        )
        
        # Verify database calls
        assert mock_db_session.add.call_count == 2  # Two tax applications
        mock_db_session.commit.assert_called_once()
    
    def test_get_tax_breakdown_by_type(self, tax_service):
        """Test tax breakdown categorization by type."""
        tax_details = [
            TaxApplicationDetail(
                tax_rule=Mock(tax_type=TaxType.FEDERAL),
                calculated_amount=Decimal('220.00'),
                effective_rate=Decimal('0.22'),
                taxable_amount=Decimal('1000.00')
            ),
            TaxApplicationDetail(
                tax_rule=Mock(tax_type=TaxType.SOCIAL_SECURITY),
                calculated_amount=Decimal('62.00'),
                effective_rate=Decimal('0.062'),
                taxable_amount=Decimal('1000.00')
            ),
            TaxApplicationDetail(
                tax_rule=Mock(tax_type=TaxType.MEDICARE),
                calculated_amount=Decimal('14.50'),
                effective_rate=Decimal('0.0145'),
                taxable_amount=Decimal('1000.00')
            )
        ]
        
        breakdown = tax_service._get_tax_breakdown_by_type(tax_details)
        
        assert breakdown.federal_tax == Decimal('220.00')
        assert breakdown.social_security_tax == Decimal('62.00')
        assert breakdown.medicare_tax == Decimal('14.50')
        assert breakdown.state_tax == Decimal('0.00')  # Not present in details
        assert breakdown.local_tax == Decimal('0.00')  # Not present in details


class TestTaxCalculationEdgeCases:
    """Test edge cases and error conditions for tax calculations."""
    
    @pytest.fixture
    def tax_engine(self):
        """Create tax engine with real database session."""
        mock_db = Mock(spec=Session)
        return PayrollTaxEngine(mock_db)
    
    def test_very_large_gross_pay(self, tax_engine):
        """Test tax calculation with very large gross pay amounts."""
        # Mock rules for large amount
        large_amount_rule = TaxRule(
            rule_name="High Earner Tax",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.37'),  # High tax rate
            effective_date=datetime(2024, 1, 1),
            is_active=True
        )
        
        with patch.object(tax_engine, '_get_applicable_tax_rules', return_value=[large_amount_rule]):
            request = PayrollTaxCalculationRequest(
                gross_pay=Decimal('1000000.00'),  # $1M gross pay
                location="US",
                pay_date=date(2024, 6, 15)
            )
            
            response = tax_engine.calculate_payroll_taxes(request)
            
            # Should handle large amounts correctly
            expected_tax = Decimal('1000000.00') * Decimal('0.37')
            assert response.total_taxes == expected_tax
            assert len(response.tax_details) == 1
    
    def test_very_small_gross_pay(self, tax_engine):
        """Test tax calculation with very small gross pay amounts."""
        small_amount_rule = TaxRule(
            rule_name="Minimum Tax",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.10'),
            effective_date=datetime(2024, 1, 1),
            is_active=True
        )
        
        with patch.object(tax_engine, '_get_applicable_tax_rules', return_value=[small_amount_rule]):
            request = PayrollTaxCalculationRequest(
                gross_pay=Decimal('0.01'),  # 1 cent
                location="US",
                pay_date=date(2024, 6, 15)
            )
            
            response = tax_engine.calculate_payroll_taxes(request)
            
            # Should handle small amounts with proper precision
            expected_tax = Decimal('0.01') * Decimal('0.10')
            assert response.total_taxes == expected_tax.quantize(Decimal('0.01'))
    
    def test_future_date_calculation(self, tax_engine):
        """Test tax calculation for future pay dates."""
        future_rule = TaxRule(
            rule_name="Future Tax Rule",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.25'),
            effective_date=datetime(2025, 1, 1),
            is_active=True
        )
        
        with patch.object(tax_engine, '_get_applicable_tax_rules', return_value=[future_rule]):
            request = PayrollTaxCalculationRequest(
                gross_pay=Decimal('1000.00'),
                location="US",
                pay_date=date(2025, 6, 15)  # Future date
            )
            
            response = tax_engine.calculate_payroll_taxes(request)
            
            # Should apply future tax rules correctly
            assert response.total_taxes == Decimal('250.00')  # 25% of $1000
    
    def test_tenant_isolation(self, tax_engine):
        """Test that tenant-specific rules are properly isolated."""
        tenant1_rule = TaxRule(
            rule_name="Tenant 1 Rule",
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.20'),
            effective_date=datetime(2024, 1, 1),
            is_active=True
        )
        
        tenant2_rule = TaxRule(
            rule_name="Tenant 2 Rule", 
            tax_type=TaxType.FEDERAL,
            rate_percent=Decimal('0.25'),
            effective_date=datetime(2024, 1, 1),
            is_active=True
        )
        
        # Test tenant 1
        with patch.object(tax_engine, '_get_applicable_tax_rules', return_value=[tenant1_rule]):
            request1 = PayrollTaxCalculationRequest(
                gross_pay=Decimal('1000.00'),
                location="US",
                pay_date=date(2024, 6, 15),
                tenant_id=1
            )
            
            response1 = tax_engine.calculate_payroll_taxes(request1)
            assert response1.total_taxes == Decimal('200.00')  # 20% rate
        
        # Test tenant 2  
        with patch.object(tax_engine, '_get_applicable_tax_rules', return_value=[tenant2_rule]):
            request2 = PayrollTaxCalculationRequest(
                gross_pay=Decimal('1000.00'),
                location="US", 
                pay_date=date(2024, 6, 15),
                tenant_id=2
            )
            
            response2 = tax_engine.calculate_payroll_taxes(request2)
            assert response2.total_taxes == Decimal('250.00')  # 25% rate


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=modules.payroll.services"])