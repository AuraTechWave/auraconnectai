# backend/workers/notification_worker.py

import asyncio
import logging
from datetime import datetime, timedelta
from arq import cron
from arq.connections import RedisSettings

from core.database import get_db, SessionLocal
from core.config_validation import config
from modules.orders.services.notification_retry_service import (
    NotificationRetryService, NotificationHealthChecker
)
from modules.orders.services.notification_metrics import NotificationMetrics


logger = logging.getLogger(__name__)


class NotificationWorker:
    """Background worker for notification processing using Arq"""
    
    @staticmethod
    async def process_retry_queue(ctx: dict) -> dict:
        """
        Process notification retry queue
        
        This runs every minute to retry failed notifications
        """
        start_time = datetime.utcnow()
        processed = 0
        errors = 0
        
        # Create a database session with proper cleanup
        # Using SessionLocal directly ensures we have full control over the session lifecycle
        db = SessionLocal()
        try:
            retry_service = NotificationRetryService(db)
            
            # Get retry stats before processing
            stats_before = retry_service.get_retry_stats()
            
            # Process retries
            await retry_service.process_retry_queue(batch_size=100)
            
            # Get stats after processing
            stats_after = retry_service.get_retry_stats()
            
            processed = stats_before["pending"] - stats_after["pending"]
            
            # Update metrics
            metrics = NotificationMetrics()
            metrics.set_retry_queue_length(stats_after["pending"])
            metrics.record_retry_batch_processed(processed)
            
            logger.info(f"Processed {processed} notification retries")
        except Exception as e:
            logger.error(f"Error processing retry queue: {e}")
            errors += 1
            
            # Record error metric
            metrics = NotificationMetrics()
            metrics.increment_worker_errors("retry_processor")
        finally:
            # Ensure the session is properly closed
            db.close()
        
        return {
            "task": "process_retry_queue",
            "processed": processed,
            "errors": errors,
            "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }
    
    @staticmethod
    async def check_notification_health(ctx: dict) -> dict:
        """
        Check health of notification channels
        
        This runs every 5 minutes to monitor channel availability
        """
        start_time = datetime.utcnow()
        channels_checked = 0
        healthy_channels = 0
        
        # Create a database session with proper cleanup
        # Using SessionLocal directly ensures we have full control over the session lifecycle
        db = SessionLocal()
        try:
            health_checker = NotificationHealthChecker(db)
            
            # Get all channels
            from modules.orders.models.notification_config_models import NotificationChannelConfig
            channels = db.query(NotificationChannelConfig).filter(
                NotificationChannelConfig.is_enabled == True
            ).all()
            
            channels_checked = len(channels)
            
            # Check each channel
            for channel in channels:
                await health_checker.check_channel_health(channel)
                if channel.health_check_status == "healthy":
                    healthy_channels += 1
            
            # Update metrics
            metrics = NotificationMetrics()
            metrics.set_healthy_channels(healthy_channels)
            metrics.set_total_channels(channels_checked)
            
            logger.info(f"Health check complete: {healthy_channels}/{channels_checked} channels healthy")
        except Exception as e:
            logger.error(f"Error checking notification health: {e}")
            
            # Record error metric
            metrics = NotificationMetrics()
            metrics.increment_worker_errors("health_checker")
        finally:
            # Ensure the session is properly closed
            db.close()
        
        return {
            "task": "check_notification_health",
            "channels_checked": channels_checked,
            "healthy_channels": healthy_channels,
            "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }
    
    @staticmethod
    async def cleanup_old_notifications(ctx: dict) -> dict:
        """
        Clean up old notification records
        
        This runs daily to remove old retry records and stats
        """
        start_time = datetime.utcnow()
        deleted_retries = 0
        deleted_stats = 0
        
        # Create a database session with proper cleanup
        # Using SessionLocal directly ensures we have full control over the session lifecycle
        db = SessionLocal()
        try:
            retry_service = NotificationRetryService(db)
            
            # Clean up old retries (older than 7 days)
            await retry_service.cleanup_old_retries(days_to_keep=7)
            
            # Clean up old stats (older than 30 days)
            from modules.orders.models.notification_config_models import NotificationChannelStats
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            deleted_stats = db.query(NotificationChannelStats).filter(
                NotificationChannelStats.stat_date < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleanup complete: {deleted_retries} retries, {deleted_stats} stats removed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            # Ensure the session is properly closed
            db.close()
        
        return {
            "task": "cleanup_old_notifications",
            "deleted_retries": deleted_retries,
            "deleted_stats": deleted_stats,
            "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }
    
    @staticmethod
    async def collect_notification_stats(ctx: dict) -> dict:
        """
        Collect notification statistics
        
        This runs every hour to aggregate notification metrics
        """
        start_time = datetime.utcnow()
        
        # Create a database session with proper cleanup
        # Using SessionLocal directly ensures we have full control over the session lifecycle
        db = SessionLocal()
        try:
            # Aggregate stats for the last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            from modules.orders.models.order_tracking_models import OrderNotification
            from modules.orders.models.notification_config_models import NotificationChannelStats
            from sqlalchemy import func
            
            # Get stats by channel
            stats = db.query(
                OrderNotification.channel,
                func.count(OrderNotification.id).label('total'),
                func.count(OrderNotification.delivered_at).label('delivered'),
                func.count(OrderNotification.failed_at).label('failed')
            ).filter(
                OrderNotification.created_at >= hour_ago
            ).group_by(OrderNotification.channel).all()
            
            # Save to stats table
            current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            
            for stat in stats:
                channel_stat = NotificationChannelStats(
                    channel_name=stat.channel.value,
                    stat_date=current_hour,
                    stat_hour=current_hour.hour,
                    total_sent=stat.total,
                    total_delivered=stat.delivered,
                    total_failed=stat.failed,
                    total_retried=0  # Would need to track this separately
                )
                db.add(channel_stat)
            
            db.commit()
            
            # Update metrics
            metrics = NotificationMetrics()
            for stat in stats:
                metrics.record_notification_stats(
                    channel=stat.channel.value,
                    sent=stat.total,
                    delivered=stat.delivered,
                    failed=stat.failed
                )
            
            logger.info(f"Collected stats for {len(stats)} channels")
        except Exception as e:
            logger.error(f"Error collecting stats: {e}")
        finally:
            # Ensure the session is properly closed
            db.close()
        
        return {
            "task": "collect_notification_stats",
            "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }


# Arq worker configuration
async def startup(ctx):
    """Initialize worker context"""
    logger.info("Notification worker starting up")
    
    # Initialize any shared resources
    ctx['start_time'] = datetime.utcnow()


async def shutdown(ctx):
    """Cleanup worker context"""
    logger.info("Notification worker shutting down")


# Get Redis URL from centralized config with production validation
def get_redis_dsn():
    """Get Redis DSN from centralized configuration.
    
    This ensures consistency with the main application's Redis configuration
    and respects production environment requirements.
    """
    if config.REDIS_URL:
        return config.REDIS_URL
    
    # In production, config validation would have already failed if REDIS_URL is missing
    # This fallback is only for development environments
    if config.ENVIRONMENT != "production":
        default_url = "redis://localhost:6379"
        logger.warning(
            "REDIS_URL not configured, using default %s (development only)",
            default_url
        )
        return default_url
    
    # This should never be reached due to config validation
    raise ValueError("REDIS_URL is required but not configured")


# Worker settings
WorkerSettings = {
    'redis_settings': RedisSettings.from_dsn(get_redis_dsn()),
    'max_jobs': 10,
    'job_timeout': 300,  # 5 minutes
    'keep_result': 3600,  # Keep results for 1 hour
    'functions': [
        NotificationWorker.process_retry_queue,
        NotificationWorker.check_notification_health,
        NotificationWorker.cleanup_old_notifications,
        NotificationWorker.collect_notification_stats,
    ],
    'cron_jobs': [
        # Process retry queue every minute
        cron(NotificationWorker.process_retry_queue, minute='*'),
        
        # Check health every 5 minutes
        cron(NotificationWorker.check_notification_health, minute='*/5'),
        
        # Collect stats every hour
        cron(NotificationWorker.collect_notification_stats, minute=0),
        
        # Cleanup daily at 2 AM
        cron(NotificationWorker.cleanup_old_notifications, hour=2, minute=0),
    ],
    'on_startup': startup,
    'on_shutdown': shutdown,
}


# For running the worker
if __name__ == '__main__':
    from arq import run_worker
    run_worker(WorkerSettings)