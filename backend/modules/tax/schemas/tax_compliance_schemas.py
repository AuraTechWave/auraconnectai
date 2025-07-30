# backend/modules/tax/schemas/tax_compliance_schemas.py

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import uuid
from enum import Enum


class FilingStatus(str, Enum):
    """Tax filing status enumeration"""
    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"
    PAID = "paid"


class FilingType(str, Enum):
    """Tax filing type enumeration"""
    SALES_TAX = "sales_tax"
    INCOME_TAX = "income_tax"
    PAYROLL_TAX = "payroll_tax"
    PROPERTY_TAX = "property_tax"
    EXCISE_TAX = "excise_tax"
    FRANCHISE_TAX = "franchise_tax"
    OTHER = "other"


# Tax Filing Schemas
class TaxFilingLineItemBase(BaseModel):
    """Base schema for tax filing line item"""
    line_number: str = Field(..., min_length=1, max_length=20)
    description: str = Field(..., min_length=1, max_length=500)
    tax_category: Optional[str] = None
    
    gross_amount: Decimal = Field(..., ge=0, decimal_places=2)
    deductions: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    exemptions: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    taxable_amount: Decimal = Field(..., ge=0, decimal_places=2)
    tax_rate: Decimal = Field(..., ge=0, le=100, decimal_places=5)
    tax_amount: Decimal = Field(..., ge=0, decimal_places=2)
    
    location_code: Optional[str] = None
    product_category: Optional[str] = None
    transaction_count: Optional[int] = Field(None, ge=0)


class TaxFilingLineItemCreate(TaxFilingLineItemBase):
    """Schema for creating tax filing line item"""
    pass


class TaxFilingLineItemResponse(TaxFilingLineItemBase):
    """Schema for tax filing line item response"""
    id: int
    filing_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TaxFilingBase(BaseModel):
    """Base schema for tax filing"""
    jurisdiction_id: int
    filing_type: FilingType
    period_start: date
    period_end: date
    due_date: date
    
    gross_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    taxable_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    exempt_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tax_collected: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    form_type: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('period_end')
    def validate_period_end(cls, v, values):
        if 'period_start' in values.data and v < values.data['period_start']:
            raise ValueError('period_end must be after period_start')
        return v


class TaxFilingCreate(TaxFilingBase):
    """Schema for creating tax filing"""
    internal_reference: str = Field(..., min_length=1, max_length=100)
    line_items: Optional[List[TaxFilingLineItemCreate]] = []
    attachments: Optional[List[Dict[str, str]]] = []


class TaxFilingUpdate(BaseModel):
    """Schema for updating tax filing"""
    status: Optional[FilingStatus] = None
    filing_number: Optional[str] = None
    filed_date: Optional[datetime] = None
    
    gross_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    taxable_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    exempt_sales: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tax_collected: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tax_due: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    penalties: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    interest: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    confirmation_number: Optional[str] = None
    notes: Optional[str] = None
    
    model_config = ConfigDict(extra="forbid")


class TaxFilingSubmit(BaseModel):
    """Schema for submitting tax filing"""
    prepared_by: str = Field(..., min_length=1)
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    submission_method: str = Field(default="electronic")
    
    model_config = ConfigDict(extra="forbid")


class TaxFilingResponse(TaxFilingBase):
    """Schema for tax filing response"""
    id: int
    filing_id: uuid.UUID
    filing_number: Optional[str]
    internal_reference: str
    
    status: FilingStatus
    filed_date: Optional[datetime]
    
    tax_due: Decimal
    penalties: Decimal
    interest: Decimal
    total_due: Decimal
    
    payment_status: Optional[str]
    payment_date: Optional[date]
    payment_reference: Optional[str]
    
    confirmation_number: Optional[str]
    
    prepared_by: Optional[str]
    prepared_date: Optional[datetime]
    reviewed_by: Optional[str]
    reviewed_date: Optional[datetime]
    approved_by: Optional[str]
    approved_date: Optional[datetime]
    
    is_amended: bool
    amendment_reason: Optional[str]
    original_filing_id: Optional[int]
    
    attachments: Optional[List[Dict[str, Any]]]
    line_items: List[TaxFilingLineItemResponse] = []
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Tax Remittance Schemas
class TaxRemittanceBase(BaseModel):
    """Base schema for tax remittance"""
    payment_date: date
    payment_method: str = Field(..., pattern="^(ach|wire|check|credit_card)$")
    payment_reference: str = Field(..., min_length=1, max_length=100)
    payment_amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    
    filing_references: List[int]  # List of filing IDs
    
    bank_account_last4: Optional[str] = Field(None, min_length=4, max_length=4)
    bank_name: Optional[str] = None
    notes: Optional[str] = None


class TaxRemittanceCreate(TaxRemittanceBase):
    """Schema for creating tax remittance"""
    pass


class TaxRemittanceResponse(TaxRemittanceBase):
    """Schema for tax remittance response"""
    id: int
    remittance_id: uuid.UUID
    status: str
    processed_date: Optional[datetime]
    confirmation_code: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Tax Audit Log Schemas
class TaxAuditLogBase(BaseModel):
    """Base schema for tax audit log"""
    event_type: str = Field(..., min_length=1, max_length=100)
    event_subtype: Optional[str] = None
    
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: str = Field(..., min_length=1, max_length=100)
    
    user_id: str = Field(..., min_length=1, max_length=100)
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    
    action: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = None
    notes: Optional[str] = None


class TaxAuditLogCreate(TaxAuditLogBase):
    """Schema for creating tax audit log"""
    filing_id: Optional[int] = None
    changes: Optional[Dict[str, Any]] = None
    amount_before: Optional[Decimal] = Field(None, decimal_places=2)
    amount_after: Optional[Decimal] = Field(None, decimal_places=2)
    tax_impact: Optional[Decimal] = Field(None, decimal_places=2)
    metadata: Optional[Dict[str, Any]] = None


class TaxAuditLogResponse(TaxAuditLogBase):
    """Schema for tax audit log response"""
    id: int
    audit_id: uuid.UUID
    event_timestamp: datetime
    filing_id: Optional[int]
    
    changes: Optional[Dict[str, Any]]
    amount_before: Optional[Decimal]
    amount_after: Optional[Decimal]
    tax_impact: Optional[Decimal]
    metadata: Optional[Dict[str, Any]]
    
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Tax Report Template Schemas
class TaxReportTemplateBase(BaseModel):
    """Base schema for tax report template"""
    template_code: str = Field(..., min_length=1, max_length=100)
    template_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    
    report_type: str = Field(..., pattern="^(filing_form|summary_report|detail_report|analytics)$")
    filing_type: Optional[FilingType] = None
    
    template_format: str = Field(..., pattern="^(json|xml|pdf|csv|excel)$")
    template_schema: Dict[str, Any]
    template_layout: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None


class TaxReportTemplateCreate(TaxReportTemplateBase):
    """Schema for creating tax report template"""
    jurisdiction_id: Optional[int] = None
    version: str = Field(default="1.0")
    effective_date: date
    expiry_date: Optional[date] = None
    is_active: bool = True


class TaxReportTemplateResponse(TaxReportTemplateBase):
    """Schema for tax report template response"""
    id: int
    template_id: uuid.UUID
    jurisdiction_id: Optional[int]
    version: str
    is_active: bool
    effective_date: date
    expiry_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Tax Reporting Schemas
class TaxReportRequest(BaseModel):
    """Request schema for generating tax reports"""
    report_type: str
    template_id: Optional[uuid.UUID] = None
    
    jurisdiction_ids: Optional[List[int]] = None
    filing_types: Optional[List[FilingType]] = None
    
    period_start: date
    period_end: date
    
    include_details: bool = True
    include_summary: bool = True
    include_trends: bool = False
    
    output_format: str = Field(default="json", pattern="^(json|pdf|excel|csv)$")
    
    filters: Optional[Dict[str, Any]] = None
    grouping: Optional[List[str]] = None
    sorting: Optional[Dict[str, str]] = None


class TaxReportResponse(BaseModel):
    """Response schema for tax reports"""
    report_id: uuid.UUID
    report_type: str
    generated_at: datetime
    generated_by: str
    
    period_start: date
    period_end: date
    
    summary: Dict[str, Any]
    details: Optional[List[Dict[str, Any]]] = None
    trends: Optional[Dict[str, Any]] = None
    
    total_records: int
    filters_applied: Dict[str, Any]
    
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# Tax Compliance Dashboard Schemas
class TaxComplianceStatus(BaseModel):
    """Tax compliance status summary"""
    jurisdiction_id: int
    jurisdiction_name: str
    filing_type: FilingType
    
    current_period_status: str  # compliant, pending, overdue
    last_filing_date: Optional[date]
    next_filing_due: Optional[date]
    
    filings_pending: int
    filings_overdue: int
    
    total_liability: Decimal
    total_paid: Decimal
    outstanding_balance: Decimal
    
    compliance_score: float = Field(..., ge=0, le=100)
    risk_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    
    alerts: List[Dict[str, Any]] = []


class TaxComplianceDashboard(BaseModel):
    """Tax compliance dashboard response"""
    as_of_date: datetime
    overall_compliance_score: float
    overall_risk_level: str
    
    total_jurisdictions: int
    compliant_jurisdictions: int
    at_risk_jurisdictions: int
    
    upcoming_deadlines: List[Dict[str, Any]]
    overdue_filings: List[Dict[str, Any]]
    recent_filings: List[Dict[str, Any]]
    
    total_tax_liability: Decimal
    total_tax_paid: Decimal
    outstanding_balance: Decimal
    
    compliance_by_jurisdiction: List[TaxComplianceStatus]
    
    alerts: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)