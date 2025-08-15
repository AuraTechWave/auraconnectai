# backend/modules/sms/services/twilio_service.py

import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.orm import Session

from modules.sms.models.sms_models import SMSMessage, SMSStatus, SMSProvider
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioService:
    """Service for interacting with Twilio SMS API"""
    
    def __init__(self):
        """Initialize Twilio client"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.messaging_service_sid = os.getenv('TWILIO_MESSAGING_SERVICE_SID')
        
        if not all([self.account_sid, self.auth_token]):
            logger.warning("Twilio credentials not configured")
            self.client = None
        else:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {str(e)}")
                self.client = None
    
    def send_sms(
        self,
        to_number: str,
        message_body: str,
        from_number: Optional[str] = None,
        media_url: Optional[List[str]] = None,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS message via Twilio
        
        Args:
            to_number: Recipient phone number in E.164 format
            message_body: Message content
            from_number: Sender phone number (optional, uses default if not provided)
            media_url: List of media URLs for MMS (optional)
            callback_url: Webhook URL for delivery status (optional)
        
        Returns:
            Dict containing message details and status
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not initialized',
                'status': SMSStatus.FAILED
            }
        
        try:
            # Determine sender
            sender = from_number or self.from_number
            if not sender and self.messaging_service_sid:
                sender = None  # Let messaging service handle it
            
            # Build message parameters
            message_params = {
                'body': message_body,
                'to': to_number
            }
            
            if self.messaging_service_sid and not from_number:
                message_params['messaging_service_sid'] = self.messaging_service_sid
            else:
                message_params['from_'] = sender
            
            if media_url:
                message_params['media_url'] = media_url
            
            if callback_url:
                message_params['status_callback'] = callback_url
            
            # Send message
            message = self.client.messages.create(**message_params)
            
            logger.info(f"SMS sent successfully to {to_number}, SID: {message.sid}")
            
            return {
                'success': True,
                'provider_message_id': message.sid,
                'status': self._map_twilio_status(message.status),
                'segments_count': message.num_segments or 1,
                'cost_amount': float(message.price) if message.price else None,
                'cost_currency': message.price_unit,
                'sent_at': message.date_sent or datetime.utcnow(),
                'from_number': message.from_,
                'to_number': message.to,
                'provider_response': {
                    'sid': message.sid,
                    'status': message.status,
                    'direction': message.direction,
                    'api_version': message.api_version
                }
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {to_number}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code,
                'status': SMSStatus.FAILED,
                'provider_error': e.msg
            }
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_number}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'status': SMSStatus.FAILED
            }
    
    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """
        Get the status of a sent message
        
        Args:
            message_sid: Twilio message SID
        
        Returns:
            Dict containing message status and details
        """
        if not self.client:
            return {'success': False, 'error': 'Twilio client not initialized'}
        
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'status': self._map_twilio_status(message.status),
                'delivered_at': message.date_sent,
                'segments_count': message.num_segments or 1,
                'cost_amount': float(message.price) if message.price else None,
                'cost_currency': message.price_unit,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except TwilioRestException as e:
            logger.error(f"Error fetching message status for {message_sid}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching message status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def list_messages(
        self,
        date_sent_after: Optional[datetime] = None,
        date_sent_before: Optional[datetime] = None,
        to_number: Optional[str] = None,
        from_number: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List messages from Twilio account
        
        Args:
            date_sent_after: Filter messages sent after this date
            date_sent_before: Filter messages sent before this date
            to_number: Filter by recipient number
            from_number: Filter by sender number
            limit: Maximum number of messages to return
        
        Returns:
            List of message dictionaries
        """
        if not self.client:
            return []
        
        try:
            filters = {}
            if date_sent_after:
                filters['date_sent_after'] = date_sent_after
            if date_sent_before:
                filters['date_sent_before'] = date_sent_before
            if to_number:
                filters['to'] = to_number
            if from_number:
                filters['from_'] = from_number
            
            messages = self.client.messages.list(limit=limit, **filters)
            
            return [
                {
                    'provider_message_id': msg.sid,
                    'status': self._map_twilio_status(msg.status),
                    'from_number': msg.from_,
                    'to_number': msg.to,
                    'message_body': msg.body,
                    'sent_at': msg.date_sent,
                    'segments_count': msg.num_segments or 1,
                    'cost_amount': float(msg.price) if msg.price else None,
                    'cost_currency': msg.price_unit,
                    'direction': msg.direction
                }
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Error listing messages: {str(e)}")
            return []
    
    def validate_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Validate a phone number using Twilio Lookup API
        
        Args:
            phone_number: Phone number to validate
        
        Returns:
            Dict containing validation results
        """
        if not self.client:
            return {'valid': False, 'error': 'Twilio client not initialized'}
        
        try:
            phone_info = self.client.lookups.v1.phone_numbers(phone_number).fetch()
            
            return {
                'valid': True,
                'formatted': phone_info.phone_number,
                'country_code': phone_info.country_code,
                'national_format': phone_info.national_format,
                'carrier': phone_info.carrier.get('name') if phone_info.carrier else None,
                'type': phone_info.carrier.get('type') if phone_info.carrier else None
            }
            
        except TwilioRestException as e:
            logger.error(f"Phone validation error for {phone_number}: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'error_code': e.code
            }
        except Exception as e:
            logger.error(f"Unexpected error validating phone number: {str(e)}")
            return {'valid': False, 'error': str(e)}
    
    def get_account_balance(self) -> Optional[float]:
        """Get current Twilio account balance"""
        if not self.client:
            return None
        
        try:
            balance = self.client.api.v2010.balance.fetch()
            return float(balance.balance)
        except Exception as e:
            logger.error(f"Error fetching account balance: {str(e)}")
            return None
    
    def get_usage_records(
        self,
        start_date: datetime,
        end_date: datetime,
        category: str = 'sms'
    ) -> List[Dict[str, Any]]:
        """
        Get usage records for billing period
        
        Args:
            start_date: Start of billing period
            end_date: End of billing period
            category: Usage category (default: 'sms')
        
        Returns:
            List of usage records
        """
        if not self.client:
            return []
        
        try:
            records = self.client.usage.records.list(
                start_date=start_date,
                end_date=end_date,
                category=category
            )
            
            return [
                {
                    'category': record.category,
                    'description': record.description,
                    'count': record.count,
                    'count_unit': record.count_unit,
                    'price': float(record.price) if record.price else 0,
                    'price_unit': record.price_unit,
                    'usage': record.usage,
                    'usage_unit': record.usage_unit,
                    'start_date': record.start_date,
                    'end_date': record.end_date
                }
                for record in records
            ]
            
        except Exception as e:
            logger.error(f"Error fetching usage records: {str(e)}")
            return []
    
    def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Twilio status callback webhook
        
        Args:
            webhook_data: Webhook payload from Twilio
        
        Returns:
            Processed status update
        """
        try:
            message_sid = webhook_data.get('MessageSid')
            message_status = webhook_data.get('MessageStatus')
            error_code = webhook_data.get('ErrorCode')
            error_message = webhook_data.get('ErrorMessage')
            
            status = self._map_twilio_status(message_status)
            
            result = {
                'provider_message_id': message_sid,
                'status': status,
                'error_code': error_code,
                'error_message': error_message
            }
            
            if status == SMSStatus.DELIVERED:
                result['delivered_at'] = datetime.utcnow()
            elif status in [SMSStatus.FAILED, SMSStatus.UNDELIVERED]:
                result['failed_at'] = datetime.utcnow()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {'error': str(e)}
    
    def _map_twilio_status(self, twilio_status: str) -> SMSStatus:
        """Map Twilio status to internal SMS status"""
        status_map = {
            'queued': SMSStatus.QUEUED,
            'sending': SMSStatus.SENDING,
            'sent': SMSStatus.SENT,
            'delivered': SMSStatus.DELIVERED,
            'failed': SMSStatus.FAILED,
            'undelivered': SMSStatus.UNDELIVERED
        }
        return status_map.get(twilio_status.lower(), SMSStatus.QUEUED)