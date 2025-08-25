# backend/modules/pos/services/migration_coach_agent.py

"""
AI-powered migration coach agent that guides restaurants through POS data migration.
Leverages existing AI infrastructure to provide intelligent field mapping and validation.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from modules.ai_recommendations.providers.openai_provider import OpenAIProvider
from modules.ai_recommendations.interfaces.model_provider_interface import (
    ModelProviderConfig,
    ModelRequest,
)
from ..schemas.migration_schemas import (
    FieldMapping,
    MigrationPlan,
    ValidationReport,
    MappingSuggestion,
)
from ..adapters.base_adapter import BasePOSAdapter

logger = logging.getLogger(__name__)


class MigrationCoachAgent:
    """AI agent that provides intelligent guidance during POS migrations"""
    
    def __init__(self, db: Session, ai_provider: Optional[OpenAIProvider] = None):
        self.db = db
        self.ai_provider = ai_provider or self._init_default_provider()
        
    def _init_default_provider(self) -> OpenAIProvider:
        """Initialize default OpenAI provider"""
        config = ModelProviderConfig(
            api_key=os.environ.get("OPENAI_API_KEY"),
            default_model="gpt-4",
            timeout=30,
            max_retries=3,
        )
        return OpenAIProvider(config)
    
    async def analyze_pos_structure(
        self,
        pos_type: str,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """Analyze POS data structure and create migration plan"""
        
        prompt = f"""
        You are a POS migration expert. Analyze this {pos_type} data structure and create a migration plan.
        
        Source POS: {pos_type}
        Sample Data Structure:
        {json.dumps(sample_data, indent=2)[:2000]}  # Limit token usage
        
        Target Schema (AuraConnect):
        {json.dumps(target_schema, indent=2)[:1000]}
        
        Please provide:
        1. Recommended field mappings with confidence scores (0.0-1.0)
        2. Data transformation requirements
        3. Potential data quality issues
        4. Migration complexity assessment (simple/moderate/complex)
        5. Estimated time and risk factors
        
        Response format:
        {
            "field_mappings": [
                {
                    "source_field": "field_name",
                    "target_field": "target_name", 
                    "confidence": 0.95,
                    "transformation": "none|lowercase|parse_json|custom",
                    "notes": "any special considerations"
                }
            ],
            "data_quality_issues": ["list of potential issues"],
            "complexity": "simple|moderate|complex",
            "estimated_hours": 4,
            "risk_factors": ["list of risks"],
            "recommendations": ["list of recommendations"]
        }
        """
        
        request = ModelRequest(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3,  # Lower temperature for more consistent analysis
            response_format="json"
        )
        
        try:
            response = await self.ai_provider.generate(request)
            plan_data = json.loads(response.content)
            
            # Track token usage for billing
            await self._track_token_usage(
                operation="analyze_structure",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tenant_id=self.db.info.get("tenant_id")
            )
            
            return MigrationPlan(**plan_data)
            
        except Exception as e:
            logger.error(f"Error analyzing POS structure: {e}")
            # Return a basic plan if AI fails
            return self._create_fallback_plan(sample_data, target_schema)
    
    async def suggest_field_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[MappingSuggestion]:
        """Generate intelligent field mapping suggestions"""
        
        prompt = f"""
        You are mapping fields from a POS system to AuraConnect.
        
        Source fields: {source_fields}
        Target fields: {target_fields}
        Context: {context or 'Restaurant menu and order management system'}
        
        For each source field, suggest the best matching target field.
        Consider semantic meaning, not just name similarity.
        
        Common mappings:
        - "itemName", "productName", "dishName" -> "name"
        - "itemPrice", "cost", "amount" -> "price"
        - "itemDescription", "details" -> "description"
        - "categoryName", "itemCategory" -> "category_id"
        - "modifierGroup", "options" -> "modifier_groups"
        
        Response format:
        [
            {
                "source": "source_field_name",
                "target": "target_field_name",
                "confidence": 0.95,
                "reasoning": "why this mapping makes sense"
            }
        ]
        """
        
        request = ModelRequest(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.2,
            response_format="json"
        )
        
        try:
            response = await self.ai_provider.generate(request)
            suggestions_data = json.loads(response.content)
            
            # Track token usage
            await self._track_token_usage(
                operation="field_mapping",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tenant_id=self.db.info.get("tenant_id")
            )
            
            return [MappingSuggestion(**s) for s in suggestions_data]
            
        except Exception as e:
            logger.error(f"Error suggesting field mappings: {e}")
            return self._create_basic_mappings(source_fields, target_fields)
    
    async def validate_pricing_data(
        self,
        items: List[Dict[str, Any]],
        pos_type: str
    ) -> ValidationReport:
        """Detect pricing anomalies and validate data integrity"""
        
        # Extract price statistics
        prices = [float(item.get("price", 0)) for item in items if item.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0
        max_price = max(prices) if prices else 0
        min_price = min(prices) if prices else 0
        
        prompt = f"""
        Analyze this pricing data from a {pos_type} POS system for anomalies:
        
        Statistics:
        - Total items: {len(items)}
        - Average price: ${avg_price:.2f}
        - Price range: ${min_price:.2f} - ${max_price:.2f}
        
        Sample items (first 10):
        {json.dumps(items[:10], indent=2)[:1000]}
        
        Check for:
        1. Suspiciously high or low prices
        2. Missing prices
        3. Incorrect decimal places (e.g., price in cents vs dollars)
        4. Duplicate items with different prices
        5. Common POS-specific issues
        
        Response format:
        {
            "anomalies": [
                {
                    "type": "high_price|low_price|missing|decimal_error|duplicate",
                    "severity": "high|medium|low",
                    "affected_items": ["item_ids"],
                    "description": "detailed description",
                    "suggested_action": "what to do"
                }
            ],
            "summary": {
                "total_issues": 5,
                "requires_manual_review": true,
                "confidence": 0.85
            }
        }
        """
        
        request = ModelRequest(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
            response_format="json"
        )
        
        try:
            response = await self.ai_provider.generate(request)
            validation_data = json.loads(response.content)
            
            # Track token usage
            await self._track_token_usage(
                operation="price_validation",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tenant_id=self.db.info.get("tenant_id")
            )
            
            return ValidationReport(**validation_data)
            
        except Exception as e:
            logger.error(f"Error validating pricing data: {e}")
            return self._create_basic_validation_report(items)
    
    async def generate_migration_summary(
        self,
        migration_stats: Dict[str, Any],
        customer_name: str
    ) -> str:
        """Generate a friendly migration summary for customers"""
        
        prompt = f"""
        Write a friendly, personalized email summary for {customer_name} about their restaurant's data migration to AuraConnect.
        
        Migration statistics:
        - Menu items migrated: {migration_stats.get('items_count', 0)}
        - Categories: {migration_stats.get('categories_count', 0)}
        - Modifiers: {migration_stats.get('modifiers_count', 0)}
        - Historical orders preserved: {migration_stats.get('orders_count', 0)}
        
        Key benefits they'll experience:
        - Real-time order tracking
        - Advanced analytics
        - Automated inventory management
        - Integrated loyalty program
        
        Keep it:
        - Friendly and conversational
        - Under 200 words
        - Focused on benefits, not technical details
        - Include a call-to-action to explore new features
        """
        
        request = ModelRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.7,
        )
        
        try:
            response = await self.ai_provider.generate(request)
            
            # Track token usage
            await self._track_token_usage(
                operation="summary_generation",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tenant_id=self.db.info.get("tenant_id")
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating migration summary: {e}")
            return self._create_fallback_summary(migration_stats, customer_name)
    
    async def _track_token_usage(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        tenant_id: Optional[str] = None
    ) -> None:
        """Track token usage for billing purposes"""
        # This would integrate with the TokenCostService
        # For now, just log it
        logger.info(
            f"Token usage - Operation: {operation}, "
            f"Input: {input_tokens}, Output: {output_tokens}, "
            f"Tenant: {tenant_id}"
        )
    
    def _create_fallback_plan(
        self,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """Create basic migration plan without AI"""
        return MigrationPlan(
            field_mappings=[],
            data_quality_issues=["Manual review required"],
            complexity="moderate",
            estimated_hours=8,
            risk_factors=["AI analysis unavailable"],
            recommendations=["Proceed with manual mapping"]
        )
    
    def _create_basic_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str]
    ) -> List[MappingSuggestion]:
        """Create basic field mappings based on name similarity"""
        suggestions = []
        
        # Simple name matching
        for source in source_fields:
            source_lower = source.lower()
            best_match = None
            best_score = 0.0
            
            for target in target_fields:
                target_lower = target.lower()
                
                # Exact match
                if source_lower == target_lower:
                    best_match = target
                    best_score = 1.0
                    break
                
                # Partial match
                if source_lower in target_lower or target_lower in source_lower:
                    score = 0.7
                    if score > best_score:
                        best_match = target
                        best_score = score
            
            if best_match:
                suggestions.append(MappingSuggestion(
                    source=source,
                    target=best_match,
                    confidence=best_score,
                    reasoning="Name similarity"
                ))
        
        return suggestions
    
    def _create_basic_validation_report(
        self,
        items: List[Dict[str, Any]]
    ) -> ValidationReport:
        """Create basic validation report without AI"""
        anomalies = []
        
        # Check for missing prices
        missing_prices = [
            item for item in items 
            if not item.get("price") or float(item.get("price", 0)) <= 0
        ]
        
        if missing_prices:
            anomalies.append({
                "type": "missing",
                "severity": "high",
                "affected_items": [item.get("id", "unknown") for item in missing_prices[:10]],
                "description": f"{len(missing_prices)} items have missing or zero prices",
                "suggested_action": "Review and update pricing for these items"
            })
        
        return ValidationReport(
            anomalies=anomalies,
            summary={
                "total_issues": len(anomalies),
                "requires_manual_review": len(anomalies) > 0,
                "confidence": 0.5
            }
        )
    
    def _create_fallback_summary(
        self,
        migration_stats: Dict[str, Any],
        customer_name: str
    ) -> str:
        """Create basic migration summary without AI"""
        return f"""
        Dear {customer_name},

        Great news! Your restaurant's data has been successfully migrated to AuraConnect.

        What we've migrated:
        - {migration_stats.get('items_count', 0)} menu items
        - {migration_stats.get('categories_count', 0)} categories
        - {migration_stats.get('modifiers_count', 0)} modifiers
        - {migration_stats.get('orders_count', 0)} historical orders

        You can now enjoy powerful new features like real-time analytics, automated inventory tracking, and integrated customer loyalty programs.

        Log in to explore your new dashboard and let us know if you need any assistance!

        Best regards,
        The AuraConnect Team
        """