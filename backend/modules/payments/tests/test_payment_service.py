# backend/modules/payments/tests/test_payment_service.py

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from modules.payments.services import payment_service
from modules.payments.models import (
    Payment,
    PaymentGateway,
    PaymentStatus,
    PaymentMethod,
    RefundStatus,
)
from modules.payments.gateways import (
    PaymentRequest,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
)
from modules.orders.models import Order


@pytest.fixture
async def mock_order():
    """Create a mock order for testing"""
    order = Mock(spec=Order)
    order.id = 123
    order.order_number = "ORD-123"
    order.customer_id = 456
    order.customer_email = "test@example.com"
    order.customer_name = "Test Customer"
    order.total_amount = Decimal("99.99")
    order.payment_status = "pending"
    return order


@pytest.fixture
async def mock_payment():
    """Create a mock payment for testing"""
    payment = Mock(spec=Payment)
    payment.id = 1
    payment.payment_id = "pay_test123"
    payment.order_id = 123
    payment.gateway = PaymentGateway.STRIPE
    payment.gateway_payment_id = "pi_test123"
    payment.amount = Decimal("99.99")
    payment.currency = "USD"
    payment.status = PaymentStatus.PENDING
    payment.metadata = {}
    return payment


class TestPaymentService:
    """Test payment service functionality"""

    @pytest.mark.asyncio
    async def test_create_payment_success(self, mock_order):
        """Test successful payment creation"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_order
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Mock gateway response
        mock_response = PaymentResponse(
            success=True,
            gateway_payment_id="pi_test123",
            status=PaymentStatus.COMPLETED,
            amount=Decimal("99.99"),
            currency="USD",
            payment_method=PaymentMethod.CARD,
            payment_method_details={"last4": "4242", "brand": "visa"},
            fee_amount=Decimal("2.99"),
            net_amount=Decimal("97.00"),
            processed_at=datetime.utcnow(),
        )

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = AsyncMock(return_value=mock_response)
            mock_gateways.get.return_value = mock_gateway

            # Execute
            payment = await payment_service.create_payment(
                db=db,
                order_id=123,
                gateway=PaymentGateway.STRIPE,
                amount=Decimal("99.99"),
                currency="USD",
            )

            # Assert
            assert payment.status == PaymentStatus.COMPLETED
            assert payment.gateway_payment_id == "pi_test123"
            assert payment.fee_amount == Decimal("2.99")
            assert payment.net_amount == Decimal("97.00")

            db.add.assert_called_once()
            db.commit.assert_called_once()
            mock_gateway.create_payment.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_payment_requires_action(self, mock_order):
        """Test payment that requires user action (3D Secure)"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_order
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Mock gateway response with action required
        mock_response = PaymentResponse(
            success=True,
            gateway_payment_id="pi_test123",
            status=PaymentStatus.REQUIRES_ACTION,
            amount=Decimal("99.99"),
            currency="USD",
            requires_action=True,
            action_url="https://stripe.com/3ds/test123",
        )

        # Mock gateway and action service
        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = AsyncMock(return_value=mock_response)
            mock_gateways.get.return_value = mock_gateway

            with patch(
                "modules.payments.services.payment_service.payment_action_service"
            ) as mock_action_service:
                mock_action_service.handle_requires_action = AsyncMock(
                    return_value={
                        "payment_id": "pay_test123",
                        "action_required": True,
                        "action_type": "3d_secure",
                        "action_url": "https://stripe.com/3ds/test123",
                    }
                )

                # Execute
                payment = await payment_service.create_payment(
                    db=db,
                    order_id=123,
                    gateway=PaymentGateway.STRIPE,
                    amount=Decimal("99.99"),
                    currency="USD",
                )

                # Assert
                assert payment.status == PaymentStatus.REQUIRES_ACTION
                mock_action_service.handle_requires_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_payment_failure(self, mock_order):
        """Test payment creation failure"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_order
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        # Mock gateway response with failure
        mock_response = PaymentResponse(
            success=False,
            status=PaymentStatus.FAILED,
            error_code="card_declined",
            error_message="Your card was declined",
        )

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = AsyncMock(return_value=mock_response)
            mock_gateways.get.return_value = mock_gateway

            # Execute
            payment = await payment_service.create_payment(
                db=db,
                order_id=123,
                gateway=PaymentGateway.STRIPE,
                amount=Decimal("99.99"),
                currency="USD",
            )

            # Assert
            assert payment.status == PaymentStatus.FAILED
            assert payment.failure_code == "card_declined"
            assert payment.failure_message == "Your card was declined"

    @pytest.mark.asyncio
    async def test_create_refund_full(self, mock_payment):
        """Test full refund creation"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_payment
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock(
            return_value=Mock(
                scalars=Mock(return_value=Mock(all=Mock(return_value=[])))
            )
        )

        mock_payment.status = PaymentStatus.COMPLETED

        # Mock gateway response
        mock_response = RefundResponse(
            success=True,
            gateway_refund_id="re_test123",
            status=RefundStatus.COMPLETED,
            amount=Decimal("99.99"),
            currency="USD",
            processed_at=datetime.utcnow(),
        )

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            with patch.object(payment_service, "_gateway_configs") as mock_configs:
                mock_gateway = AsyncMock()
                mock_gateway.create_refund = AsyncMock(return_value=mock_response)
                mock_gateways.get.return_value = mock_gateway
                mock_configs.get.return_value = {"supports_refunds": True}

                # Execute
                refund = await payment_service.create_refund(
                    db=db, payment_id=1, reason="Customer requested refund"
                )

                # Assert
                assert refund.status == RefundStatus.COMPLETED
                assert refund.amount == Decimal("99.99")
                assert mock_payment.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    async def test_create_refund_partial(self, mock_payment):
        """Test partial refund creation"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_payment
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock(
            return_value=Mock(
                scalars=Mock(return_value=Mock(all=Mock(return_value=[])))
            )
        )

        mock_payment.status = PaymentStatus.COMPLETED

        # Mock gateway response
        mock_response = RefundResponse(
            success=True,
            gateway_refund_id="re_test123",
            status=RefundStatus.COMPLETED,
            amount=Decimal("50.00"),
            currency="USD",
            processed_at=datetime.utcnow(),
        )

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            with patch.object(payment_service, "_gateway_configs") as mock_configs:
                mock_gateway = AsyncMock()
                mock_gateway.create_refund = AsyncMock(return_value=mock_response)
                mock_gateways.get.return_value = mock_gateway
                mock_configs.get.return_value = {
                    "supports_refunds": True,
                    "supports_partial_refunds": True,
                }

                # Execute
                refund = await payment_service.create_refund(
                    db=db,
                    payment_id=1,
                    amount=Decimal("50.00"),
                    reason="Partial refund for damaged item",
                )

                # Assert
                assert refund.status == RefundStatus.COMPLETED
                assert refund.amount == Decimal("50.00")
                assert mock_payment.status == PaymentStatus.PARTIALLY_REFUNDED

    @pytest.mark.asyncio
    async def test_save_payment_method(self):
        """Test saving a payment method"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.add = Mock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()

        # Mock customer
        mock_customer = Mock()
        mock_customer.id = 456
        mock_customer.email = "test@example.com"
        mock_customer.name = "Test Customer"
        db.get.return_value = mock_customer

        # Mock gateway response
        mock_response = Mock()
        mock_response.success = True
        mock_response.gateway_payment_method_id = "pm_test123"
        mock_response.method_type = PaymentMethod.CARD
        mock_response.display_name = "Visa ending in 4242"
        mock_response.card_details = {
            "last4": "4242",
            "brand": "visa",
            "exp_month": 12,
            "exp_year": 2025,
        }

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            with patch.object(payment_service, "_gateway_configs") as mock_configs:
                mock_gateway = AsyncMock()
                mock_gateway.save_payment_method = AsyncMock(return_value=mock_response)
                mock_gateway.create_customer = AsyncMock(
                    return_value=Mock(success=True, gateway_customer_id="cus_test123")
                )
                mock_gateways.get.return_value = mock_gateway
                mock_configs.get.return_value = {"supports_save_card": True}

                # Execute
                payment_method = await payment_service.save_payment_method(
                    db=db,
                    customer_id=456,
                    gateway=PaymentGateway.STRIPE,
                    payment_method_token="pm_test_token",
                    set_as_default=True,
                )

                # Assert
                assert payment_method.gateway == PaymentGateway.STRIPE
                assert payment_method.gateway_payment_method_id == "pm_test123"
                assert payment_method.card_last4 == "4242"
                assert payment_method.is_default is True


class TestRetryLogic:
    """Test retry logic for transient errors"""

    @pytest.mark.asyncio
    async def test_payment_retry_on_network_error(self, mock_order):
        """Test that payment creation retries on network errors"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_order
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        # Mock successful response after retry
        mock_response = PaymentResponse(
            success=True,
            gateway_payment_id="pi_test123",
            status=PaymentStatus.COMPLETED,
            amount=Decimal("99.99"),
            currency="USD",
        )

        # Mock gateway with network error then success
        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = AsyncMock(
                side_effect=[ConnectionError("Network error"), mock_response]
            )
            mock_gateways.get.return_value = mock_gateway

            # Patch sleep to speed up test
            with patch("asyncio.sleep", return_value=None):
                # Execute
                payment = await payment_service.create_payment(
                    db=db,
                    order_id=123,
                    gateway=PaymentGateway.STRIPE,
                    amount=Decimal("99.99"),
                    currency="USD",
                )

                # Assert
                assert payment.status == PaymentStatus.COMPLETED
                assert mock_gateway.create_payment.call_count == 2


class TestWebhookProcessing:
    """Test webhook processing"""

    @pytest.mark.asyncio
    async def test_webhook_duplicate_prevention(self):
        """Test that duplicate webhooks are not processed"""
        from modules.payments.services.webhook_service import webhook_service

        # Setup
        db = AsyncMock(spec=AsyncSession)

        # Mock existing webhook
        mock_existing = Mock()
        db.execute = AsyncMock(
            return_value=Mock(scalar_one_or_none=Mock(return_value=mock_existing))
        )

        # Execute
        result = await webhook_service.process_webhook(
            db=db,
            gateway=PaymentGateway.STRIPE,
            headers={"stripe-signature": "test"},
            body=b'{"id": "evt_test123"}',
        )

        # Assert
        assert result["status"] == "success"
        assert result["message"] == "Already processed"

    @pytest.mark.asyncio
    async def test_webhook_signature_verification(self):
        """Test webhook signature verification"""
        from modules.payments.services.webhook_service import webhook_service

        # Setup
        db = AsyncMock(spec=AsyncSession)

        # Mock gateway with invalid signature
        with patch.object(webhook_service, "payment_service") as mock_payment_service:
            mock_gateway = AsyncMock()
            mock_gateway.verify_webhook = AsyncMock(return_value=(False, None))
            mock_payment_service.get_gateway.return_value = mock_gateway

            # Execute
            result = await webhook_service.process_webhook(
                db=db,
                gateway=PaymentGateway.STRIPE,
                headers={"stripe-signature": "invalid"},
                body=b'{"id": "evt_test123"}',
            )

            # Assert
            assert result["status"] == "error"
            assert result["message"] == "Invalid signature"


class TestConcurrency:
    """Test race conditions and concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_payment_creation(self, mock_order):
        """Test handling of concurrent payment creation attempts"""
        # Setup
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = mock_order
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Track payment creation calls
        creation_count = 0

        async def mock_create_payment(*args, **kwargs):
            nonlocal creation_count
            creation_count += 1
            await asyncio.sleep(0.1)  # Simulate processing time
            return PaymentResponse(
                success=True,
                gateway_payment_id=f"pi_test{creation_count}",
                status=PaymentStatus.COMPLETED,
                amount=Decimal("99.99"),
                currency="USD",
            )

        # Mock gateway
        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = mock_create_payment
            mock_gateways.get.return_value = mock_gateway

            # Execute concurrent payments
            tasks = []
            for _ in range(3):
                task = payment_service.create_payment(
                    db=db,
                    order_id=123,
                    gateway=PaymentGateway.STRIPE,
                    amount=Decimal("99.99"),
                    currency="USD",
                )
                tasks.append(task)

            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Assert - all should succeed (idempotency key prevents duplicates)
            assert all(isinstance(r, Payment) for r in results)
            assert creation_count == 3  # Each gets unique idempotency key
