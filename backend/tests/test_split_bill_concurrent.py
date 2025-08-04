# backend/tests/test_split_bill_concurrent.py

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from modules.payments.models.split_bill_models import (
    BillSplit, SplitParticipant, PaymentAllocation,
    SplitMethod, SplitStatus, ParticipantStatus
)
from modules.payments.models.payment_models import Payment, PaymentStatus, PaymentGateway
from modules.payments.services.split_bill_service import split_bill_service
from modules.orders.models.order_models import Order


class TestConcurrentSplitBillOperations:
    """Test concurrent operations on split bills"""
    
    @pytest.mark.asyncio
    async def test_concurrent_participant_payments(
        self, db: AsyncSession, test_order: Order
    ):
        """Test multiple participants paying simultaneously"""
        
        # Create a split with 5 participants
        participants = [
            {"name": f"User{i}", "email": f"user{i}@example.com"}
            for i in range(5)
        ]
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants
        )
        
        # Prepare concurrent payment tasks
        async def make_payment(participant_id: int, amount: Decimal):
            """Simulate a participant making a payment"""
            try:
                # Create a payment record
                payment = Payment(
                    order_id=test_order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=amount,
                    currency="USD",
                    status=PaymentStatus.COMPLETED,
                    customer_email=f"user{participant_id}@example.com"
                )
                db.add(payment)
                await db.flush()
                
                # Record the payment
                allocation = await split_bill_service.record_participant_payment(
                    db, participant_id, payment, amount
                )
                
                await db.commit()
                return allocation
                
            except Exception as e:
                await db.rollback()
                raise e
        
        # Run payments concurrently
        tasks = []
        for i, participant in enumerate(split.participants):
            # Each participant pays their share
            task = make_payment(participant.id, participant.total_amount)
            tasks.append(task)
        
        # Execute all payments simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_payments = [r for r in results if not isinstance(r, Exception)]
        failed_payments = [r for r in results if isinstance(r, Exception)]
        
        # All payments should succeed due to row-level locking
        assert len(successful_payments) == 5
        assert len(failed_payments) == 0
        
        # Verify split status
        await db.refresh(split)
        assert split.status == SplitStatus.COMPLETED
        
        # Verify all participants are marked as paid
        for participant in split.participants:
            await db.refresh(participant)
            assert participant.status == ParticipantStatus.PAID
            assert participant.paid_amount >= participant.total_amount
    
    @pytest.mark.asyncio
    async def test_concurrent_partial_payments(
        self, db: AsyncSession, test_order: Order
    ):
        """Test concurrent partial payments from same participant"""
        
        # Create a simple split
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=[
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"}
            ]
        )
        
        alice = split.participants[0]
        half_amount = alice.total_amount / 2
        
        # Simulate two concurrent partial payments
        async def make_partial_payment(payment_num: int):
            """Make a partial payment"""
            try:
                payment = Payment(
                    order_id=test_order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=half_amount,
                    currency="USD",
                    status=PaymentStatus.COMPLETED,
                    customer_email="alice@example.com",
                    metadata={"payment_num": payment_num}
                )
                db.add(payment)
                await db.flush()
                
                allocation = await split_bill_service.record_participant_payment(
                    db, alice.id, payment, half_amount
                )
                
                await db.commit()
                return allocation
                
            except Exception as e:
                await db.rollback()
                raise e
        
        # Run two partial payments concurrently
        results = await asyncio.gather(
            make_partial_payment(1),
            make_partial_payment(2),
            return_exceptions=True
        )
        
        # Both should succeed with proper locking
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 2
        
        # Verify total paid amount
        await db.refresh(alice)
        assert alice.paid_amount == alice.total_amount
        assert alice.status == ParticipantStatus.PAID
        
        # Verify two allocations exist
        allocations = await db.execute(
            select(PaymentAllocation).where(
                PaymentAllocation.participant_id == alice.id
            )
        )
        assert len(allocations.scalars().all()) == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_status_updates(
        self, db: AsyncSession, test_order: Order
    ):
        """Test concurrent participant status updates"""
        
        # Create split requiring acceptance
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=[
                {"name": f"User{i}", "email": f"user{i}@example.com"}
                for i in range(10)
            ],
            settings={"require_all_acceptance": True}
        )
        
        assert split.status == SplitStatus.PENDING
        
        # All participants accept simultaneously
        async def accept_participation(participant_id: int):
            """Accept participation"""
            try:
                participant = await split_bill_service.update_participant_status(
                    db, participant_id, ParticipantStatus.ACCEPTED
                )
                return participant
            except Exception as e:
                return e
        
        tasks = [
            accept_participation(p.id)
            for p in split.participants
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 10
        
        # Split should be active after all accept
        await db.refresh(split)
        assert split.status == SplitStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_payment_allocation_race_condition(
        self, db: AsyncSession, test_order: Order
    ):
        """Test prevention of duplicate payment allocations"""
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=[
                {"name": "Alice", "email": "alice@example.com"}
            ]
        )
        
        participant = split.participants[0]
        
        # Create a single payment
        payment = Payment(
            order_id=test_order.id,
            gateway=PaymentGateway.STRIPE,
            amount=participant.total_amount,
            currency="USD",
            status=PaymentStatus.COMPLETED
        )
        db.add(payment)
        await db.commit()
        
        # Try to allocate the same payment twice concurrently
        async def allocate_payment():
            try:
                allocation = await split_bill_service.record_participant_payment(
                    db, participant.id, payment, participant.total_amount
                )
                return allocation
            except Exception as e:
                return e
        
        # Run allocations concurrently
        results = await asyncio.gather(
            allocate_payment(),
            allocate_payment(),
            return_exceptions=True
        )
        
        # Only one should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful) == 1
        assert len(failed) == 1
        assert "already exists" in str(failed[0])
    
    @pytest.mark.asyncio
    async def test_concurrent_split_cancellation(
        self, db: AsyncSession, test_order: Order
    ):
        """Test concurrent operations during split cancellation"""
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=[
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"}
            ]
        )
        
        # One user tries to pay while another cancels
        async def try_payment():
            try:
                payment = Payment(
                    order_id=test_order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=split.participants[0].total_amount,
                    currency="USD",
                    status=PaymentStatus.COMPLETED
                )
                db.add(payment)
                await db.flush()
                
                allocation = await split_bill_service.record_participant_payment(
                    db, split.participants[0].id, payment, payment.amount
                )
                await db.commit()
                return "payment_succeeded"
            except Exception as e:
                await db.rollback()
                return f"payment_failed: {str(e)}"
        
        async def try_cancel():
            try:
                await split_bill_service.cancel_split(db, split.id, "Changed plans")
                return "cancel_succeeded"
            except Exception as e:
                return f"cancel_failed: {str(e)}"
        
        # Run concurrently
        results = await asyncio.gather(try_payment(), try_cancel())
        
        # One should succeed, depends on timing
        assert "succeeded" in results[0] or "succeeded" in results[1]
        
        # Verify final state is consistent
        await db.refresh(split)
        if split.status == SplitStatus.CANCELLED:
            # If cancelled, payment should have failed
            assert "payment_failed" in results[0]
        else:
            # If payment succeeded, cancel should have failed
            assert "cancel_failed" in results[1]
    
    @pytest.mark.asyncio
    async def test_stress_many_participants(
        self, db: AsyncSession, test_order: Order
    ):
        """Stress test with many participants paying simultaneously"""
        
        # Create split with 50 participants
        num_participants = 50
        participants = [
            {"name": f"User{i}", "email": f"user{i}@example.com"}
            for i in range(num_participants)
        ]
        
        # Increase order amount for meaningful splits
        test_order.total_amount = Decimal("5000.00")
        await db.commit()
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants
        )
        
        # Simulate all participants paying at once
        async def make_payment(participant):
            """Make a payment with some randomness"""
            await asyncio.sleep(0.001 * (participant.id % 10))  # Slight delays
            
            try:
                payment = Payment(
                    order_id=test_order.id,
                    gateway=PaymentGateway.STRIPE,
                    amount=participant.total_amount,
                    currency="USD",
                    status=PaymentStatus.COMPLETED,
                    customer_email=participant.email
                )
                db.add(payment)
                await db.flush()
                
                allocation = await split_bill_service.record_participant_payment(
                    db, participant.id, payment, participant.total_amount
                )
                
                await db.commit()
                return True
                
            except Exception as e:
                await db.rollback()
                return False
        
        # Run all payments
        start_time = datetime.utcnow()
        
        tasks = [make_payment(p) for p in split.participants]
        results = await asyncio.gather(*tasks)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # All should succeed
        assert all(results)
        assert duration < 10  # Should complete reasonably fast
        
        # Verify final state
        await db.refresh(split)
        assert split.status == SplitStatus.COMPLETED
        
        # Verify all allocations
        allocations = await db.execute(
            select(PaymentAllocation).where(
                PaymentAllocation.split_id == split.id
            )
        )
        assert len(allocations.scalars().all()) == num_participants
    
    @pytest.mark.asyncio 
    async def test_concurrent_tip_distribution_updates(
        self, db: AsyncSession, test_order: Order, test_staff_list
    ):
        """Test concurrent updates to tip distributions"""
        
        from modules.payments.services.tip_service import tip_service
        
        # Create a completed split
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=[
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"}
            ],
            tip_method="percentage",
            tip_value=Decimal("20")
        )
        
        # Mark as completed
        split.status = SplitStatus.COMPLETED
        await db.commit()
        
        # Create tip distribution
        distribution = await tip_service.create_tip_distribution(
            db=db,
            split_id=split.id,
            tip_amount=split.tip_amount,
            distribution_method="pool"
        )
        
        # Process distribution
        processed = await tip_service.process_tip_distribution(
            db, distribution.id, processed_by=1
        )
        
        # Try concurrent adjustments
        async def adjust_tips(staff_id: int, amount: float):
            try:
                adjusted = await tip_service.adjust_tip_distribution(
                    db,
                    distribution.id,
                    adjustments=[{
                        'staff_id': staff_id,
                        'new_amount': amount
                    }],
                    adjusted_by=1,
                    reason=f"Adjustment for staff {staff_id}"
                )
                return True
            except Exception as e:
                return False
        
        # Run concurrent adjustments
        tasks = [
            adjust_tips(test_staff_list[0].id, 50.00),
            adjust_tips(test_staff_list[1].id, 30.00),
            adjust_tips(test_staff_list[0].id, 60.00),  # Conflicting adjustment
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some adjustments may fail due to concurrent updates
        successful = [r for r in results if r is True]
        assert len(successful) >= 1  # At least one should succeed
        
        # Verify adjustment history
        await db.refresh(distribution)
        assert 'adjustment_history' in distribution.metadata
        assert len(distribution.metadata['adjustment_history']) >= 1