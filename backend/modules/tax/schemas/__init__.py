# backend/modules/tax/schemas/__init__.py

from .tax_schemas import (
    TaxCalculationItem,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxBreakdownItem,
    TaxRuleOut,
)

from .tax_jurisdiction_schemas import (
    # Jurisdiction
    TaxJurisdictionCreate,
    TaxJurisdictionUpdate,
    TaxJurisdictionResponse,
    # Tax Rate
    TaxRateCreate,
    TaxRateUpdate,
    TaxRateResponse,
    # Tax Calculation
    TaxCalculationLocation,
    TaxCalculationLineItem,
    EnhancedTaxCalculationRequest,
    EnhancedTaxCalculationResponse,
    TaxCalculationResult,
    # Tax Rules
    TaxRuleCondition,
    TaxRuleAction,
    TaxRuleConfigurationCreate,
    TaxRuleConfigurationResponse,
    # Exemptions
    TaxExemptionCertificateCreate,
    TaxExemptionCertificateVerify,
    TaxExemptionCertificateResponse,
    # Nexus
    TaxNexusCreate,
    TaxNexusUpdate,
    TaxNexusResponse,
)

from .tax_compliance_schemas import (
    # Enums
    FilingStatus,
    FilingType,
    # Filing
    TaxFilingCreate,
    TaxFilingUpdate,
    TaxFilingSubmit,
    TaxFilingResponse,
    TaxFilingLineItemCreate,
    TaxFilingLineItemResponse,
    # Remittance
    TaxRemittanceCreate,
    TaxRemittanceResponse,
    # Audit
    TaxAuditLogCreate,
    TaxAuditLogResponse,
    # Templates
    TaxReportTemplateCreate,
    TaxReportTemplateResponse,
    # Reporting
    TaxReportRequest,
    TaxReportResponse,
    # Compliance
    TaxComplianceStatus,
    TaxComplianceDashboard,
)

__all__ = [
    # Original schemas
    "TaxCalculationItem",
    "TaxCalculationRequest",
    "TaxCalculationResponse",
    "TaxBreakdownItem",
    "TaxRuleOut",
    # Jurisdiction schemas
    "TaxJurisdictionCreate",
    "TaxJurisdictionUpdate",
    "TaxJurisdictionResponse",
    "TaxRateCreate",
    "TaxRateUpdate",
    "TaxRateResponse",
    "TaxCalculationLocation",
    "TaxCalculationLineItem",
    "EnhancedTaxCalculationRequest",
    "EnhancedTaxCalculationResponse",
    "TaxCalculationResult",
    "TaxRuleCondition",
    "TaxRuleAction",
    "TaxRuleConfigurationCreate",
    "TaxRuleConfigurationResponse",
    "TaxExemptionCertificateCreate",
    "TaxExemptionCertificateVerify",
    "TaxExemptionCertificateResponse",
    "TaxNexusCreate",
    "TaxNexusUpdate",
    "TaxNexusResponse",
    # Compliance schemas
    "FilingStatus",
    "FilingType",
    "TaxFilingCreate",
    "TaxFilingUpdate",
    "TaxFilingSubmit",
    "TaxFilingResponse",
    "TaxFilingLineItemCreate",
    "TaxFilingLineItemResponse",
    "TaxRemittanceCreate",
    "TaxRemittanceResponse",
    "TaxAuditLogCreate",
    "TaxAuditLogResponse",
    "TaxReportTemplateCreate",
    "TaxReportTemplateResponse",
    "TaxReportRequest",
    "TaxReportResponse",
    "TaxComplianceStatus",
    "TaxComplianceDashboard",
]
