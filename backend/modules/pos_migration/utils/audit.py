"""
Audit Trail Utilities for POS Migration

Comprehensive audit logging for compliance and observability.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import traceback

from core.models import AuditLog
from ..models.migration_models import MigrationLog

logger = logging.getLogger(__name__)


async def audit_log(
    db: AsyncSession,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """
    Create an audit log entry.
    
    Args:
        db: Database session
        user_id: ID of user performing action
        action: Action performed (e.g., "migration.create")
        resource_type: Type of resource affected
        resource_id: ID of affected resource
        details: Additional details about the action
        ip_address: Client IP address
        user_agent: Client user agent
    
    Returns:
        Created audit log entry
    """
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )
        
        db.add(audit_entry)
        await db.commit()
        
        # Also log to application logger
        logger.info(
            f"AUDIT: User {user_id} performed {action} on {resource_type}:{resource_id}",
            extra={
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details
            }
        )
        
        return audit_entry
    
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't fail the main operation if audit logging fails
        return None


async def log_migration_event(
    db: AsyncSession,
    job_id: str,
    log_level: str,
    message: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    source_data: Optional[Dict[str, Any]] = None,
    error_info: Optional[Dict[str, Any]] = None,
    performance_metrics: Optional[Dict[str, Any]] = None
) -> MigrationLog:
    """
    Create a detailed migration log entry.
    
    Args:
        db: Database session
        job_id: Migration job ID
        log_level: Log level (INFO, WARNING, ERROR, DEBUG)
        message: Log message
        entity_type: Type of entity being processed
        entity_id: ID of entity in source system
        action: Action being performed
        source_data: Original data from source
        error_info: Error details if applicable
        performance_metrics: Performance metrics
    
    Returns:
        Created migration log entry
    """
    try:
        log_entry = MigrationLog(
            migration_job_id=job_id,
            log_level=log_level,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            source_data=source_data,
            created_at=datetime.utcnow()
        )
        
        # Add error information if present
        if error_info:
            log_entry.error_type = error_info.get("type")
            log_entry.error_message = error_info.get("message")
            log_entry.stack_trace = error_info.get("stack_trace")
        
        # Add performance metrics if present
        if performance_metrics:
            log_entry.duration_ms = performance_metrics.get("duration_ms")
            log_entry.memory_usage_mb = performance_metrics.get("memory_mb")
        
        db.add(log_entry)
        await db.commit()
        
        return log_entry
    
    except Exception as e:
        logger.error(f"Failed to create migration log: {e}")
        return None


class MigrationAuditTrail:
    """
    Comprehensive audit trail for migration operations.
    """
    
    def __init__(self, db: AsyncSession, job_id: str):
        self.db = db
        self.job_id = job_id
        self.start_time = datetime.utcnow()
        self.events = []
    
    async def log_start(self, user_id: int, config: Dict[str, Any]):
        """Log migration start."""
        await audit_log(
            self.db,
            user_id=user_id,
            action="migration.start",
            resource_type="migration_job",
            resource_id=self.job_id,
            details={
                "config": config,
                "start_time": self.start_time.isoformat()
            }
        )
    
    async def log_entity_processing(
        self,
        entity_type: str,
        total_records: int,
        batch_size: int
    ):
        """Log start of entity processing."""
        await log_migration_event(
            self.db,
            job_id=self.job_id,
            log_level="INFO",
            message=f"Starting processing of {entity_type}",
            entity_type=entity_type,
            action="process_start",
            source_data={
                "total_records": total_records,
                "batch_size": batch_size
            }
        )
    
    async def log_batch_complete(
        self,
        entity_type: str,
        batch_num: int,
        succeeded: int,
        failed: int,
        duration_ms: int
    ):
        """Log batch processing completion."""
        await log_migration_event(
            self.db,
            job_id=self.job_id,
            log_level="INFO",
            message=f"Batch {batch_num} completed",
            entity_type=entity_type,
            action="batch_complete",
            source_data={
                "batch_num": batch_num,
                "succeeded": succeeded,
                "failed": failed
            },
            performance_metrics={
                "duration_ms": duration_ms
            }
        )
    
    async def log_validation_failure(
        self,
        entity_type: str,
        entity_id: str,
        validation_errors: List[Dict[str, Any]]
    ):
        """Log validation failure."""
        await log_migration_event(
            self.db,
            job_id=self.job_id,
            log_level="WARNING",
            message=f"Validation failed for {entity_type}:{entity_id}",
            entity_type=entity_type,
            entity_id=entity_id,
            action="validate",
            error_info={
                "type": "ValidationError",
                "message": "Data validation failed",
                "validation_errors": validation_errors
            }
        )
    
    async def log_error(
        self,
        entity_type: Optional[str],
        entity_id: Optional[str],
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log error with full context."""
        await log_migration_event(
            self.db,
            job_id=self.job_id,
            log_level="ERROR",
            message=str(error),
            entity_type=entity_type,
            entity_id=entity_id,
            action="error",
            source_data=context,
            error_info={
                "type": type(error).__name__,
                "message": str(error),
                "stack_trace": traceback.format_exc()
            }
        )
    
    async def log_completion(
        self,
        user_id: int,
        status: str,
        statistics: Dict[str, Any]
    ):
        """Log migration completion."""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        await audit_log(
            self.db,
            user_id=user_id,
            action="migration.complete",
            resource_type="migration_job",
            resource_id=self.job_id,
            details={
                "status": status,
                "duration_seconds": duration,
                "statistics": statistics,
                "end_time": end_time.isoformat()
            }
        )
    
    async def get_audit_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive audit report for the migration.
        
        Returns:
            Audit report with all events and statistics
        """
        # Get all logs for this migration
        result = await self.db.execute(
            select(MigrationLog).where(
                MigrationLog.migration_job_id == self.job_id
            ).order_by(MigrationLog.created_at)
        )
        logs = result.scalars().all()
        
        # Analyze logs
        error_count = sum(1 for log in logs if log.log_level == "ERROR")
        warning_count = sum(1 for log in logs if log.log_level == "WARNING")
        
        # Group by entity type
        entity_stats = {}
        for log in logs:
            if log.entity_type:
                if log.entity_type not in entity_stats:
                    entity_stats[log.entity_type] = {
                        "processed": 0,
                        "errors": 0,
                        "warnings": 0
                    }
                
                entity_stats[log.entity_type]["processed"] += 1
                if log.log_level == "ERROR":
                    entity_stats[log.entity_type]["errors"] += 1
                elif log.log_level == "WARNING":
                    entity_stats[log.entity_type]["warnings"] += 1
        
        return {
            "job_id": self.job_id,
            "start_time": self.start_time.isoformat(),
            "total_logs": len(logs),
            "error_count": error_count,
            "warning_count": warning_count,
            "entity_statistics": entity_stats,
            "logs": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "level": log.log_level,
                    "message": log.message,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id
                }
                for log in logs[:100]  # Limit to recent 100 logs
            ]
        }


class ComplianceLogger:
    """
    Specialized logger for compliance-related events.
    """
    
    @staticmethod
    async def log_data_access(
        db: AsyncSession,
        user_id: int,
        data_type: str,
        operation: str,
        record_count: int,
        purpose: str
    ):
        """Log data access for compliance."""
        await audit_log(
            db,
            user_id=user_id,
            action=f"data_access.{operation}",
            resource_type=data_type,
            resource_id="bulk",
            details={
                "record_count": record_count,
                "purpose": purpose,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    async def log_pii_processing(
        db: AsyncSession,
        user_id: int,
        entity_type: str,
        pii_fields: List[str],
        processing_type: str,
        justification: str
    ):
        """Log PII data processing."""
        await audit_log(
            db,
            user_id=user_id,
            action="pii_processing",
            resource_type=entity_type,
            resource_id="pii",
            details={
                "pii_fields": pii_fields,
                "processing_type": processing_type,
                "justification": justification,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    async def log_data_export(
        db: AsyncSession,
        user_id: int,
        export_format: str,
        record_count: int,
        destination: str,
        filters_applied: Dict[str, Any]
    ):
        """Log data export for compliance."""
        await audit_log(
            db,
            user_id=user_id,
            action="data_export",
            resource_type="migration_data",
            resource_id="export",
            details={
                "format": export_format,
                "record_count": record_count,
                "destination": destination,
                "filters": filters_applied,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    async def log_retention_action(
        db: AsyncSession,
        user_id: int,
        action_type: str,  # "delete", "archive", "retain"
        data_age_days: int,
        record_count: int,
        policy_name: str
    ):
        """Log data retention actions."""
        await audit_log(
            db,
            user_id=user_id,
            action=f"retention.{action_type}",
            resource_type="migration_data",
            resource_id="retention",
            details={
                "data_age_days": data_age_days,
                "record_count": record_count,
                "policy_name": policy_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )