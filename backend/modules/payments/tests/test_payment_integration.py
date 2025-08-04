# backend/modules/payments/tests/test_payment_integration.py

import pytest
from decimal import Decimal
from datetime import datetime
import asyncio
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from modules.payments.models import (
    Payment, Refund, PaymentGateway, PaymentStatus,
    RefundStatus, PaymentGatewayConfig
)
from modules.payments.services import payment_service
from modules.orders.models import Order
from modules.customers.models import Customer


@pytest.mark.integration
class TestPaymentIntegration:
    """Integration tests for payment system"""
    
    @pytest.fixture
    async def setup_test_data(self, async_session: AsyncSession):
        """Setup test data"""
        # Create customer
        customer = Customer(
            name="Test Customer",
            email="test@example.com",
            phone="+1234567890"
        )
        async_session.add(customer)
        
        # Create order
        order = Order(
            customer_id=customer.id,
            customer_email=customer.email,
            customer_name=customer.name,
            order_number="TEST-001",
            total_amount=Decimal("150.00"),
            payment_status="pending"
        )
        async_session.add(order)
        
        # Create gateway configs
        for gateway in [PaymentGateway.STRIPE, PaymentGateway.SQUARE, PaymentGateway.PAYPAL]:
            config = PaymentGatewayConfig(
                gateway=gateway,
                is_active=True,
                is_test_mode=True,
                config={
                    "test_key": "test_value"
                },
                supports_refunds=True,
                supports_partial_refunds=True,
                fee_percentage=Decimal("2.9"),
                fee_fixed=Decimal("0.30")
            )
            async_session.add(config)
        
        await async_session.commit()
        
        return {
            "customer": customer,
            "order": order
        }
    
    @pytest.mark.asyncio
    async def test_complete_payment_flow(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test complete payment flow: create -> capture -> refund"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # 1. Create payment
        payment = await payment_service.create_payment(
            db=async_session,
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            amount=order.total_amount,
            currency="USD"
        )
        
        assert payment.id is not None
        assert payment.payment_id.startswith("pay_")
        assert payment.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]
        assert payment.amount == order.total_amount
        
        # 2. Simulate payment completion (normally done by webhook)
        payment.status = PaymentStatus.COMPLETED
        payment.processed_at = datetime.utcnow()
        await async_session.commit()
        
        # 3. Create partial refund
        refund1 = await payment_service.create_refund(
            db=async_session,
            payment_id=payment.id,
            amount=Decimal("50.00"),
            reason="Partial refund for damaged item"
        )
        
        assert refund1.id is not None
        assert refund1.refund_id.startswith("ref_")
        assert refund1.amount == Decimal("50.00")
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED
        
        # 4. Create another partial refund
        refund2 = await payment_service.create_refund(
            db=async_session,
            payment_id=payment.id,
            amount=Decimal("100.00"),
            reason="Remaining refund"
        )
        
        assert refund2.amount == Decimal("100.00")
        assert payment.status == PaymentStatus.REFUNDED
    
    @pytest.mark.asyncio
    async def test_multi_gateway_payments(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test creating payments with different gateways"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # Create payments with different gateways
        gateways = [
            PaymentGateway.STRIPE,
            PaymentGateway.SQUARE,
            PaymentGateway.PAYPAL
        ]
        
        payments = []
        for gateway in gateways:
            payment = await payment_service.create_payment(
                db=async_session,
                order_id=order.id,
                gateway=gateway,
                amount=Decimal("50.00"),
                currency="USD"
            )
            payments.append(payment)
        
        # Verify all payments created
        assert len(payments) == 3
        assert all(p.gateway == g for p, g in zip(payments, gateways))
        assert all(p.amount == Decimal("50.00") for p in payments)
    
    @pytest.mark.asyncio
    async def test_payment_idempotency(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test idempotency key prevents duplicate payments"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # Create payment with specific idempotency key
        idempotency_key = "test_idempotency_123"
        
        payment1 = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key
        )
        async_session.add(payment1)
        await async_session.commit()
        
        # Try to create another payment with same idempotency key
        payment2 = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key
        )
        async_session.add(payment2)
        
        # Should raise integrity error
        with pytest.raises(Exception):  # IntegrityError
            await async_session.commit()
    
    @pytest.mark.asyncio
    async def test_concurrent_refunds(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test handling concurrent refund requests"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # Create and complete a payment
        payment = await payment_service.create_payment(
            db=async_session,
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            amount=Decimal("200.00"),
            currency="USD"
        )
        
        payment.status = PaymentStatus.COMPLETED
        await async_session.commit()
        
        # Attempt concurrent refunds
        async def create_refund(amount: Decimal):
            try:
                return await payment_service.create_refund(
                    db=async_session,
                    payment_id=payment.id,
                    amount=amount,
                    reason=f"Refund of ${amount}"
                )
            except Exception as e:
                return e
        
        # Create multiple refund tasks
        tasks = [
            create_refund(Decimal("50.00")),
            create_refund(Decimal("75.00")),
            create_refund(Decimal("100.00"))  # This should fail (exceeds total)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful_refunds = [r for r in results if isinstance(r, Refund)]
        failed_refunds = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_refunds) == 2  # Only 2 should succeed
        assert len(failed_refunds) == 1  # 1 should fail
        assert sum(r.amount for r in successful_refunds) <= payment.amount
    
    @pytest.mark.asyncio
    async def test_webhook_race_condition(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test handling of duplicate webhook events"""
        from modules.payments.services.webhook_service import webhook_service
        
        order = setup_test_data["order"]
        
        # Create a payment
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            gateway_payment_id="pi_test123",
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentStatus.PROCESSING
        )
        async_session.add(payment)
        await async_session.commit()
        
        # Simulate duplicate webhook events
        webhook_body = b'{"id": "evt_duplicate_test", "type": "payment_intent.succeeded"}'
        headers = {"stripe-signature": "test_signature"}
        
        # Process webhook multiple times concurrently
        tasks = []
        for _ in range(5):
            task = webhook_service.process_webhook(
                db=async_session,
                gateway=PaymentGateway.STRIPE,
                headers=headers,
                body=webhook_body
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Only first should process, others should detect duplicate
        processed = [r for r in results if r.get("message") != "Already processed"]
        duplicates = [r for r in results if r.get("message") == "Already processed"]
        
        assert len(processed) <= 1  # At most one processed
        assert len(duplicates) >= 4  # Others detected as duplicates


@pytest.mark.integration
class TestPaymentSecurity:
    """Security-related integration tests"""
    
    @pytest.mark.asyncio
    async def test_payment_amount_validation(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test payment amount validation"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # Test negative amount
        with pytest.raises(ValueError, match="amount must be positive"):
            await payment_service.create_payment(
                db=async_session,
                order_id=order.id,
                gateway=PaymentGateway.STRIPE,
                amount=Decimal("-10.00"),
                currency="USD"
            )
        
        # Test zero amount
        with pytest.raises(ValueError, match="amount must be positive"):
            await payment_service.create_payment(
                db=async_session,
                order_id=order.id,
                gateway=PaymentGateway.STRIPE,
                amount=Decimal("0.00"),
                currency="USD"
            )
    
    @pytest.mark.asyncio
    async def test_refund_amount_validation(
        self,
        async_session: AsyncSession,
        setup_test_data
    ):
        """Test refund amount validation"""
        order = setup_test_data["order"]
        
        # Initialize payment service
        await payment_service.initialize(async_session)
        
        # Create and complete payment
        payment = await payment_service.create_payment(
            db=async_session,
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            amount=Decimal("100.00"),
            currency="USD"
        )
        
        payment.status = PaymentStatus.COMPLETED
        await async_session.commit()
        
        # Test refund exceeding payment amount
        with pytest.raises(ValueError, match="exceeds payment amount"):
            await payment_service.create_refund(
                db=async_session,
                payment_id=payment.id,
                amount=Decimal("150.00"),
                reason="Invalid refund"
            )
        
        # Test negative refund amount
        with pytest.raises(ValueError, match="amount must be positive"):
            await payment_service.create_refund(
                db=async_session,
                payment_id=payment.id,
                amount=Decimal("-10.00"),
                reason="Invalid refund"
            )