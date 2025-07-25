from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime, date
from ..models.payroll_models import (
    TaxRule, EmployeePayment, EmployeePaymentTaxApplication
)
from ..enums.payroll_enums import TaxType
from ..schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest, PayrollTaxCalculationResponse,
    TaxApplicationDetail, TaxBreakdown
)


class PayrollTaxEngine:
    """
    Tax rule evaluation engine for payroll-specific calculations.
    Supports multi-jurisdiction rules with effective/expiry date handling.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_payroll_taxes(
        self, 
        request: PayrollTaxCalculationRequest
    ) -> PayrollTaxCalculationResponse:
        """
        Calculate applicable taxes for a pay period.
        
        Args:
            request: PayrollTaxCalculationRequest containing employee payment details
            
        Returns:
            PayrollTaxCalculationResponse with detailed tax breakdown
        """
        # Get applicable tax rules for the location and pay date
        applicable_rules = self._get_applicable_tax_rules(
            location=request.location,
            pay_date=request.pay_date,
            tenant_id=request.tenant_id
        )
        
        if not applicable_rules:
            return self._create_zero_tax_response(request)
        
        # Calculate taxes by jurisdiction
        tax_applications = []
        total_federal_tax = Decimal('0.00')
        total_state_tax = Decimal('0.00') 
        total_local_tax = Decimal('0.00')
        total_social_security_tax = Decimal('0.00')
        total_medicare_tax = Decimal('0.00')
        total_other_taxes = Decimal('0.00')
        
        for rule in applicable_rules:
            tax_application = self._apply_tax_rule(rule, request)
            if tax_application:
                tax_applications.append(tax_application)
                
                # Categorize by tax type
                if rule.tax_type == TaxType.FEDERAL:
                    total_federal_tax += tax_application.calculated_tax
                elif rule.tax_type == TaxType.STATE:
                    total_state_tax += tax_application.calculated_tax
                elif rule.tax_type == TaxType.LOCAL:
                    total_local_tax += tax_application.calculated_tax
                elif rule.tax_type == TaxType.SOCIAL_SECURITY:
                    total_social_security_tax += tax_application.calculated_tax
                elif rule.tax_type == TaxType.MEDICARE:
                    total_medicare_tax += tax_application.calculated_tax
                else:
                    total_other_taxes += tax_application.calculated_tax
        
        total_taxes = (
            total_federal_tax + total_state_tax + total_local_tax +
            total_social_security_tax + total_medicare_tax + total_other_taxes
        )
        
        return PayrollTaxCalculationResponse(
            gross_pay=request.gross_pay,
            total_taxes=total_taxes,
            net_pay=request.gross_pay - total_taxes,
            tax_breakdown=TaxBreakdown(
                federal_tax=total_federal_tax,
                state_tax=total_state_tax,
                local_tax=total_local_tax,
                social_security_tax=total_social_security_tax,
                medicare_tax=total_medicare_tax,
                other_taxes=total_other_taxes
            ),
            tax_applications=tax_applications,
            calculation_date=datetime.utcnow()
        )
    
    def _get_applicable_tax_rules(
        self, 
        location: str, 
        pay_date: date,
        tenant_id: Optional[int] = None
    ) -> List[TaxRule]:
        """
        Get tax rules applicable for given location and date.
        Handles effective/expiry dates and multi-jurisdiction filtering.
        """
        query = self.db.query(TaxRule).filter(
            TaxRule.location == location,
            TaxRule.is_active == True,
            TaxRule.effective_date <= pay_date
        )
        
        # Filter by tenant if provided
        if tenant_id:
            query = query.filter(TaxRule.tenant_id == tenant_id)
        
        # Handle expiry date (None means no expiry)
        query = query.filter(
            (TaxRule.expiry_date.is_(None)) | 
            (TaxRule.expiry_date > pay_date)
        )
        
        return query.order_by(TaxRule.tax_type, TaxRule.rule_name).all()
    
    def _apply_tax_rule(
        self, 
        rule: TaxRule, 
        request: PayrollTaxCalculationRequest
    ) -> Optional[TaxApplicationDetail]:
        """
        Apply a specific tax rule to calculate tax amount.
        Handles taxable amount limits and employee/employer portions.
        """
        # Determine taxable amount based on rule limits
        taxable_amount = self._calculate_taxable_amount(rule, request.gross_pay)
        
        if taxable_amount <= 0:
            return None
        
        # Calculate tax using employee portion (employee responsibility)
        effective_rate = rule.employee_portion or rule.rate_percent
        calculated_tax = taxable_amount * (effective_rate / 100)
        
        # Round to 2 decimal places for currency
        calculated_tax = calculated_tax.quantize(Decimal('0.01'))
        
        return TaxApplicationDetail(
            tax_rule_id=rule.id,
            rule_name=rule.rule_name,
            tax_type=rule.tax_type,
            location=rule.location,
            taxable_amount=taxable_amount,
            calculated_tax=calculated_tax,
            effective_rate=effective_rate,
            calculation_method=self._get_calculation_method(rule)
        )
    
    def _calculate_taxable_amount(
        self, 
        rule: TaxRule, 
        gross_pay: Decimal
    ) -> Decimal:
        """
        Calculate taxable amount considering min/max limits.
        """
        taxable_amount = gross_pay
        
        # Apply minimum taxable amount
        if rule.min_taxable_amount and taxable_amount < rule.min_taxable_amount:
            return Decimal('0.00')
        
        # Apply maximum taxable amount (cap)
        if rule.max_taxable_amount and taxable_amount > rule.max_taxable_amount:
            taxable_amount = rule.max_taxable_amount
        
        return taxable_amount
    
    def _get_calculation_method(self, rule: TaxRule) -> str:
        """
        Determine calculation method based on rule characteristics.
        """
        method_parts = ["percentage"]
        
        if rule.max_taxable_amount:
            method_parts.append("capped")
        if rule.min_taxable_amount:
            method_parts.append("minimum_threshold")
        if rule.employee_portion != rule.rate_percent:
            method_parts.append("split_employer_employee")
            
        return "_".join(method_parts)
    
    def _create_zero_tax_response(
        self, 
        request: PayrollTaxCalculationRequest
    ) -> PayrollTaxCalculationResponse:
        """
        Create response with zero taxes when no applicable rules found.
        """
        return PayrollTaxCalculationResponse(
            gross_pay=request.gross_pay,
            total_taxes=Decimal('0.00'),
            net_pay=request.gross_pay,
            tax_breakdown=TaxBreakdown(
                federal_tax=Decimal('0.00'),
                state_tax=Decimal('0.00'),
                local_tax=Decimal('0.00'),
                social_security_tax=Decimal('0.00'),
                medicare_tax=Decimal('0.00'),
                other_taxes=Decimal('0.00')
            ),
            tax_applications=[],
            calculation_date=datetime.utcnow()
        )
    
    def save_tax_applications(
        self, 
        employee_payment_id: int,
        tax_applications: List[TaxApplicationDetail]
    ) -> List[EmployeePaymentTaxApplication]:
        """
        Save calculated tax applications to database for audit trail.
        """
        saved_applications = []
        
        for app in tax_applications:
            db_app = EmployeePaymentTaxApplication(
                employee_payment_id=employee_payment_id,
                tax_rule_id=app.tax_rule_id,
                taxable_amount=app.taxable_amount,
                calculated_tax=app.calculated_tax,
                effective_rate=app.effective_rate,
                calculation_date=datetime.utcnow(),
                calculation_method=app.calculation_method
            )
            
            self.db.add(db_app)
            saved_applications.append(db_app)
        
        self.db.commit()
        return saved_applications
    
    def get_jurisdiction_summary(
        self, 
        location: str, 
        pay_date: date,
        tenant_id: Optional[int] = None
    ) -> Dict[str, List[Dict]]:
        """
        Get summary of all applicable tax rules by jurisdiction.
        Useful for tax setup validation and reporting.
        """
        rules = self._get_applicable_tax_rules(location, pay_date, tenant_id)
        
        jurisdiction_summary = {
            "federal": [],
            "state": [], 
            "local": [],
            "payroll_taxes": []  # Social Security, Medicare, etc.
        }
        
        for rule in rules:
            rule_info = {
                "rule_name": rule.rule_name,
                "tax_type": rule.tax_type.value,
                "rate_percent": float(rule.rate_percent),
                "employee_portion": float(rule.employee_portion or rule.rate_percent),
                "employer_portion": float(rule.employer_portion or Decimal('0.00')),
                "max_taxable_amount": float(rule.max_taxable_amount) if rule.max_taxable_amount else None
            }
            
            if rule.tax_type == TaxType.FEDERAL:
                jurisdiction_summary["federal"].append(rule_info)
            elif rule.tax_type == TaxType.STATE:
                jurisdiction_summary["state"].append(rule_info)
            elif rule.tax_type == TaxType.LOCAL:
                jurisdiction_summary["local"].append(rule_info)
            else:
                jurisdiction_summary["payroll_taxes"].append(rule_info)
        
        return jurisdiction_summary