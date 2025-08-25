# backend/modules/pos_migration/agents/migration_coach_agent.py

"""
Enhanced MigrationCoachAgent with proper module imports and fallback handling.
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from ..interfaces.agent_interface import IMigrationCoach
from ..schemas.migration_schemas import (
    FieldMapping,
    MigrationPlan,
    MappingSuggestion,
    MigrationComplexity,
    FieldTransformationType,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class MigrationCoachAgent(IMigrationCoach):
    """
    AI-powered migration coach that guides restaurants through POS data migration.
    Provides intelligent field mapping, complexity estimation, and migration planning.
    """
    
    def __init__(self, db: Session, ai_provider=None, cache_service=None):
        self.db = db
        self.ai_provider = ai_provider
        self.cache_service = cache_service
        self._token_usage = {
            "input": 0,
            "output": 0,
            "operations": []
        }
    
    @property
    def agent_name(self) -> str:
        return "MigrationCoach"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "pos_structure_analysis",
            "field_mapping_suggestion",
            "complexity_estimation",
            "migration_planning",
            "data_quality_assessment"
        ]
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the agent with configuration"""
        if not self.ai_provider and config.get("ai_provider"):
            # Initialize AI provider from config
            provider_config = config["ai_provider"]
            # This would initialize the actual provider
            logger.info(f"Initialized {self.agent_name} with AI provider")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health and dependencies"""
        health = {
            "status": "healthy",
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {}
        }
        
        # Check AI provider
        if self.ai_provider:
            try:
                # Would call actual health check
                health["dependencies"]["ai_provider"] = "healthy"
            except Exception as e:
                health["dependencies"]["ai_provider"] = f"unhealthy: {str(e)}"
                health["status"] = "degraded"
        else:
            health["dependencies"]["ai_provider"] = "not configured"
            health["status"] = "degraded"
        
        # Check cache
        if self.cache_service:
            try:
                # Would check cache connectivity
                health["dependencies"]["cache"] = "healthy"
            except Exception as e:
                health["dependencies"]["cache"] = f"unhealthy: {str(e)}"
        
        return health
    
    async def get_token_usage(self) -> TokenUsage:
        """Get current token usage statistics"""
        return TokenUsage(
            migration_id="current",
            tenant_id=self.db.info.get("tenant_id", "unknown"),
            operation_type="migration_coaching",
            model="gpt-4",
            input_tokens=self._token_usage["input"],
            output_tokens=self._token_usage["output"],
            cost_usd=Decimal(
                (self._token_usage["input"] * 0.03 + 
                 self._token_usage["output"] * 0.06) / 1000
            )
        )
    
    async def analyze_pos_structure(
        self,
        pos_type: str,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """Analyze POS data structure and create migration plan"""
        
        # Check cache first
        cache_key = self._generate_cache_key("analyze", pos_type, sample_data)
        if self.cache_service:
            cached_plan = await self._get_cached_result(cache_key)
            if cached_plan:
                logger.info(f"Using cached migration plan for {pos_type}")
                return MigrationPlan(**cached_plan)
        
        # Try AI analysis
        if self.ai_provider:
            try:
                plan = await self._ai_analyze_structure(pos_type, sample_data, target_schema)
                
                # Cache the result
                if self.cache_service:
                    await self._cache_result(cache_key, plan.dict())
                
                return plan
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
        
        # Fallback to rule-based analysis
        logger.info("Using rule-based analysis fallback")
        return self._rule_based_analysis(pos_type, sample_data, target_schema)
    
    async def suggest_field_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[MappingSuggestion]:
        """Generate intelligent field mapping suggestions"""
        
        # Check cache
        cache_key = self._generate_cache_key(
            "mappings", 
            ",".join(sorted(source_fields)), 
            ",".join(sorted(target_fields))
        )
        if self.cache_service:
            cached_mappings = await self._get_cached_result(cache_key)
            if cached_mappings:
                return [MappingSuggestion(**m) for m in cached_mappings]
        
        # Try AI suggestions
        if self.ai_provider:
            try:
                suggestions = await self._ai_suggest_mappings(
                    source_fields, target_fields, context
                )
                
                # Cache results
                if self.cache_service:
                    await self._cache_result(
                        cache_key, 
                        [s.dict() for s in suggestions]
                    )
                
                return suggestions
            except Exception as e:
                logger.error(f"AI mapping suggestion failed: {e}")
        
        # Fallback to rule-based mapping
        return self._rule_based_mappings(source_fields, target_fields)
    
    async def estimate_complexity(
        self,
        data_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate migration complexity and timeline"""
        
        # Simple rule-based complexity estimation
        total_items = data_stats.get("total_items", 0)
        total_categories = data_stats.get("total_categories", 0)
        total_modifiers = data_stats.get("total_modifiers", 0)
        has_custom_fields = data_stats.get("has_custom_fields", False)
        
        # Calculate complexity score
        complexity_score = (
            total_items * 1 +
            total_categories * 2 +
            total_modifiers * 3 +
            (100 if has_custom_fields else 0)
        )
        
        # Determine complexity level
        if complexity_score < 500:
            complexity = MigrationComplexity.SIMPLE
            estimated_hours = 2
        elif complexity_score < 2000:
            complexity = MigrationComplexity.MODERATE
            estimated_hours = 4
        else:
            complexity = MigrationComplexity.COMPLEX
            estimated_hours = 8
        
        return {
            "complexity": complexity,
            "estimated_hours": estimated_hours,
            "complexity_score": complexity_score,
            "factors": {
                "items": total_items,
                "categories": total_categories,
                "modifiers": total_modifiers,
                "custom_fields": has_custom_fields
            }
        }
    
    # Private helper methods
    
    def _generate_cache_key(self, operation: str, *args) -> str:
        """Generate cache key from operation and arguments"""
        key_data = f"{operation}:" + ":".join(str(arg) for arg in args)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def _get_cached_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if available"""
        if not self.cache_service:
            return None
        
        try:
            # Would call actual cache service
            return None  # Placeholder
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
            return None
    
    async def _cache_result(self, key: str, data: Dict[str, Any]) -> None:
        """Cache result for future use"""
        if not self.cache_service:
            return
        
        try:
            # Would call actual cache service
            pass  # Placeholder
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
    
    def _rule_based_analysis(
        self,
        pos_type: str,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """Fallback rule-based analysis when AI is unavailable"""
        
        # Extract basic statistics
        field_mappings = []
        data_quality_issues = []
        risk_factors = []
        
        # Analyze based on POS type
        if pos_type == "toast":
            field_mappings = self._analyze_toast_structure(sample_data)
            if "dataQualityIssues" in sample_data:
                data_quality_issues = [
                    issue["description"] 
                    for issue in sample_data["dataQualityIssues"]
                ]
        elif pos_type == "square":
            field_mappings = self._analyze_square_structure(sample_data)
            if "dataQualityNotes" in sample_data:
                data_quality_issues = [
                    note["issue"] 
                    for note in sample_data["dataQualityNotes"]
                ]
        elif pos_type == "clover":
            field_mappings = self._analyze_clover_structure(sample_data)
        
        # Estimate complexity
        item_count = self._count_items(sample_data)
        if item_count > 1000:
            complexity = MigrationComplexity.COMPLEX
            estimated_hours = 8
            risk_factors.append("Large dataset may require batched processing")
        elif item_count > 200:
            complexity = MigrationComplexity.MODERATE
            estimated_hours = 4
        else:
            complexity = MigrationComplexity.SIMPLE
            estimated_hours = 2
        
        return MigrationPlan(
            field_mappings=field_mappings,
            data_quality_issues=data_quality_issues,
            complexity=complexity,
            estimated_hours=estimated_hours,
            risk_factors=risk_factors,
            recommendations=[
                "Review all field mappings before proceeding",
                "Test with a small sample first",
                "Backup existing data before migration"
            ],
            confidence_score=0.7  # Lower confidence for rule-based
        )
    
    def _analyze_toast_structure(self, data: Dict[str, Any]) -> List[FieldMapping]:
        """Analyze Toast-specific data structure"""
        mappings = []
        
        # Standard Toast mappings
        toast_mappings = {
            "guid": "external_id",
            "name": "name",
            "description": "description",
            "price": "price",
            "visibility": "availability",
            "modifierGroups": "modifier_groups"
        }
        
        for source, target in toast_mappings.items():
            mappings.append(FieldMapping(
                source_field=source,
                target_field=target,
                confidence=0.9,
                transformation=FieldTransformationType.NONE,
                notes="Standard Toast field mapping"
            ))
        
        # Special handling for price (Toast uses cents)
        mappings.append(FieldMapping(
            source_field="price",
            target_field="price",
            confidence=0.95,
            transformation=FieldTransformationType.PARSE_DECIMAL,
            notes="Convert from cents to dollars",
            custom_logic="value / 100"
        ))
        
        return mappings
    
    def _analyze_square_structure(self, data: Dict[str, Any]) -> List[FieldMapping]:
        """Analyze Square-specific data structure"""
        mappings = []
        
        # Square uses nested structure
        square_mappings = {
            "item_data.name": "name",
            "item_data.description": "description",
            "item_variation_data.price_money.amount": "price",
            "category_id": "category_id",
            "modifier_list_info": "modifier_groups"
        }
        
        for source, target in square_mappings.items():
            mappings.append(FieldMapping(
                source_field=source,
                target_field=target,
                confidence=0.85,
                transformation=FieldTransformationType.PARSE_JSON,
                notes="Square nested field extraction"
            ))
        
        return mappings
    
    def _analyze_clover_structure(self, data: Dict[str, Any]) -> List[FieldMapping]:
        """Analyze Clover-specific data structure"""
        # Similar to other POS systems
        return []
    
    def _count_items(self, data: Dict[str, Any]) -> int:
        """Count total items in the data"""
        count = 0
        
        # Toast structure
        if "menus" in data:
            for menu in data.get("menus", []):
                for group in menu.get("groups", []):
                    count += len(group.get("items", []))
        
        # Square structure
        elif "catalog" in data:
            for obj in data.get("catalog", {}).get("objects", []):
                if obj.get("type") == "ITEM":
                    count += 1
        
        return count
    
    def _rule_based_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str]
    ) -> List[MappingSuggestion]:
        """Create rule-based field mappings"""
        
        # Common mapping patterns
        mapping_rules = {
            # Exact matches
            "name": "name",
            "description": "description",
            "price": "price",
            "category": "category_id",
            "sku": "sku",
            
            # Common variations
            "itemname": "name",
            "item_name": "name",
            "productname": "name",
            "itemprice": "price",
            "item_price": "price",
            "cost": "price",
            "amount": "price",
            "categoryname": "category_id",
            "category_name": "category_id",
            "itemcategory": "category_id",
            "item_category": "category_id",
        }
        
        suggestions = []
        mapped_targets = set()
        
        for source in source_fields:
            source_lower = source.lower().replace("_", "").replace("-", "")
            
            # Check exact match
            if source in target_fields:
                suggestions.append(MappingSuggestion(
                    source=source,
                    target=source,
                    confidence=1.0,
                    reasoning="Exact field name match"
                ))
                mapped_targets.add(source)
                continue
            
            # Check mapping rules
            if source_lower in mapping_rules:
                target = mapping_rules[source_lower]
                if target in target_fields and target not in mapped_targets:
                    suggestions.append(MappingSuggestion(
                        source=source,
                        target=target,
                        confidence=0.8,
                        reasoning="Common field pattern match"
                    ))
                    mapped_targets.add(target)
                    continue
            
            # Fuzzy matching
            best_match = None
            best_score = 0.0
            
            for target in target_fields:
                if target in mapped_targets:
                    continue
                
                score = self._calculate_similarity(source_lower, target.lower())
                if score > best_score and score > 0.5:
                    best_match = target
                    best_score = score
            
            if best_match:
                suggestions.append(MappingSuggestion(
                    source=source,
                    target=best_match,
                    confidence=best_score,
                    reasoning=f"Fuzzy match with {best_score:.0%} similarity"
                ))
                mapped_targets.add(best_match)
        
        return suggestions
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity score"""
        # Simple character overlap ratio
        set1 = set(str1)
        set2 = set(str2)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union
    
    # AI-powered methods (would use actual AI provider)
    
    async def _ai_analyze_structure(
        self,
        pos_type: str,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """AI-powered structure analysis"""
        # This would call the actual AI provider
        # For now, return rule-based result
        return self._rule_based_analysis(pos_type, sample_data, target_schema)
    
    async def _ai_suggest_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        context: Optional[Dict[str, Any]]
    ) -> List[MappingSuggestion]:
        """AI-powered mapping suggestions"""
        # This would call the actual AI provider
        # For now, return rule-based result
        return self._rule_based_mappings(source_fields, target_fields)