# backend/modules/sms/services/sms_service.py

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.sms.models.sms_models import (
    SMSMessage, SMSTemplate, SMSOptOut, SMSStatus, 
    SMSProvider, SMSDirection, SMSTemplateCategory
)
from modules.sms.schemas.sms_schemas import (
    SMSMessageCreate, SMSSendRequest, SMSBulkSendRequest
)
from modules.sms.services.twilio_service import TwilioService
from modules.sms.services.template_service import SMSTemplateService
from modules.sms.services.opt_out_service import OptOutService
from modules.sms.services.cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)


class SMSService:
    """Main service for sending and managing SMS messages"""
    
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.template_service = SMSTemplateService(db)
        self.opt_out_service = OptOutService(db)
        self.cost_tracking = CostTrackingService(db)
        self.max_retry_attempts = 3
        self.retry_delay_minutes = 5
    
    async def send_sms(
        self,
        request: SMSSendRequest,
        user_id: Optional[int] = None
    ) -> SMSMessage:
        """
        Send a single SMS message
        
        Args:
            request: SMS send request data
            user_id: ID of the user sending the message
        
        Returns:
            Created SMSMessage record
        """
        # Check opt-out status
        if self.opt_out_service.is_opted_out(request.to_number):
            logger.warning(f"Cannot send SMS to {request.to_number} - user opted out")
            raise ValueError("Recipient has opted out of SMS messages")
        
        # Prepare message body
        if request.template_id:
            message_body = self.template_service.render_template(
                request.template_id,
                request.template_variables or {}
            )
        else:
            message_body = request.message
        
        if not message_body:
            raise ValueError("Message body cannot be empty")
        
        # Create database record
        sms_message = SMSMessage(
            provider=SMSProvider.TWILIO,
            direction=SMSDirection.OUTBOUND,
            status=SMSStatus.QUEUED,
            from_number=self.twilio_service.from_number,
            to_number=request.to_number,
            message_body=message_body,
            template_id=request.template_id,
            template_variables=request.template_variables,
            customer_id=request.customer_id,
            order_id=request.order_id,
            reservation_id=request.reservation_id,
            created_by=user_id
        )
        
        self.db.add(sms_message)
        self.db.commit()
        
        # Schedule or send immediately
        if request.schedule_at and request.schedule_at > datetime.utcnow():
            sms_message.metadata = {'scheduled_at': request.schedule_at.isoformat()}
            self.db.commit()
            logger.info(f"SMS scheduled for {request.schedule_at}: ID {sms_message.id}")
        else:
            await self._send_message(sms_message)
        
        return sms_message
    
    async def send_bulk_sms(
        self,
        request: SMSBulkSendRequest,
        user_id: Optional[int] = None
    ) -> List[SMSMessage]:
        """
        Send bulk SMS messages
        
        Args:
            request: Bulk SMS send request
            user_id: ID of the user sending messages
        
        Returns:
            List of created SMSMessage records
        """
        messages = []
        
        for recipient_request in request.recipients:
            try:
                message = await self.send_sms(recipient_request, user_id)
                messages.append(message)
            except Exception as e:
                logger.error(f"Failed to send SMS to {recipient_request.to_number}: {str(e)}")
                # Continue with other messages
        
        return messages
    
    async def _send_message(self, sms_message: SMSMessage) -> None:
        """
        Internal method to send message via provider
        
        Args:
            sms_message: SMS message to send
        """
        try:
            # Update status to sending
            sms_message.status = SMSStatus.SENDING
            self.db.commit()
            
            # Send via Twilio
            result = self.twilio_service.send_sms(
                to_number=sms_message.to_number,
                message_body=sms_message.message_body,
                from_number=sms_message.from_number
            )
            
            if result['success']:
                sms_message.status = result['status']
                sms_message.provider_message_id = result['provider_message_id']
                sms_message.segments_count = result.get('segments_count', 1)
                sms_message.cost_amount = result.get('cost_amount')
                sms_message.cost_currency = result.get('cost_currency', 'USD')
                sms_message.sent_at = result.get('sent_at', datetime.utcnow())
                sms_message.provider_response = result.get('provider_response')
                
                # Track cost
                if sms_message.cost_amount:
                    await self.cost_tracking.track_message_cost(sms_message)
                
            else:
                sms_message.status = SMSStatus.FAILED
                sms_message.provider_error = result.get('error')
                sms_message.failed_at = datetime.utcnow()
                
                # Schedule retry if applicable
                if sms_message.retry_count < self.max_retry_attempts:
                    sms_message.retry_count += 1
                    sms_message.next_retry_at = datetime.utcnow() + timedelta(
                        minutes=self.retry_delay_minutes * sms_message.retry_count
                    )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error sending SMS {sms_message.id}: {str(e)}")
            sms_message.status = SMSStatus.FAILED
            sms_message.provider_error = str(e)
            sms_message.failed_at = datetime.utcnow()
            self.db.commit()
    
    async def retry_failed_messages(self) -> int:
        """
        Retry failed messages that are scheduled for retry
        
        Returns:
            Number of messages retried
        """
        messages_to_retry = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.status == SMSStatus.FAILED,
                SMSMessage.retry_count < self.max_retry_attempts,
                SMSMessage.next_retry_at <= datetime.utcnow()
            )
        ).all()
        
        count = 0
        for message in messages_to_retry:
            await self._send_message(message)
            count += 1
        
        logger.info(f"Retried {count} failed messages")
        return count
    
    async def process_scheduled_messages(self) -> int:
        """
        Process messages scheduled for sending
        
        Returns:
            Number of messages processed
        """
        scheduled_messages = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.status == SMSStatus.QUEUED,
                SMSMessage.metadata['scheduled_at'].astext <= datetime.utcnow().isoformat()
            )
        ).all()
        
        count = 0
        for message in scheduled_messages:
            await self._send_message(message)
            count += 1
        
        logger.info(f"Processed {count} scheduled messages")
        return count
    
    def update_message_status(
        self,
        provider_message_id: str,
        status: SMSStatus,
        delivered_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> Optional[SMSMessage]:
        """
        Update message status from webhook callback
        
        Args:
            provider_message_id: Provider's message ID
            status: New status
            delivered_at: Delivery timestamp
            failed_at: Failure timestamp
            error_message: Error message if failed
        
        Returns:
            Updated SMSMessage or None if not found
        """
        message = self.db.query(SMSMessage).filter(
            SMSMessage.provider_message_id == provider_message_id
        ).first()
        
        if not message:
            logger.warning(f"Message not found for provider ID: {provider_message_id}")
            return None
        
        message.status = status
        
        if delivered_at:
            message.delivered_at = delivered_at
        
        if failed_at:
            message.failed_at = failed_at
        
        if error_message:
            message.provider_error = error_message
        
        self.db.commit()
        logger.info(f"Updated status for message {message.id} to {status}")
        
        return message
    
    def get_message_history(
        self,
        customer_id: Optional[int] = None,
        phone_number: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[SMSStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SMSMessage]:
        """
        Get message history with filters
        
        Args:
            customer_id: Filter by customer
            phone_number: Filter by phone number
            start_date: Filter messages after this date
            end_date: Filter messages before this date
            status: Filter by status
            limit: Maximum number of results
            offset: Pagination offset
        
        Returns:
            List of SMS messages
        """
        query = self.db.query(SMSMessage)
        
        if customer_id:
            query = query.filter(SMSMessage.customer_id == customer_id)
        
        if phone_number:
            query = query.filter(
                or_(
                    SMSMessage.to_number == phone_number,
                    SMSMessage.from_number == phone_number
                )
            )
        
        if start_date:
            query = query.filter(SMSMessage.created_at >= start_date)
        
        if end_date:
            query = query.filter(SMSMessage.created_at <= end_date)
        
        if status:
            query = query.filter(SMSMessage.status == status)
        
        return query.order_by(SMSMessage.created_at.desc()).offset(offset).limit(limit).all()
    
    def get_message_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get SMS statistics for a period
        
        Args:
            start_date: Start of period
            end_date: End of period
        
        Returns:
            Dictionary with statistics
        """
        messages = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.created_at >= start_date,
                SMSMessage.created_at <= end_date
            )
        ).all()
        
        total_messages = len(messages)
        delivered = sum(1 for m in messages if m.status == SMSStatus.DELIVERED)
        failed = sum(1 for m in messages if m.status == SMSStatus.FAILED)
        total_segments = sum(m.segments_count for m in messages)
        total_cost = sum(m.cost_amount or 0 for m in messages)
        
        return {
            'total_messages': total_messages,
            'delivered': delivered,
            'failed': failed,
            'delivery_rate': (delivered / total_messages * 100) if total_messages > 0 else 0,
            'total_segments': total_segments,
            'total_cost': total_cost,
            'average_cost_per_message': total_cost / total_messages if total_messages > 0 else 0,
            'by_status': {
                status.value: sum(1 for m in messages if m.status == status)
                for status in SMSStatus
            }
        }