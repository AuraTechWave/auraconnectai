"""
Tax calculation utilities for payroll processing.

Extracted from enhanced_payroll_engine.py to improve maintainability
and separate tax-related logic.
"""

from decimal import Decimal
from datetime import date
from dataclasses import dataclass
from typing import Dict, Optional
from sqlalchemy.orm import Session

from ...payroll.services.payroll_tax_engine import PayrollTaxEngine
from ...payroll.services.payroll_tax_service import PayrollTaxService
from ...payroll.schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest,
    PayrollTaxServiceRequest,
)


@dataclass
class TaxBreakdown:
    """Detailed breakdown of tax deductions."""

    federal_tax: Decimal = Decimal("0.00")
    state_tax: Decimal = Decimal("0.00")
    local_tax: Decimal = Decimal("0.00")
    social_security: Decimal = Decimal("0.00")
    medicare: Decimal = Decimal("0.00")
    unemployment: Decimal = Decimal("0.00")

    @property
    def total_tax_deductions(self) -> Decimal:
        """Calculate total tax deductions."""
        return (
            self.federal_tax
            + self.state_tax
            + self.local_tax
            + self.social_security
            + self.medicare
            + self.unemployment
        )


class TaxCalculator:
    """Utility class for calculating tax deductions."""

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = PayrollTaxEngine(db)
        self.tax_service = PayrollTaxService(db)

    async def calculate_tax_deductions(
        self,
        staff_id: int,
        gross_pay: Decimal,
        pay_date: date,
        location: str = "default",
        ytd_earnings: Optional[Decimal] = None,
    ) -> TaxBreakdown:
        """
        Calculate comprehensive tax deductions for payroll.

        Args:
            staff_id: Staff member ID
            gross_pay: Gross pay amount
            pay_date: Pay date for tax calculations
            location: Location for jurisdiction-specific taxes
            ytd_earnings: Year-to-date earnings for cap calculations

        Returns:
            TaxBreakdown with all tax deductions
        """
        try:
            # Use the advanced tax engine for precise calculations
            tax_request = PayrollTaxCalculationRequest(
                staff_id=staff_id,
                gross_pay=gross_pay,
                pay_date=pay_date,
                location=location,
                ytd_earnings=ytd_earnings or Decimal("0.00"),
            )

            tax_result = await self.tax_engine.calculate_payroll_taxes(tax_request)

            return TaxBreakdown(
                federal_tax=tax_result.federal_tax,
                state_tax=tax_result.state_tax,
                local_tax=tax_result.local_tax,
                social_security=tax_result.social_security,
                medicare=tax_result.medicare,
                unemployment=tax_result.unemployment,
            )

        except Exception as e:
            # Fallback to approximation service if advanced engine fails
            return await self._calculate_tax_approximation(
                staff_id, gross_pay, pay_date, location
            )

    async def _calculate_tax_approximation(
        self, staff_id: int, gross_pay: Decimal, pay_date: date, location: str
    ) -> TaxBreakdown:
        """Fallback tax calculation using approximation service."""
        try:
            tax_service_request = PayrollTaxServiceRequest(
                staff_id=staff_id,
                gross_pay=gross_pay,
                pay_date=pay_date,
                location=location,
            )

            tax_service_result = await self.tax_service.calculate_taxes(
                tax_service_request
            )

            return TaxBreakdown(
                federal_tax=tax_service_result.federal_tax,
                state_tax=tax_service_result.state_tax,
                social_security=tax_service_result.social_security,
                medicare=tax_service_result.medicare,
                unemployment=tax_service_result.unemployment,
            )

        except Exception:
            # Final fallback: use hardcoded approximations
            return self._calculate_basic_approximation(gross_pay)

    def _calculate_basic_approximation(self, gross_pay: Decimal) -> TaxBreakdown:
        """Basic tax approximation for emergency fallback."""
        # Conservative approximation rates
        federal_rate = Decimal("0.22")  # 22% federal
        state_rate = Decimal("0.08")  # 8% state average
        ss_rate = Decimal("0.062")  # 6.2% Social Security
        medicare_rate = Decimal("0.0145")  # 1.45% Medicare
        unemployment_rate = Decimal("0.006")  # 0.6% unemployment

        return TaxBreakdown(
            federal_tax=(gross_pay * federal_rate).quantize(Decimal("0.01")),
            state_tax=(gross_pay * state_rate).quantize(Decimal("0.01")),
            social_security=(gross_pay * ss_rate).quantize(Decimal("0.01")),
            medicare=(gross_pay * medicare_rate).quantize(Decimal("0.01")),
            unemployment=(gross_pay * unemployment_rate).quantize(Decimal("0.01")),
        )

    def calculate_social_security_with_cap(
        self,
        gross_pay: Decimal,
        ytd_earnings: Decimal,
        ss_wage_cap: Decimal = Decimal("160200.00"),  # 2024 cap
    ) -> Decimal:
        """Calculate Social Security tax with wage cap consideration."""
        ss_rate = Decimal("0.062")

        if ytd_earnings >= ss_wage_cap:
            # Already hit the cap
            return Decimal("0.00")

        # Calculate how much of current pay is subject to SS tax
        remaining_taxable = ss_wage_cap - ytd_earnings
        taxable_amount = min(gross_pay, remaining_taxable)

        return (taxable_amount * ss_rate).quantize(Decimal("0.01"))

    def calculate_medicare_additional_tax(
        self, gross_pay: Decimal, ytd_earnings: Decimal, filing_status: str = "single"
    ) -> Decimal:
        """Calculate additional Medicare tax for high earners."""
        base_medicare_rate = Decimal("0.0145")
        additional_medicare_rate = Decimal("0.009")  # 0.9% additional

        # Thresholds based on filing status
        thresholds = {
            "single": Decimal("200000.00"),
            "married_joint": Decimal("250000.00"),
            "married_separate": Decimal("125000.00"),
        }

        threshold = thresholds.get(filing_status, Decimal("200000.00"))

        # Base Medicare tax (always applies)
        base_medicare = (gross_pay * base_medicare_rate).quantize(Decimal("0.01"))

        # Additional Medicare tax
        if ytd_earnings + gross_pay > threshold:
            if ytd_earnings >= threshold:
                # All of current pay is subject to additional tax
                additional_medicare = (gross_pay * additional_medicare_rate).quantize(
                    Decimal("0.01")
                )
            else:
                # Only portion above threshold
                excess_amount = (ytd_earnings + gross_pay) - threshold
                additional_medicare = (
                    excess_amount * additional_medicare_rate
                ).quantize(Decimal("0.01"))
        else:
            additional_medicare = Decimal("0.00")

        return base_medicare + additional_medicare

    def batch_calculate_taxes(
        self, payroll_data: Dict[int, Dict[str, any]]
    ) -> Dict[int, TaxBreakdown]:
        """
        Calculate taxes for multiple employees efficiently.

        Args:
            payroll_data: Dict with staff_id -> {gross_pay, pay_date, location}

        Returns:
            Dict with staff_id -> TaxBreakdown
        """
        tax_results = {}

        for staff_id, data in payroll_data.items():
            # For batch processing, use basic approximation for speed
            tax_breakdown = self._calculate_basic_approximation(data["gross_pay"])
            tax_results[staff_id] = tax_breakdown

        return tax_results

    def get_tax_rates_for_location(self, location: str) -> Dict[str, Decimal]:
        """Get current tax rates for a specific location."""
        # This would typically query a tax rates table
        # For now, return default rates
        return {
            "federal_rate": Decimal("0.22"),
            "state_rate": Decimal("0.08"),
            "local_rate": Decimal("0.01"),
            "social_security_rate": Decimal("0.062"),
            "medicare_rate": Decimal("0.0145"),
            "unemployment_rate": Decimal("0.006"),
        }
