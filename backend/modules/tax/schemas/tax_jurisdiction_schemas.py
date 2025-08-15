# backend/modules/tax/schemas/tax_jurisdiction_schemas.py

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import uuid


# Jurisdiction Schemas
class TaxJurisdictionBase(BaseModel):
    """Base schema for tax jurisdiction"""

    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    jurisdiction_type: str = Field(..., pattern="^(federal|state|county|city|special)$")
    parent_jurisdiction_id: Optional[int] = None

    country_code: str = Field(..., min_length=2, max_length=2)
    state_code: Optional[str] = Field(None, max_length=10)
    county_name: Optional[str] = Field(None, max_length=100)
    city_name: Optional[str] = Field(None, max_length=100)
    zip_codes: Optional[List[str]] = None

    filing_frequency: Optional[str] = Field(
        None, pattern="^(monthly|quarterly|annually)$"
    )
    filing_due_day: Optional[int] = Field(None, ge=1, le=31)
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None

    tax_authority_name: Optional[str] = None
    tax_authority_website: Optional[str] = None
    tax_authority_phone: Optional[str] = None
    tax_authority_email: Optional[str] = None
    tax_authority_address: Optional[str] = None


class TaxJurisdictionCreate(TaxJurisdictionBase):
    """Schema for creating tax jurisdiction"""

    effective_date: date = Field(default_factory=date.today)
    is_active: bool = True


class TaxJurisdictionUpdate(BaseModel):
    """Schema for updating tax jurisdiction"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    filing_frequency: Optional[str] = None
    filing_due_day: Optional[int] = Field(None, ge=1, le=31)
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    is_active: Optional[bool] = None
    expiry_date: Optional[date] = None

    model_config = ConfigDict(extra="forbid")


class TaxJurisdictionResponse(TaxJurisdictionBase):
    """Schema for tax jurisdiction response"""

    id: int
    jurisdiction_id: uuid.UUID
    is_active: bool
    effective_date: date
    expiry_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Tax Rate Schemas
class TaxRateBase(BaseModel):
    """Base schema for tax rate"""

    tax_type: str = Field(..., min_length=1, max_length=50)
    tax_subtype: Optional[str] = Field(None, max_length=50)
    tax_category: Optional[str] = Field(None, max_length=100)

    rate_percent: Decimal = Field(..., ge=0, le=100, decimal_places=5)
    flat_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)

    min_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    max_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    bracket_name: Optional[str] = None

    applies_to: Optional[str] = Field(None, max_length=100)
    exemption_categories: Optional[List[str]] = None

    compound_on: Optional[List[str]] = None
    ordering: int = Field(default=0)
    calculation_method: str = Field(
        default="percentage", pattern="^(percentage|flat|tiered)$"
    )

    @field_validator("max_amount")
    def validate_max_amount(cls, v, values):
        if (
            v is not None
            and "min_amount" in values.data
            and values.data["min_amount"] is not None
        ):
            if v < values.data["min_amount"]:
                raise ValueError("max_amount must be greater than min_amount")
        return v


class TaxRateCreate(TaxRateBase):
    """Schema for creating tax rate"""

    jurisdiction_id: int
    effective_date: date
    expiry_date: Optional[date] = None
    is_active: bool = True


class TaxRateUpdate(BaseModel):
    """Schema for updating tax rate"""

    rate_percent: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=5)
    flat_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    is_active: Optional[bool] = None
    expiry_date: Optional[date] = None

    model_config = ConfigDict(extra="forbid")


class TaxRateResponse(TaxRateBase):
    """Schema for tax rate response"""

    id: int
    rate_id: uuid.UUID
    jurisdiction_id: int
    effective_date: date
    expiry_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Tax Calculation Request/Response
class TaxCalculationLocation(BaseModel):
    """Location details for tax calculation"""

    country_code: str = Field(..., min_length=2, max_length=2)
    state_code: Optional[str] = None
    county_name: Optional[str] = None
    city_name: Optional[str] = None
    zip_code: Optional[str] = None
    address: Optional[str] = None


class TaxCalculationLineItem(BaseModel):
    """Line item for tax calculation"""

    line_id: str
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    quantity: int = Field(default=1, ge=1)
    category: Optional[str] = None
    tax_code: Optional[str] = None
    is_exempt: bool = False
    exemption_reason: Optional[str] = None


class EnhancedTaxCalculationRequest(BaseModel):
    """Enhanced tax calculation request"""

    transaction_id: Optional[str] = None
    transaction_date: date
    location: TaxCalculationLocation
    line_items: List[TaxCalculationLineItem]
    customer_id: Optional[int] = None
    exemption_certificate_id: Optional[uuid.UUID] = None
    shipping_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    discount_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)

    model_config = ConfigDict(extra="forbid")


class TaxCalculationResult(BaseModel):
    """Result of tax calculation"""

    line_id: str
    taxable_amount: Decimal
    tax_details: List[Dict[str, Any]]  # Jurisdiction, rate, amount
    total_tax: Decimal
    effective_rate: Decimal


class EnhancedTaxCalculationResponse(BaseModel):
    """Enhanced tax calculation response"""

    transaction_id: Optional[str]
    calculation_date: datetime
    subtotal: Decimal
    taxable_amount: Decimal
    exempt_amount: Decimal
    total_tax: Decimal
    total_amount: Decimal

    line_results: List[TaxCalculationResult]
    tax_summary_by_jurisdiction: Dict[str, Dict[str, Decimal]]
    applied_exemptions: List[Dict[str, Any]]
    warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


# Tax Rule Configuration Schemas
class TaxRuleCondition(BaseModel):
    """Condition for tax rule"""

    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, in, not_in, contains
    value: Any

    @field_validator("operator")
    def validate_operator(cls, v):
        valid_operators = [
            "eq",
            "ne",
            "gt",
            "lt",
            "gte",
            "lte",
            "in",
            "not_in",
            "contains",
        ]
        if v not in valid_operators:
            raise ValueError(f"Invalid operator. Must be one of: {valid_operators}")
        return v


class TaxRuleAction(BaseModel):
    """Action for tax rule"""

    action_type: str  # apply_rate, reduce_rate, exempt, add_fee
    parameters: Dict[str, Any]


class TaxRuleConfigurationBase(BaseModel):
    """Base schema for tax rule configuration"""

    rule_name: str = Field(..., min_length=1, max_length=200)
    rule_code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    tax_type: str = Field(..., min_length=1, max_length=50)
    rule_type: str = Field(..., pattern="^(exemption|holiday|threshold|nexus|special)$")

    conditions: List[TaxRuleCondition]
    actions: List[TaxRuleAction]

    requires_documentation: bool = False
    documentation_types: Optional[List[str]] = None
    priority: int = Field(default=0)


class TaxRuleConfigurationCreate(TaxRuleConfigurationBase):
    """Schema for creating tax rule configuration"""

    jurisdiction_id: int
    effective_date: date
    expiry_date: Optional[date] = None
    is_active: bool = True


class TaxRuleConfigurationResponse(TaxRuleConfigurationBase):
    """Schema for tax rule configuration response"""

    id: int
    rule_id: uuid.UUID
    jurisdiction_id: int
    effective_date: date
    expiry_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Tax Exemption Certificate Schemas
class TaxExemptionCertificateBase(BaseModel):
    """Base schema for tax exemption certificate"""

    customer_id: int
    customer_name: str = Field(..., min_length=1, max_length=200)
    customer_tax_id: Optional[str] = None

    certificate_number: str = Field(..., min_length=1, max_length=100)
    exemption_type: str = Field(..., pattern="^(resale|nonprofit|government|other)$")
    exemption_reason: Optional[str] = None

    jurisdiction_ids: List[int]
    tax_types: List[str]

    issue_date: date
    expiry_date: Optional[date] = None


class TaxExemptionCertificateCreate(TaxExemptionCertificateBase):
    """Schema for creating tax exemption certificate"""

    document_url: Optional[str] = None
    is_active: bool = True


class TaxExemptionCertificateVerify(BaseModel):
    """Schema for verifying tax exemption certificate"""

    is_verified: bool
    verified_by: str
    verification_notes: Optional[str] = None


class TaxExemptionCertificateResponse(TaxExemptionCertificateBase):
    """Schema for tax exemption certificate response"""

    id: int
    certificate_id: uuid.UUID
    is_active: bool
    is_verified: bool
    verified_date: Optional[date]
    verified_by: Optional[str]
    document_url: Optional[str]
    last_used_date: Optional[date]
    usage_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Tax Nexus Schemas
class TaxNexusBase(BaseModel):
    """Base schema for tax nexus"""

    nexus_type: str = Field(
        ..., pattern="^(physical|economic|affiliate|click_through)$"
    )
    establishment_date: date
    registration_date: Optional[date] = None
    registration_number: Optional[str] = None

    sales_threshold: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    transaction_threshold: Optional[int] = Field(None, ge=0)
    threshold_period: Optional[str] = Field(
        None, pattern="^(annual|quarterly|monthly)$"
    )

    filing_frequency: Optional[str] = Field(
        None, pattern="^(monthly|quarterly|annually)$"
    )
    notes: Optional[str] = None


class TaxNexusCreate(TaxNexusBase):
    """Schema for creating tax nexus"""

    jurisdiction_id: int
    is_active: bool = True
    requires_filing: bool = True


class TaxNexusUpdate(BaseModel):
    """Schema for updating tax nexus"""

    registration_date: Optional[date] = None
    registration_number: Optional[str] = None
    is_active: Optional[bool] = None
    requires_filing: Optional[bool] = None
    last_filing_date: Optional[date] = None
    next_filing_date: Optional[date] = None

    model_config = ConfigDict(extra="forbid")


class TaxNexusResponse(TaxNexusBase):
    """Schema for tax nexus response"""

    id: int
    nexus_id: uuid.UUID
    jurisdiction_id: int
    is_active: bool
    requires_filing: bool
    last_filing_date: Optional[date]
    next_filing_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
