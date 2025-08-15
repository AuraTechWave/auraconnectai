# backend/modules/tax/services/__init__.py

from .tax_engine import TaxEngine
from .tax_calculation_engine import TaxCalculationEngine
from .tax_compliance_service import TaxComplianceService
from .tax_filing_automation_service import (
    TaxFilingAutomationService,
    AutomationFrequency,
)
from .tax_integration_service import (
    TaxIntegrationService,
    TaxProviderInterface,
    AvalaraTaxProvider,
    TaxJarProvider,
    create_tax_integration_service,
)

__all__ = [
    # Original engine
    "TaxEngine",
    # Enhanced services
    "TaxCalculationEngine",
    "TaxComplianceService",
    "TaxFilingAutomationService",
    "AutomationFrequency",
    # Integration services
    "TaxIntegrationService",
    "TaxProviderInterface",
    "AvalaraTaxProvider",
    "TaxJarProvider",
    "create_tax_integration_service",
]
