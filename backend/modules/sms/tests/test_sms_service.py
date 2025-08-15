# backend/modules/sms/tests/test_sms_service.py

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from modules.sms.services.sms_service import SMSService
from modules.sms.services.twilio_service import TwilioService
from modules.sms.services.template_service import SMSTemplateService
from modules.sms.services.opt_out_service import OptOutService
from modules.sms.models.sms_models import (
    SMSMessage, SMSTemplate, SMSOptOut, SMSStatus, 
    SMSProvider, SMSDirection, SMSTemplateCategory
)
from modules.sms.schemas.sms_schemas import (
    SMSSendRequest, SMSTemplateCreate, SMSOptOutCreate
)


@pytest.fixture
def db_session():
    """Create a mock database session"""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def sms_service(db_session):
    """Create SMS service instance"""
    return SMSService(db_session)


@pytest.fixture
def template_service(db_session):
    """Create template service instance"""
    return SMSTemplateService(db_session)


@pytest.fixture
def opt_out_service(db_session):
    """Create opt-out service instance"""
    return OptOutService(db_session)


class TestSMSService:
    """Test SMS service functionality"""
    
    @pytest.mark.asyncio
    async def test_send_sms_success(self, sms_service, db_session):
        """Test successful SMS sending"""
        # Mock opt-out check
        sms_service.opt_out_service.is_opted_out = Mock(return_value=False)
        
        # Mock Twilio service
        sms_service.twilio_service.send_sms = Mock(return_value={
            'success': True,
            'provider_message_id': 'SM123456',
            'status': SMSStatus.SENT,
            'segments_count': 1,
            'cost_amount': 0.0075,
            'cost_currency': 'USD',
            'sent_at': datetime.utcnow(),
            'from_number': '+1234567890',
            'to_number': '+0987654321'
        })
        
        # Create request
        request = SMSSendRequest(
            to_number='+0987654321',
            message='Test message',
            customer_id=1
        )
        
        # Send SMS
        with patch.object(sms_service, '_send_message', new_callable=AsyncMock):
            message = await sms_service.send_sms(request, user_id=1)
        
        # Assertions
        assert message is not None
        db_session.add.assert_called_once()
        db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_send_sms_opted_out(self, sms_service):
        """Test SMS sending to opted-out number"""
        # Mock opt-out check
        sms_service.opt_out_service.is_opted_out = Mock(return_value=True)
        
        request = SMSSendRequest(
            to_number='+0987654321',
            message='Test message'
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="opted out"):
            await sms_service.send_sms(request)
    
    @pytest.mark.asyncio
    async def test_send_sms_with_template(self, sms_service, db_session):
        """Test SMS sending with template"""
        # Mock opt-out check
        sms_service.opt_out_service.is_opted_out = Mock(return_value=False)
        
        # Mock template rendering
        sms_service.template_service.render_template = Mock(
            return_value='Hi John, your reservation is confirmed!'
        )
        
        request = SMSSendRequest(
            to_number='+0987654321',
            template_id=1,
            template_variables={'name': 'John'},
            customer_id=1
        )
        
        with patch.object(sms_service, '_send_message', new_callable=AsyncMock):
            message = await sms_service.send_sms(request, user_id=1)
        
        # Verify template was rendered
        sms_service.template_service.render_template.assert_called_once_with(
            1, {'name': 'John'}
        )
    
    def test_get_message_history(self, sms_service, db_session):
        """Test retrieving message history"""
        # Mock query result
        mock_messages = [
            Mock(spec=SMSMessage, id=1, status=SMSStatus.DELIVERED),
            Mock(spec=SMSMessage, id=2, status=SMSStatus.SENT)
        ]
        
        db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_messages
        
        messages = sms_service.get_message_history(
            customer_id=1,
            limit=10
        )
        
        assert len(messages) == 2
        db_session.query.assert_called_once()


class TestTemplateService:
    """Test template service functionality"""
    
    def test_create_template(self, template_service, db_session):
        """Test template creation"""
        template_data = SMSTemplateCreate(
            name='test_template',
            category=SMSTemplateCategory.RESERVATION,
            template_body='Hi {{name}}, your reservation is confirmed!',
            is_active=True
        )
        
        # Mock query for duplicate check
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        template = template_service.create_template(template_data, user_id=1)
        
        assert template is not None
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
    
    def test_render_template(self, template_service, db_session):
        """Test template rendering"""
        # Mock template
        mock_template = Mock(
            spec=SMSTemplate,
            id=1,
            template_body='Hi {{name}}, your order #{{order_id}} is ready!',
            is_active=True,
            usage_count=0
        )
        
        template_service.get_template = Mock(return_value=mock_template)
        
        rendered = template_service.render_template(
            template_id=1,
            variables={'name': 'John', 'order_id': '12345'}
        )
        
        assert rendered == 'Hi John, your order #12345 is ready!'
        assert mock_template.usage_count == 1
    
    def test_calculate_segments(self, template_service):
        """Test SMS segment calculation"""
        # Test single segment (GSM)
        segments = template_service._calculate_segments('Hello World!')
        assert segments == 1
        
        # Test multi-segment (GSM)
        long_message = 'A' * 200  # 200 characters
        segments = template_service._calculate_segments(long_message)
        assert segments == 2
        
        # Test Unicode message
        unicode_message = 'Hello 😊 World!'
        segments = template_service._calculate_segments(unicode_message)
        assert segments == 1  # Should be 1 for short Unicode


class TestOptOutService:
    """Test opt-out service functionality"""
    
    def test_process_opt_out(self, opt_out_service, db_session):
        """Test opt-out processing"""
        # Mock existing record check
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        opt_out = opt_out_service.process_opt_out(
            phone_number='+1234567890',
            reason='User request',
            method='web',
            customer_id=1
        )
        
        assert opt_out is not None
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
    
    def test_process_opt_in(self, opt_out_service, db_session):
        """Test opt-in processing"""
        # Mock existing opt-out record
        mock_opt_out = Mock(
            spec=SMSOptOut,
            phone_number='+1234567890',
            opted_out=True,
            categories_opted_out=None
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = mock_opt_out
        
        opt_out = opt_out_service.process_opt_in(
            phone_number='+1234567890',
            method='sms_reply'
        )
        
        assert opt_out is not None
        assert mock_opt_out.opted_out == False
        assert mock_opt_out.opted_in_date is not None
    
    def test_is_opted_out(self, opt_out_service, db_session):
        """Test opt-out status check"""
        # Test opted out
        mock_opt_out = Mock(
            spec=SMSOptOut,
            opted_out=True,
            categories_opted_out=None
        )
        db_session.query.return_value.filter.return_value.first.return_value = mock_opt_out
        
        is_opted_out = opt_out_service.is_opted_out('+1234567890')
        assert is_opted_out == True
        
        # Test not opted out
        mock_opt_out.opted_out = False
        is_opted_out = opt_out_service.is_opted_out('+1234567890')
        assert is_opted_out == False
        
        # Test no record
        db_session.query.return_value.filter.return_value.first.return_value = None
        is_opted_out = opt_out_service.is_opted_out('+9999999999')
        assert is_opted_out == False
    
    def test_process_inbound_message(self, opt_out_service, db_session):
        """Test processing inbound messages for keywords"""
        # Test STOP keyword
        result = opt_out_service.process_inbound_message(
            phone_number='+1234567890',
            message_body='STOP'
        )
        assert result['action'] == 'opt_out'
        
        # Test START keyword
        result = opt_out_service.process_inbound_message(
            phone_number='+1234567890',
            message_body='START'
        )
        assert result['action'] == 'opt_in'
        
        # Test no keyword
        result = opt_out_service.process_inbound_message(
            phone_number='+1234567890',
            message_body='Hello there'
        )
        assert result['action'] == 'none'


class TestTwilioService:
    """Test Twilio service functionality"""
    
    @patch('modules.sms.services.twilio_service.Client')
    def test_send_sms_success(self, mock_twilio_client):
        """Test successful SMS sending via Twilio"""
        # Setup mock
        mock_message = Mock(
            sid='SM123456',
            status='sent',
            num_segments=1,
            price='0.0075',
            price_unit='USD',
            date_sent=datetime.utcnow(),
            from_='+1234567890',
            to='+0987654321',
            direction='outbound-api',
            api_version='2010-04-01'
        )
        
        mock_client_instance = Mock()
        mock_client_instance.messages.create.return_value = mock_message
        mock_twilio_client.return_value = mock_client_instance
        
        # Create service
        twilio_service = TwilioService()
        twilio_service.client = mock_client_instance
        
        # Send SMS
        result = twilio_service.send_sms(
            to_number='+0987654321',
            message_body='Test message'
        )
        
        assert result['success'] == True
        assert result['provider_message_id'] == 'SM123456'
        assert result['status'] == SMSStatus.SENT
    
    def test_map_twilio_status(self):
        """Test Twilio status mapping"""
        twilio_service = TwilioService()
        
        assert twilio_service._map_twilio_status('queued') == SMSStatus.QUEUED
        assert twilio_service._map_twilio_status('sent') == SMSStatus.SENT
        assert twilio_service._map_twilio_status('delivered') == SMSStatus.DELIVERED
        assert twilio_service._map_twilio_status('failed') == SMSStatus.FAILED
        assert twilio_service._map_twilio_status('undelivered') == SMSStatus.UNDELIVERED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])