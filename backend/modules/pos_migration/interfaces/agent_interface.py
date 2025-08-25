# backend/modules/pos_migration/interfaces/agent_interface.py

"""
Abstract base interfaces for migration agents.
Ensures consistent implementation across all AI agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..schemas.migration_schemas import (
    MigrationPlan,
    ValidationReport,
    ComplianceReport,
    TokenUsage,
)


class BaseMigrationAgent(ABC):
    """Base interface for all migration agents"""
    
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the agent's name for logging and tracking"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the agent with configuration"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health and dependencies"""
        pass
    
    @abstractmethod
    async def get_token_usage(self) -> TokenUsage:
        """Get current token usage statistics"""
        pass


class IMigrationCoach(BaseMigrationAgent):
    """Interface for migration coaching agent"""
    
    @abstractmethod
    async def analyze_pos_structure(
        self,
        pos_type: str,
        sample_data: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> MigrationPlan:
        """Analyze POS data and create migration plan"""
        pass
    
    @abstractmethod
    async def suggest_field_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Suggest intelligent field mappings"""
        pass
    
    @abstractmethod
    async def estimate_complexity(
        self,
        data_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate migration complexity and timeline"""
        pass


class ISyncValidator(BaseMigrationAgent):
    """Interface for data validation agent"""
    
    @abstractmethod
    async def validate_pricing_data(
        self,
        items: List[Dict[str, Any]],
        pos_type: str
    ) -> ValidationReport:
        """Validate pricing data for anomalies"""
        pass
    
    @abstractmethod
    async def check_data_completeness(
        self,
        data: Dict[str, Any],
        required_fields: List[str]
    ) -> ValidationReport:
        """Check if all required fields are present"""
        pass
    
    @abstractmethod
    async def detect_duplicates(
        self,
        items: List[Dict[str, Any]],
        key_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Detect duplicate entries"""
        pass
    
    @abstractmethod
    async def validate_relationships(
        self,
        data: Dict[str, Any],
        relationship_rules: Dict[str, Any]
    ) -> ValidationReport:
        """Validate data relationships and foreign keys"""
        pass


class IComplianceAuditor(BaseMigrationAgent):
    """Interface for compliance auditing agent"""
    
    @abstractmethod
    async def verify_customer_consent(
        self,
        customers: List[Dict[str, Any]],
        required_permissions: List[str]
    ) -> ComplianceReport:
        """Verify customer consent for data migration"""
        pass
    
    @abstractmethod
    async def generate_audit_trail(
        self,
        migration_id: str,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive audit trail"""
        pass
    
    @abstractmethod
    async def check_data_retention_compliance(
        self,
        data_categories: List[str],
        retention_policies: Dict[str, int]
    ) -> ComplianceReport:
        """Check data retention compliance"""
        pass
    
    @abstractmethod
    async def generate_deletion_report(
        self,
        migration_id: str,
        deleted_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate report for deleted records"""
        pass


class IFallbackHandler(ABC):
    """Interface for handling AI service failures"""
    
    @abstractmethod
    async def get_cached_suggestion(
        self,
        operation: str,
        input_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached AI suggestion"""
        pass
    
    @abstractmethod
    async def store_suggestion(
        self,
        operation: str,
        input_hash: str,
        suggestion: Dict[str, Any],
        ttl: int = 86400
    ) -> None:
        """Cache AI suggestion for future use"""
        pass
    
    @abstractmethod
    async def get_rule_based_mapping(
        self,
        source_field: str,
        target_fields: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get rule-based mapping when AI unavailable"""
        pass
    
    @abstractmethod
    async def get_offline_validation(
        self,
        data: Dict[str, Any],
        validation_type: str
    ) -> Dict[str, Any]:
        """Perform offline validation without AI"""
        pass