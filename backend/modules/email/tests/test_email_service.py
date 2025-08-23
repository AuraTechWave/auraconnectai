# backend/modules/email/tests/test_email_service.py

"""
Unit tests for email service
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from modules.email.services.email_service import EmailService
from modules.email.schemas.email_schemas import EmailSendRequest
from modules.email.models.email_models import EmailMessage, EmailUnsubscribe, EmailTemplate
from modules.email.services.sendgrid_service import SendGridService
from modules.email.services.ses_service import SESService


class TestEmailService:
    """Test email service functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def email_service(self, mock_db):
        """Create email service instance"""
        return EmailService(mock_db)
    
    @pytest.fixture
    def sample_email_request(self):
        """Sample email send request"""
        return EmailSendRequest(
            to_email="test@example.com",
            subject="Test Email",
            body_html="<h1>Hello</h1>",
            body_text="Hello",
            category="transactional"
        )
    
    async def test_send_email_success(self, email_service, mock_db, sample_email_request):
        """Test successful email sending"""
        # Mock unsubscribe check
        mock_db.query().filter().first.return_value = None
        
        # Mock provider
        with patch.object(email_service, '_get_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_provider.send_email.return_value = {
                "success": True,
                "message_id": "test-123",
                "provider": "sendgrid"
            }
            mock_get_provider.return_value = mock_provider
            
            # Send email
            result = await email_service.send_email(sample_email_request)
            
            # Verify
            assert isinstance(result, EmailMessage)
            assert result.to_email == "test@example.com"
            assert result.subject == "Test Email"
            assert result.status == "sent"
            assert result.provider == "sendgrid"
            assert result.provider_message_id == "test-123"
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called()
    
    async def test_send_email_unsubscribed(self, email_service, mock_db, sample_email_request):
        """Test email not sent to unsubscribed user"""
        # Mock unsubscribe check - user is unsubscribed
        mock_unsubscribe = Mock(spec=EmailUnsubscribe)
        mock_unsubscribe.email = "test@example.com"
        mock_unsubscribe.is_active = True
        mock_db.query().filter().first.return_value = mock_unsubscribe
        
        # Send email
        result = await email_service.send_email(sample_email_request)
        
        # Verify
        assert isinstance(result, EmailMessage)
        assert result.status == "suppressed"
        assert result.error_message == "User has unsubscribed from transactional emails"
    
    async def test_send_email_with_template(self, email_service, mock_db):
        """Test sending email with template"""
        # Mock template
        mock_template = Mock(spec=EmailTemplate)
        mock_template.subject = "Welcome {{name}}!"
        mock_template.body_html = "<h1>Welcome {{name}}!</h1>"
        mock_template.body_text = "Welcome {{name}}!"
        mock_template.is_active = True
        
        # Mock template service
        with patch.object(email_service.template_service, 'get_template_by_name') as mock_get_template:
            mock_get_template.return_value = mock_template
            
            # Mock unsubscribe check
            mock_db.query().filter().first.return_value = None
            
            # Mock provider
            with patch.object(email_service, '_get_provider') as mock_get_provider:
                mock_provider = Mock()
                mock_provider.send_email.return_value = {
                    "success": True,
                    "message_id": "test-456"
                }
                mock_get_provider.return_value = mock_provider
                
                # Create request with template
                request = EmailSendRequest(
                    to_email="user@example.com",
                    template_name="welcome",
                    variables={"name": "John Doe"}
                )
                
                # Send email
                result = await email_service.send_email(request)
                
                # Verify template rendering
                assert result.subject == "Welcome John Doe!"
                assert "<h1>Welcome John Doe!</h1>" in result.body_html
                assert "Welcome John Doe!" in result.body_text
    
    async def test_send_email_with_retry(self, email_service, mock_db, sample_email_request):
        """Test email retry on provider failure"""
        # Mock unsubscribe check
        mock_db.query().filter().first.return_value = None
        
        # Mock provider failure then success
        with patch.object(email_service, '_get_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_provider.send_email.side_effect = [
                {"success": False, "error": "Network error"},
                {"success": True, "message_id": "test-789", "provider": "aws_ses"}
            ]
            mock_get_provider.return_value = mock_provider
            
            # Send email
            result = await email_service.send_email(sample_email_request)
            
            # Verify retry happened
            assert mock_provider.send_email.call_count == 2
            assert result.status == "sent"
            assert result.provider == "aws_ses"
            assert result.retry_count == 1
    
    async def test_send_email_all_providers_fail(self, email_service, mock_db, sample_email_request):
        """Test email marked as failed when all providers fail"""
        # Mock unsubscribe check
        mock_db.query().filter().first.return_value = None
        
        # Mock all providers failing
        with patch('modules.email.services.email_service.email_settings') as mock_settings:
            mock_settings.EMAIL_MAX_RETRY_ATTEMPTS = 2
            
            with patch.object(email_service, '_get_provider') as mock_get_provider:
                mock_provider = Mock()
                mock_provider.send_email.return_value = {
                    "success": False,
                    "error": "Provider error"
                }
                mock_get_provider.return_value = mock_provider
                
                # Send email
                result = await email_service.send_email(sample_email_request)
                
                # Verify marked as failed
                assert result.status == "failed"
                assert result.error_message == "Provider error"
                assert result.retry_count == 2
    
    def test_get_provider_sendgrid(self, email_service):
        """Test getting SendGrid provider"""
        with patch('modules.email.services.email_service.email_settings') as mock_settings:
            mock_settings.EMAIL_DEFAULT_PROVIDER = "sendgrid"
            
            provider = email_service._get_provider()
            assert isinstance(provider, SendGridService)
    
    def test_get_provider_ses(self, email_service):
        """Test getting AWS SES provider"""
        with patch('modules.email.services.email_service.email_settings') as mock_settings:
            mock_settings.EMAIL_DEFAULT_PROVIDER = "aws_ses"
            
            provider = email_service._get_provider("aws_ses")
            assert isinstance(provider, SESService)
    
    async def test_process_webhook_sendgrid(self, email_service, mock_db):
        """Test processing SendGrid webhook"""
        # Mock email message
        mock_message = Mock(spec=EmailMessage)
        mock_message.id = 1
        mock_message.provider_message_id = "sg-123"
        mock_db.query().filter().first.return_value = mock_message
        
        # Process webhook
        events = [{
            "sg_message_id": "sg-123",
            "event": "delivered",
            "timestamp": 1640000000
        }]
        
        await email_service.process_webhook("sendgrid", events)
        
        # Verify status updated
        assert mock_message.status == "delivered"
        assert mock_message.delivered_at is not None
        mock_db.commit.assert_called()
    
    async def test_get_email_analytics(self, email_service, mock_db):
        """Test getting email analytics"""
        # Mock query results
        mock_results = [
            ("sent", 100),
            ("delivered", 95),
            ("opened", 50),
            ("clicked", 20),
            ("bounced", 3),
            ("failed", 2)
        ]
        mock_db.query().filter().group_by().all.return_value = mock_results
        
        # Get analytics
        from datetime import datetime, timedelta
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        analytics = await email_service.get_email_analytics(
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify results
        assert analytics["total_sent"] == 100
        assert analytics["delivery_rate"] == 95.0
        assert analytics["open_rate"] == 50.0
        assert analytics["click_rate"] == 20.0
        assert analytics["bounce_rate"] == 3.0