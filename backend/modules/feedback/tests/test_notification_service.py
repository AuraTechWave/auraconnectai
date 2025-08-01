# backend/modules/feedback/tests/test_notification_service.py

"""
Unit tests for notification service including email and SMS backends.

Tests cover:
- Email notification sending with SMTP
- SMS notification sending with Twilio
- Background task queuing
- Template rendering
- Error handling and retries
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import asyncio
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from modules.feedback.services.notification_service import (
    NotificationService,
    EmailBackend,
    SMSBackend,
    PushNotificationBackend,
    NotificationTemplate
)
from modules.feedback.models.feedback_models import Review, Feedback, Customer
from modules.feedback.services.background_tasks import BackgroundTaskProcessor


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


@pytest.fixture
def email_backend():
    """Create email backend instance with test configuration"""
    with patch.dict(os.environ, {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@example.com',
        'SMTP_PASSWORD': 'testpass',
        'FROM_EMAIL': 'noreply@test.com',
        'FROM_NAME': 'Test App'
    }):
        return EmailBackend()


@pytest.fixture
def sms_backend():
    """Create SMS backend instance with test configuration"""
    with patch.dict(os.environ, {
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token',
        'TWILIO_FROM_NUMBER': '+1234567890'
    }):
        return SMSBackend()


@pytest.fixture
def notification_service(mock_db):
    """Create notification service instance"""
    return NotificationService(mock_db)


class TestEmailBackend:
    """Test cases for email notification backend"""
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, email_backend):
        """Test successful email sending"""
        # Mock SMTP
        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        with patch('smtplib.SMTP', mock_smtp):
            result = await email_backend.send_email(
                to_email='recipient@example.com',
                subject='Test Subject',
                html_content='<p>Test HTML content</p>',
                text_content='Test text content'
            )
        
        # Verify SMTP was called correctly
        mock_smtp.assert_called_once_with(email_backend.smtp_host, email_backend.smtp_port)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            email_backend.smtp_username,
            email_backend.smtp_password
        )
        mock_smtp_instance.send_message.assert_called_once()
        
        # Verify result
        assert result['success'] is True
        assert result['message_id'] is not None
        assert 'timestamp' in result
    
    @pytest.mark.asyncio
    async def test_send_email_with_reply_to(self, email_backend):
        """Test email sending with reply-to header"""
        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        with patch('smtplib.SMTP', mock_smtp):
            result = await email_backend.send_email(
                to_email='recipient@example.com',
                subject='Test Subject',
                html_content='<p>Test content</p>',
                reply_to='replyto@example.com'
            )
        
        # Get the message that was sent
        sent_message = mock_smtp_instance.send_message.call_args[0][0]
        assert sent_message['Reply-To'] == 'replyto@example.com'
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_send_email_smtp_error(self, email_backend):
        """Test email sending with SMTP error"""
        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.send_message.side_effect = Exception("SMTP Error")
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        with patch('smtplib.SMTP', mock_smtp):
            result = await email_backend.send_email(
                to_email='recipient@example.com',
                subject='Test Subject',
                html_content='<p>Test content</p>'
            )
        
        assert result['success'] is False
        assert 'SMTP Error' in result['error']
    
    @pytest.mark.asyncio
    async def test_send_email_authentication_error(self, email_backend):
        """Test email sending with authentication error"""
        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.login.side_effect = Exception("Authentication failed")
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        with patch('smtplib.SMTP', mock_smtp):
            result = await email_backend.send_email(
                to_email='recipient@example.com',
                subject='Test Subject',
                html_content='<p>Test content</p>'
            )
        
        assert result['success'] is False
        assert 'Authentication failed' in result['error']
    
    def test_validate_email_format(self, email_backend):
        """Test email format validation"""
        # Valid emails
        assert email_backend._validate_email('user@example.com') is True
        assert email_backend._validate_email('user.name+tag@example.co.uk') is True
        
        # Invalid emails
        assert email_backend._validate_email('invalid.email') is False
        assert email_backend._validate_email('@example.com') is False
        assert email_backend._validate_email('user@') is False
        assert email_backend._validate_email('') is False


class TestSMSBackend:
    """Test cases for SMS notification backend"""
    
    @pytest.mark.asyncio
    async def test_send_sms_success(self, sms_backend):
        """Test successful SMS sending"""
        # Mock Twilio client
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'test_message_sid'
        mock_message.status = 'sent'
        mock_client.messages.create.return_value = mock_message
        
        with patch('twilio.rest.Client', return_value=mock_client):
            result = await sms_backend.send_sms(
                to_number='+0987654321',
                message='Test SMS message'
            )
        
        # Verify Twilio client was called correctly
        mock_client.messages.create.assert_called_once_with(
            body='Test SMS message',
            from_=sms_backend.from_number,
            to='+0987654321'
        )
        
        # Verify result
        assert result['success'] is True
        assert result['message_sid'] == 'test_message_sid'
        assert result['status'] == 'sent'
    
    @pytest.mark.asyncio
    async def test_send_sms_twilio_error(self, sms_backend):
        """Test SMS sending with Twilio error"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Twilio Error")
        
        with patch('twilio.rest.Client', return_value=mock_client):
            result = await sms_backend.send_sms(
                to_number='+0987654321',
                message='Test SMS message'
            )
        
        assert result['success'] is False
        assert 'Twilio Error' in result['error']
    
    @pytest.mark.asyncio
    async def test_send_sms_invalid_number(self, sms_backend):
        """Test SMS sending with invalid phone number"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Invalid phone number")
        
        with patch('twilio.rest.Client', return_value=mock_client):
            result = await sms_backend.send_sms(
                to_number='invalid',
                message='Test SMS message'
            )
        
        assert result['success'] is False
        assert 'Invalid phone number' in result['error']
    
    @pytest.mark.asyncio
    async def test_send_sms_message_truncation(self, sms_backend):
        """Test SMS message truncation for long messages"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'test_message_sid'
        mock_message.status = 'sent'
        mock_client.messages.create.return_value = mock_message
        
        # Create a message longer than 160 characters
        long_message = 'A' * 200
        
        with patch('twilio.rest.Client', return_value=mock_client):
            result = await sms_backend.send_sms(
                to_number='+0987654321',
                message=long_message
            )
        
        # Verify message was truncated
        sent_message = mock_client.messages.create.call_args[1]['body']
        assert len(sent_message) == 160
        assert sent_message == long_message[:160]
        assert result['success'] is True


class TestNotificationService:
    """Test cases for notification service"""
    
    @pytest.mark.asyncio
    async def test_send_review_invitation(self, notification_service, mock_db):
        """Test sending review invitation notification"""
        # Mock customer
        mock_customer = Mock(spec=Customer)
        mock_customer.id = 1
        mock_customer.email = 'customer@example.com'
        mock_customer.phone = '+1234567890'
        mock_customer.first_name = 'John'
        mock_customer.last_name = 'Doe'
        mock_customer.notification_preferences = {
            'email': True,
            'sms': True
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_customer
        
        # Mock email and SMS backends
        with patch.object(notification_service.email_backend, 'send_email', new_callable=AsyncMock) as mock_email, \
             patch.object(notification_service.sms_backend, 'send_sms', new_callable=AsyncMock) as mock_sms, \
             patch.object(notification_service, '_queue_notification_task', new_callable=AsyncMock) as mock_queue:
            
            mock_email.return_value = {'success': True, 'message_id': 'email123'}
            mock_sms.return_value = {'success': True, 'message_sid': 'sms123'}
            
            result = await notification_service.send_review_invitation(
                customer_id=1,
                entity_type='product',
                entity_id=100
            )
        
        # Verify notification was queued
        mock_queue.assert_called_once()
        
        # Verify result
        assert result['success'] is True
        assert result['notifications_queued'] == 1
    
    @pytest.mark.asyncio
    async def test_send_feedback_response_notification(self, notification_service, mock_db):
        """Test sending feedback response notification"""
        # Mock feedback and customer
        mock_customer = Mock(spec=Customer)
        mock_customer.email = 'customer@example.com'
        mock_customer.first_name = 'Jane'
        
        mock_feedback = Mock(spec=Feedback)
        mock_feedback.id = 1
        mock_feedback.customer = mock_customer
        mock_feedback.subject = 'Test Feedback'
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_feedback
        
        # Mock background task
        with patch.object(notification_service, '_queue_notification_task', new_callable=AsyncMock) as mock_queue:
            result = await notification_service.send_feedback_response_notification(
                feedback_id=1,
                response_id=10
            )
        
        # Verify notification was queued
        mock_queue.assert_called_once()
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_queue_notification_task(self, notification_service, mock_db):
        """Test queuing notification tasks"""
        # Mock background processor
        mock_processor = Mock(spec=BackgroundTaskProcessor)
        mock_processor.enqueue_notification = AsyncMock()
        
        with patch('backend.modules.feedback.services.notification_service.background_processor', mock_processor):
            await notification_service._queue_notification_task(
                notification_type='test_notification',
                data={'test': 'data'}
            )
        
        # Verify task was enqueued
        mock_processor.enqueue_notification.assert_called_once_with(
            notification_type='test_notification',
            test='data'
        )
    
    @pytest.mark.asyncio
    async def test_notification_rate_limiting(self, notification_service, mock_db):
        """Test notification rate limiting"""
        # Test that rate limiting prevents too many notifications
        notification_service._should_rate_limit = Mock(return_value=True)
        
        result = await notification_service.send_review_invitation(
            customer_id=1,
            entity_type='product',
            entity_id=100
        )
        
        assert result['success'] is False
        assert 'rate limited' in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_process_notification_from_queue(self, notification_service, mock_db):
        """Test processing notification from background queue"""
        # Mock data
        notification_data = {
            'type': 'email',
            'to_email': 'test@example.com',
            'subject': 'Test Subject',
            'template': 'review_invitation',
            'context': {'name': 'Test User'}
        }
        
        # Mock email backend
        with patch.object(notification_service.email_backend, 'send_email', new_callable=AsyncMock) as mock_email:
            mock_email.return_value = {'success': True, 'message_id': 'test123'}
            
            result = await notification_service.process_notification(notification_data)
        
        # Verify email was sent
        mock_email.assert_called_once()
        assert result['success'] is True
    
    def test_render_template(self, notification_service):
        """Test template rendering"""
        template = NotificationTemplate(
            name='test_template',
            subject='Hello {{name}}',
            html_body='<p>Welcome {{name}}!</p>',
            text_body='Welcome {{name}}!'
        )
        
        rendered = notification_service._render_template(
            template,
            context={'name': 'John Doe'}
        )
        
        assert rendered['subject'] == 'Hello John Doe'
        assert rendered['html'] == '<p>Welcome John Doe!</p>'
        assert rendered['text'] == 'Welcome John Doe!'


class TestBackgroundTaskQueuing:
    """Test cases for background task queuing with correct parameters"""
    
    @pytest.mark.asyncio
    async def test_notification_task_queued_with_correct_params(self, notification_service):
        """Test that notification tasks are queued with correct parameters"""
        # Mock background processor
        mock_processor = Mock(spec=BackgroundTaskProcessor)
        mock_processor.enqueue_notification = AsyncMock()
        
        with patch('backend.modules.feedback.services.notification_service.background_processor', mock_processor):
            # Queue email notification
            await notification_service._queue_notification_task(
                notification_type='review_invitation',
                data={
                    'customer_id': 123,
                    'entity_type': 'product',
                    'entity_id': 456
                }
            )
        
        # Verify correct parameters
        mock_processor.enqueue_notification.assert_called_once_with(
            notification_type='review_invitation',
            customer_id=123,
            entity_type='product',
            entity_id=456
        )
    
    @pytest.mark.asyncio
    async def test_multiple_notification_types_queued(self, notification_service):
        """Test queuing different notification types"""
        mock_processor = Mock(spec=BackgroundTaskProcessor)
        mock_processor.enqueue_notification = AsyncMock()
        
        with patch('backend.modules.feedback.services.notification_service.background_processor', mock_processor):
            # Queue different notification types
            await notification_service._queue_notification_task(
                notification_type='review_invitation',
                data={'customer_id': 1}
            )
            
            await notification_service._queue_notification_task(
                notification_type='feedback_response',
                data={'feedback_id': 2, 'response_id': 3}
            )
            
            await notification_service._queue_notification_task(
                notification_type='review_moderation',
                data={'review_id': 4, 'action': 'approved'}
            )
        
        # Verify all were queued correctly
        assert mock_processor.enqueue_notification.call_count == 3
        
        # Check each call
        calls = mock_processor.enqueue_notification.call_args_list
        assert calls[0][1]['notification_type'] == 'review_invitation'
        assert calls[1][1]['notification_type'] == 'feedback_response'
        assert calls[2][1]['notification_type'] == 'review_moderation'
    
    @pytest.mark.asyncio
    async def test_task_queue_error_handling(self, notification_service):
        """Test error handling when queuing fails"""
        mock_processor = Mock(spec=BackgroundTaskProcessor)
        mock_processor.enqueue_notification = AsyncMock(side_effect=Exception("Queue full"))
        
        with patch('backend.modules.feedback.services.notification_service.background_processor', mock_processor):
            # Should not raise exception, but handle gracefully
            try:
                await notification_service._queue_notification_task(
                    notification_type='test',
                    data={'test': 'data'}
                )
            except Exception:
                pytest.fail("Queue error should be handled gracefully")


class TestNotificationTemplates:
    """Test cases for notification templates"""
    
    def test_review_invitation_template(self, notification_service):
        """Test review invitation template rendering"""
        template = notification_service.templates.get('review_invitation')
        assert template is not None
        
        rendered = notification_service._render_template(
            template,
            context={
                'customer_name': 'John Doe',
                'entity_type': 'product',
                'entity_name': 'Amazing Widget',
                'review_link': 'https://example.com/review/123'
            }
        )
        
        assert 'John Doe' in rendered['html']
        assert 'Amazing Widget' in rendered['html']
        assert 'https://example.com/review/123' in rendered['html']
    
    def test_feedback_response_template(self, notification_service):
        """Test feedback response template rendering"""
        template = notification_service.templates.get('feedback_response')
        assert template is not None
        
        rendered = notification_service._render_template(
            template,
            context={
                'customer_name': 'Jane Smith',
                'feedback_subject': 'Product Issue',
                'response_preview': 'Thank you for your feedback...',
                'response_link': 'https://example.com/feedback/456'
            }
        )
        
        assert 'Jane Smith' in rendered['text']
        assert 'Product Issue' in rendered['text']
        assert 'Thank you for your feedback' in rendered['text']


# Additional test fixtures and utilities
@pytest.fixture
def sample_review():
    """Create a sample review for testing"""
    review = Mock(spec=Review)
    review.id = 1
    review.customer_id = 100
    review.product_id = 200
    review.rating = 5
    review.title = "Great product!"
    review.content = "This product exceeded my expectations."
    review.created_at = datetime.utcnow()
    return review


@pytest.fixture
def sample_feedback():
    """Create a sample feedback for testing"""
    feedback = Mock(spec=Feedback)
    feedback.id = 1
    feedback.customer_id = 100
    feedback.subject = "Feature Request"
    feedback.message = "It would be great if the product had..."
    feedback.created_at = datetime.utcnow()
    return feedback