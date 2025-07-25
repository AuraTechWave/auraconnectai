from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, date
from ..enums.payroll_enums import TaxType


class PayrollTaxCalculationRequest(BaseModel):
    """Request schema for payroll tax calculations."""
    
    employee_id: int = Field(..., description="Employee/Staff ID")
    location: str = Field(
        ..., description="Location/jurisdiction for tax rules"
    )
    gross_pay: Decimal = Field(
        ..., ge=0, description="Gross pay amount for the period"
    )
    pay_date: date = Field(
        ..., description="Pay date for determining applicable tax rules"
    )
    tenant_id: Optional[int] = Field(
        None, description="Tenant ID for multi-tenant setup"
    )
    
    class Config:
        json_encoders = {
            Decimal: str,
            date: lambda v: v.isoformat()
        }


class TaxApplicationDetail(BaseModel):
    """Detailed information about a specific tax rule application."""
    
    tax_rule_id: int = Field(..., description="ID of the applied tax rule")
    rule_name: str = Field(..., description="Name of the tax rule")
    tax_type: TaxType = Field(
        ..., description="Type of tax (federal, state, local, etc.)"
    )
    location: str = Field(..., description="Jurisdiction location")
    taxable_amount: Decimal = Field(
        ..., ge=0, description="Amount subject to this tax"
    )
    calculated_tax: Decimal = Field(
        ..., ge=0, description="Calculated tax amount"
    )
    effective_rate: Decimal = Field(
        ..., ge=0, description="Effective tax rate applied"
    )
    calculation_method: str = Field(
        ..., description="Method used for calculation"
    )
    
    class Config:
        json_encoders = {
            Decimal: str
        }


class TaxBreakdown(BaseModel):
    """Breakdown of taxes by category."""
    
    federal_tax: Decimal = Field(default=Decimal('0.00'), ge=0)
    state_tax: Decimal = Field(default=Decimal('0.00'), ge=0)
    local_tax: Decimal = Field(default=Decimal('0.00'), ge=0)
    social_security_tax: Decimal = Field(default=Decimal('0.00'), ge=0)
    medicare_tax: Decimal = Field(default=Decimal('0.00'), ge=0)
    other_taxes: Decimal = Field(default=Decimal('0.00'), ge=0)
    
    class Config:
        json_encoders = {
            Decimal: str
        }


class PayrollTaxCalculationResponse(BaseModel):
    """Response schema for payroll tax calculations."""
    
    gross_pay: Decimal = Field(
        ..., ge=0, description="Original gross pay amount"
    )
    total_taxes: Decimal = Field(
        ..., ge=0, description="Total calculated taxes"
    )
    net_pay: Decimal = Field(
        ..., ge=0, description="Net pay after tax deductions"
    )
    tax_breakdown: TaxBreakdown = Field(
        ..., description="Breakdown by tax category"
    )
    tax_applications: List[TaxApplicationDetail] = Field(
        default_factory=list,
        description="Detailed tax rule applications"
    )
    calculation_date: datetime = Field(
        ..., description="When calculation was performed"
    )
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class TaxRuleValidationRequest(BaseModel):
    """Request to validate tax rule setup for a location."""
    
    location: str = Field(..., description="Location to validate")
    pay_date: date = Field(..., description="Date to check rule applicability")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class TaxRuleValidationResponse(BaseModel):
    """Response for tax rule validation."""
    
    location: str
    total_rules: int = Field(
        ..., description="Total applicable tax rules"
    )
    jurisdiction_summary: dict = Field(
        ..., description="Rules grouped by jurisdiction"
    )
    missing_jurisdictions: List[str] = Field(
        default_factory=list,
        description="Expected jurisdictions without rules"
    )
    potential_issues: List[str] = Field(
        default_factory=list,
        description="Potential configuration issues"
    )
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class PayrollTaxServiceRequest(BaseModel):
    """Internal service request for payroll tax integration."""
    
    employee_payment_id: Optional[int] = Field(
        None, description="Existing payment record ID"
    )
    staff_id: int = Field(..., description="Staff member ID")
    payroll_policy_id: int = Field(..., description="Payroll policy ID")
    pay_period_start: date = Field(
        ..., description="Pay period start date"
    )
    pay_period_end: date = Field(..., description="Pay period end date")
    gross_pay: Decimal = Field(
        ..., ge=0, description="Calculated gross pay"
    )
    location: str = Field(..., description="Employee work location")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")
    
    class Config:
        json_encoders = {
            Decimal: str,
            date: lambda v: v.isoformat()
        }


class PayrollTaxServiceResponse(BaseModel):
    """Internal service response for payroll tax integration."""
    
    employee_payment_id: Optional[int] = Field(
        None, description="Payment record ID"
    )
    tax_calculation: PayrollTaxCalculationResponse = Field(
        ..., description="Tax calculation results"
    )
    applications_saved: bool = Field(
        default=False,
        description="Whether tax applications were persisted"
    )
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }