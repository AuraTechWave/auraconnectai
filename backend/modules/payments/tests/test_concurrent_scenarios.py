# backend/modules/payments/tests/test_concurrent_scenarios.py

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
import random
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.payments.models import (
    Payment,
    Refund,
    PaymentGateway,
    PaymentStatus,
    RefundStatus,
    PaymentWebhook,
)
from modules.payments.services import payment_service, webhook_service
from modules.orders.models import Order
from modules.customers.models import Customer


@pytest.mark.asyncio
@pytest.mark.integration
class TestConcurrentPaymentScenarios:
    """Test concurrent payment operations and race conditions"""

    @pytest.fixture
    async def setup_concurrent_test_data(self, async_session: AsyncSession):
        """Setup data for concurrent tests"""
        customers = []
        orders = []

        # Create multiple customers and orders
        for i in range(10):
            customer = Customer(
                name=f"Customer {i}",
                email=f"customer{i}@example.com",
                phone=f"+123456789{i}",
            )
            async_session.add(customer)
            customers.append(customer)

        await async_session.flush()

        for i, customer in enumerate(customers):
            order = Order(
                customer_id=customer.id,
                customer_email=customer.email,
                customer_name=customer.name,
                order_number=f"CONC-{i:03d}",
                total_amount=Decimal(random.uniform(50, 500)),
                payment_status="pending",
            )
            async_session.add(order)
            orders.append(order)

        await async_session.commit()

        return {"customers": customers, "orders": orders}

    @pytest.mark.asyncio
    async def test_concurrent_payment_creation_same_order(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test multiple concurrent payment attempts for the same order"""
        order = setup_concurrent_test_data["orders"][0]

        # Mock gateway to simulate processing delay
        async def slow_create_payment(*args, **kwargs):
            await asyncio.sleep(random.uniform(0.1, 0.3))
            return Mock(
                success=True,
                gateway_payment_id=f"pi_{uuid.uuid4().hex[:8]}",
                status=PaymentStatus.PROCESSING,
                amount=order.total_amount,
                currency="USD",
                fee_amount=Decimal("3.00"),
                net_amount=order.total_amount - Decimal("3.00"),
            )

        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = slow_create_payment
            mock_gateways.get.return_value = mock_gateway

            # Attempt to create multiple payments concurrently
            tasks = []
            for i in range(5):
                task = payment_service.create_payment(
                    db=async_session,
                    order_id=order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=order.total_amount,
                    currency="USD",
                )
                tasks.append(task)

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify results
            successful_payments = [r for r in results if isinstance(r, Payment)]
            errors = [r for r in results if isinstance(r, Exception)]

            # All should succeed (each gets unique payment_id)
            assert len(successful_payments) == 5
            assert len(errors) == 0

            # Verify all payments have unique IDs
            payment_ids = [p.payment_id for p in successful_payments]
            assert len(set(payment_ids)) == 5

    @pytest.mark.asyncio
    async def test_concurrent_refunds_race_condition(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test race condition when multiple refunds exceed payment amount"""
        order = setup_concurrent_test_data["orders"][1]

        # Create a completed payment
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            gateway_payment_id="pi_test123",
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentStatus.COMPLETED,
            customer_id=order.customer_id,
        )
        async_session.add(payment)
        await async_session.commit()

        # Mock gateway refund
        async def mock_create_refund(*args, **kwargs):
            await asyncio.sleep(random.uniform(0.05, 0.15))
            return Mock(
                success=True,
                gateway_refund_id=f"re_{uuid.uuid4().hex[:8]}",
                status=RefundStatus.COMPLETED,
                amount=args[0].amount,
                currency="USD",
            )

        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_refund = mock_create_refund
            mock_gateways.get.return_value = mock_gateway

            with patch.object(payment_service, "_gateway_configs") as mock_configs:
                mock_configs.get.return_value = {
                    "supports_refunds": True,
                    "supports_partial_refunds": True,
                }

                # Create concurrent refund tasks that would exceed payment amount
                refund_amounts = [
                    Decimal("40.00"),
                    Decimal("35.00"),
                    Decimal("30.00"),
                    Decimal("25.00"),  # Total: 130.00 > 100.00
                ]

                tasks = []
                for amount in refund_amounts:
                    task = payment_service.create_refund(
                        db=async_session,
                        payment_id=payment.id,
                        amount=amount,
                        reason=f"Refund ${amount}",
                    )
                    tasks.append(task)

                # Execute concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results
                successful_refunds = [r for r in results if isinstance(r, Refund)]
                failed_refunds = [r for r in results if isinstance(r, Exception)]

                # Calculate total refunded
                total_refunded = sum(r.amount for r in successful_refunds)

                # Total refunded should not exceed payment amount
                assert total_refunded <= payment.amount
                assert len(failed_refunds) >= 1  # At least one should fail

    @pytest.mark.asyncio
    async def test_concurrent_payment_status_updates(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test concurrent webhook status updates for same payment"""
        order = setup_concurrent_test_data["orders"][2]

        # Create a processing payment
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            gateway_payment_id="pi_concurrent_test",
            amount=Decimal("200.00"),
            currency="USD",
            status=PaymentStatus.PROCESSING,
        )
        async_session.add(payment)
        await async_session.commit()

        # Simulate concurrent webhook events
        webhook_events = [
            {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_concurrent_test", "status": "succeeded"}},
            },
            {
                "type": "payment_intent.payment_failed",
                "data": {"object": {"id": "pi_concurrent_test", "status": "failed"}},
            },
            {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_concurrent_test", "status": "succeeded"}},
            },
        ]

        # Mock gateway webhook verification
        with patch.object(webhook_service, "payment_service") as mock_payment_service:
            mock_gateway = AsyncMock()
            mock_gateway.verify_webhook = AsyncMock(
                side_effect=[(True, event) for event in webhook_events]
            )
            mock_payment_service.get_gateway.return_value = mock_gateway

            # Process webhooks concurrently
            tasks = []
            for i, event in enumerate(webhook_events):
                task = webhook_service.process_webhook(
                    db=async_session,
                    gateway=PaymentGateway.STRIPE,
                    headers={"stripe-signature": f"sig_{i}"},
                    body=str(event).encode(),
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Refresh payment
            await async_session.refresh(payment)

            # Payment should have a final status (not mixed state)
            assert payment.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED]

    @pytest.mark.asyncio
    async def test_concurrent_payment_method_operations(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test concurrent save/delete operations on payment methods"""
        customer = setup_concurrent_test_data["customers"][0]

        # Mock gateway responses
        save_responses = []
        for i in range(5):
            save_responses.append(
                Mock(
                    success=True,
                    gateway_payment_method_id=f"pm_{i}",
                    method_type="card",
                    display_name=f"Card {i}",
                    card_details={"last4": f"{i:04d}", "brand": "visa"},
                )
            )

        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.save_payment_method = AsyncMock(side_effect=save_responses)
            mock_gateway.delete_payment_method = AsyncMock(return_value=True)
            mock_gateway.create_customer = AsyncMock(
                return_value=Mock(success=True, gateway_customer_id="cus_test123")
            )
            mock_gateways.get.return_value = mock_gateway

            with patch.object(payment_service, "_gateway_configs") as mock_configs:
                mock_configs.get.return_value = {"supports_save_card": True}

                # Save multiple payment methods concurrently
                save_tasks = []
                for i in range(5):
                    task = payment_service.save_payment_method(
                        db=async_session,
                        customer_id=customer.id,
                        gateway=PaymentGateway.STRIPE,
                        payment_method_token=f"tok_{i}",
                        set_as_default=(i == 0),  # First one is default
                    )
                    save_tasks.append(task)

                saved_methods = await asyncio.gather(*save_tasks)

                # Verify all saved
                assert len(saved_methods) == 5

                # Now delete some concurrently while listing
                delete_tasks = []
                list_tasks = []

                # Delete first 3
                for method in saved_methods[:3]:
                    delete_task = payment_service.delete_payment_method(
                        db=async_session, payment_method_id=method.id
                    )
                    delete_tasks.append(delete_task)

                # List methods while deleting
                for _ in range(3):
                    list_task = payment_service.list_customer_payment_methods(
                        db=async_session,
                        customer_id=customer.id,
                        gateway=PaymentGateway.STRIPE,
                    )
                    list_tasks.append(list_task)

                # Execute all operations concurrently
                all_tasks = delete_tasks + list_tasks
                results = await asyncio.gather(*all_tasks, return_exceptions=True)

                # Final list should have 2 active methods
                final_methods = await payment_service.list_customer_payment_methods(
                    db=async_session,
                    customer_id=customer.id,
                    gateway=PaymentGateway.STRIPE,
                )

                assert len(final_methods) == 2

    @pytest.mark.asyncio
    async def test_high_volume_concurrent_payments(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test system behavior under high concurrent load"""
        orders = setup_concurrent_test_data["orders"]

        # Statistics tracking
        stats = {"total": 0, "successful": 0, "failed": 0, "duration": 0}

        # Mock gateway with realistic behavior
        async def realistic_payment(*args, **kwargs):
            # Simulate network latency
            await asyncio.sleep(random.uniform(0.1, 0.5))

            # Simulate occasional failures
            if random.random() < 0.05:  # 5% failure rate
                raise ConnectionError("Network timeout")

            if random.random() < 0.02:  # 2% decline rate
                return Mock(
                    success=False,
                    status=PaymentStatus.FAILED,
                    error_code="card_declined",
                    error_message="Card declined",
                )

            return Mock(
                success=True,
                gateway_payment_id=f"pi_{uuid.uuid4().hex[:8]}",
                status=PaymentStatus.COMPLETED,
                amount=kwargs["request"].amount,
                currency="USD",
                fee_amount=kwargs["request"].amount * Decimal("0.029"),
                net_amount=kwargs["request"].amount * Decimal("0.971"),
            )

        with patch.object(payment_service, "_gateways") as mock_gateways:
            mock_gateway = AsyncMock()
            mock_gateway.create_payment = realistic_payment
            mock_gateways.get.return_value = mock_gateway

            # Create many concurrent payment tasks
            start_time = asyncio.get_event_loop().time()

            tasks = []
            for i in range(50):  # 50 concurrent payments
                order = orders[i % len(orders)]
                task = payment_service.create_payment(
                    db=async_session,
                    order_id=order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=order.total_amount,
                    currency="USD",
                )
                tasks.append(task)

            # Execute with timeout
            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = asyncio.get_event_loop().time()
            stats["duration"] = end_time - start_time

            # Analyze results
            for result in results:
                stats["total"] += 1
                if isinstance(result, Payment):
                    if result.status == PaymentStatus.COMPLETED:
                        stats["successful"] += 1
                    else:
                        stats["failed"] += 1
                else:
                    stats["failed"] += 1

            # Performance assertions
            assert stats["duration"] < 10  # Should complete within 10 seconds
            assert stats["successful"] / stats["total"] > 0.9  # >90% success rate

            # Verify database consistency
            payment_count = await async_session.scalar(select(func.count(Payment.id)))
            assert payment_count == stats["total"]

    @pytest.mark.asyncio
    async def test_payment_action_expiry_race_condition(
        self, async_session: AsyncSession, setup_concurrent_test_data
    ):
        """Test race condition between action completion and expiry"""
        from modules.payments.services.payment_action_service import (
            payment_action_service,
        )

        order = setup_concurrent_test_data["orders"][3]

        # Create payment requiring action
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            gateway_payment_id="pi_action_test",
            amount=Decimal("150.00"),
            currency="USD",
            status=PaymentStatus.REQUIRES_ACTION,
            metadata={
                "action_required": {
                    "type": "3d_secure",
                    "url": "https://stripe.com/3ds/test",
                    "requested_at": datetime.utcnow().isoformat(),
                    "expires_at": datetime.utcnow().isoformat(),  # Already expired
                }
            },
        )
        async_session.add(payment)
        await async_session.commit()

        # Concurrent operations
        async def complete_action():
            await asyncio.sleep(0.1)
            return await payment_action_service.complete_action(
                db=async_session, payment_id=payment.id, success=True
            )

        async def check_expiry():
            await asyncio.sleep(0.05)
            return await payment_action_service.check_expired_actions(
                db=async_session, cancel_expired=True
            )

        # Race between completion and expiry check
        results = await asyncio.gather(
            complete_action(), check_expiry(), return_exceptions=True
        )

        # Refresh payment
        await async_session.refresh(payment)

        # Payment should have a definitive status
        assert payment.status in [
            PaymentStatus.PROCESSING,  # Completed action
            PaymentStatus.CANCELLED,  # Expired
        ]
