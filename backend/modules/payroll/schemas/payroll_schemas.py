# backend/modules/payroll/schemas/payroll_schemas.py

"""
Pydantic schemas for payroll module API endpoints.

Provides request/response models for:
- Tax calculations
- Payroll configurations
- Employee payments
- Tax rules
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from ..enums.payroll_enums import (
    TaxRuleType,
    TaxRuleStatus,
    PaymentStatus,
    PayrollJobStatus,
)


# Tax Calculation Schemas


class TaxRuleResponse(BaseModel):
    """Response model for tax rule information"""

    id: int
    tax_type: TaxRuleType
    location: str
    rate: Decimal
    cap_amount: Optional[Decimal] = None
    employer_rate: Optional[Decimal] = None
    description: Optional[str] = None
    effective_date: date
    expiry_date: Optional[date] = None
    status: TaxRuleStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


# Payroll Configuration Schemas


class PayrollConfigurationResponse(BaseModel):
    """Response model for payroll configuration"""

    id: int
    tenant_id: Optional[int] = None
    config_key: str
    config_value: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PayrollConfigurationCreate(BaseModel):
    """Request model for creating payroll configuration"""

    tenant_id: Optional[int] = None
    config_key: str = Field(..., min_length=1, max_length=100)
    config_value: str = Field(..., min_length=1)
    is_active: bool = True


class StaffPayPolicyResponse(BaseModel):
    """Response model for staff pay policy"""

    id: int
    staff_id: int
    base_hourly_rate: Decimal
    overtime_multiplier: Decimal = Decimal("1.5")
    double_time_multiplier: Decimal = Decimal("2.0")
    location: str = "default"
    health_insurance: Decimal = Decimal("0.00")
    dental_insurance: Decimal = Decimal("0.00")
    vision_insurance: Decimal = Decimal("0.00")
    retirement_401k_percentage: Decimal = Decimal("0.00")
    life_insurance: Decimal = Decimal("0.00")
    disability_insurance: Decimal = Decimal("0.00")
    parking_fee: Decimal = Decimal("0.00")
    other_deductions: Decimal = Decimal("0.00")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {Decimal: str}


class StaffPayPolicyCreate(BaseModel):
    """Request model for creating staff pay policy"""

    staff_id: int
    base_hourly_rate: Decimal = Field(..., gt=0)
    overtime_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1)
    double_time_multiplier: Decimal = Field(default=Decimal("2.0"), ge=1)
    location: str = "default"
    health_insurance: Decimal = Field(default=Decimal("0.00"), ge=0)
    dental_insurance: Decimal = Field(default=Decimal("0.00"), ge=0)
    vision_insurance: Decimal = Field(default=Decimal("0.00"), ge=0)
    retirement_401k_percentage: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    life_insurance: Decimal = Field(default=Decimal("0.00"), ge=0)
    disability_insurance: Decimal = Field(default=Decimal("0.00"), ge=0)
    parking_fee: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_deductions: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_active: bool = True


class OvertimeRuleResponse(BaseModel):
    """Response model for overtime rule"""

    id: int
    location: str
    daily_overtime_threshold: Decimal
    weekly_overtime_threshold: Decimal
    daily_double_time_threshold: Optional[Decimal] = None
    weekly_double_time_threshold: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {Decimal: str}


class OvertimeRuleCreate(BaseModel):
    """Request model for creating overtime rule"""

    location: str = Field(..., min_length=1, max_length=100)
    daily_overtime_threshold: Decimal = Field(default=Decimal("8.0"), gt=0)
    weekly_overtime_threshold: Decimal = Field(default=Decimal("40.0"), gt=0)
    daily_double_time_threshold: Optional[Decimal] = Field(
        default=Decimal("12.0"), gt=0
    )
    weekly_double_time_threshold: Optional[Decimal] = Field(
        default=Decimal("60.0"), gt=0
    )


class RoleBasedPayRateResponse(BaseModel):
    """Response model for role-based pay rate"""

    id: int
    role_name: str
    location: str = "default"
    base_hourly_rate: Decimal
    overtime_multiplier: Decimal = Decimal("1.5")
    effective_date: datetime
    expiry_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {Decimal: str}


class RoleBasedPayRateCreate(BaseModel):
    """Request model for creating role-based pay rate"""

    role_name: str = Field(..., min_length=1, max_length=100)
    location: str = "default"
    base_hourly_rate: Decimal = Field(..., gt=0)
    overtime_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1)
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None

    @field_validator("effective_date", mode="before")
    def set_effective_date(cls, v):
        return v or datetime.utcnow()


# Employee Payment Schemas


class PaymentHistoryItem(BaseModel):
    """Response model for payment history item"""

    id: int
    pay_period_start: date
    pay_period_end: date
    gross_amount: Decimal
    net_amount: Decimal
    regular_hours: Decimal
    overtime_hours: Decimal
    status: PaymentStatus
    processed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    class Config:
        json_encoders = {Decimal: str}


class PaymentHistoryResponse(BaseModel):
    """Response model for employee payment history"""

    employee_id: int
    total_count: int
    limit: int
    offset: int
    summary: Dict[str, Any]
    payments: List[PaymentHistoryItem]


class PaymentDetailResponse(BaseModel):
    """Response model for detailed payment information"""

    id: int
    employee_id: int
    pay_period_start: date
    pay_period_end: date
    hours: Dict[str, str]
    earnings: Dict[str, str]
    deductions: Dict[str, Dict[str, str]]
    net_amount: str
    payment_info: Dict[str, Any]
    tax_applications: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class PaymentSummaryResponse(BaseModel):
    """Response model for payment summary by period"""

    period: Dict[str, str]
    employee_count: int
    payment_count: int
    totals: Dict[str, str]
    taxes: Dict[str, str]
    benefits: Dict[str, str]
    hours: Dict[str, str]


class PaymentStatusUpdate(BaseModel):
    """Request model for updating payment status"""

    status: PaymentStatus
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentExportRequest(BaseModel):
    """Request model for exporting payment data"""

    start_date: date
    end_date: date
    employee_ids: Optional[List[int]] = None
    format: str = Field(default="csv", pattern="^(csv|excel|pdf)$")
    include_details: bool = True


class PaymentExportResponse(BaseModel):
    """Response model for payment export"""

    status: str
    message: str
    export_id: str
    format: str
    record_count: int
    download_url: str


# Payroll Job Tracking Schemas


class PayrollJobResponse(BaseModel):
    """Response model for payroll job tracking"""

    id: int
    job_id: str
    job_type: str
    status: PayrollJobStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any]
    tenant_id: Optional[int] = None

    class Config:
        orm_mode = True


class PayrollJobCreate(BaseModel):
    """Request model for creating payroll job"""

    job_id: str
    job_type: str
    metadata: Dict[str, Any] = {}
    tenant_id: Optional[int] = None
