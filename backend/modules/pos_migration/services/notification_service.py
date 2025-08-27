# backend/modules/pos_migration/services/notification_service.py

"""
Notification service for migration events.
Handles email notifications, WebSocket events, and progress updates.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..schemas.migration_schemas import (
    MigrationPlan,
    ValidationReport,
    MigrationProgressEvent,
)
from modules.auth.models import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles notifications for migration events"""
    
    def __init__(self, db: Session):
        self.db = db
        
    async def send_migration_started(
        self,
        migration_id: str,
        tenant_id: str,
        user_id: str
    ):
        """Send notification that migration has started"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # This would integrate with email service
        logger.info(
            f"Migration {migration_id} started for tenant {tenant_id} "
            f"by user {user.email}"
        )
        
        # Would send actual email here
        await self._send_email(
            to=user.email,
            subject="POS Data Migration Started",
            body=f"""
            Your POS data migration has begun!
            
            Migration ID: {migration_id}
            
            We'll keep you updated on the progress. You can monitor the 
            migration status in real-time through your dashboard.
            
            This process typically takes 2-4 hours depending on your data volume.
            """
        )
    
    async def send_migration_completed(
        self,
        migration_id: str,
        tenant_id: str,
        user_id: str,
        summary: str
    ):
        """Send notification that migration completed successfully"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        await self._send_email(
            to=user.email,
            subject="POS Data Migration Completed Successfully!",
            body=summary
        )
    
    async def send_migration_failed(
        self,
        migration_id: str,
        error: str
    ):
        """Send notification that migration failed"""
        
        # Would look up user/tenant from migration record
        logger.error(f"Migration {migration_id} failed: {error}")
        
        # Send email to admin and user
        await self._send_email(
            to="admin@auraconnect.ai",
            subject=f"Migration Failed: {migration_id}",
            body=f"""
            Migration {migration_id} has failed with error:
            
            {error}
            
            Please investigate and contact the customer if needed.
            """
        )
    
    async def send_review_required(
        self,
        migration_id: str,
        validation_report: ValidationReport,
        mapping_plan: MigrationPlan
    ):
        """Send notification that manual review is required"""
        
        # Format validation issues
        issues_summary = "\n".join([
            f"- {anomaly.description} ({anomaly.severity.value} severity)"
            for anomaly in validation_report.anomalies[:5]
        ])
        
        if len(validation_report.anomalies) > 5:
            issues_summary += f"\n... and {len(validation_report.anomalies) - 5} more issues"
        
        await self._send_email(
            to="admin@auraconnect.ai",
            subject=f"Manual Review Required: Migration {migration_id}",
            body=f"""
            Migration {migration_id} requires manual review before proceeding.
            
            Validation Issues Found:
            {issues_summary}
            
            Complexity: {mapping_plan.complexity.value}
            Confidence Score: {mapping_plan.confidence_score}
            
            Please review the migration in the admin dashboard and approve or modify 
            the field mappings before continuing.
            """
        )
    
    async def send_migration_cancelled(
        self,
        migration_id: str,
        reason: str
    ):
        """Send notification that migration was cancelled"""
        
        logger.info(f"Migration {migration_id} cancelled: {reason}")
        
        await self._send_email(
            to="admin@auraconnect.ai",
            subject=f"Migration Cancelled: {migration_id}",
            body=f"""
            Migration {migration_id} has been cancelled.
            
            Reason: {reason}
            
            Any imported data has been rolled back.
            """
        )
    
    async def emit_progress_event(
        self,
        event: MigrationProgressEvent
    ):
        """Emit WebSocket event for real-time updates"""
        
        # This would integrate with WebSocket manager
        # For now, just log
        logger.debug(
            f"Progress event: {event.type} for migration {event.migration_id}"
        )
    
    async def _send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ):
        """Send email (placeholder for actual implementation)"""
        
        # This would integrate with email service (SendGrid, AWS SES, etc.)
        logger.info(f"Email to {to}: {subject}")
        
        # In production, this would:
        # 1. Use email templates
        # 2. Queue emails for delivery
        # 3. Track delivery status
        # 4. Handle unsubscribes
    
    async def send_consent_request(
        self,
        customer_email: str,
        consent_token: str,
        data_categories: list[str]
    ):
        """Send consent request email to customer"""
        
        categories_list = "\n".join([f"- {cat}" for cat in data_categories])
        
        await self._send_email(
            to=customer_email,
            subject="Permission to Import Your Restaurant Data",
            body=f"""
            We're ready to import your restaurant data to AuraConnect!
            
            To comply with data protection regulations, we need your consent to 
            import the following data categories:
            
            {categories_list}
            
            Please click the link below to review and approve:
            https://app.auraconnect.ai/consent/{consent_token}
            
            This link will expire in 48 hours.
            
            Your data privacy is important to us. You can withdraw consent at any 
            time through your account settings.
            """
        )
    
    def format_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Format duration in human-readable format"""
        
        duration = end_time - start_time
        hours = duration.total_seconds() / 3600
        
        if hours < 1:
            minutes = duration.total_seconds() / 60
            return f"{int(minutes)} minutes"
        else:
            return f"{hours:.1f} hours"