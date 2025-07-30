# backend/modules/tax/services/tax_integration_service.py

from typing import Dict, List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
import logging
import httpx
import asyncio
from abc import ABC, abstractmethod
import json

from ..schemas.tax_jurisdiction_schemas import (
    TaxCalculationLocation,
    EnhancedTaxCalculationRequest,
    EnhancedTaxCalculationResponse
)

logger = logging.getLogger(__name__)


class TaxProviderInterface(ABC):
    """Abstract interface for tax service providers"""
    
    @abstractmethod
    async def calculate_tax(
        self,
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Calculate tax for a transaction"""
        pass
    
    @abstractmethod
    async def validate_address(
        self,
        address: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate and standardize address"""
        pass
    
    @abstractmethod
    async def get_tax_rates(
        self,
        location: TaxCalculationLocation,
        tax_date: date
    ) -> List[Dict[str, Any]]:
        """Get tax rates for a location"""
        pass
    
    @abstractmethod
    async def file_return(
        self,
        filing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """File a tax return"""
        pass


class AvalaraTaxProvider(TaxProviderInterface):
    """Avalara AvaTax integration"""
    
    def __init__(self, config: Dict[str, str]):
        self.account_id = config.get("account_id")
        self.license_key = config.get("license_key")
        self.company_code = config.get("company_code", "DEFAULT")
        self.environment = config.get("environment", "sandbox")
        
        self.base_url = (
            "https://rest.avatax.com"
            if self.environment == "production"
            else "https://sandbox-rest.avatax.com"
        )
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.account_id, self.license_key),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30.0
        )
    
    async def calculate_tax(
        self,
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Calculate tax using Avalara AvaTax"""
        try:
            # Build AvaTax request
            avatax_request = {
                "type": "SalesInvoice",
                "companyCode": self.company_code,
                "date": request.transaction_date.isoformat(),
                "customerCode": str(request.customer_id) if request.customer_id else "GUEST",
                "purchaseOrderNo": request.transaction_id,
                "addresses": {
                    "shipTo": {
                        "line1": request.location.address or "",
                        "city": request.location.city_name or "",
                        "region": request.location.state_code or "",
                        "country": request.location.country_code,
                        "postalCode": request.location.zip_code or ""
                    }
                },
                "lines": []
            }
            
            # Add line items
            for idx, item in enumerate(request.line_items):
                avatax_request["lines"].append({
                    "number": str(idx + 1),
                    "quantity": item.quantity,
                    "amount": float(item.amount),
                    "taxCode": item.tax_code or "P0000000",
                    "itemCode": item.line_id,
                    "description": f"Line item {item.line_id}",
                    "taxIncluded": False
                })
            
            # Add exemption if applicable
            if request.exemption_certificate_id:
                avatax_request["exemptionNo"] = str(request.exemption_certificate_id)
            
            # Call AvaTax API
            response = await self.client.post(
                "/api/v2/transactions/create",
                json=avatax_request
            )
            
            if response.status_code != 201:
                raise Exception(f"AvaTax error: {response.text}")
            
            result = response.json()
            
            # Convert to our response format
            return self._convert_avatax_response(result, request)
            
        except Exception as e:
            logger.error(f"Avalara tax calculation error: {str(e)}")
            raise
    
    async def validate_address(
        self,
        address: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate address using Avalara"""
        try:
            response = await self.client.get(
                "/api/v2/addresses/resolve",
                params={
                    "line1": address.get("line1", ""),
                    "line2": address.get("line2", ""),
                    "city": address.get("city", ""),
                    "region": address.get("state", ""),
                    "postalCode": address.get("zip", ""),
                    "country": address.get("country", "US")
                }
            )
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "error": "Address validation failed"
                }
            
            result = response.json()
            
            return {
                "valid": result.get("validatedAddresses", []) != [],
                "standardized": result.get("validatedAddresses", [{}])[0]
                if result.get("validatedAddresses") else None,
                "messages": result.get("messages", [])
            }
            
        except Exception as e:
            logger.error(f"Address validation error: {str(e)}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    async def get_tax_rates(
        self,
        location: TaxCalculationLocation,
        tax_date: date
    ) -> List[Dict[str, Any]]:
        """Get tax rates for a location"""
        try:
            response = await self.client.get(
                "/api/v2/taxrates/byaddress",
                params={
                    "line1": location.address or "",
                    "city": location.city_name or "",
                    "region": location.state_code or "",
                    "postalCode": location.zip_code or "",
                    "country": location.country_code
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get tax rates: {response.text}")
            
            result = response.json()
            
            return [
                {
                    "jurisdiction": rate["jurisName"],
                    "jurisdiction_type": rate["jurisType"],
                    "rate": rate["rate"],
                    "tax_type": rate["taxType"],
                    "tax_name": rate["taxName"]
                }
                for rate in result.get("rates", [])
            ]
            
        except Exception as e:
            logger.error(f"Get tax rates error: {str(e)}")
            raise
    
    async def file_return(
        self,
        filing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """File a tax return via Avalara"""
        # This would use Avalara's Returns API
        # Implementation depends on specific filing requirements
        raise NotImplementedError("Avalara Returns API integration pending")
    
    def _convert_avatax_response(
        self,
        avatax_response: Dict[str, Any],
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Convert AvaTax response to our format"""
        from ..schemas.tax_jurisdiction_schemas import TaxCalculationResult
        
        line_results = []
        tax_summary = {}
        
        # Process line items
        for line in avatax_response.get("lines", []):
            line_id = request.line_items[int(line["lineNumber"]) - 1].line_id
            
            tax_details = []
            for detail in line.get("details", []):
                jurisdiction_name = detail["jurisName"]
                tax_type = detail["taxName"]
                
                tax_details.append({
                    "jurisdiction_name": jurisdiction_name,
                    "jurisdiction_type": detail["jurisType"],
                    "tax_type": tax_type,
                    "rate": Decimal(str(detail["rate"])),
                    "tax_amount": Decimal(str(detail["tax"])),
                    "calculation_method": "percentage"
                })
                
                # Update summary
                if jurisdiction_name not in tax_summary:
                    tax_summary[jurisdiction_name] = {}
                
                if tax_type not in tax_summary[jurisdiction_name]:
                    tax_summary[jurisdiction_name][tax_type] = Decimal("0")
                
                tax_summary[jurisdiction_name][tax_type] += Decimal(str(detail["tax"]))
            
            line_results.append(TaxCalculationResult(
                line_id=line_id,
                taxable_amount=Decimal(str(line["taxableAmount"])),
                tax_details=tax_details,
                total_tax=Decimal(str(line["tax"])),
                effective_rate=Decimal(str(line["tax"])) / Decimal(str(line["lineAmount"])) * 100
                if Decimal(str(line["lineAmount"])) > 0 else Decimal("0")
            ))
        
        return EnhancedTaxCalculationResponse(
            transaction_id=request.transaction_id,
            calculation_date=datetime.utcnow(),
            subtotal=Decimal(str(avatax_response["totalAmount"])),
            taxable_amount=Decimal(str(avatax_response["totalTaxable"])),
            exempt_amount=Decimal(str(avatax_response["totalExempt"])),
            total_tax=Decimal(str(avatax_response["totalTax"])),
            total_amount=Decimal(str(avatax_response["totalAmount"])) + 
                       Decimal(str(avatax_response["totalTax"])),
            line_results=line_results,
            tax_summary_by_jurisdiction=tax_summary,
            applied_exemptions=[],
            warnings=[]
        )


class TaxJarProvider(TaxProviderInterface):
    """TaxJar integration"""
    
    def __init__(self, config: Dict[str, str]):
        self.api_token = config.get("api_token")
        self.base_url = "https://api.taxjar.com/v2"
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def calculate_tax(
        self,
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Calculate tax using TaxJar"""
        try:
            # Build TaxJar request
            taxjar_request = {
                "from_country": "US",
                "from_zip": "00000",  # Would get from merchant config
                "to_country": request.location.country_code,
                "to_zip": request.location.zip_code,
                "to_state": request.location.state_code,
                "to_city": request.location.city_name,
                "amount": float(sum(item.amount * item.quantity for item in request.line_items)),
                "shipping": float(request.shipping_amount) if request.shipping_amount else 0,
                "line_items": []
            }
            
            # Add line items
            for item in request.line_items:
                taxjar_request["line_items"].append({
                    "id": item.line_id,
                    "quantity": item.quantity,
                    "unit_price": float(item.amount / item.quantity),
                    "product_tax_code": item.tax_code
                })
            
            # Add customer ID for exemptions
            if request.customer_id:
                taxjar_request["customer_id"] = str(request.customer_id)
            
            # Call TaxJar API
            response = await self.client.post(
                "/taxes",
                json=taxjar_request
            )
            
            if response.status_code != 200:
                raise Exception(f"TaxJar error: {response.text}")
            
            result = response.json()
            
            # Convert to our response format
            return self._convert_taxjar_response(result["tax"], request)
            
        except Exception as e:
            logger.error(f"TaxJar tax calculation error: {str(e)}")
            raise
    
    async def validate_address(
        self,
        address: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate address using TaxJar"""
        try:
            response = await self.client.post(
                "/addresses/validate",
                json={
                    "country": address.get("country", "US"),
                    "state": address.get("state", ""),
                    "zip": address.get("zip", ""),
                    "city": address.get("city", ""),
                    "street": address.get("line1", "")
                }
            )
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "error": "Address validation failed"
                }
            
            result = response.json()
            
            return {
                "valid": True,
                "standardized": result["addresses"][0] if result.get("addresses") else None,
                "messages": []
            }
            
        except Exception as e:
            logger.error(f"Address validation error: {str(e)}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    async def get_tax_rates(
        self,
        location: TaxCalculationLocation,
        tax_date: date
    ) -> List[Dict[str, Any]]:
        """Get tax rates for a location"""
        try:
            response = await self.client.get(
                f"/rates/{location.zip_code}",
                params={
                    "city": location.city_name,
                    "state": location.state_code,
                    "country": location.country_code
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get tax rates: {response.text}")
            
            result = response.json()["rate"]
            
            rates = []
            
            # Add state rate
            if result.get("state_rate", 0) > 0:
                rates.append({
                    "jurisdiction": result.get("state", ""),
                    "jurisdiction_type": "state",
                    "rate": result["state_rate"],
                    "tax_type": "sales",
                    "tax_name": "State Sales Tax"
                })
            
            # Add county rate
            if result.get("county_rate", 0) > 0:
                rates.append({
                    "jurisdiction": result.get("county", ""),
                    "jurisdiction_type": "county",
                    "rate": result["county_rate"],
                    "tax_type": "sales",
                    "tax_name": "County Sales Tax"
                })
            
            # Add city rate
            if result.get("city_rate", 0) > 0:
                rates.append({
                    "jurisdiction": result.get("city", ""),
                    "jurisdiction_type": "city",
                    "rate": result["city_rate"],
                    "tax_type": "sales",
                    "tax_name": "City Sales Tax"
                })
            
            # Add special district rate
            if result.get("special_rate", 0) > 0:
                rates.append({
                    "jurisdiction": "Special District",
                    "jurisdiction_type": "special",
                    "rate": result["special_rate"],
                    "tax_type": "sales",
                    "tax_name": "Special District Tax"
                })
            
            return rates
            
        except Exception as e:
            logger.error(f"Get tax rates error: {str(e)}")
            raise
    
    async def file_return(
        self,
        filing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """File a tax return via TaxJar"""
        # TaxJar AutoFile integration
        raise NotImplementedError("TaxJar AutoFile integration pending")
    
    def _convert_taxjar_response(
        self,
        taxjar_response: Dict[str, Any],
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Convert TaxJar response to our format"""
        from ..schemas.tax_jurisdiction_schemas import TaxCalculationResult
        
        # TaxJar returns aggregated tax, need to distribute to line items
        total_amount = sum(item.amount * item.quantity for item in request.line_items)
        
        line_results = []
        tax_summary = {}
        
        # Build tax details from breakdown
        tax_details = []
        
        if taxjar_response.get("state_tax_collectable", 0) > 0:
            tax_details.append({
                "jurisdiction_name": taxjar_response.get("jurisdictions", {}).get("state", "State"),
                "jurisdiction_type": "state",
                "tax_type": "sales",
                "rate": Decimal(str(taxjar_response.get("state_tax_rate", 0))) * 100,
                "tax_amount": Decimal(str(taxjar_response["state_tax_collectable"]))
            })
        
        if taxjar_response.get("county_tax_collectable", 0) > 0:
            tax_details.append({
                "jurisdiction_name": taxjar_response.get("jurisdictions", {}).get("county", "County"),
                "jurisdiction_type": "county",
                "tax_type": "sales",
                "rate": Decimal(str(taxjar_response.get("county_tax_rate", 0))) * 100,
                "tax_amount": Decimal(str(taxjar_response["county_tax_collectable"]))
            })
        
        if taxjar_response.get("city_tax_collectable", 0) > 0:
            tax_details.append({
                "jurisdiction_name": taxjar_response.get("jurisdictions", {}).get("city", "City"),
                "jurisdiction_type": "city",
                "tax_type": "sales",
                "rate": Decimal(str(taxjar_response.get("city_tax_rate", 0))) * 100,
                "tax_amount": Decimal(str(taxjar_response["city_tax_collectable"]))
            })
        
        if taxjar_response.get("special_district_tax_collectable", 0) > 0:
            tax_details.append({
                "jurisdiction_name": "Special District",
                "jurisdiction_type": "special",
                "tax_type": "sales",
                "rate": Decimal(str(taxjar_response.get("special_tax_rate", 0))) * 100,
                "tax_amount": Decimal(str(taxjar_response["special_district_tax_collectable"]))
            })
        
        # Distribute tax proportionally to line items
        for item in request.line_items:
            item_amount = item.amount * item.quantity
            item_proportion = item_amount / total_amount if total_amount > 0 else Decimal("0")
            
            item_tax_details = []
            item_total_tax = Decimal("0")
            
            for detail in tax_details:
                item_tax = detail["tax_amount"] * item_proportion
                item_tax_details.append({
                    **detail,
                    "tax_amount": item_tax
                })
                item_total_tax += item_tax
                
                # Update summary
                jurisdiction = detail["jurisdiction_name"]
                tax_type = detail["tax_type"]
                
                if jurisdiction not in tax_summary:
                    tax_summary[jurisdiction] = {}
                if tax_type not in tax_summary[jurisdiction]:
                    tax_summary[jurisdiction][tax_type] = Decimal("0")
                
                tax_summary[jurisdiction][tax_type] += item_tax
            
            line_results.append(TaxCalculationResult(
                line_id=item.line_id,
                taxable_amount=item_amount,
                tax_details=item_tax_details,
                total_tax=item_total_tax,
                effective_rate=item_total_tax / item_amount * 100 if item_amount > 0 else Decimal("0")
            ))
        
        return EnhancedTaxCalculationResponse(
            transaction_id=request.transaction_id,
            calculation_date=datetime.utcnow(),
            subtotal=Decimal(str(taxjar_response.get("taxable_amount", 0))),
            taxable_amount=Decimal(str(taxjar_response.get("taxable_amount", 0))),
            exempt_amount=Decimal("0"),  # TaxJar doesn't provide this separately
            total_tax=Decimal(str(taxjar_response.get("amount_to_collect", 0))),
            total_amount=Decimal(str(taxjar_response.get("taxable_amount", 0))) + 
                       Decimal(str(taxjar_response.get("amount_to_collect", 0))),
            line_results=line_results,
            tax_summary_by_jurisdiction=tax_summary,
            applied_exemptions=[],
            warnings=[]
        )


class TaxIntegrationService:
    """Service for managing external tax provider integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers: Dict[str, TaxProviderInterface] = {}
        self.default_provider = config.get("default_provider", "internal")
        
        # Initialize configured providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize tax providers based on configuration"""
        provider_configs = self.config.get("providers", {})
        
        for provider_name, provider_config in provider_configs.items():
            if not provider_config.get("enabled", False):
                continue
            
            if provider_name == "avalara":
                self.providers[provider_name] = AvalaraTaxProvider(provider_config)
            elif provider_name == "taxjar":
                self.providers[provider_name] = TaxJarProvider(provider_config)
            # Add more providers as needed
    
    async def calculate_tax(
        self,
        request: EnhancedTaxCalculationRequest,
        provider: Optional[str] = None
    ) -> EnhancedTaxCalculationResponse:
        """Calculate tax using specified or default provider"""
        provider_name = provider or self.default_provider
        
        if provider_name == "internal":
            # Use internal calculation engine
            raise NotImplementedError("Use TaxCalculationEngine for internal calculations")
        
        if provider_name not in self.providers:
            raise ValueError(f"Tax provider '{provider_name}' not configured")
        
        return await self.providers[provider_name].calculate_tax(request)
    
    async def validate_address(
        self,
        address: Dict[str, str],
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate address using external provider"""
        provider_name = provider or self.default_provider
        
        if provider_name == "internal":
            # Basic internal validation
            return {
                "valid": bool(address.get("zip") and address.get("state")),
                "standardized": address,
                "messages": []
            }
        
        if provider_name not in self.providers:
            raise ValueError(f"Tax provider '{provider_name}' not configured")
        
        return await self.providers[provider_name].validate_address(address)
    
    async def get_tax_rates(
        self,
        location: TaxCalculationLocation,
        tax_date: date,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tax rates from external provider"""
        provider_name = provider or self.default_provider
        
        if provider_name == "internal":
            raise NotImplementedError("Use TaxCalculationEngine for internal rates")
        
        if provider_name not in self.providers:
            raise ValueError(f"Tax provider '{provider_name}' not configured")
        
        return await self.providers[provider_name].get_tax_rates(location, tax_date)
    
    async def sync_tax_rates(
        self,
        provider: str,
        locations: List[TaxCalculationLocation]
    ) -> Dict[str, Any]:
        """Sync tax rates from external provider to internal database"""
        if provider not in self.providers:
            raise ValueError(f"Tax provider '{provider}' not configured")
        
        synced_count = 0
        errors = []
        
        for location in locations:
            try:
                rates = await self.providers[provider].get_tax_rates(
                    location, date.today()
                )
                
                # TODO: Save rates to database
                synced_count += len(rates)
                
            except Exception as e:
                errors.append({
                    "location": f"{location.city_name}, {location.state_code}",
                    "error": str(e)
                })
        
        return {
            "synced_count": synced_count,
            "location_count": len(locations),
            "errors": errors
        }
    
    async def close(self):
        """Close all provider connections"""
        for provider in self.providers.values():
            if hasattr(provider, 'client'):
                await provider.client.aclose()


# Utility functions for provider configuration
def get_tax_provider_config() -> Dict[str, Any]:
    """Get tax provider configuration from environment or settings"""
    import os
    
    return {
        "default_provider": os.getenv("TAX_DEFAULT_PROVIDER", "internal"),
        "providers": {
            "avalara": {
                "enabled": os.getenv("AVALARA_ENABLED", "false").lower() == "true",
                "account_id": os.getenv("AVALARA_ACCOUNT_ID"),
                "license_key": os.getenv("AVALARA_LICENSE_KEY"),
                "company_code": os.getenv("AVALARA_COMPANY_CODE", "DEFAULT"),
                "environment": os.getenv("AVALARA_ENVIRONMENT", "sandbox")
            },
            "taxjar": {
                "enabled": os.getenv("TAXJAR_ENABLED", "false").lower() == "true",
                "api_token": os.getenv("TAXJAR_API_TOKEN")
            }
        }
    }


def create_tax_integration_service() -> TaxIntegrationService:
    """Factory function to create tax integration service"""
    config = get_tax_provider_config()
    return TaxIntegrationService(config)