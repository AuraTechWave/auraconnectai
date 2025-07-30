# backend/modules/tax/services/tax_calculation_engine.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import logging
from collections import defaultdict

from ..models import (
    TaxJurisdiction, TaxRate, TaxRuleConfiguration,
    TaxExemptionCertificate, TaxNexus
)
from ..schemas.tax_jurisdiction_schemas import (
    EnhancedTaxCalculationRequest,
    EnhancedTaxCalculationResponse,
    TaxCalculationResult,
    TaxCalculationLocation
)

logger = logging.getLogger(__name__)


class TaxCalculationEngine:
    """Enhanced tax calculation engine with multi-jurisdiction support"""
    
    def __init__(self, db: Session):
        self.db = db
        self._rate_cache = {}
        self._rule_cache = {}
        
    def calculate_tax(
        self,
        request: EnhancedTaxCalculationRequest,
        tenant_id: Optional[int] = None
    ) -> EnhancedTaxCalculationResponse:
        """
        Calculate tax for a transaction with multi-jurisdiction support
        """
        try:
            # Step 1: Identify applicable jurisdictions
            jurisdictions = self._get_applicable_jurisdictions(
                request.location, tenant_id
            )
            
            if not jurisdictions:
                return self._create_zero_tax_response(request)
            
            # Step 2: Check for exemptions
            exemptions = self._get_applicable_exemptions(
                request.customer_id,
                request.exemption_certificate_id,
                jurisdictions,
                tenant_id
            )
            
            # Step 3: Get applicable tax rates and rules
            tax_rates = self._get_applicable_tax_rates(
                jurisdictions,
                request.transaction_date,
                tenant_id
            )
            
            tax_rules = self._get_applicable_tax_rules(
                jurisdictions,
                request.transaction_date,
                tenant_id
            )
            
            # Step 4: Calculate tax for each line item
            line_results = []
            total_tax = Decimal("0")
            taxable_amount = Decimal("0")
            exempt_amount = Decimal("0")
            tax_summary = defaultdict(lambda: defaultdict(Decimal))
            
            for item in request.line_items:
                line_result = self._calculate_line_item_tax(
                    item,
                    tax_rates,
                    tax_rules,
                    exemptions,
                    request
                )
                line_results.append(line_result)
                
                total_tax += line_result.total_tax
                if line_result.taxable_amount > 0:
                    taxable_amount += line_result.taxable_amount
                else:
                    exempt_amount += item.amount * item.quantity
                
                # Update tax summary
                for detail in line_result.tax_details:
                    jurisdiction_name = detail["jurisdiction_name"]
                    tax_type = detail["tax_type"]
                    tax_summary[jurisdiction_name][tax_type] += detail["tax_amount"]
            
            # Step 5: Apply shipping and discount if applicable
            if request.shipping_amount and request.shipping_amount > 0:
                shipping_tax = self._calculate_shipping_tax(
                    request.shipping_amount,
                    tax_rates,
                    exemptions
                )
                total_tax += shipping_tax["total_tax"]
                taxable_amount += shipping_tax["taxable_amount"]
                
                # Update summary
                for jurisdiction, amount in shipping_tax["breakdown"].items():
                    tax_summary[jurisdiction]["shipping_tax"] += amount
            
            # Step 6: Create response
            subtotal = sum(
                item.amount * item.quantity for item in request.line_items
            ) + (request.shipping_amount or Decimal("0"))
            
            if request.discount_amount:
                subtotal -= request.discount_amount
            
            warnings = self._generate_warnings(
                jurisdictions, tax_rates, exemptions
            )
            
            return EnhancedTaxCalculationResponse(
                transaction_id=request.transaction_id,
                calculation_date=datetime.utcnow(),
                subtotal=subtotal,
                taxable_amount=taxable_amount,
                exempt_amount=exempt_amount,
                total_tax=total_tax,
                total_amount=subtotal + total_tax,
                line_results=line_results,
                tax_summary_by_jurisdiction=dict(tax_summary),
                applied_exemptions=[
                    {
                        "certificate_id": str(cert.certificate_id),
                        "exemption_type": cert.exemption_type,
                        "jurisdictions": cert.jurisdiction_ids
                    }
                    for cert in exemptions
                ],
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Tax calculation error: {str(e)}")
            raise
    
    def _get_applicable_jurisdictions(
        self,
        location: TaxCalculationLocation,
        tenant_id: Optional[int]
    ) -> List[TaxJurisdiction]:
        """Get all applicable tax jurisdictions for a location"""
        query = self.db.query(TaxJurisdiction).filter(
            TaxJurisdiction.is_active == True,
            TaxJurisdiction.country_code == location.country_code
        )
        
        if tenant_id:
            query = query.filter(TaxJurisdiction.tenant_id == tenant_id)
        
        # Federal jurisdiction
        jurisdictions = query.filter(
            TaxJurisdiction.jurisdiction_type == "federal"
        ).all()
        
        # State jurisdiction
        if location.state_code:
            state_jurisdictions = query.filter(
                TaxJurisdiction.jurisdiction_type == "state",
                TaxJurisdiction.state_code == location.state_code
            ).all()
            jurisdictions.extend(state_jurisdictions)
        
        # County jurisdiction
        if location.county_name:
            county_jurisdictions = query.filter(
                TaxJurisdiction.jurisdiction_type == "county",
                TaxJurisdiction.state_code == location.state_code,
                TaxJurisdiction.county_name == location.county_name
            ).all()
            jurisdictions.extend(county_jurisdictions)
        
        # City jurisdiction
        if location.city_name:
            city_jurisdictions = query.filter(
                TaxJurisdiction.jurisdiction_type == "city",
                TaxJurisdiction.state_code == location.state_code,
                TaxJurisdiction.city_name == location.city_name
            ).all()
            jurisdictions.extend(city_jurisdictions)
        
        # Special jurisdictions (by zip code)
        if location.zip_code:
            special_jurisdictions = query.filter(
                TaxJurisdiction.jurisdiction_type == "special"
            ).all()
            
            for jurisdiction in special_jurisdictions:
                if jurisdiction.zip_codes and location.zip_code in jurisdiction.zip_codes:
                    jurisdictions.append(jurisdiction)
        
        return jurisdictions
    
    def _get_applicable_tax_rates(
        self,
        jurisdictions: List[TaxJurisdiction],
        transaction_date: date,
        tenant_id: Optional[int]
    ) -> List[TaxRate]:
        """Get applicable tax rates for jurisdictions"""
        jurisdiction_ids = [j.id for j in jurisdictions]
        
        query = self.db.query(TaxRate).filter(
            TaxRate.jurisdiction_id.in_(jurisdiction_ids),
            TaxRate.is_active == True,
            TaxRate.effective_date <= transaction_date,
            or_(
                TaxRate.expiry_date.is_(None),
                TaxRate.expiry_date >= transaction_date
            )
        )
        
        if tenant_id:
            query = query.filter(TaxRate.tenant_id == tenant_id)
        
        return query.order_by(TaxRate.ordering).all()
    
    def _get_applicable_tax_rules(
        self,
        jurisdictions: List[TaxJurisdiction],
        transaction_date: date,
        tenant_id: Optional[int]
    ) -> List[TaxRuleConfiguration]:
        """Get applicable tax rules for jurisdictions"""
        jurisdiction_ids = [j.id for j in jurisdictions]
        
        query = self.db.query(TaxRuleConfiguration).filter(
            TaxRuleConfiguration.jurisdiction_id.in_(jurisdiction_ids),
            TaxRuleConfiguration.is_active == True,
            TaxRuleConfiguration.effective_date <= transaction_date,
            or_(
                TaxRuleConfiguration.expiry_date.is_(None),
                TaxRuleConfiguration.expiry_date >= transaction_date
            )
        )
        
        if tenant_id:
            query = query.filter(TaxRuleConfiguration.tenant_id == tenant_id)
        
        return query.order_by(TaxRuleConfiguration.priority.desc()).all()
    
    def _get_applicable_exemptions(
        self,
        customer_id: Optional[int],
        certificate_id: Optional[str],
        jurisdictions: List[TaxJurisdiction],
        tenant_id: Optional[int]
    ) -> List[TaxExemptionCertificate]:
        """Get applicable exemption certificates"""
        if not customer_id and not certificate_id:
            return []
        
        query = self.db.query(TaxExemptionCertificate).filter(
            TaxExemptionCertificate.is_active == True,
            TaxExemptionCertificate.is_verified == True
        )
        
        if certificate_id:
            query = query.filter(
                TaxExemptionCertificate.certificate_id == certificate_id
            )
        elif customer_id:
            query = query.filter(
                TaxExemptionCertificate.customer_id == customer_id
            )
        
        if tenant_id:
            query = query.filter(TaxExemptionCertificate.tenant_id == tenant_id)
        
        certificates = query.all()
        
        # Filter certificates that apply to our jurisdictions
        jurisdiction_ids = [j.id for j in jurisdictions]
        applicable_certificates = []
        
        for cert in certificates:
            if any(jid in cert.jurisdiction_ids for jid in jurisdiction_ids):
                # Check if certificate is still valid
                if cert.expiry_date is None or cert.expiry_date >= date.today():
                    applicable_certificates.append(cert)
                    
                    # Update usage tracking
                    cert.last_used_date = date.today()
                    cert.usage_count += 1
        
        if applicable_certificates:
            self.db.commit()
        
        return applicable_certificates
    
    def _calculate_line_item_tax(
        self,
        item: Any,
        tax_rates: List[TaxRate],
        tax_rules: List[TaxRuleConfiguration],
        exemptions: List[TaxExemptionCertificate],
        request: EnhancedTaxCalculationRequest
    ) -> TaxCalculationResult:
        """Calculate tax for a single line item"""
        base_amount = item.amount * item.quantity
        taxable_amount = base_amount
        tax_details = []
        total_tax = Decimal("0")
        
        # Check if item is exempt
        if item.is_exempt or self._is_item_exempt(item, exemptions):
            return TaxCalculationResult(
                line_id=item.line_id,
                taxable_amount=Decimal("0"),
                tax_details=[{
                    "jurisdiction_name": "All",
                    "tax_type": "exempt",
                    "rate": Decimal("0"),
                    "tax_amount": Decimal("0"),
                    "reason": item.exemption_reason or "Certificate exemption"
                }],
                total_tax=Decimal("0"),
                effective_rate=Decimal("0")
            )
        
        # Apply tax rules to determine taxable amount
        for rule in tax_rules:
            if self._evaluate_rule(rule, item, request):
                taxable_amount = self._apply_rule_action(
                    rule, taxable_amount, base_amount
                )
        
        # Calculate taxes for each rate
        applied_taxes = {}
        
        for rate in tax_rates:
            if not self._is_rate_applicable(rate, item):
                continue
            
            # Check if this tax should compound on others
            calculation_base = taxable_amount
            if rate.compound_on:
                for compound_tax in rate.compound_on:
                    if compound_tax in applied_taxes:
                        calculation_base += applied_taxes[compound_tax]
            
            # Calculate tax amount
            if rate.calculation_method == "percentage":
                tax_amount = (
                    calculation_base * rate.rate_percent / 100
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif rate.calculation_method == "flat":
                tax_amount = rate.flat_amount or Decimal("0")
            else:  # tiered
                tax_amount = self._calculate_tiered_tax(
                    calculation_base, rate
                )
            
            # Apply min/max thresholds
            if rate.min_amount and calculation_base < rate.min_amount:
                tax_amount = Decimal("0")
            elif rate.max_amount and calculation_base > rate.max_amount:
                # Only tax up to max amount
                if rate.calculation_method == "percentage":
                    tax_amount = (
                        rate.max_amount * rate.rate_percent / 100
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            if tax_amount > 0:
                jurisdiction = next(
                    j for j in tax_rates 
                    if j.id == rate.jurisdiction_id
                )
                
                tax_details.append({
                    "jurisdiction_name": rate.jurisdiction.name,
                    "jurisdiction_type": rate.jurisdiction.jurisdiction_type,
                    "tax_type": rate.tax_type,
                    "tax_subtype": rate.tax_subtype,
                    "rate": rate.rate_percent,
                    "tax_amount": tax_amount,
                    "calculation_method": rate.calculation_method
                })
                
                total_tax += tax_amount
                applied_taxes[f"{rate.tax_type}_{rate.jurisdiction_id}"] = tax_amount
        
        effective_rate = (
            total_tax / base_amount * 100 if base_amount > 0 
            else Decimal("0")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return TaxCalculationResult(
            line_id=item.line_id,
            taxable_amount=taxable_amount,
            tax_details=tax_details,
            total_tax=total_tax,
            effective_rate=effective_rate
        )
    
    def _calculate_shipping_tax(
        self,
        shipping_amount: Decimal,
        tax_rates: List[TaxRate],
        exemptions: List[TaxExemptionCertificate]
    ) -> Dict[str, Any]:
        """Calculate tax on shipping charges"""
        result = {
            "taxable_amount": shipping_amount,
            "total_tax": Decimal("0"),
            "breakdown": {}
        }
        
        # Check if shipping is exempt
        shipping_exempt = any(
            "shipping" in cert.tax_types for cert in exemptions
        )
        
        if shipping_exempt:
            result["taxable_amount"] = Decimal("0")
            return result
        
        # Apply shipping tax rates
        for rate in tax_rates:
            if rate.tax_type == "sales" and rate.applies_to in ["all", "shipping"]:
                tax_amount = (
                    shipping_amount * rate.rate_percent / 100
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                
                result["total_tax"] += tax_amount
                result["breakdown"][rate.jurisdiction.name] = tax_amount
        
        return result
    
    def _evaluate_rule(
        self,
        rule: TaxRuleConfiguration,
        item: Any,
        request: EnhancedTaxCalculationRequest
    ) -> bool:
        """Evaluate if a tax rule applies to an item"""
        try:
            conditions = rule.conditions
            
            # All conditions must be met
            for condition in conditions:
                field = condition.get("field")
                operator = condition.get("operator")
                value = condition.get("value")
                
                # Get field value from item or request
                if hasattr(item, field):
                    field_value = getattr(item, field)
                elif hasattr(request, field):
                    field_value = getattr(request, field)
                else:
                    continue
                
                # Evaluate condition
                if not self._evaluate_condition(field_value, operator, value):
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error evaluating rule {rule.rule_code}: {str(e)}")
            return False
    
    def _evaluate_condition(
        self,
        field_value: Any,
        operator: str,
        compare_value: Any
    ) -> bool:
        """Evaluate a single condition"""
        if operator == "eq":
            return field_value == compare_value
        elif operator == "ne":
            return field_value != compare_value
        elif operator == "gt":
            return field_value > compare_value
        elif operator == "lt":
            return field_value < compare_value
        elif operator == "gte":
            return field_value >= compare_value
        elif operator == "lte":
            return field_value <= compare_value
        elif operator == "in":
            return field_value in compare_value
        elif operator == "not_in":
            return field_value not in compare_value
        elif operator == "contains":
            return compare_value in str(field_value)
        
        return False
    
    def _apply_rule_action(
        self,
        rule: TaxRuleConfiguration,
        taxable_amount: Decimal,
        base_amount: Decimal
    ) -> Decimal:
        """Apply rule action to modify taxable amount"""
        try:
            actions = rule.actions
            
            for action in actions:
                action_type = action.get("action_type")
                parameters = action.get("parameters", {})
                
                if action_type == "exempt":
                    return Decimal("0")
                elif action_type == "reduce_rate":
                    reduction = Decimal(str(parameters.get("percentage", 0)))
                    return taxable_amount * (100 - reduction) / 100
                elif action_type == "apply_rate":
                    rate = Decimal(str(parameters.get("rate", 0)))
                    return base_amount * rate / 100
                elif action_type == "add_fee":
                    fee = Decimal(str(parameters.get("amount", 0)))
                    return taxable_amount + fee
            
            return taxable_amount
            
        except Exception as e:
            logger.warning(f"Error applying rule action: {str(e)}")
            return taxable_amount
    
    def _is_rate_applicable(self, rate: TaxRate, item: Any) -> bool:
        """Check if a tax rate applies to an item"""
        # Check if item category is in exemption list
        if rate.exemption_categories and item.category:
            if item.category in rate.exemption_categories:
                return False
        
        # Check if rate applies to this type of item
        if rate.applies_to and rate.applies_to != "all":
            if item.category and item.category not in rate.applies_to:
                return False
        
        return True
    
    def _is_item_exempt(
        self,
        item: Any,
        exemptions: List[TaxExemptionCertificate]
    ) -> bool:
        """Check if an item is exempt based on certificates"""
        if not exemptions:
            return False
        
        for cert in exemptions:
            # Check if certificate covers this tax type
            if "sales" in cert.tax_types or "all" in cert.tax_types:
                # Check if there are category-specific exemptions
                if hasattr(item, "category") and item.category:
                    # Certificate might have category restrictions
                    # This would need to be implemented based on business rules
                    pass
                return True
        
        return False
    
    def _calculate_tiered_tax(
        self,
        amount: Decimal,
        rate: TaxRate
    ) -> Decimal:
        """Calculate tax for tiered rates"""
        # This would need to be implemented based on specific tiered tax structures
        # For now, return simple percentage calculation
        return (amount * rate.rate_percent / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    
    def _generate_warnings(
        self,
        jurisdictions: List[TaxJurisdiction],
        tax_rates: List[TaxRate],
        exemptions: List[TaxExemptionCertificate]
    ) -> List[str]:
        """Generate warnings about tax calculation"""
        warnings = []
        
        # Check for missing tax rates
        jurisdiction_ids_with_rates = set(rate.jurisdiction_id for rate in tax_rates)
        for jurisdiction in jurisdictions:
            if jurisdiction.id not in jurisdiction_ids_with_rates:
                warnings.append(
                    f"No tax rates found for {jurisdiction.name} ({jurisdiction.jurisdiction_type})"
                )
        
        # Check for expiring exemption certificates
        for cert in exemptions:
            if cert.expiry_date:
                days_until_expiry = (cert.expiry_date - date.today()).days
                if days_until_expiry <= 30:
                    warnings.append(
                        f"Exemption certificate {cert.certificate_number} expires in {days_until_expiry} days"
                    )
        
        # Check for nexus requirements
        nexus_jurisdictions = self.db.query(TaxNexus).filter(
            TaxNexus.is_active == True,
            TaxNexus.requires_filing == True
        ).all()
        
        for nexus in nexus_jurisdictions:
            if nexus.next_filing_date:
                days_until_filing = (nexus.next_filing_date - date.today()).days
                if days_until_filing <= 7:
                    warnings.append(
                        f"Tax filing due for {nexus.jurisdiction.name} in {days_until_filing} days"
                    )
        
        return warnings
    
    def _create_zero_tax_response(
        self,
        request: EnhancedTaxCalculationRequest
    ) -> EnhancedTaxCalculationResponse:
        """Create response with zero tax"""
        subtotal = sum(
            item.amount * item.quantity for item in request.line_items
        ) + (request.shipping_amount or Decimal("0"))
        
        if request.discount_amount:
            subtotal -= request.discount_amount
        
        line_results = [
            TaxCalculationResult(
                line_id=item.line_id,
                taxable_amount=Decimal("0"),
                tax_details=[],
                total_tax=Decimal("0"),
                effective_rate=Decimal("0")
            )
            for item in request.line_items
        ]
        
        return EnhancedTaxCalculationResponse(
            transaction_id=request.transaction_id,
            calculation_date=datetime.utcnow(),
            subtotal=subtotal,
            taxable_amount=Decimal("0"),
            exempt_amount=subtotal,
            total_tax=Decimal("0"),
            total_amount=subtotal,
            line_results=line_results,
            tax_summary_by_jurisdiction={},
            applied_exemptions=[],
            warnings=["No applicable tax jurisdictions found for this location"]
        )