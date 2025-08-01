# backend/modules/orders/tasks/webhook_retry_task.py

"""
Background task for retrying failed webhook processing.

Runs periodically to retry webhooks that failed processing.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from core.database import get_db
from core.config import settings
from modules.orders.services.external_pos_webhook_service import ExternalPOSWebhookService
from modules.orders.models.external_pos_models import ExternalPOSWebhookEvent
from modules.orders.enums.external_pos_enums import WebhookProcessingStatus

logger = logging.getLogger(__name__)


class WebhookRetryScheduler:
    """Scheduler for retrying failed webhooks"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.retry_job_id = "webhook_retry_job"
        self.cleanup_job_id = "webhook_cleanup_job"
        
    def start(self):
        """Start the webhook retry scheduler"""
        if self.is_running:
            logger.warning("Webhook retry scheduler already running")
            return
            
        try:
            # Add retry job
            self.scheduler.add_job(
                func=self._retry_webhooks_task,
                trigger=IntervalTrigger(minutes=settings.WEBHOOK_RETRY_SCHEDULER_INTERVAL_MINUTES),
                id=self.retry_job_id,
                name="Webhook Retry Task",
                replace_existing=True,
                max_instances=1
            )
            
            # Add cleanup job
            self.scheduler.add_job(
                func=self._cleanup_old_webhooks_task,
                trigger=IntervalTrigger(hours=settings.WEBHOOK_CLEANUP_INTERVAL_HOURS),
                id=self.cleanup_job_id,
                name="Webhook Cleanup Task",
                replace_existing=True,
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Webhook retry scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start webhook retry scheduler: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
            
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Webhook retry scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping webhook retry scheduler: {e}", exc_info=True)
    
    async def _retry_webhooks_task(self):
        """Task to retry failed webhooks"""
        db = next(get_db())
        try:
            service = ExternalPOSWebhookService(db)
            
            # Get webhooks that need retry
            retry_webhooks = db.query(ExternalPOSWebhookEvent).filter(
                ExternalPOSWebhookEvent.processing_status == WebhookProcessingStatus.RETRY,
                ExternalPOSWebhookEvent.processing_attempts < settings.WEBHOOK_MAX_RETRY_ATTEMPTS
            ).order_by(
                ExternalPOSWebhookEvent.created_at.asc()
            ).limit(settings.WEBHOOK_RETRY_BATCH_SIZE).all()
            
            if not retry_webhooks:
                logger.debug("No webhooks to retry")
                return
                
            logger.info(f"Found {len(retry_webhooks)} webhooks to retry")
            
            success_count = 0
            failure_count = 0
            
            for webhook in retry_webhooks:
                try:
                    # Add exponential backoff
                    minutes_since_last_attempt = (
                        datetime.utcnow() - webhook.updated_at
                    ).total_seconds() / 60
                    
                    # Wait at least 2^attempt minutes between retries
                    min_wait_minutes = 2 ** (webhook.processing_attempts - 1)
                    
                    if minutes_since_last_attempt < min_wait_minutes:
                        logger.debug(
                            f"Skipping webhook {webhook.id}, "
                            f"waiting {min_wait_minutes - minutes_since_last_attempt:.1f} more minutes"
                        )
                        continue
                        
                    success = await service.process_webhook_event(webhook.id)
                    
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                        
                except Exception as e:
                    logger.error(
                        f"Error retrying webhook {webhook.id}: {str(e)}",
                        exc_info=True
                    )
                    failure_count += 1
                    
            logger.info(
                f"Webhook retry complete: {success_count} succeeded, "
                f"{failure_count} failed"
            )
            
        except Exception as e:
            logger.error(f"Error in webhook retry task: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    async def _cleanup_old_webhooks_task(self):
        """Clean up old processed webhooks"""
        db = next(get_db())
        try:
            # Keep webhooks for configured retention period
            cutoff_date = datetime.utcnow() - timedelta(days=settings.WEBHOOK_RETENTION_DAYS)
            
            # Delete old processed webhooks with batch limit
            deleted_count = db.query(ExternalPOSWebhookEvent).filter(
                ExternalPOSWebhookEvent.processing_status.in_([
                    WebhookProcessingStatus.PROCESSED,
                    WebhookProcessingStatus.DUPLICATE,
                    WebhookProcessingStatus.IGNORED
                ]),
                ExternalPOSWebhookEvent.created_at < cutoff_date
            ).limit(settings.WEBHOOK_CLEANUP_MAX_DELETE_BATCH).delete(synchronize_session='fetch')
            
            db.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old webhook events")
                
        except Exception as e:
            logger.error(f"Error cleaning up webhooks: {str(e)}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def trigger_immediate_retry(self) -> bool:
        """Trigger an immediate retry of failed webhooks"""
        if not self.is_running:
            logger.warning("Scheduler not running")
            return False
            
        try:
            self.scheduler.add_job(
                func=self._retry_webhooks_task,
                id=f"immediate_retry_{datetime.utcnow().timestamp()}",
                name="Immediate Webhook Retry",
                run_date=datetime.now()
            )
            logger.info("Immediate webhook retry triggered")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger immediate retry: {str(e)}")
            return False
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        if not self.is_running:
            return {
                "scheduler_running": False,
                "jobs": []
            }
            
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
            })
            
        return {
            "scheduler_running": True,
            "jobs": jobs
        }


# Global scheduler instance
webhook_retry_scheduler = WebhookRetryScheduler()


# Startup and shutdown functions
async def start_webhook_retry_scheduler():
    """Start the webhook retry scheduler on app startup"""
    try:
        webhook_retry_scheduler.start()
        logger.info("Webhook retry scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to start webhook retry scheduler: {e}", exc_info=True)
        # Don't fail startup if scheduler fails


async def stop_webhook_retry_scheduler():
    """Stop the webhook retry scheduler on app shutdown"""
    try:
        webhook_retry_scheduler.stop()
        logger.info("Webhook retry scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping webhook retry scheduler: {e}", exc_info=True)