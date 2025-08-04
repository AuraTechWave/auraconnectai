# backend/core/menu_sync_scheduler.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .menu_sync_models import (
    MenuSyncConfig, MenuSyncJob, POSIntegration, SyncDirection, SyncStatus
)
from .menu_sync_service import MenuSyncService
from .menu_sync_schemas import StartSyncRequest
from core.database import get_db


logger = logging.getLogger(__name__)


class MenuSyncScheduler:
    """Service for scheduling and automating menu synchronization jobs"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self._running_jobs = {}  # Track currently running sync jobs
        
    async def setup_automatic_sync_jobs(self):
        """Set up automatic sync jobs based on configuration"""
        
        with next(get_db()) as db:
            # Get all integrations with auto sync enabled
            configs = db.query(MenuSyncConfig).filter(
                MenuSyncConfig.sync_enabled == True,
                MenuSyncConfig.auto_sync_enabled == True
            ).all()
            
            for config in configs:
                await self._schedule_auto_sync(config)
    
    async def _schedule_auto_sync(self, config: MenuSyncConfig):
        """Schedule automatic sync for a specific configuration"""
        
        job_id = f"auto_sync_{config.pos_integration_id}"
        
        # Remove existing job if any
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        # Determine trigger based on configuration
        trigger = None
        
        if config.sync_frequency_minutes:
            # Interval-based scheduling
            trigger = IntervalTrigger(minutes=config.sync_frequency_minutes)
        
        elif config.sync_time_windows:
            # Time window-based scheduling
            trigger = self._create_time_window_trigger(config.sync_time_windows)
        
        if trigger:
            self.scheduler.add_job(
                self._execute_scheduled_sync,
                trigger=trigger,
                id=job_id,
                args=[config.pos_integration_id],
                name=f"Auto sync for POS integration {config.pos_integration_id}",
                max_instances=1,  # Prevent overlapping jobs
                coalesce=True,    # Combine missed runs
                misfire_grace_time=300  # 5 minutes grace for missed jobs
            )
            
            logger.info(f"Scheduled auto sync for POS integration {config.pos_integration_id}")
    
    def _create_time_window_trigger(self, time_windows: List[Dict[str, str]]) -> Optional[CronTrigger]:
        """Create a cron trigger based on time windows"""
        
        # This is a simplified implementation
        # In practice, you'd want to handle multiple time windows and more complex scheduling
        
        if not time_windows or not isinstance(time_windows, list):
            return None
        
        # Use the first time window for simplicity
        window = time_windows[0]
        start_time = window.get("start", "09:00")  # Default to 9 AM
        
        try:
            hour, minute = map(int, start_time.split(":"))
            return CronTrigger(hour=hour, minute=minute)
        except (ValueError, AttributeError):
            logger.error(f"Invalid time window format: {window}")
            return None
    
    async def _execute_scheduled_sync(self, pos_integration_id: int):
        """Execute a scheduled sync job"""
        
        # Check if there's already a running job for this integration
        if pos_integration_id in self._running_jobs:
            logger.info(f"Sync already running for POS integration {pos_integration_id}, skipping")
            return
        
        try:
            with next(get_db()) as db:
                # Get configuration
                config = db.query(MenuSyncConfig).filter(
                    MenuSyncConfig.pos_integration_id == pos_integration_id
                ).first()
                
                if not config or not config.sync_enabled:
                    logger.warning(f"Sync disabled or config not found for POS integration {pos_integration_id}")
                    return
                
                # Check if we're within allowed time windows
                if not self._is_within_time_window(config.sync_time_windows):
                    logger.info(f"Current time is outside sync windows for POS integration {pos_integration_id}")
                    return
                
                # Check for existing active jobs
                active_jobs = db.query(MenuSyncJob).filter(
                    MenuSyncJob.pos_integration_id == pos_integration_id,
                    MenuSyncJob.status.in_([SyncStatus.PENDING, SyncStatus.IN_PROGRESS])
                ).count()
                
                if active_jobs >= config.max_concurrent_jobs:
                    logger.info(f"Max concurrent jobs reached for POS integration {pos_integration_id}")
                    return
                
                # Mark job as running
                self._running_jobs[pos_integration_id] = datetime.utcnow()
                
                # Create and start sync job
                sync_service = MenuSyncService(db)
                
                sync_request = StartSyncRequest(
                    pos_integration_id=pos_integration_id,
                    sync_direction=config.default_sync_direction,
                    conflict_resolution=config.default_conflict_resolution
                )
                
                sync_job = await sync_service.start_sync(sync_request)
                
                logger.info(f"Started scheduled sync job {sync_job.job_id} for POS integration {pos_integration_id}")
                
        except Exception as e:
            logger.error(f"Error executing scheduled sync for POS integration {pos_integration_id}: {str(e)}")
        
        finally:
            # Remove from running jobs
            self._running_jobs.pop(pos_integration_id, None)
    
    def _is_within_time_window(self, time_windows: Optional[List[Dict[str, str]]]) -> bool:
        """Check if current time is within allowed sync windows"""
        
        if not time_windows:
            return True  # No restrictions
        
        current_time = datetime.now().time()
        current_day = datetime.now().strftime("%A").lower()
        
        for window in time_windows:
            # Check day restriction
            if "days" in window:
                allowed_days = [day.lower() for day in window["days"]]
                if current_day not in allowed_days:
                    continue
            
            # Check time range
            start_time_str = window.get("start", "00:00")
            end_time_str = window.get("end", "23:59")
            
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
                
                if start_time <= current_time <= end_time:
                    return True
                    
            except ValueError:
                logger.error(f"Invalid time format in window: {window}")
                continue
        
        return False
    
    async def schedule_one_time_sync(self, pos_integration_id: int, scheduled_at: datetime,
                                   sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
                                   entity_types: Optional[List[str]] = None,
                                   entity_ids: Optional[List[int]] = None) -> str:
        """Schedule a one-time sync job"""
        
        job_id = f"onetime_sync_{pos_integration_id}_{int(scheduled_at.timestamp())}"
        
        self.scheduler.add_job(
            self._execute_one_time_sync,
            trigger="date",
            run_date=scheduled_at,
            id=job_id,
            args=[pos_integration_id, sync_direction, entity_types, entity_ids],
            name=f"One-time sync for POS integration {pos_integration_id}",
            max_instances=1
        )
        
        logger.info(f"Scheduled one-time sync {job_id} for {scheduled_at}")
        return job_id
    
    async def _execute_one_time_sync(self, pos_integration_id: int, sync_direction: SyncDirection,
                                   entity_types: Optional[List[str]] = None,
                                   entity_ids: Optional[List[int]] = None):
        """Execute a one-time sync job"""
        
        try:
            with next(get_db()) as db:
                sync_service = MenuSyncService(db)
                
                sync_request = StartSyncRequest(
                    pos_integration_id=pos_integration_id,
                    sync_direction=sync_direction,
                    entity_types=entity_types,
                    entity_ids=entity_ids
                )
                
                sync_job = await sync_service.start_sync(sync_request)
                
                logger.info(f"Started one-time sync job {sync_job.job_id}")
                
        except Exception as e:
            logger.error(f"Error executing one-time sync: {str(e)}")
    
    def cancel_scheduled_sync(self, job_id: str) -> bool:
        """Cancel a scheduled sync job"""
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Cancelled scheduled sync job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {str(e)}")
            return False
    
    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """Get list of all scheduled sync jobs"""
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
                "args": job.args if hasattr(job, 'args') else []
            })
        
        return jobs
    
    async def update_sync_schedule(self, pos_integration_id: int):
        """Update sync schedule for a POS integration (call when config changes)"""
        
        with next(get_db()) as db:
            config = db.query(MenuSyncConfig).filter(
                MenuSyncConfig.pos_integration_id == pos_integration_id
            ).first()
            
            if config:
                await self._schedule_auto_sync(config)
    
    def get_running_jobs(self) -> Dict[int, datetime]:
        """Get currently running sync jobs"""
        return self._running_jobs.copy()
    
    async def setup_health_check_jobs(self):
        """Set up periodic health check jobs"""
        
        # Schedule cleanup of old sync logs
        self.scheduler.add_job(
            self._cleanup_old_sync_logs,
            trigger=CronTrigger(hour=2, minute=0),  # Run at 2 AM daily
            id="cleanup_sync_logs",
            name="Cleanup old sync logs",
            max_instances=1
        )
        
        # Schedule conflict auto-resolution
        self.scheduler.add_job(
            self._auto_resolve_conflicts,
            trigger=IntervalTrigger(minutes=30),  # Run every 30 minutes
            id="auto_resolve_conflicts",
            name="Auto-resolve conflicts",
            max_instances=1
        )
        
        # Schedule sync health monitoring
        self.scheduler.add_job(
            self._monitor_sync_health,
            trigger=IntervalTrigger(minutes=15),  # Run every 15 minutes
            id="monitor_sync_health",
            name="Monitor sync health",
            max_instances=1
        )
        
        logger.info("Scheduled health check jobs")
    
    async def _cleanup_old_sync_logs(self):
        """Clean up old sync logs and statistics"""
        
        try:
            with next(get_db()) as db:
                # Delete sync logs older than 30 days
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                
                deleted_logs = db.query(MenuSyncLog).filter(
                    MenuSyncLog.created_at < cutoff_date
                ).delete()
                
                # Delete old completed jobs (keep for 7 days)
                job_cutoff_date = datetime.utcnow() - timedelta(days=7)
                
                deleted_jobs = db.query(MenuSyncJob).filter(
                    MenuSyncJob.completed_at < job_cutoff_date,
                    MenuSyncJob.status.in_([SyncStatus.SUCCESS, SyncStatus.ERROR])
                ).delete()
                
                db.commit()
                
                logger.info(f"Cleaned up {deleted_logs} old sync logs and {deleted_jobs} old jobs")
                
        except Exception as e:
            logger.error(f"Error during sync log cleanup: {str(e)}")
    
    async def _auto_resolve_conflicts(self):
        """Automatically resolve conflicts that are marked as auto-resolvable"""
        
        try:
            with next(get_db()) as db:
                from .menu_sync_conflict_resolver import MenuSyncConflictResolver
                
                resolver = MenuSyncConflictResolver(db)
                results = resolver.auto_resolve_conflicts(max_conflicts=50)
                
                if results["resolved"] > 0:
                    logger.info(f"Auto-resolved {results['resolved']} conflicts")
                    
        except Exception as e:
            logger.error(f"Error during auto conflict resolution: {str(e)}")
    
    async def _monitor_sync_health(self):
        """Monitor sync health and send alerts if needed"""
        
        try:
            with next(get_db()) as db:
                # Check for failed jobs in the last hour
                hour_ago = datetime.utcnow() - timedelta(hours=1)
                
                failed_jobs = db.query(MenuSyncJob).filter(
                    MenuSyncJob.status == SyncStatus.ERROR,
                    MenuSyncJob.created_at >= hour_ago
                ).count()
                
                # Check for stuck jobs (running for more than 2 hours)
                stuck_cutoff = datetime.utcnow() - timedelta(hours=2)
                
                stuck_jobs = db.query(MenuSyncJob).filter(
                    MenuSyncJob.status == SyncStatus.IN_PROGRESS,
                    MenuSyncJob.started_at < stuck_cutoff
                ).all()
                
                # Check for high conflict rate
                unresolved_conflicts = db.query(MenuSyncConflict).filter(
                    MenuSyncConflict.status == "unresolved",
                    MenuSyncConflict.created_at >= hour_ago
                ).count()
                
                # Log health status
                if failed_jobs > 5:
                    logger.warning(f"High number of failed sync jobs in last hour: {failed_jobs}")
                
                if stuck_jobs:
                    logger.warning(f"Found {len(stuck_jobs)} stuck sync jobs")
                    # Could mark them as failed and retry
                
                if unresolved_conflicts > 10:
                    logger.warning(f"High number of unresolved conflicts: {unresolved_conflicts}")
                
        except Exception as e:
            logger.error(f"Error during sync health monitoring: {str(e)}")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Menu sync scheduler shut down")


# Global scheduler instance
menu_sync_scheduler = MenuSyncScheduler()


async def initialize_sync_scheduler():
    """Initialize the sync scheduler with default jobs"""
    await menu_sync_scheduler.setup_automatic_sync_jobs()
    await menu_sync_scheduler.setup_health_check_jobs()
    logger.info("Menu sync scheduler initialized")


def get_sync_scheduler() -> MenuSyncScheduler:
    """Get the global sync scheduler instance"""
    return menu_sync_scheduler