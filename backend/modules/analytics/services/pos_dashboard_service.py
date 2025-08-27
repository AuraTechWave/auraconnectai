# backend/modules/analytics/services/pos_dashboard_service.py

"""
Service for POS analytics dashboard operations.

Handles dashboard data aggregation with caching.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import json
from collections import defaultdict

from core.cache import cache_manager as cache_service
from modules.orders.models.external_pos_models import ExternalPOSProvider
from modules.analytics.models.pos_analytics_models import (
    POSAnalyticsSnapshot,
    POSProviderPerformance,
    POSTerminalHealth,
    POSAnalyticsAlert,
)
from modules.analytics.schemas.pos_analytics_schemas import (
    POSDashboardResponse,
    POSProviderSummary,
    POSTransactionTrend,
    POSAlert,
    POSHealthStatus,
    AlertSeverity,
)
from .pos.base_service import POSAnalyticsBaseService
from .pos_trends_service import POSTrendsService
from .pos_alerts_service import POSAlertsService
from .optimized_queries import OptimizedAnalyticsQueries
from ..utils.query_monitor import monitor_query_performance
from ..utils.cache_manager import cached_query

logger = logging.getLogger(__name__)


class POSDashboardService(POSAnalyticsBaseService):
    """Service for POS analytics dashboard"""

    CACHE_TTL = 300  # 5 minutes cache

    def __init__(self, db: Session):
        super().__init__(db)
        self.trends_service = POSTrendsService(db)
        self.alerts_service = POSAlertsService(db)

    @monitor_query_performance("pos_dashboard.get_dashboard_data")
    async def get_dashboard_data(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
        include_offline: bool = True,
    ) -> POSDashboardResponse:
        """Get comprehensive dashboard data with caching"""

        # Generate cache key
        cache_key = self.get_cache_key(
            "dashboard",
            start_date,
            end_date,
            tuple(provider_ids) if provider_ids else None,
            tuple(terminal_ids) if terminal_ids else None,
        )

        # Try to get from cache
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached dashboard data for key: {cache_key}")
            return POSDashboardResponse(**json.loads(cached_data))

        # Generate fresh data
        dashboard_data = await self._generate_dashboard_data(
            start_date, end_date, provider_ids, terminal_ids, include_offline
        )

        # Cache the result
        await cache_service.set(cache_key, dashboard_data.json(), ttl=self.CACHE_TTL)

        return dashboard_data

    async def _generate_dashboard_data(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]],
        terminal_ids: Optional[List[str]],
        include_offline: bool,
    ) -> POSDashboardResponse:
        """Generate fresh dashboard data"""

        # Get provider summaries
        providers = await self._get_provider_summaries(
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
            if total_transactions > 0
            else 0.0
        )

        average_transaction_value = (
            total_transaction_value / total_transactions
            if total_transactions > 0
            else Decimal("0.00")
        )

        # Get terminal health breakdown
        terminal_health = await self._get_terminal_health_breakdown(
            provider_ids, terminal_ids
        )

        # Get transaction trends
        transaction_trends = await self.trends_service.get_transaction_trends(
            start_date, end_date, None, None, "hourly"
        )

        # Get active alerts
        alerts, _ = await self.alerts_service.get_active_alerts(limit=20, offset=0)

        # Calculate overall performance metrics
        overall_uptime = await self._calculate_overall_uptime(
            provider_ids, start_date, end_date
        )
        avg_sync_time = await self._calculate_average_sync_time(
            provider_ids, start_date, end_date
        )
        avg_webhook_time = await self._calculate_average_webhook_time(
            provider_ids, start_date, end_date
        )

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
            transaction_trends=[
                POSTransactionTrend(**trend) for trend in transaction_trends
            ],
            active_alerts=alerts,
            generated_at=datetime.utcnow(),
            time_range=f"{start_date.isoformat()} to {end_date.isoformat()}",
        )

    @monitor_query_performance("pos_dashboard.get_provider_summaries")
    @cached_query("pos_provider_summaries", ttl=300)
    async def _get_provider_summaries(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        include_offline: bool = True,
    ) -> List[POSProviderSummary]:
        """Get summary metrics for each provider using optimized queries"""

        # Use the optimized query that eliminates N+1 patterns
        results = OptimizedAnalyticsQueries.get_provider_summaries_optimized(
            self.db,
            start_date,
            end_date,
            provider_ids,
            include_offline,
        )

        summaries = []
        for row in results:
            # Calculate rates
            total_tx = row.total_transactions or 0
            success_tx = row.successful_transactions or 0
            tx_success_rate = (success_tx / total_tx * 100) if total_tx > 0 else 0.0

            total_syncs = row.total_syncs or 0
            success_syncs = row.successful_syncs or 0
            sync_success_rate = (
                (success_syncs / total_syncs * 100) if total_syncs > 0 else 0.0
            )

            total_webhooks = row.total_webhooks or 0
            success_webhooks = row.successful_webhooks or 0
            webhook_success_rate = (
                (success_webhooks / total_webhooks * 100) if total_webhooks > 0 else 0.0
            )

            # Calculate health status using terminal stats from the optimized query
            terminal_stats = {
                "total": row.total_terminals or 0,
                "active": row.active_terminals or 0,
                "offline": row.offline_terminals or 0,
            }
            health_status = self._calculate_provider_health_status(
                terminal_stats, tx_success_rate, row.uptime or 100.0
            )

            summaries.append(
                POSProviderSummary(
                    provider_id=row.id,
                    provider_name=row.provider_name,
                    provider_code=row.provider_code,
                    is_active=row.is_active,
                    total_terminals=row.total_terminals or 0,
                    active_terminals=row.active_terminals or 0,
                    offline_terminals=row.offline_terminals or 0,
                    total_transactions=total_tx,
                    successful_transactions=success_tx,
                    failed_transactions=row.failed_transactions or 0,
                    transaction_success_rate=tx_success_rate,
                    total_transaction_value=Decimal(str(row.total_value or 0)),
                    total_syncs=total_syncs,
                    sync_success_rate=sync_success_rate,
                    average_sync_time_ms=row.avg_sync_time or 0.0,
                    total_webhooks=total_webhooks,
                    webhook_success_rate=webhook_success_rate,
                    overall_health_status=health_status,
                    uptime_percentage=row.uptime or 100.0,
                    active_alerts=row.active_alerts or 0,
                )
            )

        return summaries

    def _get_provider_terminal_stats(self, provider_id: int) -> Dict[str, int]:
        """Get terminal statistics for a provider"""
        terminals = (
            self.db.query(POSTerminalHealth)
            .filter(POSTerminalHealth.provider_id == provider_id)
            .all()
        )

        total = len(terminals)
        active = sum(1 for t in terminals if t.is_online)
        offline = total - active

        return {"total": total, "active": active, "offline": offline}

    def _calculate_provider_health_status(
        self, terminal_stats: Dict[str, int], success_rate: float, uptime: float
    ) -> POSHealthStatus:
        """Calculate overall health status for a provider"""

        # Check critical conditions
        if terminal_stats["active"] == 0 and terminal_stats["total"] > 0:
            return POSHealthStatus.OFFLINE

        offline_percentage = (
            (terminal_stats["offline"] / terminal_stats["total"] * 100)
            if terminal_stats["total"] > 0
            else 0
        )

        if offline_percentage > 50:
            return POSHealthStatus.CRITICAL

        # Check performance metrics
        if success_rate < 90 or uptime < 95 or offline_percentage > 20:
            return POSHealthStatus.DEGRADED

        return POSHealthStatus.HEALTHY

    async def _get_terminal_health_breakdown(
        self,
        provider_ids: Optional[List[int]] = None,
        terminal_ids: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Get breakdown of terminal health statuses"""

        query = self.db.query(
            POSTerminalHealth.health_status,
            func.count(POSTerminalHealth.id).label("count"),
        )

        if provider_ids:
            query = query.filter(POSTerminalHealth.provider_id.in_(provider_ids))

        if terminal_ids:
            query = query.filter(POSTerminalHealth.terminal_id.in_(terminal_ids))

        results = query.group_by(POSTerminalHealth.health_status).all()

        breakdown = {"healthy": 0, "degraded": 0, "critical": 0, "offline": 0}

        for status, count in results:
            breakdown[status] = count

        return breakdown

    async def _calculate_overall_uptime(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Calculate overall uptime percentage"""

        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.uptime_percentage).label("avg_uptime")
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date(),
        )

        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))

        result = query.first()
        return result.avg_uptime or 100.0

    async def _calculate_average_sync_time(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Calculate average sync time in milliseconds"""

        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.average_sync_time_ms).label("avg_time")
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date(),
        )

        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))

        result = query.first()
        return result.avg_time or 0.0

    async def _calculate_average_webhook_time(
        self,
        provider_ids: Optional[List[int]],
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Calculate average webhook processing time in milliseconds"""

        query = self.db.query(
            func.avg(POSAnalyticsSnapshot.average_webhook_processing_time_ms).label(
                "avg_time"
            )
        ).filter(
            POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
            POSAnalyticsSnapshot.snapshot_date <= end_date.date(),
        )

        if provider_ids:
            query = query.filter(POSAnalyticsSnapshot.provider_id.in_(provider_ids))

        result = query.first()
        return result.avg_time or 0.0

    async def get_terminal_health_summary(
        self, provider_id: Optional[int] = None, health_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get terminal health summary with caching"""

        cache_key = f"terminal_health:{provider_id or 'all'}:{health_status or 'all'}"

        cached_data = await cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        query = self.db.query(POSTerminalHealth)

        if provider_id:
            query = query.filter(POSTerminalHealth.provider_id == provider_id)

        if health_status:
            query = query.filter(POSTerminalHealth.health_status == health_status)

        terminals = query.all()

        # Group by provider
        by_provider = defaultdict(
            lambda: {
                "total": 0,
                "healthy": 0,
                "degraded": 0,
                "critical": 0,
                "offline": 0,
            }
        )

        for terminal in terminals:
            provider_name = terminal.provider.provider_name
            by_provider[provider_name]["total"] += 1

            if terminal.is_online:
                by_provider[provider_name][terminal.health_status] += 1
            else:
                by_provider[provider_name]["offline"] += 1

        result = {
            "summary": dict(by_provider),
            "total_terminals": len(terminals),
            "filters": {"provider_id": provider_id, "health_status": health_status},
        }

        # Cache for 1 minute
        await cache_service.set(cache_key, json.dumps(result), ttl=60)

        return result

    async def trigger_data_refresh(
        self, provider_id: Optional[int] = None, requested_by: int = None
    ) -> str:
        """Trigger analytics data refresh and clear cache"""

        # Clear relevant cache entries
        cache_pattern = f"dashboard:*"
        if provider_id:
            cache_pattern = f"*providers:{provider_id}*"

        await cache_service.delete_pattern(cache_pattern)

        # Also clear terminal health cache
        await cache_service.delete_pattern("terminal_health:*")

        # This would typically submit a background task
        import uuid

        task_id = str(uuid.uuid4())

        logger.info(
            f"Analytics refresh triggered: task_id={task_id}, "
            f"provider_id={provider_id}, requested_by={requested_by}"
        )

        return task_id
