# backend/modules/orders/tasks/sync_tasks.py

"""
Background tasks for order synchronization.

Implements scheduled and on-demand sync tasks using APScheduler.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
import sqlalchemy.exc
import httpx

from core.database import get_db
from modules.orders.services.sync_service import OrderSyncService
from modules.orders.models.sync_models import SyncConfiguration
from core.config import settings

logger = logging.getLogger(__name__)


class OrderSyncScheduler:
    """Manages scheduled order synchronization tasks"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.sync_job_id = "order_sync_job"
        self.health_check_job_id = "sync_health_check"
        self.cleanup_job_id = "sync_cleanup"
        self.is_running = False
        
    def start(self):
        """Start the scheduler with sync tasks"""
        if self.is_running:
            logger.warning("Sync scheduler already running")
            return
        
        try:
            # Add sync job - runs every 10 minutes by default
            self._add_sync_job()
            
            # Add health check job - runs every hour
            self.scheduler.add_job(
                func=self._health_check_task,
                trigger=IntervalTrigger(minutes=settings.SYNC_HEALTH_CHECK_INTERVAL_MINUTES),
                id=self.health_check_job_id,
                name="Sync Health Check",
                replace_existing=True
            )
            
            # Add cleanup job - runs periodically
            self.scheduler.add_job(
                func=self._cleanup_task,
                trigger=IntervalTrigger(hours=settings.SYNC_CLEANUP_INTERVAL_HOURS),
                id=self.cleanup_job_id,
                name="Sync Cleanup",
                replace_existing=True
            )
            
            # Start scheduler
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Order sync scheduler started successfully")
            
        except ImportError as e:
            logger.error(f"Missing required dependency for scheduler: {e}")
            raise
        except Exception as e:
            logger.critical(f"Failed to start sync scheduler: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Order sync scheduler stopped")
        except RuntimeError as e:
            logger.warning(f"Scheduler already stopped: {e}")
        except Exception as e:
            logger.error(f"Unexpected error stopping sync scheduler: {e}", exc_info=True)
    
    def _add_sync_job(self):
        """Add or update the main sync job"""
        # Get sync interval from config
        db = next(get_db())
        try:
            interval_minutes = SyncConfiguration.get_config(
                db, "sync_interval_minutes", 10
            )
            enabled = SyncConfiguration.get_config(
                db, "sync_enabled", True
            )
            
            if not enabled:
                logger.info("Order sync is disabled in configuration")
                # Remove job if it exists
                if self.scheduler.get_job(self.sync_job_id):
                    self.scheduler.remove_job(self.sync_job_id)
                return
            
            # Add or update job
            self.scheduler.add_job(
                func=self._sync_task,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=self.sync_job_id,
                name=f"Order Sync (every {interval_minutes} minutes)",
                replace_existing=True,
                max_instances=1  # Prevent overlapping runs
            )
            
            logger.info(f"Sync job scheduled to run every {interval_minutes} minutes")
            
        finally:
            db.close()
    
    async def _sync_task(self):
        """Main sync task that runs periodically"""
        logger.info("Starting scheduled order sync task")
        
        db = next(get_db())
        sync_service = OrderSyncService(db)
        
        try:
            # Check if sync is enabled
            enabled = SyncConfiguration.get_config(db, "sync_enabled", True)
            if not enabled:
                logger.info("Order sync is disabled, skipping")
                return
            
            # Run sync
            start_time = datetime.utcnow()
            batch = await sync_service.sync_pending_orders()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Sync task completed in {duration:.2f}s - "
                f"Batch {batch.batch_id}: {batch.successful_syncs} success, "
                f"{batch.failed_syncs} failed"
            )
            
            # Check if we need to adjust sync interval based on performance
            if batch.failed_syncs > batch.successful_syncs:
                logger.warning(
                    "High failure rate detected, consider checking connectivity"
                )
            
        except httpx.HTTPError as e:
            logger.error(f"Network error during sync task: {e}")
            # Don't re-raise to prevent job from being removed
        except Exception as e:
            logger.critical(f"Unexpected sync task failure: {e}", exc_info=True)
            # Don't re-raise to prevent job from being removed
        finally:
            await sync_service.close()
            db.close()
    
    async def _health_check_task(self):
        """Health check task to monitor sync system"""
        logger.debug("Running sync health check")
        
        db = next(get_db())
        sync_service = OrderSyncService(db)
        
        try:
            # Get sync status
            status = await sync_service.get_sync_status()
            
            # Check for issues
            issues = []
            
            # Check for high number of unsynced orders
            if status["unsynced_orders"] > 100:
                issues.append(
                    f"High number of unsynced orders: {status['unsynced_orders']}"
                )
            
            # Check for pending conflicts
            if status["pending_conflicts"] > 10:
                issues.append(
                    f"Multiple unresolved conflicts: {status['pending_conflicts']}"
                )
            
            # Check last batch status
            last_batch = status.get("last_batch")
            if last_batch:
                if last_batch["failed_syncs"] > last_batch["successful_syncs"]:
                    issues.append("Last sync batch had high failure rate")
                
                # Check if last batch was too long ago
                if last_batch["completed_at"]:
                    last_sync = datetime.fromisoformat(last_batch["completed_at"])
                    if datetime.utcnow() - last_sync > timedelta(hours=1):
                        issues.append("No successful sync in the last hour")
            
            # Log issues
            if issues:
                logger.warning(f"Sync health check issues: {', '.join(issues)}")
                # TODO: Send alerts/notifications
            else:
                logger.info("Sync health check passed")
            
        except (httpx.HTTPError, asyncio.TimeoutError) as e:
            logger.warning(f"Health check network issue: {e}")
        except Exception as e:
            logger.error(f"Unexpected health check failure: {e}", exc_info=True)
        finally:
            await sync_service.close()
            db.close()
    
    async def _cleanup_task(self):
        """Cleanup old sync logs and data"""
        logger.info("Running sync cleanup task")
        
        db = next(get_db())
        
        try:
            # Get retention period from config
            retention_days = SyncConfiguration.get_config(
                db, "sync_log_retention_days", 30
            )
            
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Delete old sync logs
            from modules.orders.models.sync_models import SyncLog, SyncBatch
            
            deleted_logs = db.query(SyncLog).filter(
                SyncLog.started_at < cutoff_date
            ).delete()
            
            # Delete old batches without logs
            deleted_batches = db.query(SyncBatch).filter(
                SyncBatch.started_at < cutoff_date,
                ~SyncBatch.sync_logs.any()
            ).delete()
            
            db.commit()
            
            logger.info(
                f"Cleanup completed: deleted {deleted_logs} logs "
                f"and {deleted_batches} batches older than {retention_days} days"
            )
            
        except sqlalchemy.exc.SQLAlchemyError as e:
            logger.error(f"Database error during cleanup: {e}")
            db.rollback()
        except Exception as e:
            logger.critical(f"Unexpected cleanup task failure: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def trigger_manual_sync(self) -> bool:
        """Trigger a manual sync immediately"""
        try:
            # Run sync task immediately
            self.scheduler.add_job(
                func=self._sync_task,
                id=f"manual_sync_{datetime.utcnow().timestamp()}",
                name="Manual Sync",
                run_date=datetime.now()  # Run immediately
            )
            logger.info("Manual sync triggered")
            return True
        except RuntimeError as e:
            logger.warning(f"Scheduler not running: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error triggering manual sync: {e}", exc_info=True)
            return False
    
    def update_sync_interval(self, minutes: int) -> bool:
        """Update sync interval dynamically"""
        try:
            # Update configuration
            db = next(get_db())
            try:
                config = db.query(SyncConfiguration).filter(
                    SyncConfiguration.config_key == "sync_interval_minutes"
                ).first()
                
                if config:
                    config.config_value = minutes
                else:
                    config = SyncConfiguration(
                        config_key="sync_interval_minutes",
                        config_value=minutes
                    )
                    db.add(config)
                
                db.commit()
                
                # Update job
                self._add_sync_job()
                
                logger.info(f"Sync interval updated to {minutes} minutes")
                return True
                
            finally:
                db.close()
                
        except sqlalchemy.exc.SQLAlchemyError as e:
            logger.error(f"Database error updating sync interval: {e}")
            return False
        except ValueError as e:
            logger.error(f"Invalid sync interval value: {e}")
            return False
        except Exception as e:
            logger.critical(f"Unexpected error updating sync interval: {e}", exc_info=True)
            return False
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get status of all sync jobs"""
        jobs = []
        
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "is_running": job.pending
            })
        
        return {
            "scheduler_running": self.is_running,
            "jobs": jobs
        }


# Global scheduler instance
order_sync_scheduler = OrderSyncScheduler()


# FastAPI startup/shutdown events
async def start_sync_scheduler():
    """Start sync scheduler on application startup"""
    try:
        order_sync_scheduler.start()
        logger.info("Order sync scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to start sync scheduler: {e}", exc_info=True)
        # Don't fail startup if scheduler fails
        pass


async def stop_sync_scheduler():
    """Stop sync scheduler on application shutdown"""
    try:
        order_sync_scheduler.stop()
        logger.info("Order sync scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping sync scheduler: {e}", exc_info=True)