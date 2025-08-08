# backend/modules/payments/services/webhook_queue_service.py

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from ..models.payment_models import PaymentWebhook, PaymentGateway
from .webhook_service import webhook_service


logger = logging.getLogger(__name__)


class WebhookQueueService:
    """
    Service for queuing and processing webhooks asynchronously
    """
    
    def __init__(self):
        self.redis_settings = RedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
        self._pool = None
    
    async def get_pool(self):
        """Get or create Redis pool for Arq"""
        if not self.redis_settings:
            return None
        if not self._pool:
            self._pool = await create_pool(self.redis_settings)
        return self._pool
    
    async def queue_webhook(
        self,
        gateway: PaymentGateway,
        headers: Dict[str, str],
        body: bytes,
        priority: int = 5
    ) -> str:
        """
        Queue a webhook for asynchronous processing
        
        Args:
            gateway: Payment gateway type
            headers: Webhook headers
            body: Raw webhook body
            priority: Job priority (1-10, lower is higher priority)
            
        Returns:
            Job ID
        """
        try:
            pool = await self.get_pool()
            if not pool:
                logger.warning("Redis not configured, processing webhook synchronously")
                # Fallback to synchronous processing
                return "sync-processing"
            
            # Create job data
            job_data = {
                'gateway': gateway.value,
                'headers': headers,
                'body': body.decode('utf-8') if isinstance(body, bytes) else body,
                'received_at': datetime.utcnow().isoformat()
            }
            
            # Queue the job with retry configuration
            job = await pool.enqueue_job(
                'process_payment_webhook',
                job_data,
                _job_ttl=3600,  # Keep job result for 1 hour
                _queue_name='payment_webhooks',
                _defer_by=timedelta(seconds=0),
                _job_try=1,
                _job_retry=3,  # Retry up to 3 times
                _retry_delay=60,  # Wait 60 seconds between retries
                _priority=priority
            )
            
            logger.info(f"Queued webhook for {gateway} with job ID: {job.job_id}")
            return job.job_id
            
        except Exception as e:
            logger.error(f"Failed to queue webhook: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a queued webhook job"""
        try:
            pool = await self.get_pool()
            if not pool:
                return None
            job = await pool.job(job_id)
            
            if not job:
                return None
            
            return {
                'job_id': job.job_id,
                'function': job.function,
                'status': job.status,
                'enqueue_time': job.enqueue_time,
                'start_time': job.start_time,
                'finish_time': job.finish_time,
                'result': job.result,
                'error': job.error
            }
            
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._pool:
            await self._pool.close()
            self._pool = None


# Global instance
webhook_queue_service = WebhookQueueService()


# Arq worker functions (these will be run by the worker process)

async def process_payment_webhook(ctx: dict, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a payment webhook in the background
    
    This function is called by the Arq worker
    """
    start_time = datetime.utcnow()
    
    try:
        # Extract data
        gateway = PaymentGateway(job_data['gateway'])
        headers = job_data['headers']
        body = job_data['body'].encode('utf-8') if isinstance(job_data['body'], str) else job_data['body']
        
        # Get database session
        async for db in get_db():
            try:
                # Process webhook
                result = await webhook_service.process_webhook(
                    db=db,
                    gateway=gateway,
                    headers=headers,
                    body=body
                )
                
                # Calculate processing time
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                return {
                    'status': 'success',
                    'result': result,
                    'processing_time': processing_time,
                    'processed_at': datetime.utcnow().isoformat()
                }
                
            finally:
                await db.close()
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'status': 'error',
            'error': str(e),
            'processing_time': processing_time,
            'processed_at': datetime.utcnow().isoformat()
        }


async def retry_failed_webhooks(ctx: dict) -> Dict[str, Any]:
    """
    Periodic task to retry failed webhooks
    
    This runs every 5 minutes to check for webhooks that need retry
    """
    retried_count = 0
    
    try:
        async for db in get_db():
            try:
                # Find webhooks that need retry
                from sqlalchemy import select, and_
                
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                
                result = await db.execute(
                    select(PaymentWebhook).where(
                        and_(
                            PaymentWebhook.processed == False,
                            PaymentWebhook.retry_count < 3,
                            PaymentWebhook.created_at < cutoff_time
                        )
                    ).limit(50)  # Process max 50 at a time
                )
                
                webhooks = result.scalars().all()
                
                for webhook in webhooks:
                    try:
                        # Re-queue the webhook
                        await webhook_queue_service.queue_webhook(
                            gateway=webhook.gateway,
                            headers=webhook.headers,
                            body=json.dumps(webhook.payload).encode('utf-8'),
                            priority=8  # Lower priority for retries
                        )
                        
                        # Update retry count
                        webhook.retry_count += 1
                        retried_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to retry webhook {webhook.id}: {e}")
                
                await db.commit()
                
            finally:
                await db.close()
        
        return {
            'status': 'success',
            'retried_count': retried_count,
            'processed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to retry webhooks: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'retried_count': retried_count
        }


# Worker configuration
WORKER_FUNCTIONS = [
    process_payment_webhook,
    retry_failed_webhooks
]

# Cron jobs configuration
CRON_JOBS = [
    {
        'func': retry_failed_webhooks,
        'cron': '*/5 * * * *',  # Every 5 minutes
        'unique': True,
        'timeout': 300  # 5 minute timeout
    }
]


def get_worker_settings():
    """Get Arq worker settings"""
    return {
        'redis_settings': RedisSettings.from_dsn(settings.redis_url),
        'max_jobs': 10,
        'job_timeout': 300,  # 5 minutes
        'keep_result': 3600,  # 1 hour
        'poll_delay': 0.5,
        'queue_read_limit': 10,
        'functions': WORKER_FUNCTIONS,
        'cron_jobs': CRON_JOBS,
        'on_startup': startup,
        'on_shutdown': shutdown,
        'retry_jobs': True,
        'max_tries': 3,
        'health_check_interval': 60,
        'health_check_key': 'arq:health:payment_webhooks'
    }


async def startup(ctx):
    """Worker startup function"""
    logger.info("Payment webhook worker starting up...")
    ctx['start_time'] = datetime.utcnow()


async def shutdown(ctx):
    """Worker shutdown function"""
    logger.info("Payment webhook worker shutting down...")
    if 'start_time' in ctx:
        uptime = datetime.utcnow() - ctx['start_time']
        logger.info(f"Worker uptime: {uptime}")