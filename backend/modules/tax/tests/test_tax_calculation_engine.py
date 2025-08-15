# backend/modules/tax/tests/test_tax_calculation_engine.py

import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from core.database import Base
from modules.tax.models import (
    TaxJurisdiction,
    TaxRate,
    TaxRuleConfiguration,
    TaxExemptionCertificate,
)
from modules.tax.schemas import (
    EnhancedTaxCalculationRequest,
    TaxCalculationLocation,
    TaxCalculationLineItem,
)
from modules.tax.services import TaxCalculationEngine


class TestTaxCalculationEngine:
    """Test suite for tax calculation engine"""

    @pytest.fixture
    def test_db(self):
        """Create test database"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        yield db

        db.close()
        Base.metadata.drop_all(bind=engine)

    @pytest.fixture
    def sample_jurisdictions(self, test_db):
        """Create sample tax jurisdictions"""
        # Federal
        federal = TaxJurisdiction(
            jurisdiction_id=uuid.uuid4(),
            name="United States",
            code="US",
            jurisdiction_type="federal",
            country_code="US",
            is_active=True,
            effective_date=date(2020, 1, 1),
            tenant_id=1,
        )
        test_db.add(federal)

        # State
        state = TaxJurisdiction(
            jurisdiction_id=uuid.uuid4(),
            name="California",
            code="CA",
            jurisdiction_type="state",
            parent_jurisdiction_id=federal.id,
            country_code="US",
            state_code="CA",
            is_active=True,
            effective_date=date(2020, 1, 1),
            tenant_id=1,
        )
        test_db.add(state)
        test_db.flush()

        # County
        county = TaxJurisdiction(
            jurisdiction_id=uuid.uuid4(),
            name="Los Angeles County",
            code="LA-COUNTY",
            jurisdiction_type="county",
            parent_jurisdiction_id=state.id,
            country_code="US",
            state_code="CA",
            county_name="Los Angeles",
            is_active=True,
            effective_date=date(2020, 1, 1),
            tenant_id=1,
        )
        test_db.add(county)

        # City
        city = TaxJurisdiction(
            jurisdiction_id=uuid.uuid4(),
            name="Los Angeles",
            code="LA-CITY",
            jurisdiction_type="city",
            parent_jurisdiction_id=county.id,
            country_code="US",
            state_code="CA",
            county_name="Los Angeles",
            city_name="Los Angeles",
            is_active=True,
            effective_date=date(2020, 1, 1),
            tenant_id=1,
        )
        test_db.add(city)

        test_db.commit()

        return {"federal": federal, "state": state, "county": county, "city": city}

    @pytest.fixture
    def sample_tax_rates(self, test_db, sample_jurisdictions):
        """Create sample tax rates"""
        rates = []

        # State sales tax - 6%
        state_rate = TaxRate(
            rate_id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdictions["state"].id,
            tax_type="sales",
            tax_subtype="state_sales",
            rate_percent=Decimal("6.0"),
            effective_date=date(2020, 1, 1),
            is_active=True,
            calculation_method="percentage",
            ordering=1,
            tenant_id=1,
        )
        rates.append(state_rate)
        test_db.add(state_rate)

        # County sales tax - 1%
        county_rate = TaxRate(
            rate_id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdictions["county"].id,
            tax_type="sales",
            tax_subtype="county_sales",
            rate_percent=Decimal("1.0"),
            effective_date=date(2020, 1, 1),
            is_active=True,
            calculation_method="percentage",
            ordering=2,
            tenant_id=1,
        )
        rates.append(county_rate)
        test_db.add(county_rate)

        # City sales tax - 1.5%
        city_rate = TaxRate(
            rate_id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdictions["city"].id,
            tax_type="sales",
            tax_subtype="city_sales",
            rate_percent=Decimal("1.5"),
            effective_date=date(2020, 1, 1),
            is_active=True,
            calculation_method="percentage",
            ordering=3,
            tenant_id=1,
        )
        rates.append(city_rate)
        test_db.add(city_rate)

        test_db.commit()

        return rates

    def test_basic_tax_calculation(
        self, test_db, sample_jurisdictions, sample_tax_rates
    ):
        """Test basic tax calculation with multiple jurisdictions"""
        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-001",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="US",
                state_code="CA",
                county_name="Los Angeles",
                city_name="Los Angeles",
                zip_code="90001",
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("100.00"),
                    quantity=1,
                    category="general",
                    is_exempt=False,
                )
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Total tax should be 8.5% (6% + 1% + 1.5%)
        assert response.total_tax == Decimal("8.50")
        assert response.taxable_amount == Decimal("100.00")
        assert response.total_amount == Decimal("108.50")

        # Check tax breakdown
        assert len(response.line_results) == 1
        line_result = response.line_results[0]
        assert line_result.total_tax == Decimal("8.50")
        assert len(line_result.tax_details) == 3  # State, County, City

    def test_tax_exemption(self, test_db, sample_jurisdictions, sample_tax_rates):
        """Test tax calculation with exemption"""
        # Create exemption certificate
        certificate = TaxExemptionCertificate(
            certificate_id=uuid.uuid4(),
            customer_id=123,
            customer_name="Test Nonprofit",
            certificate_number="EXEMPT-001",
            exemption_type="nonprofit",
            jurisdiction_ids=[j.id for j in sample_jurisdictions.values()],
            tax_types=["sales"],
            issue_date=date.today(),
            is_active=True,
            is_verified=True,
            tenant_id=1,
        )
        test_db.add(certificate)
        test_db.commit()

        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-002",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="US",
                state_code="CA",
                county_name="Los Angeles",
                city_name="Los Angeles",
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("100.00"),
                    quantity=1,
                    is_exempt=False,
                )
            ],
            customer_id=123,
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Should be exempt
        assert response.total_tax == Decimal("0.00")
        assert response.exempt_amount == Decimal("100.00")
        assert len(response.applied_exemptions) == 1

    def test_tax_rules(self, test_db, sample_jurisdictions, sample_tax_rates):
        """Test tax calculation with special rules"""
        # Create a tax holiday rule
        holiday_rule = TaxRuleConfiguration(
            rule_id=uuid.uuid4(),
            rule_name="Back to School Tax Holiday",
            rule_code="BTS-HOLIDAY-2025",
            jurisdiction_id=sample_jurisdictions["state"].id,
            tax_type="sales",
            rule_type="holiday",
            conditions=[
                {
                    "field": "category",
                    "operator": "in",
                    "value": ["clothing", "school_supplies"],
                },
                {"field": "amount", "operator": "lte", "value": 100},
            ],
            actions=[{"action_type": "exempt", "parameters": {}}],
            effective_date=date.today(),
            is_active=True,
            priority=10,
            tenant_id=1,
        )
        test_db.add(holiday_rule)
        test_db.commit()

        engine = TaxCalculationEngine(test_db)

        # Test with qualifying item
        request = EnhancedTaxCalculationRequest(
            transaction_id="test-003",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="US",
                state_code="CA",
                county_name="Los Angeles",
                city_name="Los Angeles",
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("50.00"),
                    quantity=1,
                    category="clothing",
                    is_exempt=False,
                )
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Should be exempt due to tax holiday
        assert response.total_tax == Decimal("0.00")
        assert response.taxable_amount == Decimal("0.00")

    def test_shipping_tax(self, test_db, sample_jurisdictions, sample_tax_rates):
        """Test tax calculation on shipping"""
        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-004",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="US",
                state_code="CA",
                county_name="Los Angeles",
                city_name="Los Angeles",
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("100.00"),
                    quantity=1,
                    is_exempt=False,
                )
            ],
            shipping_amount=Decimal("10.00"),
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Tax on items (100) + shipping (10) = 110 * 8.5% = 9.35
        assert response.subtotal == Decimal("110.00")
        assert response.total_tax == Decimal("9.35")
        assert response.total_amount == Decimal("119.35")

    def test_tiered_rates(self, test_db, sample_jurisdictions):
        """Test calculation with tiered tax rates"""
        # Create tiered rate
        tiered_rate = TaxRate(
            rate_id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdictions["state"].id,
            tax_type="luxury",
            rate_percent=Decimal("10.0"),
            min_amount=Decimal("1000.00"),
            effective_date=date(2020, 1, 1),
            is_active=True,
            calculation_method="percentage",
            tenant_id=1,
        )
        test_db.add(tiered_rate)
        test_db.commit()

        engine = TaxCalculationEngine(test_db)

        # Test below threshold
        request = EnhancedTaxCalculationRequest(
            transaction_id="test-005",
            transaction_date=date.today(),
            location=TaxCalculationLocation(country_code="US", state_code="CA"),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("500.00"),
                    quantity=1,
                    is_exempt=False,
                )
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Should not include luxury tax
        assert "luxury" not in str(response.tax_summary_by_jurisdiction)

    def test_multiple_line_items(self, test_db, sample_jurisdictions, sample_tax_rates):
        """Test calculation with multiple line items"""
        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-006",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="US",
                state_code="CA",
                county_name="Los Angeles",
                city_name="Los Angeles",
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("50.00"),
                    quantity=2,  # $100 total
                    is_exempt=False,
                ),
                TaxCalculationLineItem(
                    line_id="item2",
                    amount=Decimal("25.00"),
                    quantity=1,
                    is_exempt=False,
                ),
                TaxCalculationLineItem(
                    line_id="item3",
                    amount=Decimal("75.00"),
                    quantity=1,
                    is_exempt=True,  # Exempt item
                ),
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Tax on non-exempt items only: (100 + 25) * 8.5% = 10.625
        assert response.taxable_amount == Decimal("125.00")
        assert response.exempt_amount == Decimal("75.00")
        assert response.total_tax == Decimal("10.63")  # Rounded
        assert response.total_amount == Decimal("210.63")

    def test_no_applicable_jurisdictions(self, test_db):
        """Test calculation with no applicable jurisdictions"""
        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-007",
            transaction_date=date.today(),
            location=TaxCalculationLocation(
                country_code="GB", state_code="ENG"  # No UK jurisdictions in test data
            ),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("100.00"),
                    quantity=1,
                    is_exempt=False,
                )
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Should return zero tax with warning
        assert response.total_tax == Decimal("0.00")
        assert len(response.warnings) > 0
        assert "No applicable tax jurisdictions" in response.warnings[0]

    def test_expired_rates(self, test_db, sample_jurisdictions):
        """Test that expired rates are not applied"""
        # Create expired rate
        expired_rate = TaxRate(
            rate_id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdictions["state"].id,
            tax_type="sales",
            rate_percent=Decimal("5.0"),
            effective_date=date(2020, 1, 1),
            expiry_date=date(2023, 12, 31),  # Expired
            is_active=True,
            calculation_method="percentage",
            tenant_id=1,
        )
        test_db.add(expired_rate)
        test_db.commit()

        engine = TaxCalculationEngine(test_db)

        request = EnhancedTaxCalculationRequest(
            transaction_id="test-008",
            transaction_date=date.today(),
            location=TaxCalculationLocation(country_code="US", state_code="CA"),
            line_items=[
                TaxCalculationLineItem(
                    line_id="item1",
                    amount=Decimal("100.00"),
                    quantity=1,
                    is_exempt=False,
                )
            ],
        )

        response = engine.calculate_tax(request, tenant_id=1)

        # Should not apply expired rate
        for line_result in response.line_results:
            for detail in line_result.tax_details:
                assert detail["rate"] != Decimal("5.0")
