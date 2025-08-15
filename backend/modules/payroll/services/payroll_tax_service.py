from sqlalchemy.orm import Session
from typing import Optional
from decimal import Decimal
from datetime import date
from .payroll_tax_engine import PayrollTaxEngine
from ..models.payroll_models import EmployeePayment
from ..schemas.payroll_tax_schemas import (
    PayrollTaxServiceRequest,
    PayrollTaxServiceResponse,
    PayrollTaxCalculationRequest,
    TaxRuleValidationRequest,
    TaxRuleValidationResponse,
)


class PayrollTaxService:
    """
    Internal service API for payroll tax computations.
    Provides high-level interface for payroll system integration.
    """

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = PayrollTaxEngine(db)

    def calculate_and_save_taxes(
        self, request: PayrollTaxServiceRequest
    ) -> PayrollTaxServiceResponse:
        """
        Calculate taxes for an employee payment and optionally save to database.

        Args:
            request: PayrollTaxServiceRequest with payment details

        Returns:
            PayrollTaxServiceResponse with calculation results
        """
        # Create tax calculation request
        tax_request = PayrollTaxCalculationRequest(
            employee_id=request.staff_id,
            location=request.location,
            gross_pay=request.gross_pay,
            pay_date=request.pay_period_end,  # Use end date for tax rule lookup
            tenant_id=request.tenant_id,
        )

        # Calculate taxes
        tax_calculation = self.tax_engine.calculate_payroll_taxes(tax_request)

        applications_saved = False

        # Save tax applications if employee_payment_id is provided
        if request.employee_payment_id:
            self.tax_engine.save_tax_applications(
                employee_payment_id=request.employee_payment_id,
                tax_applications=tax_calculation.tax_applications,
            )
            applications_saved = True

        return PayrollTaxServiceResponse(
            employee_payment_id=request.employee_payment_id,
            tax_calculation=tax_calculation,
            applications_saved=applications_saved,
        )

    def update_employee_payment_taxes(
        self, employee_payment_id: int
    ) -> PayrollTaxServiceResponse:
        """
        Update tax calculations for an existing employee payment record.

        Args:
            employee_payment_id: ID of the EmployeePayment record

        Returns:
            PayrollTaxServiceResponse with updated calculations
        """
        # Get employee payment record
        payment = (
            self.db.query(EmployeePayment)
            .filter(EmployeePayment.id == employee_payment_id)
            .first()
        )

        if not payment:
            raise ValueError(f"Employee payment {employee_payment_id} not found")

        # Create service request from existing payment
        request = PayrollTaxServiceRequest(
            employee_payment_id=employee_payment_id,
            staff_id=payment.staff_id,
            payroll_policy_id=payment.payroll_policy_id,
            pay_period_start=payment.pay_period_start.date(),
            pay_period_end=payment.pay_period_end.date(),
            gross_pay=payment.gross_pay,
            location=payment.payroll_policy.location,
            tenant_id=payment.tenant_id,
        )

        # Calculate and save taxes
        response = self.calculate_and_save_taxes(request)

        # Update employee payment record with calculated taxes
        tax_breakdown = response.tax_calculation.tax_breakdown

        payment.federal_tax = tax_breakdown.federal_tax
        payment.state_tax = tax_breakdown.state_tax
        payment.local_tax = tax_breakdown.local_tax
        payment.social_security_tax = tax_breakdown.social_security_tax
        payment.medicare_tax = tax_breakdown.medicare_tax

        # Update total deductions (assumes other deductions remain the same)
        payment.total_deductions = (
            tax_breakdown.federal_tax
            + tax_breakdown.state_tax
            + tax_breakdown.local_tax
            + tax_breakdown.social_security_tax
            + tax_breakdown.medicare_tax
            + payment.insurance_deduction
            + payment.retirement_deduction
            + payment.other_deductions
        )

        # Update net pay
        payment.net_pay = payment.gross_pay - payment.total_deductions

        self.db.commit()

        return response

    def validate_tax_setup(
        self, request: TaxRuleValidationRequest
    ) -> TaxRuleValidationResponse:
        """
        Validate tax rule setup for a given location and date.

        Args:
            request: TaxRuleValidationRequest with location and date

        Returns:
            TaxRuleValidationResponse with validation results
        """
        jurisdiction_summary = self.tax_engine.get_jurisdiction_summary(
            location=request.location,
            pay_date=request.pay_date,
            tenant_id=request.tenant_id,
        )

        total_rules = sum(len(rules) for rules in jurisdiction_summary.values())

        # Check for missing jurisdictions (basic validation)
        missing_jurisdictions = []
        potential_issues = []

        if not jurisdiction_summary["federal"]:
            missing_jurisdictions.append("federal")

        if not jurisdiction_summary["state"]:
            missing_jurisdictions.append("state")

        # Check for common payroll taxes
        payroll_tax_types = [
            rule["tax_type"] for rule in jurisdiction_summary["payroll_taxes"]
        ]

        if "SOCIAL_SECURITY" not in payroll_tax_types:
            potential_issues.append("Missing Social Security tax rule")

        if "MEDICARE" not in payroll_tax_types:
            potential_issues.append("Missing Medicare tax rule")

        return TaxRuleValidationResponse(
            location=request.location,
            total_rules=total_rules,
            jurisdiction_summary=jurisdiction_summary,
            missing_jurisdictions=missing_jurisdictions,
            potential_issues=potential_issues,
        )

    def get_effective_tax_rates(
        self,
        location: str,
        gross_pay: Decimal,
        pay_date: date,
        tenant_id: Optional[int] = None,
    ) -> dict:
        """
        Get effective tax rates for a given gross pay amount.
        Useful for payroll estimation and planning.

        Args:
            location: Employee work location
            gross_pay: Gross pay amount to calculate rates for
            pay_date: Date for tax rule lookup
            tenant_id: Optional tenant ID

        Returns:
            Dictionary with effective tax rates and amounts
        """
        # Create a sample calculation request
        tax_request = PayrollTaxCalculationRequest(
            employee_id=0,  # Dummy ID for rate calculation
            location=location,
            gross_pay=gross_pay,
            pay_date=pay_date,
            tenant_id=tenant_id,
        )

        # Calculate taxes
        tax_calculation = self.tax_engine.calculate_payroll_taxes(tax_request)

        # Calculate effective rates
        effective_rates = {}

        if gross_pay > 0:
            breakdown = tax_calculation.tax_breakdown

            effective_rates = {
                "gross_pay": float(gross_pay),
                "total_tax_rate": float(tax_calculation.total_taxes / gross_pay * 100),
                "federal_rate": float(breakdown.federal_tax / gross_pay * 100),
                "state_rate": float(breakdown.state_tax / gross_pay * 100),
                "local_rate": float(breakdown.local_tax / gross_pay * 100),
                "social_security_rate": float(
                    breakdown.social_security_tax / gross_pay * 100
                ),
                "medicare_rate": float(breakdown.medicare_tax / gross_pay * 100),
                "other_rate": float(breakdown.other_taxes / gross_pay * 100),
                "net_pay_rate": float(tax_calculation.net_pay / gross_pay * 100),
                "total_taxes": float(tax_calculation.total_taxes),
                "net_pay": float(tax_calculation.net_pay),
            }

        return effective_rates

    def bulk_recalculate_taxes(
        self,
        location: str,
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None,
    ) -> dict:
        """
        Bulk recalculate taxes for all employees in a location and pay period.
        Useful for tax rule updates or corrections.

        Args:
            location: Location to recalculate taxes for
            pay_period_start: Start of pay period
            pay_period_end: End of pay period
            tenant_id: Optional tenant ID

        Returns:
            Dictionary with recalculation summary
        """
        # Find all employee payments for the criteria
        query = (
            self.db.query(EmployeePayment)
            .join(EmployeePayment.payroll_policy)
            .filter(
                EmployeePayment.pay_period_start == pay_period_start,
                EmployeePayment.pay_period_end == pay_period_end,
            )
        )

        # Filter by location through payroll policy
        query = query.filter(EmployeePayment.payroll_policy.has(location=location))

        if tenant_id:
            query = query.filter(EmployeePayment.tenant_id == tenant_id)

        payments = query.all()

        # Recalculate taxes for each payment
        updated_count = 0
        errors = []

        for payment in payments:
            try:
                self.update_employee_payment_taxes(payment.id)
                updated_count += 1
            except Exception as e:
                errors.append(
                    {
                        "employee_payment_id": payment.id,
                        "staff_id": payment.staff_id,
                        "error": str(e),
                    }
                )

        return {
            "total_payments": len(payments),
            "updated_count": updated_count,
            "error_count": len(errors),
            "errors": errors,
        }
