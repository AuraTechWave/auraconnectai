# backend/modules/sms/services/delivery_tracking_service.py

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.sms.models.sms_models import SMSMessage, SMSStatus, SMSProvider
from modules.sms.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class DeliveryTrackingService:
    """Service for tracking SMS delivery status"""
    
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
    
    async def update_delivery_status(
        self,
        provider_message_id: str,
        status: SMSStatus,
        delivered_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[SMSMessage]:
        """
        Update delivery status from webhook
        
        Args:
            provider_message_id: Provider's message ID
            status: New delivery status
            delivered_at: Delivery timestamp
            failed_at: Failure timestamp
            error_code: Error code if failed
            error_message: Error message if failed
        
        Returns:
            Updated message or None
        """
        message = self.db.query(SMSMessage).filter(
            SMSMessage.provider_message_id == provider_message_id
        ).first()
        
        if not message:
            logger.warning(f"Message not found for provider ID: {provider_message_id}")
            return None
        
        # Update status
        message.status = status
        
        if delivered_at:
            message.delivered_at = delivered_at
        
        if failed_at:
            message.failed_at = failed_at
        
        if error_code or error_message:
            error_info = message.provider_response or {}
            error_info['error_code'] = error_code
            error_info['error_message'] = error_message
            message.provider_response = error_info
            message.provider_error = error_message
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"Updated delivery status for message {message.id}: {status.value}")
        
        # Trigger any callbacks or notifications
        await self._handle_status_update(message)
        
        return message
    
    async def check_pending_deliveries(self) -> int:
        """
        Check and update status for pending messages
        
        Returns:
            Number of messages updated
        """
        # Get messages that are sent but not yet delivered/failed
        pending_messages = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.status.in_([SMSStatus.SENT, SMSStatus.SENDING]),
                SMSMessage.provider_message_id.isnot(None),
                SMSMessage.sent_at < datetime.utcnow() - timedelta(minutes=5)  # At least 5 minutes old
            )
        ).limit(100).all()
        
        updated_count = 0
        
        for message in pending_messages:
            try:
                # Query provider for status
                if message.provider == SMSProvider.TWILIO:
                    status_info = self.twilio_service.get_message_status(message.provider_message_id)
                    
                    if status_info['success']:
                        new_status = status_info['status']
                        
                        if new_status != message.status:
                            await self.update_delivery_status(
                                provider_message_id=message.provider_message_id,
                                status=new_status,
                                delivered_at=status_info.get('delivered_at'),
                                error_code=status_info.get('error_code'),
                                error_message=status_info.get('error_message')
                            )
                            updated_count += 1
                
            except Exception as e:
                logger.error(f"Error checking status for message {message.id}: {str(e)}")
        
        logger.info(f"Updated {updated_count} pending message statuses")
        return updated_count
    
    async def handle_webhook(
        self,
        provider: SMSProvider,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle delivery status webhook from provider
        
        Args:
            provider: SMS provider
            webhook_data: Webhook payload
        
        Returns:
            Processing result
        """
        try:
            if provider == SMSProvider.TWILIO:
                result = self.twilio_service.handle_webhook(webhook_data)
                
                if 'provider_message_id' in result:
                    message = await self.update_delivery_status(
                        provider_message_id=result['provider_message_id'],
                        status=result.get('status', SMSStatus.SENT),
                        delivered_at=result.get('delivered_at'),
                        failed_at=result.get('failed_at'),
                        error_code=result.get('error_code'),
                        error_message=result.get('error_message')
                    )
                    
                    return {
                        'success': True,
                        'message_id': message.id if message else None,
                        'status': result.get('status', SMSStatus.SENT).value
                    }
            
            return {'success': False, 'error': 'Unsupported provider'}
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _handle_status_update(self, message: SMSMessage):
        """
        Handle internal actions based on status update
        
        Args:
            message: Updated SMS message
        """
        # If message failed and has retries left, schedule retry
        if message.status == SMSStatus.FAILED and message.retry_count < 3:
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=5 * (message.retry_count + 1)
            )
            self.db.commit()
            logger.info(f"Scheduled retry for message {message.id} at {message.next_retry_at}")
        
        # If message is related to a reservation, update reservation status
        if message.reservation_id and message.status == SMSStatus.DELIVERED:
            # This would integrate with reservation service
            logger.info(f"SMS delivered for reservation {message.reservation_id}")
        
        # If message is marketing and bounced, auto opt-out
        if message.status == SMSStatus.BOUNCED:
            from modules.sms.services.opt_out_service import OptOutService
            opt_out_service = OptOutService(self.db)
            opt_out_service.process_opt_out(
                phone_number=message.to_number,
                reason='Message bounced',
                method='system'
            )
            logger.info(f"Auto opted-out {message.to_number} due to bounce")
    
    def get_delivery_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        provider: Optional[SMSProvider] = None
    ) -> Dict[str, Any]:
        """
        Get delivery metrics for a period
        
        Args:
            start_date: Start of period
            end_date: End of period
            provider: Specific provider (None for all)
        
        Returns:
            Delivery metrics
        """
        query = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.created_at >= start_date,
                SMSMessage.created_at <= end_date
            )
        )
        
        if provider:
            query = query.filter(SMSMessage.provider == provider)
        
        messages = query.all()
        
        total_messages = len(messages)
        
        # Status breakdown
        status_counts = {}
        for status in SMSStatus:
            count = sum(1 for m in messages if m.status == status)
            status_counts[status.value] = count
        
        # Calculate delivery rate
        delivered = status_counts.get(SMSStatus.DELIVERED.value, 0)
        delivery_rate = (delivered / total_messages * 100) if total_messages > 0 else 0
        
        # Calculate average delivery time
        delivery_times = []
        for message in messages:
            if message.sent_at and message.delivered_at:
                delivery_time = (message.delivered_at - message.sent_at).total_seconds()
                delivery_times.append(delivery_time)
        
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        
        # Failure analysis
        failed_messages = [m for m in messages if m.status in [SMSStatus.FAILED, SMSStatus.UNDELIVERED]]
        failure_reasons = {}
        for message in failed_messages:
            if message.provider_response and 'error_code' in message.provider_response:
                error_code = message.provider_response['error_code']
                failure_reasons[error_code] = failure_reasons.get(error_code, 0) + 1
        
        # Retry statistics
        retried_messages = [m for m in messages if m.retry_count > 0]
        successful_retries = sum(1 for m in retried_messages if m.status == SMSStatus.DELIVERED)
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_messages': total_messages,
            'status_breakdown': status_counts,
            'delivery_rate': delivery_rate,
            'average_delivery_time_seconds': avg_delivery_time,
            'failure_analysis': {
                'total_failed': len(failed_messages),
                'failure_rate': (len(failed_messages) / total_messages * 100) if total_messages > 0 else 0,
                'failure_reasons': failure_reasons
            },
            'retry_statistics': {
                'messages_retried': len(retried_messages),
                'successful_retries': successful_retries,
                'retry_success_rate': (successful_retries / len(retried_messages) * 100) if retried_messages else 0
            }
        }
    
    def get_real_time_status(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get real-time status of recent messages
        
        Args:
            limit: Maximum number of messages to return
        
        Returns:
            List of recent message statuses
        """
        recent_messages = self.db.query(SMSMessage).order_by(
            SMSMessage.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                'id': message.id,
                'to_number': message.to_number[-4:] if message.to_number else None,  # Last 4 digits for privacy
                'status': message.status.value,
                'created_at': message.created_at.isoformat(),
                'sent_at': message.sent_at.isoformat() if message.sent_at else None,
                'delivered_at': message.delivered_at.isoformat() if message.delivered_at else None,
                'segments': message.segments_count,
                'cost': message.cost_amount,
                'retry_count': message.retry_count
            }
            for message in recent_messages
        ]