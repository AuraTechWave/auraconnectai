# backend/modules/payments/services/split_bill_notification_queue.py

import logging
from typing import Dict, Any, List
from datetime import datetime
import json
from arq import create_pool
from arq.connections import RedisSettings

from core.config import settings
from ...notifications.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class SplitBillNotificationQueue:
    """
    Queue service for asynchronous split bill notifications
    """
    
    def __init__(self):
        self.redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    
    async def queue_participant_invitation(
        self,
        participant_data: Dict[str, Any],
        split_data: Dict[str, Any],
        priority: int = 5
    ) -> str:
        """Queue invitation email for a participant"""
        
        job_data = {
            'type': 'participant_invitation',
            'participant': participant_data,
            'split': split_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        pool = await create_pool(self.redis_settings)
        try:
            job = await pool.enqueue_job(
                'send_split_bill_notification',
                job_data,
                _job_try=3,  # Retry up to 3 times
                _queue_name='notifications',
                _defer_by=0,  # Send immediately
                _priority=priority
            )
            
            logger.info(f"Queued invitation for {participant_data.get('email')} - Job ID: {job.job_id}")
            return job.job_id
            
        finally:
            await pool.close()
    
    async def queue_bulk_invitations(
        self,
        participants: List[Dict[str, Any]],
        split_data: Dict[str, Any]
    ) -> List[str]:
        """Queue multiple invitation emails"""
        
        job_ids = []
        pool = await create_pool(self.redis_settings)
        
        try:
            for participant in participants:
                if participant.get('notify_via_email') and participant.get('email'):
                    job_data = {
                        'type': 'participant_invitation',
                        'participant': participant,
                        'split': split_data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    job = await pool.enqueue_job(
                        'send_split_bill_notification',
                        job_data,
                        _job_try=3,
                        _queue_name='notifications',
                        _defer_by=0
                    )
                    job_ids.append(job.job_id)
            
            logger.info(f"Queued {len(job_ids)} invitation emails")
            return job_ids
            
        finally:
            await pool.close()
    
    async def queue_status_update(
        self,
        organizer_email: str,
        participant_name: str,
        status: str,
        reason: str = None
    ) -> str:
        """Queue status update notification"""
        
        job_data = {
            'type': 'status_update',
            'organizer_email': organizer_email,
            'participant_name': participant_name,
            'status': status,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        pool = await create_pool(self.redis_settings)
        try:
            job = await pool.enqueue_job(
                'send_split_bill_notification',
                job_data,
                _job_try=3,
                _queue_name='notifications',
                _defer_by=0
            )
            
            return job.job_id
            
        finally:
            await pool.close()
    
    async def queue_payment_received(
        self,
        organizer_data: Dict[str, Any],
        participant_data: Dict[str, Any],
        amount: float
    ) -> str:
        """Queue payment received notification"""
        
        job_data = {
            'type': 'payment_received',
            'organizer': organizer_data,
            'participant': participant_data,
            'amount': amount,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        pool = await create_pool(self.redis_settings)
        try:
            job = await pool.enqueue_job(
                'send_split_bill_notification',
                job_data,
                _job_try=3,
                _queue_name='notifications',
                _defer_by=0,
                _priority=3  # Higher priority for payment notifications
            )
            
            return job.job_id
            
        finally:
            await pool.close()
    
    async def queue_payment_reminder(
        self,
        participant_data: Dict[str, Any],
        amount_due: float,
        access_link: str
    ) -> str:
        """Queue payment reminder"""
        
        job_data = {
            'type': 'payment_reminder',
            'participant': participant_data,
            'amount_due': amount_due,
            'access_link': access_link,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        pool = await create_pool(self.redis_settings)
        try:
            job = await pool.enqueue_job(
                'send_split_bill_notification',
                job_data,
                _job_try=3,
                _queue_name='notifications',
                _defer_by=0
            )
            
            return job.job_id
            
        finally:
            await pool.close()
    
    async def queue_split_cancelled(
        self,
        participants: List[Dict[str, Any]],
        organizer_name: str
    ) -> List[str]:
        """Queue cancellation notifications"""
        
        job_ids = []
        pool = await create_pool(self.redis_settings)
        
        try:
            for participant in participants:
                if participant.get('notify_via_email') and participant.get('email'):
                    job_data = {
                        'type': 'split_cancelled',
                        'participant': participant,
                        'organizer_name': organizer_name,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    job = await pool.enqueue_job(
                        'send_split_bill_notification',
                        job_data,
                        _job_try=3,
                        _queue_name='notifications',
                        _defer_by=0
                    )
                    job_ids.append(job.job_id)
            
            return job_ids
            
        finally:
            await pool.close()


# Worker function to process notifications
async def send_split_bill_notification(ctx: Dict[str, Any], job_data: Dict[str, Any]):
    """
    Worker function to process split bill notifications
    
    This function is called by the Arq worker to process queued notifications
    """
    
    notification_type = job_data.get('type')
    
    try:
        if notification_type == 'participant_invitation':
            participant = job_data['participant']
            split = job_data['split']
            
            await notification_service.send_email(
                to_email=participant['email'],
                subject=f"You've been invited to split a bill",
                template="split_bill_invitation",
                context={
                    'participant_name': participant['name'],
                    'organizer_name': split['organizer_name'],
                    'total_amount': str(participant['total_amount']),
                    'share_amount': str(participant['share_amount']),
                    'tip_amount': str(participant['tip_amount']),
                    'access_link': f"/split/{participant['access_token']}"
                }
            )
            
        elif notification_type == 'status_update':
            await notification_service.send_email(
                to_email=job_data['organizer_email'],
                subject=f"{job_data['participant_name']} has {job_data['status']} the bill split",
                template="split_status_update",
                context={
                    'participant_name': job_data['participant_name'],
                    'status': job_data['status'],
                    'reason': job_data.get('reason')
                }
            )
            
        elif notification_type == 'payment_received':
            organizer = job_data['organizer']
            participant = job_data['participant']
            
            await notification_service.send_email(
                to_email=organizer['email'],
                subject=f"Payment received from {participant['name']}",
                template="split_payment_received",
                context={
                    'organizer_name': organizer['name'],
                    'participant_name': participant['name'],
                    'amount': str(job_data['amount']),
                    'remaining': str(participant.get('remaining_amount', 0))
                }
            )
            
        elif notification_type == 'payment_reminder':
            participant = job_data['participant']
            
            await notification_service.send_email(
                to_email=participant['email'],
                subject="Reminder: Payment pending for bill split",
                template="split_payment_reminder",
                context={
                    'participant_name': participant['name'],
                    'amount_due': str(job_data['amount_due']),
                    'access_link': job_data['access_link']
                }
            )
            
        elif notification_type == 'split_cancelled':
            participant = job_data['participant']
            
            await notification_service.send_email(
                to_email=participant['email'],
                subject="Bill split has been cancelled",
                template="split_cancelled",
                context={
                    'participant_name': participant['name'],
                    'organizer_name': job_data['organizer_name']
                }
            )
            
        logger.info(f"Successfully processed {notification_type} notification")
        
    except Exception as e:
        logger.error(f"Failed to process {notification_type} notification: {e}")
        raise  # Re-raise to trigger retry


# Arq worker configuration
def get_worker_settings():
    """Get Arq worker settings for split bill notifications"""
    return {
        'functions': [send_split_bill_notification],
        'redis_settings': RedisSettings.from_dsn(settings.REDIS_URL),
        'queue_name': 'notifications',
        'max_jobs': 10,
        'job_timeout': 30,
    }


# Global instance
split_bill_notification_queue = SplitBillNotificationQueue()