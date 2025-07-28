# backend/core/menu_sync_monitor.py

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from dataclasses import dataclass
from enum import Enum

from .menu_sync_models import (
    MenuSyncJob, MenuSyncLog, MenuSyncConflict, MenuSyncStatistics,
    POSIntegration, MenuSyncConfig, SyncStatus, SyncDirection
)


logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SyncHealthMetrics:
    """Data class for sync health metrics"""
    overall_health: HealthStatus
    pos_integration_id: int
    last_successful_sync: Optional[datetime]
    pending_conflicts: int
    active_jobs: int
    sync_enabled: bool
    success_rate_24h: float
    error_rate_24h: float
    avg_sync_time: Optional[float]
    total_entities_synced_24h: int
    issues: List[Dict[str, str]]
    recommendations: List[str]
    last_updated: datetime


class MenuSyncMonitor:
    """Service for monitoring menu synchronization health and performance"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_sync_health(self, pos_integration_id: int) -> SyncHealthMetrics:
        """Get comprehensive sync health metrics for a POS integration"""
        
        # Get basic integration info
        pos_integration = self.db.query(POSIntegration).get(pos_integration_id)
        if not pos_integration:
            raise ValueError(f"POS integration {pos_integration_id} not found")
        
        sync_config = self.db.query(MenuSyncConfig).filter(
            MenuSyncConfig.pos_integration_id == pos_integration_id
        ).first()
        
        # Calculate time windows
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_hour = now - timedelta(hours=1)
        
        # Get recent job statistics
        jobs_24h = self.db.query(MenuSyncJob).filter(
            and_(
                MenuSyncJob.pos_integration_id == pos_integration_id,
                MenuSyncJob.created_at >= last_24h
            )
        ).all()
        
        successful_jobs = [job for job in jobs_24h if job.status == SyncStatus.SUCCESS]
        failed_jobs = [job for job in jobs_24h if job.status == SyncStatus.ERROR]
        
        # Calculate success/error rates
        total_jobs = len(jobs_24h)
        success_rate = (len(successful_jobs) / total_jobs * 100) if total_jobs > 0 else 100
        error_rate = (len(failed_jobs) / total_jobs * 100) if total_jobs > 0 else 0
        
        # Get last successful sync
        last_successful_sync = None
        if successful_jobs:
            last_successful_sync = max(job.completed_at for job in successful_jobs if job.completed_at)
        
        # Calculate average sync time
        avg_sync_time = None
        completed_jobs = [job for job in jobs_24h if job.started_at and job.completed_at]
        if completed_jobs:
            sync_times = [
                (job.completed_at - job.started_at).total_seconds()
                for job in completed_jobs
            ]
            avg_sync_time = sum(sync_times) / len(sync_times)
        
        # Count pending conflicts
        pending_conflicts = self.db.query(MenuSyncConflict).join(
            MenuSyncJob
        ).filter(
            and_(
                MenuSyncJob.pos_integration_id == pos_integration_id,
                MenuSyncConflict.status == "unresolved"
            )
        ).count()
        
        # Count active jobs
        active_jobs = self.db.query(MenuSyncJob).filter(
            and_(
                MenuSyncJob.pos_integration_id == pos_integration_id,
                MenuSyncJob.status.in_([SyncStatus.PENDING, SyncStatus.IN_PROGRESS])
            )
        ).count()
        
        # Calculate total entities synced
        total_entities_synced = sum(job.successful_entities for job in jobs_24h)
        
        # Analyze issues and determine health status
        issues = []
        recommendations = []
        health_status = self._determine_health_status(
            pos_integration_id, success_rate, error_rate, pending_conflicts,
            active_jobs, last_successful_sync, issues, recommendations
        )
        
        return SyncHealthMetrics(
            overall_health=health_status,
            pos_integration_id=pos_integration_id,
            last_successful_sync=last_successful_sync,
            pending_conflicts=pending_conflicts,
            active_jobs=active_jobs,
            sync_enabled=sync_config.sync_enabled if sync_config else False,
            success_rate_24h=success_rate,
            error_rate_24h=error_rate,
            avg_sync_time=avg_sync_time,
            total_entities_synced_24h=total_entities_synced,
            issues=issues,
            recommendations=recommendations,
            last_updated=now
        )
    
    def _determine_health_status(self, pos_integration_id: int, success_rate: float,
                               error_rate: float, pending_conflicts: int, active_jobs: int,
                               last_successful_sync: Optional[datetime],
                               issues: List[Dict[str, str]], 
                               recommendations: List[str]) -> HealthStatus:
        """Determine overall health status based on metrics"""
        
        status = HealthStatus.HEALTHY
        
        # Check success rate
        if success_rate < 50:
            status = HealthStatus.CRITICAL
            issues.append({
                "type": "low_success_rate",
                "severity": "critical",
                "message": f"Success rate is critically low: {success_rate:.1f}%"
            })
            recommendations.append("Check POS system connectivity and credentials")
        elif success_rate < 80:
            status = max(status, HealthStatus.ERROR)
            issues.append({
                "type": "low_success_rate",
                "severity": "error",
                "message": f"Success rate is low: {success_rate:.1f}%"
            })
            recommendations.append("Review recent sync failures and resolve underlying issues")
        elif success_rate < 95:
            status = max(status, HealthStatus.WARNING)
            issues.append({
                "type": "low_success_rate",
                "severity": "warning",
                "message": f"Success rate could be improved: {success_rate:.1f}%"
            })
        
        # Check error rate
        if error_rate > 50:
            status = HealthStatus.CRITICAL
            issues.append({
                "type": "high_error_rate",
                "severity": "critical",
                "message": f"Error rate is critically high: {error_rate:.1f}%"
            })
        elif error_rate > 20:
            status = max(status, HealthStatus.ERROR)
            issues.append({
                "type": "high_error_rate",
                "severity": "error",
                "message": f"Error rate is high: {error_rate:.1f}%"
            })
        elif error_rate > 5:
            status = max(status, HealthStatus.WARNING)
            issues.append({
                "type": "high_error_rate",
                "severity": "warning",
                "message": f"Error rate is elevated: {error_rate:.1f}%"
            })
        
        # Check last successful sync
        if last_successful_sync:
            hours_since_success = (datetime.utcnow() - last_successful_sync).total_seconds() / 3600
            if hours_since_success > 48:
                status = HealthStatus.CRITICAL
                issues.append({
                    "type": "stale_sync",
                    "severity": "critical",
                    "message": f"No successful sync in {hours_since_success:.1f} hours"
                })
                recommendations.append("Investigate sync failures and restore connectivity")
            elif hours_since_success > 24:
                status = max(status, HealthStatus.ERROR)
                issues.append({
                    "type": "stale_sync",
                    "severity": "error",
                    "message": f"No successful sync in {hours_since_success:.1f} hours"
                })
                recommendations.append("Check sync schedule and resolve any blocking issues")
            elif hours_since_success > 12:
                status = max(status, HealthStatus.WARNING)
                issues.append({
                    "type": "stale_sync",
                    "severity": "warning",
                    "message": f"Last successful sync was {hours_since_success:.1f} hours ago"
                })
        else:
            status = HealthStatus.CRITICAL
            issues.append({
                "type": "no_successful_sync",
                "severity": "critical",
                "message": "No successful sync found in recent history"
            })
            recommendations.append("Check POS integration setup and credentials")
        
        # Check pending conflicts
        if pending_conflicts > 50:
            status = max(status, HealthStatus.ERROR)
            issues.append({
                "type": "high_conflicts",
                "severity": "error",
                "message": f"High number of pending conflicts: {pending_conflicts}"
            })
            recommendations.append("Review and resolve pending conflicts to prevent sync degradation")
        elif pending_conflicts > 20:
            status = max(status, HealthStatus.WARNING)
            issues.append({
                "type": "moderate_conflicts",
                "severity": "warning",
                "message": f"Moderate number of pending conflicts: {pending_conflicts}"
            })
            recommendations.append("Consider auto-resolution strategies for common conflict types")
        
        # Check stuck jobs
        stuck_jobs = self._get_stuck_jobs(pos_integration_id)
        if stuck_jobs:
            status = max(status, HealthStatus.ERROR)
            issues.append({
                "type": "stuck_jobs",
                "severity": "error",
                "message": f"Found {len(stuck_jobs)} stuck sync jobs"
            })
            recommendations.append("Cancel stuck jobs and investigate causes")
        
        return status
    
    def _get_stuck_jobs(self, pos_integration_id: int) -> List[MenuSyncJob]:
        """Get jobs that appear to be stuck (running for too long)"""
        
        # Jobs running for more than 2 hours are considered stuck
        stuck_cutoff = datetime.utcnow() - timedelta(hours=2)
        
        return self.db.query(MenuSyncJob).filter(
            and_(
                MenuSyncJob.pos_integration_id == pos_integration_id,
                MenuSyncJob.status == SyncStatus.IN_PROGRESS,
                MenuSyncJob.started_at < stuck_cutoff
            )
        ).all()
    
    def get_sync_performance_metrics(self, pos_integration_id: int, 
                                   period_hours: int = 24) -> Dict[str, Any]:
        """Get detailed performance metrics for sync operations"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=period_hours)
        
        # Get jobs in the period
        jobs = self.db.query(MenuSyncJob).filter(
            and_(
                MenuSyncJob.pos_integration_id == pos_integration_id,
                MenuSyncJob.created_at >= cutoff_time
            )
        ).all()
        
        if not jobs:
            return {
                "period_hours": period_hours,
                "total_jobs": 0,
                "job_statistics": {},
                "performance_metrics": {},
                "entity_statistics": {},
                "error_analysis": {}
            }
        
        # Job statistics
        job_stats = {
            "total": len(jobs),
            "successful": len([j for j in jobs if j.status == SyncStatus.SUCCESS]),
            "failed": len([j for j in jobs if j.status == SyncStatus.ERROR]),
            "in_progress": len([j for j in jobs if j.status == SyncStatus.IN_PROGRESS]),
            "pending": len([j for j in jobs if j.status == SyncStatus.PENDING]),
            "conflicts": len([j for j in jobs if j.status == SyncStatus.CONFLICT])
        }
        
        # Performance metrics
        completed_jobs = [j for j in jobs if j.started_at and j.completed_at]
        performance_metrics = {}
        
        if completed_jobs:
            durations = [(j.completed_at - j.started_at).total_seconds() for j in completed_jobs]
            performance_metrics = {
                "avg_duration_seconds": sum(durations) / len(durations),
                "min_duration_seconds": min(durations),
                "max_duration_seconds": max(durations),
                "median_duration_seconds": sorted(durations)[len(durations) // 2]
            }
        
        # Entity statistics
        entity_stats = {
            "total_entities_processed": sum(j.processed_entities for j in jobs),
            "total_entities_successful": sum(j.successful_entities for j in jobs),
            "total_entities_failed": sum(j.failed_entities for j in jobs),
            "total_conflicts_detected": sum(j.conflicts_detected for j in jobs)
        }
        
        # Error analysis
        failed_jobs = [j for j in jobs if j.status == SyncStatus.ERROR and j.error_message]
        error_analysis = {}
        
        if failed_jobs:
            error_messages = [j.error_message for j in failed_jobs]
            error_types = {}
            
            for msg in error_messages:
                # Simple error categorization
                if "connection" in msg.lower() or "timeout" in msg.lower():
                    error_types["connectivity"] = error_types.get("connectivity", 0) + 1
                elif "auth" in msg.lower() or "credential" in msg.lower():
                    error_types["authentication"] = error_types.get("authentication", 0) + 1
                elif "rate limit" in msg.lower():
                    error_types["rate_limiting"] = error_types.get("rate_limiting", 0) + 1
                else:
                    error_types["other"] = error_types.get("other", 0) + 1
            
            error_analysis = {
                "total_errors": len(failed_jobs),
                "error_types": error_types,
                "most_recent_error": failed_jobs[-1].error_message if failed_jobs else None
            }
        
        return {
            "period_hours": period_hours,
            "total_jobs": len(jobs),
            "job_statistics": job_stats,
            "performance_metrics": performance_metrics,
            "entity_statistics": entity_stats,
            "error_analysis": error_analysis
        }
    
    def get_sync_trends(self, pos_integration_id: int, days: int = 7) -> Dict[str, Any]:
        """Get sync trends over time for visualization"""
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get statistics records
        stats = self.db.query(MenuSyncStatistics).filter(
            and_(
                MenuSyncStatistics.pos_integration_id == pos_integration_id,
                MenuSyncStatistics.period_start >= start_date,
                MenuSyncStatistics.period_type == "hour"
            )
        ).order_by(MenuSyncStatistics.period_start).all()
        
        # Format data for charts
        trend_data = {
            "timestamps": [],
            "success_rates": [],
            "error_rates": [],
            "entity_counts": [],
            "conflict_counts": [],
            "avg_durations": []
        }
        
        for stat in stats:
            trend_data["timestamps"].append(stat.period_start.isoformat())
            trend_data["success_rates"].append(stat.success_rate_percentage or 0)
            trend_data["error_rates"].append(stat.error_rate_percentage or 0)
            trend_data["entity_counts"].append(stat.total_entities_synced)
            trend_data["conflict_counts"].append(stat.total_conflicts)
            trend_data["avg_durations"].append(stat.avg_job_duration_seconds or 0)
        
        # Calculate summary statistics
        summary = {}
        if stats:
            summary = {
                "period_days": days,
                "avg_success_rate": sum(s.success_rate_percentage or 0 for s in stats) / len(stats),
                "avg_error_rate": sum(s.error_rate_percentage or 0 for s in stats) / len(stats),
                "total_entities_synced": sum(s.total_entities_synced for s in stats),
                "total_conflicts": sum(s.total_conflicts for s in stats),
                "total_jobs": sum(s.total_jobs for s in stats)
            }
        
        return {
            "summary": summary,
            "trend_data": trend_data,
            "data_points": len(stats)
        }
    
    def get_conflict_analysis(self, pos_integration_id: int) -> Dict[str, Any]:
        """Get detailed analysis of sync conflicts"""
        
        # Get all conflicts for this integration
        conflicts = self.db.query(MenuSyncConflict).join(
            MenuSyncJob
        ).filter(
            MenuSyncJob.pos_integration_id == pos_integration_id
        ).all()
        
        if not conflicts:
            return {
                "total_conflicts": 0,
                "by_status": {},
                "by_entity_type": {},
                "by_conflict_type": {},
                "by_severity": {},
                "resolution_analysis": {},
                "trend_analysis": {}
            }
        
        # Analyze by status
        by_status = {}
        for conflict in conflicts:
            by_status[conflict.status] = by_status.get(conflict.status, 0) + 1
        
        # Analyze by entity type
        by_entity_type = {}
        for conflict in conflicts:
            by_entity_type[conflict.entity_type] = by_entity_type.get(conflict.entity_type, 0) + 1
        
        # Analyze by conflict type
        by_conflict_type = {}
        for conflict in conflicts:
            by_conflict_type[conflict.conflict_type] = by_conflict_type.get(conflict.conflict_type, 0) + 1
        
        # Analyze by severity
        by_severity = {}
        for conflict in conflicts:
            by_severity[conflict.severity] = by_severity.get(conflict.severity, 0) + 1
        
        # Resolution analysis
        resolved_conflicts = [c for c in conflicts if c.status == "resolved"]
        resolution_analysis = {}
        
        if resolved_conflicts:
            by_strategy = {}
            resolution_times = []
            
            for conflict in resolved_conflicts:
                if conflict.resolution_strategy:
                    strategy = conflict.resolution_strategy.value
                    by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
                
                if conflict.created_at and conflict.resolved_at:
                    resolution_time = (conflict.resolved_at - conflict.created_at).total_seconds() / 3600
                    resolution_times.append(resolution_time)
            
            resolution_analysis = {
                "total_resolved": len(resolved_conflicts),
                "by_strategy": by_strategy,
                "avg_resolution_time_hours": sum(resolution_times) / len(resolution_times) if resolution_times else 0,
                "auto_resolved": len([c for c in resolved_conflicts if c.resolved_by == 0])
            }
        
        # Trend analysis (conflicts over time)
        last_30_days = datetime.utcnow() - timedelta(days=30)
        recent_conflicts = [c for c in conflicts if c.created_at >= last_30_days]
        
        # Group by day
        daily_counts = {}
        for conflict in recent_conflicts:
            day_key = conflict.created_at.date().isoformat()
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
        
        trend_analysis = {
            "conflicts_last_30_days": len(recent_conflicts),
            "daily_breakdown": daily_counts,
            "peak_day": max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None
        }
        
        return {
            "total_conflicts": len(conflicts),
            "by_status": by_status,
            "by_entity_type": by_entity_type,
            "by_conflict_type": by_conflict_type,
            "by_severity": by_severity,
            "resolution_analysis": resolution_analysis,
            "trend_analysis": trend_analysis
        }
    
    def get_integration_overview(self) -> List[Dict[str, Any]]:
        """Get overview of all POS integrations and their sync health"""
        
        integrations = self.db.query(POSIntegration).all()
        overview = []
        
        for integration in integrations:
            try:
                health_metrics = self.get_sync_health(integration.id)
                
                overview.append({
                    "pos_integration_id": integration.id,
                    "vendor": integration.vendor,
                    "status": integration.status,
                    "health_status": health_metrics.overall_health.value,
                    "success_rate_24h": health_metrics.success_rate_24h,
                    "pending_conflicts": health_metrics.pending_conflicts,
                    "active_jobs": health_metrics.active_jobs,
                    "last_successful_sync": health_metrics.last_successful_sync.isoformat() if health_metrics.last_successful_sync else None,
                    "sync_enabled": health_metrics.sync_enabled,
                    "issue_count": len(health_metrics.issues)
                })
                
            except Exception as e:
                logger.error(f"Error getting health metrics for integration {integration.id}: {str(e)}")
                overview.append({
                    "pos_integration_id": integration.id,
                    "vendor": integration.vendor,
                    "status": integration.status,
                    "health_status": "error",
                    "error": str(e)
                })
        
        return overview
    
    def generate_health_report(self, pos_integration_id: int) -> Dict[str, Any]:
        """Generate a comprehensive health report for a POS integration"""
        
        health_metrics = self.get_sync_health(pos_integration_id)
        performance_metrics = self.get_sync_performance_metrics(pos_integration_id, 24)
        conflict_analysis = self.get_conflict_analysis(pos_integration_id)
        trends = self.get_sync_trends(pos_integration_id, 7)
        
        return {
            "integration_id": pos_integration_id,
            "report_generated_at": datetime.utcnow().isoformat(),
            "health_metrics": health_metrics.__dict__,
            "performance_metrics": performance_metrics,
            "conflict_analysis": conflict_analysis,
            "trends": trends,
            "recommendations": self._generate_recommendations(
                health_metrics, performance_metrics, conflict_analysis
            )
        }
    
    def _generate_recommendations(self, health_metrics: SyncHealthMetrics,
                                performance_metrics: Dict[str, Any],
                                conflict_analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        
        recommendations = []
        
        # Add existing recommendations from health metrics
        recommendations.extend(health_metrics.recommendations)
        
        # Performance-based recommendations
        if performance_metrics.get("performance_metrics", {}).get("avg_duration_seconds", 0) > 300:  # 5 minutes
            recommendations.append("Sync operations are taking longer than expected - consider optimizing batch sizes")
        
        # Conflict-based recommendations
        conflict_stats = conflict_analysis.get("by_conflict_type", {})
        if conflict_stats.get("data_mismatch", 0) > 10:
            recommendations.append("High number of data mismatch conflicts - review field mappings and transformation rules")
        
        if conflict_stats.get("deleted_entity", 0) > 5:
            recommendations.append("Multiple entity deletion conflicts - establish clear deletion policies")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations