# backend/modules/analytics/services/pos_analytics_service.py

"""
Service layer for POS analytics operations.

Handles data aggregation, calculations, and business logic
for POS analytics dashboard.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, case, distinct
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
import logging
import json
import uuid
from collections import defaultdict

from backend.modules.orders.models.external_pos_models import (
    ExternalPOSProvider, ExternalPOSWebhookEvent, ExternalPOSPaymentUpdate
)
from backend.modules.orders.models.sync_models import OrderSyncStatus, SyncStatus
from ..models.pos_analytics_models import (
    POSAnalyticsSnapshot, POSProviderPerformance, POSTerminalHealth, POSAnalyticsAlert
)
from ..schemas.pos_analytics_schemas import (
    POSDashboardResponse, POSProviderSummary, POSTerminalSummary,
    POSTransactionTrend, POSSyncMetrics, POSWebhookMetrics,
    POSErrorAnalysis, POSPerformanceMetrics, POSAlert,
    POSProviderDetailsResponse, POSTerminalDetailsResponse,
    POSComparisonResponse, POSHealthStatus, AlertSeverity
)

logger = logging.getLogger(__name__)


class POSAnalyticsService:
    """Service for POS analytics operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_dashboard_data(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
        include_offline: bool = True
    ) -> POSDashboardResponse:
        """Get comprehensive dashboard data"""
        
        # Get provider summaries
        providers = self._get_provider_summaries(
            start_date, end_date, provider_ids, include_offline
        )
        
        # Calculate totals
        total_providers = len(providers)
        active_providers = sum(1 for p in providers if p.is_active)
        total_terminals = sum(p.total_terminals for p in providers)
        online_terminals = sum(p.active_terminals for p in providers)
        
        # Aggregate transaction metrics
        total_transactions = sum(p.total_transactions for p in providers)
        successful_transactions = sum(p.successful_transactions for p in providers)
        total_transaction_value = sum(p.total_transaction_value for p in providers)
        
        transaction_success_rate = (
            (successful_transactions / total_transactions * 100) 
            if total_transactions > 0 else 0.0
        )
        
        average_transaction_value = (
            total_transaction_value / total_transactions
            if total_transactions > 0 else Decimal("0.00")
        )
        
        # Get terminal health breakdown
        terminal_health = self._get_terminal_health_breakdown(provider_ids, terminal_ids)
        
        # Get transaction trends
        transaction_trends = self._get_transaction_trends(
            start_date, end_date, provider_ids, terminal_ids, granularity="hourly"
        )
        
        # Get active alerts
        active_alerts = self._get_active_alerts_list(provider_ids, terminal_ids, limit=20)
        
        # Calculate overall performance metrics
        overall_uptime = self._calculate_overall_uptime(provider_ids, start_date, end_date)
        avg_sync_time = self._calculate_average_sync_time(provider_ids, start_date, end_date)
        avg_webhook_time = self._calculate_average_webhook_time(provider_ids, start_date, end_date)
        
        return POSDashboardResponse(
            total_providers=total_providers,
            active_providers=active_providers,
            total_terminals=total_terminals,
            online_terminals=online_terminals,
            total_transactions=total_transactions,
            successful_transactions=successful_transactions,
            transaction_success_rate=transaction_success_rate,
            total_transaction_value=total_transaction_value,
            average_transaction_value=average_transaction_value,
            overall_uptime=overall_uptime,
            average_sync_time_ms=avg_sync_time,
            average_webhook_time_ms=avg_webhook_time,
            providers=providers,
            healthy_terminals=terminal_health["healthy"],
            degraded_terminals=terminal_health["degraded"],
            critical_terminals=terminal_health["critical"],
            offline_terminals=terminal_health["offline"],
            transaction_trends=transaction_trends,
            active_alerts=active_alerts,
            generated_at=datetime.utcnow(),
            time_range=f"{start_date.isoformat()} to {end_date.isoformat()}"
        )
    
    def _get_provider_summaries(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        include_offline: bool = True
    ) -> List[POSProviderSummary]:
        """Get summary metrics for each provider"""
        
        # Base query for providers
        query = self.db.query(ExternalPOSProvider)
        
        if provider_ids:
            query = query.filter(ExternalPOSProvider.id.in_(provider_ids))
        
        if not include_offline:
            query = query.filter(ExternalPOSProvider.is_active == True)
        
        providers = query.all()
        summaries = []
        
        for provider in providers:
            # Get aggregated metrics from snapshots
            snapshot_data = self._get_provider_snapshot_data(
                provider.id, start_date, end_date
            )
            
            # Get terminal counts
            terminal_stats = self._get_provider_terminal_stats(provider.id)
            
            # Get sync metrics
            sync_metrics = self._get_provider_sync_metrics(
                provider.id, start_date, end_date
            )
            
            # Get webhook metrics
            webhook_metrics = self._get_provider_webhook_metrics(
                provider.id, start_date, end_date
            )
            
            # Calculate health status
            health_status = self._calculate_provider_health_status(
                provider.id, snapshot_data, terminal_stats
            )
            
            # Count active alerts
            active_alerts = self.db.query(POSAnalyticsAlert).filter(
                POSAnalyticsAlert.provider_id == provider.id,
                POSAnalyticsAlert.is_active == True
            ).count()
            
            summaries.append(POSProviderSummary(
                provider_id=provider.id,
                provider_name=provider.provider_name,
                provider_code=provider.provider_code,
                is_active=provider.is_active,
                total_terminals=terminal_stats["total"],
                active_terminals=terminal_stats["active"],
                offline_terminals=terminal_stats["offline"],
                total_transactions=snapshot_data["total_transactions"],
                successful_transactions=snapshot_data["successful_transactions"],
                failed_transactions=snapshot_data["failed_transactions"],
                transaction_success_rate=snapshot_data["transaction_success_rate"],
                total_transaction_value=Decimal(str(snapshot_data["total_value"])),
                total_syncs=sync_metrics["total"],
                sync_success_rate=sync_metrics["success_rate"],
                average_sync_time_ms=sync_metrics["avg_time_ms"],
                total_webhooks=webhook_metrics["total"],
                webhook_success_rate=webhook_metrics["success_rate"],
                overall_health_status=health_status,
                uptime_percentage=snapshot_data["uptime_percentage"],
                active_alerts=active_alerts
            ))
        
        return summaries
    
    def _get_provider_snapshot_data(
        self,
        provider_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get aggregated snapshot data for a provider"""
        
        result = self.db.query(
            func.sum(POSAnalyticsSnapshot.total_transactions).label("total_transactions"),
            func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful_transactions"),
            func.sum(POSAnalyticsSnapshot.failed_transactions).label("failed_transactions"),
            func.sum(POSAnalyticsSnapshot.total_transaction_value).label("total_value"),
            func.avg(POSAnalyticsSnapshot.uptime_percentage).label("uptime_percentage")
        ).filter(
            POSAnalyticsSnapshot.provider_id == provider_id,
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        ).first()
        
        total_tx = result.total_transactions or 0
        success_tx = result.successful_transactions or 0
        
        return {
            "total_transactions": total_tx,
            "successful_transactions": success_tx,
            "failed_transactions": result.failed_transactions or 0,
            "total_value": result.total_value or 0,
            "transaction_success_rate": (success_tx / total_tx * 100) if total_tx > 0 else 0.0,
            "uptime_percentage": result.uptime_percentage or 100.0
        }
    
    def _get_provider_terminal_stats(self, provider_id: int) -> Dict[str, int]:
        """Get terminal statistics for a provider"""
        
        terminals = self.db.query(POSTerminalHealth).filter(
            POSTerminalHealth.provider_id == provider_id
        ).all()
        
        total = len(terminals)
        active = sum(1 for t in terminals if t.is_online)
        offline = total - active
        
        return {
            "total": total,
            "active": active,
            "offline": offline
        }
    
    def _get_provider_sync_metrics(
        self,
        provider_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get sync metrics for a provider"""
        
        # Get from snapshots
        result = self.db.query(
            func.sum(POSAnalyticsSnapshot.total_syncs).label("total"),
            func.sum(POSAnalyticsSnapshot.successful_syncs).label("successful"),
            func.avg(POSAnalyticsSnapshot.average_sync_time_ms).label("avg_time")
        ).filter(
            POSAnalyticsSnapshot.provider_id == provider_id,
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        ).first()
        
        total = result.total or 0
        successful = result.successful or 0
        
        return {
            "total": total,
            "successful": successful,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "avg_time_ms": result.avg_time or 0.0
        }
    
    def _get_provider_webhook_metrics(
        self,
        provider_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get webhook metrics for a provider"""
        
        # Get from snapshots
        result = self.db.query(
            func.sum(POSAnalyticsSnapshot.total_webhooks).label("total"),
            func.sum(POSAnalyticsSnapshot.successful_webhooks).label("successful"),
            func.avg(POSAnalyticsSnapshot.average_webhook_processing_time_ms).label("avg_time")
        ).filter(
            POSAnalyticsSnapshot.provider_id == provider_id,
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        ).first()
        
        total = result.total or 0
        successful = result.successful or 0
        
        return {
            "total": total,
            "successful": successful,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "avg_time_ms": result.avg_time or 0.0
        }
    
    def _calculate_provider_health_status(
        self,
        provider_id: int,
        snapshot_data: Dict[str, Any],
        terminal_stats: Dict[str, int]
    ) -> POSHealthStatus:
        """Calculate overall health status for a provider"""
        
        # Check critical conditions
        if terminal_stats["active"] == 0 and terminal_stats["total"] > 0:
            return POSHealthStatus.OFFLINE
        
        offline_percentage = (
            (terminal_stats["offline"] / terminal_stats["total"] * 100)
            if terminal_stats["total"] > 0 else 0
        )
        
        if offline_percentage > 50:
            return POSHealthStatus.CRITICAL
        
        # Check performance metrics
        success_rate = snapshot_data["transaction_success_rate"]
        uptime = snapshot_data["uptime_percentage"]
        
        if success_rate < 90 or uptime < 95 or offline_percentage > 20:
            return POSHealthStatus.DEGRADED
        
        return POSHealthStatus.HEALTHY
    
    def _get_terminal_health_breakdown(
        self,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Get breakdown of terminal health statuses"""
        
        query = self.db.query(
            POSTerminalHealth.health_status,
            func.count(POSTerminalHealth.id).label("count")
        )
        
        if provider_ids:
            query = query.filter(POSTerminalHealth.provider_id.in_(provider_ids))
        
        if terminal_ids:
            query = query.filter(POSTerminalHealth.terminal_id.in_(terminal_ids))
        
        results = query.group_by(POSTerminalHealth.health_status).all()
        
        breakdown = {
            "healthy": 0,
            "degraded": 0,
            "critical": 0,
            "offline": 0
        }
        
        for status, count in results:
            breakdown[status] = count
        
        return breakdown
    
    def _get_transaction_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
        granularity: str = "hourly"
    ) -> List[POSTransactionTrend]:
        """Get transaction trend data"""
        
        # Query snapshots for trend data
        query = self.db.query(
            POSAnalyticsSnapshot.snapshot_date,
            POSAnalyticsSnapshot.snapshot_hour,
            func.sum(POSAnalyticsSnapshot.total_transactions).label("count"),
            func.sum(POSAnalyticsSnapshot.total_transaction_value).label("value"),
            func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful")
        )
        
        query = query.filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))
        
        if terminal_ids:
            query = query.filter(POSAnalyticsSnapshot.terminal_id.in_(terminal_ids))
        
        if granularity == "hourly":
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date,
                POSAnalyticsSnapshot.snapshot_hour
            )
        else:
            query = query.group_by(
                POSAnalyticsSnapshot.snapshot_date
            ).order_by(
                POSAnalyticsSnapshot.snapshot_date
            )
        
        results = query.all()
        
        trends = []
        for row in results:
            if granularity == "hourly":
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time()) + timedelta(hours=row.snapshot_hour)
            else:
                timestamp = datetime.combine(row.snapshot_date, datetime.min.time())
            
            count = row.count or 0
            successful = row.successful or 0
            value = Decimal(str(row.value or 0))
            
            trends.append(POSTransactionTrend(
                timestamp=timestamp,
                transaction_count=count,
                transaction_value=value,
                success_rate=(successful / count * 100) if count > 0 else 0.0,
                average_value=value / count if count > 0 else Decimal("0.00")
            ))
        
        return trends
    
    def _get_active_alerts_list(
        self,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[POSAlert]:
        """Get list of active alerts"""
        
        query = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.is_active == True
        )
        
        if provider_ids:
            query = query.filter(POSAnalyticsAlert.provider_id.in_(provider_ids))
        
        if terminal_ids:
            query = query.filter(POSAnalyticsAlert.terminal_id.in_(terminal_ids))
        
        query = query.order_by(
            POSAnalyticsAlert.severity.desc(),
            POSAnalyticsAlert.created_at.desc()
        ).limit(limit)
        
        alerts = query.all()
        
        return [
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
    
    def _calculate_overall_uptime(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate overall uptime percentage"""
        
        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.uptime_percentage).label("avg_uptime")
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))
        
        result = query.first()
        return result.avg_uptime or 100.0
    
    def _calculate_average_sync_time(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate average sync time in milliseconds"""
        
        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.average_sync_time_ms).label("avg_time")
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))
        
        result = query.first()
        return result.avg_time or 0.0
    
    def _calculate_average_webhook_time(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate average webhook processing time in milliseconds"""
        
        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.average_webhook_processing_time_ms).label("avg_time")
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date()
        )
        
        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))
        
        result = query.first()
        return result.avg_time or 0.0
    
    def validate_provider_exists(self, provider_id: int) -> bool:
        """Check if provider exists"""
        return self.db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.id == provider_id
        ).count() > 0
    
    def validate_terminal_exists(self, terminal_id: str) -> bool:
        """Check if terminal exists"""
        return self.db.query(POSTerminalHealth).filter(
            POSTerminalHealth.terminal_id == terminal_id
        ).count() > 0
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get active alerts with filters"""
        
        query = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.is_active == True
        )
        
        if severity:
            query = query.filter(POSAnalyticsAlert.severity == severity.value)
        
        if provider_id:
            query = query.filter(POSAnalyticsAlert.provider_id == provider_id)
        
        if terminal_id:
            query = query.filter(POSAnalyticsAlert.terminal_id == terminal_id)
        
        alerts = query.order_by(
            POSAnalyticsAlert.severity.desc(),
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
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value,
                "acknowledged": alert.acknowledged,
                "created_at": alert.created_at.isoformat()
            }
            for alert in alerts
        ]
    
    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: int,
        notes: Optional[str] = None
    ) -> bool:
        """Acknowledge an alert"""
        
        alert = self.db.query(POSAnalyticsAlert).filter(
            POSAnalyticsAlert.alert_id == uuid.UUID(alert_id),
            POSAnalyticsAlert.is_active == True,
            POSAnalyticsAlert.acknowledged == False
        ).first()
        
        if not alert:
            return False
        
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        
        if notes:
            alert.context_data = alert.context_data or {}
            alert.context_data["acknowledgment_notes"] = notes
        
        self.db.commit()
        return True
    
    def get_terminal_health_summary(
        self,
        provider_id: Optional[int] = None,
        health_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get terminal health summary"""
        
        query = self.db.query(POSTerminalHealth)
        
        if provider_id:
            query = query.filter(POSTerminalHealth.provider_id == provider_id)
        
        if health_status:
            query = query.filter(POSTerminalHealth.health_status == health_status)
        
        terminals = query.all()
        
        # Group by provider
        by_provider = defaultdict(lambda: {
            "total": 0,
            "healthy": 0,
            "degraded": 0,
            "critical": 0,
            "offline": 0
        })
        
        for terminal in terminals:
            provider_name = terminal.provider.provider_name
            by_provider[provider_name]["total"] += 1
            
            if terminal.is_online:
                by_provider[provider_name][terminal.health_status] += 1
            else:
                by_provider[provider_name]["offline"] += 1
        
        return {
            "summary": dict(by_provider),
            "total_terminals": len(terminals),
            "filters": {
                "provider_id": provider_id,
                "health_status": health_status
            }
        }
    
    def get_transaction_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_id: Optional[int] = None,
        terminal_id: Optional[str] = None,
        granularity: str = "hourly"
    ) -> List[Dict[str, Any]]:
        """Get transaction trend data for charts"""
        
        trends = self._get_transaction_trends(
            start_date, end_date,
            [provider_id] if provider_id else None,
            [terminal_id] if terminal_id else None,
            granularity
        )
        
        return [
            {
                "timestamp": trend.timestamp.isoformat(),
                "transaction_count": trend.transaction_count,
                "transaction_value": float(trend.transaction_value),
                "success_rate": trend.success_rate,
                "average_value": float(trend.average_value)
            }
            for trend in trends
        ]
    
    async def trigger_data_refresh(
        self,
        provider_id: Optional[int] = None,
        requested_by: int = None
    ) -> str:
        """Trigger analytics data refresh"""
        
        # This would typically submit a background task
        # For now, return a mock task ID
        task_id = str(uuid.uuid4())
        
        logger.info(
            f"Analytics refresh triggered: task_id={task_id}, "
            f"provider_id={provider_id}, requested_by={requested_by}"
        )
        
        return task_id
    
    # Additional methods for provider details, terminal details, comparison, and export
    # would be implemented similarly...