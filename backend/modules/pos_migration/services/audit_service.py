# backend/modules/pos_migration/services/audit_service.py

"""
Audit service for tracking migration operations and ensuring compliance.
Provides detailed logging and reporting for GDPR/CCPA compliance.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..schemas.migration_schemas import (
    AuditLogEntry,
    ComplianceReport,
    ConsentResponse,
    ConsentStatus,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Handles audit logging and compliance reporting"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logs: Dict[str, List[AuditLogEntry]] = {}
        
    async def log_operation(
        self,
        migration_id: str,
        operation: str,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        details: Dict[str, Any] = None,
        data_categories: List[str] = None,
        compliance_notes: Optional[str] = None
    ):
        """Log a migration operation for audit trail"""
        
        entry = AuditLogEntry(
            migration_id=migration_id,
            operation=operation,
            user_id=user_id,
            agent_name=agent_name,
            details=details or {},
            data_categories=data_categories or [],
            compliance_notes=compliance_notes
        )
        
        # Store in memory for now - would persist to database
        if migration_id not in self.audit_logs:
            self.audit_logs[migration_id] = []
        
        self.audit_logs[migration_id].append(entry)
        
        # Log to system logger as well
        logger.info(
            f"Audit: Migration {migration_id} - {operation} "
            f"by {user_id or agent_name or 'system'}"
        )
    
    async def generate_compliance_report(
        self,
        migration_id: str
    ) -> ComplianceReport:
        """Generate compliance report for migration"""
        
        logs = self.audit_logs.get(migration_id, [])
        
        # Extract data inventory from logs
        data_inventory = {}
        for log in logs:
            for category in log.data_categories:
                if category not in data_inventory:
                    data_inventory[category] = []
                data_inventory[category].append(log.operation)
        
        # Check for consent records
        consent_records = []
        for log in logs:
            if log.operation == "consent_received":
                consent_records.append(
                    ConsentResponse(
                        consent_token=log.details.get("token", ""),
                        status=ConsentStatus.GRANTED,
                        granted_categories=log.data_categories,
                        responded_at=log.timestamp
                    )
                )
        
        # Determine compliance status
        has_personal_data = any(
            cat in ["customer_data", "payment_data", "personal_info"]
            for cat in data_inventory.keys()
        )
        
        gdpr_compliant = not has_personal_data or len(consent_records) > 0
        ccpa_compliant = gdpr_compliant  # Simplified
        
        report = ComplianceReport(
            migration_id=migration_id,
            gdpr_compliant=gdpr_compliant,
            ccpa_compliant=ccpa_compliant,
            consent_records=consent_records,
            data_inventory=data_inventory,
            retention_schedule={
                "transaction_data": 730,  # 2 years
                "customer_data": 365,     # 1 year
                "analytics_data": 180     # 6 months
            },
            deletion_requests=[]
        )
        
        return report
    
    async def get_audit_trail(
        self,
        migration_id: str,
        operation_filter: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AuditLogEntry]:
        """Retrieve audit trail for migration"""
        
        logs = self.audit_logs.get(migration_id, [])
        
        # Apply filters
        if operation_filter:
            logs = [l for l in logs if l.operation == operation_filter]
            
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
            
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]
        
        return sorted(logs, key=lambda x: x.timestamp)
    
    async def record_data_access(
        self,
        migration_id: str,
        data_type: str,
        record_count: int,
        purpose: str,
        accessed_by: str
    ):
        """Record data access for compliance"""
        
        await self.log_operation(
            migration_id=migration_id,
            operation="data_access",
            user_id=accessed_by,
            details={
                "data_type": data_type,
                "record_count": record_count,
                "purpose": purpose
            },
            data_categories=[data_type],
            compliance_notes=f"Accessed {record_count} {data_type} records for {purpose}"
        )
    
    async def record_data_deletion(
        self,
        migration_id: str,
        data_type: str,
        record_ids: List[str],
        reason: str,
        deleted_by: str
    ):
        """Record data deletion for right to be forgotten"""
        
        await self.log_operation(
            migration_id=migration_id,
            operation="data_deletion",
            user_id=deleted_by,
            details={
                "data_type": data_type,
                "record_count": len(record_ids),
                "record_ids": record_ids[:10],  # Sample for audit
                "reason": reason
            },
            data_categories=[data_type],
            compliance_notes=f"Deleted {len(record_ids)} records: {reason}"
        )
    
    def get_migration_summary(self, migration_id: str) -> Dict[str, Any]:
        """Get summary statistics for migration"""
        
        logs = self.audit_logs.get(migration_id, [])
        
        if not logs:
            return {"error": "No audit logs found"}
        
        operations = {}
        for log in logs:
            operations[log.operation] = operations.get(log.operation, 0) + 1
        
        return {
            "migration_id": migration_id,
            "start_time": min(log.timestamp for log in logs),
            "end_time": max(log.timestamp for log in logs),
            "total_operations": len(logs),
            "operations_breakdown": operations,
            "data_categories_accessed": list(set(
                cat for log in logs 
                for cat in log.data_categories
            )),
            "users_involved": list(set(
                log.user_id for log in logs 
                if log.user_id
            ))
        }