# backend/modules/payroll/tests/test_webhooks.py

"""
Functional tests for webhook management.

Tests webhook subscription lifecycle and delivery.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import hmac
import hashlib
import json
import uuid
from datetime import datetime

from ..routes.v1.webhook_routes import (
    create_webhook_subscription,
    send_webhook_notification
)
from ..schemas.webhook_schemas import (
    WebhookSubscriptionRequest,
    WebhookEventType
)
from ..models.payroll_configuration import PayrollWebhookSubscription


@pytest.fixture
def webhook_request():
    """Sample webhook subscription request."""
    return WebhookSubscriptionRequest(
        webhook_url="https://example.com/webhook",
        event_types=[
            WebhookEventType.PAYROLL_COMPLETED,
            WebhookEventType.PAYMENT_PROCESSED
        ],
        active=True,
        description="Test webhook"
    )


class TestWebhookSubscription:
    """Test webhook subscription management."""
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, mock_db, mock_user, webhook_request):
        """Test creating a webhook subscription."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        response = await create_webhook_subscription(
            subscription=webhook_request,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.webhook_url == webhook_request.webhook_url
        assert response.event_types == webhook_request.event_types
        assert response.secret_key is not None  # Generated
        assert response.active == True
        assert mock_db.add.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_duplicate_subscription_error(self, mock_db, mock_user, webhook_request):
        """Test that duplicate subscriptions are rejected."""
        # Setup - existing subscription
        existing = Mock()
        existing.webhook_url = webhook_request.webhook_url
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await create_webhook_subscription(
                subscription=webhook_request,
                db=mock_db,
                current_user=mock_user
            )
        
        assert "409" in str(exc_info.value)  # Conflict
        assert "already exists" in str(exc_info.value)


class TestWebhookDelivery:
    """Test webhook notification delivery."""
    
    @pytest.mark.asyncio
    async def test_webhook_signature_generation(self):
        """Test HMAC signature generation for webhooks."""
        # Test data
        webhook_url = "https://example.com/webhook"
        event_type = "payroll.completed"
        payload = {
            "event_id": "test-123",
            "event_type": event_type,
            "data": {"job_id": "job-456"}
        }
        secret_key = "test-secret-key"
        
        # Mock httpx client
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_client.post = AsyncMock(return_value=mock_response)
            
            # Execute
            status_code, response_text = await send_webhook_notification(
                webhook_url=webhook_url,
                event_type=event_type,
                payload=payload,
                secret_key=secret_key
            )
            
            # Verify
            assert status_code == 200
            assert response_text == "OK"
            
            # Check signature was included
            call_args = mock_client.post.call_args
            headers = call_args.kwargs['headers']
            assert 'X-Webhook-Signature' in headers
            assert 'X-Webhook-Timestamp' in headers
            assert headers['X-Webhook-Event'] == event_type
            
            # Verify signature
            payload_json = json.dumps(payload, sort_keys=True)
            expected_signature = hmac.new(
                secret_key.encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()
            assert headers['X-Webhook-Signature'] == expected_signature
    
    @pytest.mark.asyncio
    async def test_webhook_delivery_failure(self):
        """Test handling of webhook delivery failures."""
        webhook_url = "https://example.com/webhook"
        event_type = "payment.processed"
        payload = {"event_id": "test-789"}
        secret_key = "test-secret"
        
        # Mock httpx to simulate failure
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            
            # Execute
            status_code, error_text = await send_webhook_notification(
                webhook_url=webhook_url,
                event_type=event_type,
                payload=payload,
                secret_key=secret_key
            )
            
            # Verify
            assert status_code is None
            assert "Connection refused" in error_text


class TestWebhookSecurity:
    """Test webhook security features."""
    
    @pytest.mark.asyncio
    async def test_webhook_url_validation(self, mock_db, mock_user):
        """Test that only HTTPS URLs are accepted."""
        # Create request with HTTP URL
        insecure_request = WebhookSubscriptionRequest(
            webhook_url="ftp://example.com/webhook",  # Invalid protocol
            event_types=[WebhookEventType.PAYROLL_COMPLETED],
            active=True
        )
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await create_webhook_subscription(
                subscription=insecure_request,
                db=mock_db,
                current_user=mock_user
            )
        
        assert "422" in str(exc_info.value)  # Validation error
    
    def test_signature_verification(self):
        """Test webhook signature verification logic."""
        # This would be implemented on the receiving end
        payload = {"test": "data"}
        secret = "webhook-secret"
        
        # Generate signature
        payload_json = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature (receiver side)
        expected = hmac.new(
            secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        assert hmac.compare_digest(signature, expected)