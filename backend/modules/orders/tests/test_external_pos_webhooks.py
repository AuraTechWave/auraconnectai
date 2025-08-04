# backend/modules/orders/tests/test_external_pos_webhooks.py

"""
Tests for external POS webhook functionality.
"""

import pytest
import json
import hmac
import hashlib
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from core.database import get_db
from modules.orders.models.external_pos_models import (
    ExternalPOSProvider, ExternalPOSWebhookEvent, ExternalPOSPaymentUpdate
)
from modules.orders.enums.external_pos_enums import (
    AuthenticationType, WebhookProcessingStatus, PaymentStatus
)
from modules.orders.services.webhook_auth_service import WebhookAuthService
from modules.orders.services.external_pos_webhook_service import ExternalPOSWebhookService


class TestWebhookAuthentication:
    """Test webhook authentication and verification"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def square_provider(self):
        """Create Square provider configuration"""
        return ExternalPOSProvider(
            id=1,
            provider_code="square",
            provider_name="Square",
            webhook_endpoint_id="square-webhook",
            is_active=True,
            auth_type=AuthenticationType.HMAC_SHA256,
            auth_config={
                "webhook_secret": "test_square_secret",
                "signature_header": "X-Square-Signature"
            },
            supported_events=["payment.updated"]
        )
    
    @pytest.fixture
    def stripe_provider(self):
        """Create Stripe provider configuration"""
        return ExternalPOSProvider(
            id=2,
            provider_code="stripe",
            provider_name="Stripe",
            webhook_endpoint_id="stripe-webhook",
            is_active=True,
            auth_type=AuthenticationType.HMAC_SHA256,
            auth_config={
                "webhook_secret": "whsec_test_secret",
                "signature_header": "Stripe-Signature"
            },
            supported_events=["payment_intent.succeeded"]
        )
    
    @pytest.mark.asyncio
    async def test_verify_square_webhook_valid(self, mock_db, square_provider):
        """Test valid Square webhook verification"""
        mock_db.query().filter().first.return_value = square_provider
        
        # Create test payload
        payload = {"test": "data"}
        body = json.dumps(payload).encode()
        
        # Generate Square signature
        headers = {"x-square-signature": "test_sig"}
        string_to_sign = headers["x-square-signature"] + body.decode()
        signature = base64.b64encode(
            hmac.new(
                b"test_square_secret",
                string_to_sign.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        auth_service = WebhookAuthService(mock_db)
        is_valid, error, details = await auth_service.verify_webhook_request(
            provider_code="square",
            headers=headers,
            body=body,
            request_signature=signature
        )
        
        assert is_valid is True
        assert error is None
        assert details["provider"] == "square"
    
    @pytest.mark.asyncio
    async def test_verify_stripe_webhook_valid(self, mock_db, stripe_provider):
        """Test valid Stripe webhook verification"""
        mock_db.query().filter().first.return_value = stripe_provider
        
        # Create test payload
        payload = {"test": "data"}
        body = json.dumps(payload).encode()
        timestamp = "1234567890"
        
        # Generate Stripe signature
        signed_payload = f"{timestamp}.{body.decode()}"
        signature = hmac.new(
            b"whsec_test_secret",
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        stripe_signature = f"t={timestamp},v1={signature}"
        headers = {"stripe-signature": stripe_signature}
        
        auth_service = WebhookAuthService(mock_db)
        
        # Mock datetime to avoid timestamp validation failure
        with patch('backend.modules.orders.services.webhook_auth_service.datetime') as mock_datetime:
            mock_datetime.utcnow().timestamp.return_value = int(timestamp) + 10
            
            is_valid, error, details = await auth_service.verify_webhook_request(
                provider_code="stripe",
                headers=headers,
                body=body,
                request_signature=stripe_signature
            )
        
        assert is_valid is True
        assert error is None
        assert details["provider"] == "stripe"
    
    @pytest.mark.asyncio
    async def test_verify_webhook_invalid_signature(self, mock_db, square_provider):
        """Test webhook verification with invalid signature"""
        mock_db.query().filter().first.return_value = square_provider
        
        body = json.dumps({"test": "data"}).encode()
        headers = {"x-square-signature": "invalid_signature"}
        
        auth_service = WebhookAuthService(mock_db)
        is_valid, error, details = await auth_service.verify_webhook_request(
            provider_code="square",
            headers=headers,
            body=body,
            request_signature="wrong_signature"
        )
        
        assert is_valid is False
        assert "Invalid" in error
    
    def test_generate_test_signature(self, mock_db, stripe_provider):
        """Test generating test signatures"""
        mock_db.query().filter().first.return_value = stripe_provider
        
        auth_service = WebhookAuthService(mock_db)
        test_body = {"event": "test"}
        
        headers = auth_service.generate_test_signature(
            provider_code="stripe",
            body=test_body,
            timestamp=1234567890
        )
        
        assert "Stripe-Signature" in headers
        assert headers["Stripe-Signature"].startswith("t=1234567890,v1=")


class TestWebhookEndpoints:
    """Test webhook API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication"""
        with patch('backend.core.auth.get_current_user') as mock:
            mock.return_value = Mock(id=1, role="admin")
            yield mock
    
    def test_receive_webhook_unknown_provider(self, client):
        """Test webhook from unknown provider"""
        response = client.post(
            "/api/webhooks/external-pos/unknown_provider/events",
            json={"test": "data"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_receive_webhook_success(self, client):
        """Test successful webhook reception"""
        with patch('backend.modules.orders.routers.external_pos_webhook_router.get_db') as mock_get_db:
            mock_db = Mock()
            mock_provider = Mock(
                id=1,
                provider_code="square",
                is_active=True
            )
            mock_db.query().filter().first.return_value = mock_provider
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('backend.modules.orders.routers.external_pos_webhook_router.WebhookAuthService') as mock_auth:
                mock_auth_instance = Mock()
                mock_auth_instance.verify_webhook_request = AsyncMock(
                    return_value=(True, None, {"verified": True})
                )
                mock_auth.return_value = mock_auth_instance
                
                response = client.post(
                    "/api/webhooks/external-pos/square/events",
                    json={
                        "type": "payment.updated",
                        "data": {"payment": {"id": "123"}}
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "accepted"
                assert "event_id" in data
    
    def test_get_provider_status(self, client, mock_auth):
        """Test getting provider webhook status"""
        with patch('backend.modules.orders.routers.external_pos_webhook_router.get_db') as mock_get_db:
            mock_db = Mock()
            mock_provider = Mock(
                provider_code="square",
                provider_name="Square",
                is_active=True
            )
            mock_db.query().filter().first.return_value = mock_provider
            mock_db.query().filter().order_by().limit().all.return_value = []
            mock_get_db.return_value = mock_db
            
            response = client.get("/api/webhooks/external-pos/square/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["provider"]["code"] == "square"
            assert data["provider"]["is_active"] is True


class TestWebhookProcessing:
    """Test webhook event processing"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def webhook_event(self):
        """Create test webhook event"""
        provider = Mock(provider_code="square")
        return Mock(
            id=1,
            event_id=uuid.uuid4(),
            provider=provider,
            provider_id=1,
            event_type="payment.completed",
            request_body={
                "type": "payment.updated",
                "data": {
                    "object": {
                        "payment": {
                            "id": "PAYMENT_123",
                            "order_id": "ORDER_123",
                            "amount_money": {
                                "amount": 1000,
                                "currency": "USD"
                            },
                            "status": "COMPLETED"
                        }
                    }
                }
            },
            processing_status=WebhookProcessingStatus.PENDING,
            processing_attempts=0
        )
    
    @pytest.mark.asyncio
    async def test_process_payment_webhook(self, mock_db, webhook_event):
        """Test processing payment webhook"""
        mock_db.query().filter().first.return_value = webhook_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.flush = Mock()
        
        service = ExternalPOSWebhookService(mock_db)
        
        # Mock order matching
        with patch.object(service, '_match_order', return_value=None):
            success = await service.process_webhook_event(webhook_event.id)
        
        assert success is True
        assert webhook_event.processing_status == WebhookProcessingStatus.PROCESSED
        
        # Check payment update was created
        payment_update_calls = [
            call for call in mock_db.add.call_args_list
            if hasattr(call[0][0], 'external_transaction_id')
        ]
        assert len(payment_update_calls) > 0
    
    @pytest.mark.asyncio
    async def test_process_duplicate_webhook(self, mock_db, webhook_event):
        """Test duplicate webhook detection"""
        mock_db.query().filter().first.side_effect = [
            webhook_event,  # First call returns the event
            Mock()  # Second call returns duplicate
        ]
        
        service = ExternalPOSWebhookService(mock_db)
        success = await service.process_webhook_event(webhook_event.id)
        
        assert success is True
        assert webhook_event.processing_status == WebhookProcessingStatus.DUPLICATE
    
    def test_extract_square_payment_data(self, mock_db):
        """Test extracting payment data from Square webhook"""
        service = ExternalPOSWebhookService(mock_db)
        
        square_body = {
            "data": {
                "object": {
                    "payment": {
                        "id": "PAYMENT_123",
                        "order_id": "ORDER_123",
                        "amount_money": {
                            "amount": 1500,
                            "currency": "USD"
                        },
                        "status": "COMPLETED",
                        "card_details": {
                            "card": {
                                "last_4": "1234",
                                "card_brand": "VISA"
                            }
                        }
                    }
                }
            }
        }
        
        data = service._extract_payment_data("square", square_body)
        
        assert data["transaction_id"] == "PAYMENT_123"
        assert data["amount"] == 15.00  # Converted from cents
        assert data["status"] == PaymentStatus.COMPLETED
        assert data["card_last_four"] == "1234"


class TestWebhookRetryScheduler:
    """Test webhook retry scheduler"""
    
    @pytest.mark.asyncio
    async def test_retry_scheduler_start_stop(self):
        """Test starting and stopping retry scheduler"""
        from modules.orders.tasks.webhook_retry_task import WebhookRetryScheduler
        
        scheduler = WebhookRetryScheduler()
        
        # Start scheduler
        scheduler.start()
        assert scheduler.is_running is True
        
        # Get status
        status = scheduler.get_status()
        assert status["scheduler_running"] is True
        assert len(status["jobs"]) >= 2  # retry and cleanup jobs
        
        # Stop scheduler
        scheduler.stop()
        assert scheduler.is_running is False