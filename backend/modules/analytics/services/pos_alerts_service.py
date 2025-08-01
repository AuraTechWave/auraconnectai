# backend/modules/analytics/services/pos_alerts_service.py

"""
Service for POS analytics alerts.

Handles alert management and notifications.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import logging

from modules.analytics.models.pos_analytics_models import POSAnalyticsAlert
from modules.analytics.schemas.pos_analytics_schemas import (
    POSAlert, AlertSeverity
)
from .pos.base_service import POSAnalyticsBaseService

logger = logging.getLogger(__name__)


class POSAlertsService(POSAnalyticsBaseService):
    """Service for POS analytics alerts"""
    
    async def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[POSAlert], int]:
        """Get active alerts with pagination"""
        
        # Base query with eager loading
        query = self.db.query(POSAnalyticsAlert).options(
            joinedload(POSAnalyticsAlert.provider),
            joinedload(POSAnalyticsAlert.acknowledger)
        ).filter(
            POSAnalyticsAlert.is_active == True
        )
        
        # Apply filters
        if severity:
            query = query.filter(POSAnalyticsAlert.severity == severity.value)
        
        if provider_id:
            query = query.filter(POSAnalyticsAlert.provider_id == provider_id)
        
        if terminal_id:
            query = query.filter(POSAnalyticsAlert.terminal_id == terminal_id)
        
        # Get total count
        total_count = query.count()
        
        # Apply ordering and pagination
        alerts = query.order_by(
            POSAnalyticsAlert.severity.desc(),
            POSAnalyticsAlert.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        # Convert to schema
        alert_list = [
            POSAlert(
                alert_id=str(alert.alert_id),
                alert_type=alert.alert_type,
                severity=AlertSeverity(alert.severity),
                provider_id=alert.provider_id,
                provider_name=alert.provider.provider_name if alert.provider else None,
                terminal_id=alert.terminal_id,
                title=alert.title,
                description=alert.description,
                metric_value=alert.metric_value,
                threshold_value=alert.threshold_value,
                is_active=alert.is_active,
                acknowledged=alert.acknowledged,
                acknowledged_by=alert.acknowledger.name if alert.acknowledger else None,
                acknowledged_at=alert.acknowledged_at,
                created_at=alert.created_at,
                resolved_at=alert.resolved_at,
                context_data=alert.context_data or {}
            )
            for alert in alerts
        ]
        
        return alert_list, total_count
    
    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: int,
        notes: Optional[str] = None
    ) -> None:
        """Acknowledge an alert"""
        
        try:
            alert_uuid = UUID(alert_id)
        except ValueError:
            raise KeyError("Invalid alert ID format")
        
        alert = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.alert_id == alert_uuid,
            POSAnalyticsAlert.is_active == True,
            POSAnalyticsAlert.acknowledged == False
        ).first()
        
        if not alert:
            raise KeyError("Alert not found or already acknowledged")
        
        # Update alert
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        
        if notes:
            alert.context_data = alert.context_data or {}
            alert.context_data["acknowledgment_notes"] = notes
        
        self.db.commit()
        
        logger.info(f"Alert {alert_id} acknowledged by user {acknowledged_by}")
    
    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: int,
        resolution_notes: str
    ) -> None:
        """Resolve an alert"""
        
        try:
            alert_uuid = UUID(alert_id)
        except ValueError:
            raise KeyError("Invalid alert ID format")
        
        alert = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.alert_id == alert_uuid,
            POSAnalyticsAlert.is_active == True
        ).first()
        
        if not alert:
            raise KeyError("Alert not found")
        
        # Update alert
        alert.is_active = False
        alert.resolved_at = datetime.utcnow()
        
        # Add resolution info to context
        alert.context_data = alert.context_data or {}
        alert.context_data["resolved_by"] = resolved_by
        alert.context_data["resolution_notes"] = resolution_notes
        
        self.db.commit()
        
        logger.info(f"Alert {alert_id} resolved by user {resolved_by}")
    
    async def get_alert_history(
        self,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        days_back: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical alerts"""
        
        since_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = self.db.query(POSAnalyticsAlert).options(
            joinedload(POSAnalyticsAlert.provider),
            joinedload(POSAnalyticsAlert.acknowledger)
        ).filter(
            POSAnalyticsAlert.created_at >= since_date
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsAlert.provider_id == provider_id)
        
        if terminal_id:
            query = query.filter(POSAnalyticsAlert.terminal_id == terminal_id)
        
        alerts = query.order_by(
            POSAnalyticsAlert.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "alert_id": str(alert.alert_id),
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "provider_id": alert.provider_id,
                "provider_name": alert.provider.provider_name if alert.provider else None,
                "terminal_id": alert.terminal_id,
                "title": alert.title,
                "description": alert.description,
                "is_active": alert.is_active,
                "acknowledged": alert.acknowledged,
                "acknowledged_by": alert.acknowledger.name if alert.acknowledger else None,
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "created_at": alert.created_at.isoformat(),
                "duration_minutes": self._calculate_alert_duration(alert)
            }
            for alert in alerts
        ]
    
    def _calculate_alert_duration(self, alert: POSAnalyticsAlert) -> Optional[int]:
        """Calculate alert duration in minutes"""
        if alert.resolved_at:
            duration = alert.resolved_at - alert.created_at
            return int(duration.total_seconds() / 60)
        elif not alert.is_active:
            # Alert is inactive but no resolved_at (shouldn't happen)
            return None
        else:
            # Alert is still active
            duration = datetime.utcnow() - alert.created_at
            return int(duration.total_seconds() / 60)
    
    async def create_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        title: str,
        description: str,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new alert"""
        
        alert = POSAnalyticsAlert(
            alert_type=alert_type,
            severity=severity.value,
            provider_id=provider_id,
            terminal_id=terminal_id,
            title=title,
            description=description,
            metric_value=metric_value,
            threshold_value=threshold_value,
            is_active=True,
            acknowledged=False,
            context_data=context_data or {},
            notification_sent=False
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        logger.info(
            f"Created alert {alert.alert_id}: {alert_type} - {severity.value}"
        )
        
        # TODO: Trigger notification service
        
        return str(alert.alert_id)
    
    async def check_duplicate_alert(
        self,
        alert_type: str,
        provider_id: Optional[int],
        terminal_id: Optional[str],
        hours_back: int = 24
    ) -> bool:
        """Check if similar alert exists in recent time"""
        
        since_date = datetime.utcnow() - timedelta(hours=hours_back)
        
        query = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.alert_type == alert_type,
            POSAnalyticsAlert.is_active == True,
            POSAnalyticsAlert.created_at >= since_date
        )
        
        if provider_id:
            query = query.filter(POSAnalyticsAlert.provider_id == provider_id)
        
        if terminal_id:
            query = query.filter(POSAnalyticsAlert.terminal_id == terminal_id)
        
        return query.count() > 0