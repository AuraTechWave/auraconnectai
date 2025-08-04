# backend/tests/test_split_bill.py

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.models.split_bill_models import (
    BillSplit, SplitParticipant, PaymentAllocation, TipDistribution,
    SplitMethod, SplitStatus, ParticipantStatus, TipMethod
)
from modules.payments.services.split_bill_service import split_bill_service
from modules.payments.services.tip_service import tip_service
from modules.orders.models.order_models import Order, OrderItem


class TestSplitBillService:
    """Test cases for split bill functionality"""
    
    @pytest.mark.asyncio
    async def test_create_equal_split(self, db: AsyncSession, test_order: Order):
        """Test creating an equal split among participants"""
        
        # Prepare test data
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
            {"name": "Charlie", "email": "charlie@example.com"}
        ]
        
        # Create split
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants,
            tip_method=TipMethod.PERCENTAGE,
            tip_value=Decimal("18")
        )
        
        assert split is not None
        assert split.split_method == SplitMethod.EQUAL
        assert split.status == SplitStatus.ACTIVE  # No acceptance required
        assert len(split.participants) == 3
        
        # Verify equal distribution
        expected_share = split.total_amount / 3
        for participant in split.participants:
            assert abs(participant.total_amount - expected_share) < Decimal("0.01")
    
    @pytest.mark.asyncio
    async def test_create_percentage_split(self, db: AsyncSession, test_order: Order):
        """Test creating a percentage-based split"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split_config = {
            "percentages": {
                "alice@example.com": 60,
                "bob@example.com": 40
            }
        }
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.PERCENTAGE,
            participants=participants,
            split_config=split_config,
            tip_method=TipMethod.PERCENTAGE,
            tip_value=Decimal("20")
        )
        
        assert split is not None
        assert split.split_method == SplitMethod.PERCENTAGE
        
        # Verify percentage distribution
        alice = next(p for p in split.participants if p.email == "alice@example.com")
        bob = next(p for p in split.participants if p.email == "bob@example.com")
        
        assert abs(alice.total_amount - (split.total_amount * Decimal("0.6"))) < Decimal("0.01")
        assert abs(bob.total_amount - (split.total_amount * Decimal("0.4"))) < Decimal("0.01")
    
    @pytest.mark.asyncio
    async def test_create_amount_split(self, db: AsyncSession, test_order: Order):
        """Test creating a fixed amount split"""
        
        total = test_order.total_amount
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split_config = {
            "amounts": {
                "alice@example.com": float(total * Decimal("0.7")),
                "bob@example.com": float(total * Decimal("0.3"))
            }
        }
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.AMOUNT,
            participants=participants,
            split_config=split_config
        )
        
        assert split is not None
        assert split.split_method == SplitMethod.AMOUNT
        
        alice = next(p for p in split.participants if p.email == "alice@example.com")
        bob = next(p for p in split.participants if p.email == "bob@example.com")
        
        # Amounts should match configured values plus proportional tax/tip
        assert alice.share_amount > bob.share_amount
    
    @pytest.mark.asyncio
    async def test_create_item_split(self, db: AsyncSession, test_order_with_items: Order):
        """Test creating an item-based split"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com", "id": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com", "id": "bob@example.com"}
        ]
        
        # Assume order has 3 items
        split_config = {
            "items": [
                {
                    "item_id": 1,
                    "price": 20.00,
                    "quantity": 1,
                    "participant_ids": ["alice@example.com"]
                },
                {
                    "item_id": 2,
                    "price": 30.00,
                    "quantity": 1,
                    "participant_ids": ["bob@example.com"]
                },
                {
                    "item_id": 3,
                    "price": 10.00,
                    "quantity": 2,
                    "participant_ids": ["alice@example.com", "bob@example.com"]
                }
            ]
        }
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order_with_items.id,
            split_method=SplitMethod.ITEM,
            participants=participants,
            split_config=split_config,
            tip_method=TipMethod.PERCENTAGE,
            tip_value=Decimal("15")
        )
        
        assert split is not None
        assert split.split_method == SplitMethod.ITEM
        
        alice = next(p for p in split.participants if p.email == "alice@example.com")
        bob = next(p for p in split.participants if p.email == "bob@example.com")
        
        # Alice should pay for item 1 (20) + half of item 3 (10)
        # Bob should pay for item 2 (30) + half of item 3 (10)
        assert alice.share_amount < bob.share_amount  # 30 < 40
    
    @pytest.mark.asyncio
    async def test_participant_acceptance_flow(self, db: AsyncSession, test_order: Order):
        """Test participant acceptance/decline flow"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants,
            settings={"require_all_acceptance": True}
        )
        
        assert split.status == SplitStatus.PENDING  # Requires acceptance
        
        # Alice accepts
        alice = split.participants[0]
        await split_bill_service.update_participant_status(
            db, alice.id, ParticipantStatus.ACCEPTED
        )
        
        # Split should still be pending
        await db.refresh(split)
        assert split.status == SplitStatus.PENDING
        
        # Bob accepts
        bob = split.participants[1]
        await split_bill_service.update_participant_status(
            db, bob.id, ParticipantStatus.ACCEPTED
        )
        
        # Split should now be active
        await db.refresh(split)
        assert split.status == SplitStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_participant_payment_recording(
        self, db: AsyncSession, test_order: Order, test_payment
    ):
        """Test recording participant payments"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants
        )
        
        alice = split.participants[0]
        
        # Record partial payment
        partial_amount = alice.total_amount / 2
        allocation = await split_bill_service.record_participant_payment(
            db, alice.id, test_payment, partial_amount
        )
        
        assert allocation is not None
        assert allocation.allocated_amount == partial_amount
        
        await db.refresh(alice)
        assert alice.paid_amount == partial_amount
        assert alice.status != ParticipantStatus.PAID  # Not fully paid
        
        await db.refresh(split)
        assert split.status == SplitStatus.PARTIALLY_PAID
        
        # Record remaining payment
        remaining = alice.total_amount - partial_amount
        allocation2 = await split_bill_service.record_participant_payment(
            db, alice.id, test_payment, remaining
        )
        
        await db.refresh(alice)
        assert alice.status == ParticipantStatus.PAID
        assert alice.paid_amount >= alice.total_amount
    
    @pytest.mark.asyncio
    async def test_split_cancellation(self, db: AsyncSession, test_order: Order):
        """Test cancelling a split"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants
        )
        
        # Cancel the split
        cancelled_split = await split_bill_service.cancel_split(
            db, split.id, "Changed our minds"
        )
        
        assert cancelled_split.status == SplitStatus.CANCELLED
        assert cancelled_split.metadata.get('cancellation_reason') == "Changed our minds"
        
        # All participants should be declined
        for participant in cancelled_split.participants:
            if participant.status == ParticipantStatus.PENDING:
                await db.refresh(participant)
                assert participant.status == ParticipantStatus.DECLINED
    
    @pytest.mark.asyncio
    async def test_split_expiration(self, db: AsyncSession, test_order: Order):
        """Test split expiration handling"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        split = await split_bill_service.create_split(
            db=db,
            order_id=test_order.id,
            split_method=SplitMethod.EQUAL,
            participants=participants,
            settings={"expires_in_hours": 1}
        )
        
        assert split.expires_at is not None
        assert split.expires_at > datetime.utcnow()
        assert split.expires_at < datetime.utcnow() + timedelta(hours=2)


class TestTipService:
    """Test cases for tip calculation and distribution"""
    
    def test_percentage_tip_calculation(self):
        """Test percentage-based tip calculation"""
        
        subtotal = Decimal("100.00")
        tip = tip_service.calculate_tip(
            subtotal=subtotal,
            tip_method=TipMethod.PERCENTAGE,
            tip_value=Decimal("18")
        )
        
        assert tip == Decimal("18.00")
    
    def test_amount_tip_calculation(self):
        """Test fixed amount tip"""
        
        subtotal = Decimal("100.00")
        tip = tip_service.calculate_tip(
            subtotal=subtotal,
            tip_method=TipMethod.AMOUNT,
            tip_value=Decimal("10.00")
        )
        
        assert tip == Decimal("10.00")
    
    def test_round_up_tip_calculation(self):
        """Test round-up tip calculation"""
        
        subtotal = Decimal("87.43")
        tip = tip_service.calculate_tip(
            subtotal=subtotal,
            tip_method=TipMethod.ROUND_UP,
            tip_value=Decimal("5"),  # Round to nearest $5
            current_total=subtotal
        )
        
        # Should round up to $90 (next $5 increment)
        assert tip == Decimal("2.57")  # 90 - 87.43
    
    def test_tip_suggestions(self):
        """Test tip suggestion generation"""
        
        subtotal = Decimal("50.00")
        suggestions = tip_service.suggest_tip_amounts(subtotal)
        
        assert len(suggestions) >= 4
        assert any(s['percentage'] == 15 for s in suggestions)
        assert any(s['percentage'] == 18 for s in suggestions)
        assert any(s['percentage'] == 20 for s in suggestions)
        
        # Check calculation
        tip_18 = next(s for s in suggestions if s['percentage'] == 18)
        assert tip_18['tip_amount'] == 9.00  # 18% of 50
        assert tip_18['total_amount'] == 59.00
    
    @pytest.mark.asyncio
    async def test_tip_distribution_pool(self, db: AsyncSession, test_staff_list):
        """Test equal tip pool distribution"""
        
        distribution = await tip_service.create_tip_distribution(
            db=db,
            tip_amount=Decimal("100.00"),
            distribution_method="pool"
        )
        
        assert distribution is not None
        
        # Process distribution
        processed = await tip_service.process_tip_distribution(
            db, distribution.id, processed_by=1
        )
        
        assert processed.is_distributed
        assert len(processed.distributions) == len(test_staff_list)
        
        # Each staff should get equal share
        per_person = Decimal("100.00") / len(test_staff_list)
        for dist in processed.distributions:
            assert abs(Decimal(str(dist['amount'])) - per_person) < Decimal("0.01")
    
    @pytest.mark.asyncio
    async def test_tip_distribution_by_role(self, db: AsyncSession, test_staff_by_role):
        """Test role-based tip distribution"""
        
        config = {
            "role_percentages": {
                "server": 50,
                "bartender": 30,
                "busser": 20
            }
        }
        
        distribution = await tip_service.create_tip_distribution(
            db=db,
            tip_amount=Decimal("100.00"),
            distribution_method="role",
            distribution_config=config
        )
        
        processed = await tip_service.process_tip_distribution(
            db, distribution.id, processed_by=1
        )
        
        # Verify role-based distribution
        server_total = sum(
            Decimal(str(d['amount'])) for d in processed.distributions
            if d.get('role') == 'server'
        )
        
        assert abs(server_total - Decimal("50.00")) < Decimal("0.01")
    
    @pytest.mark.asyncio
    async def test_tip_adjustment(self, db: AsyncSession):
        """Test adjusting tip distribution"""
        
        # Create and process initial distribution
        distribution = await tip_service.create_tip_distribution(
            db=db,
            tip_amount=Decimal("100.00"),
            distribution_method="pool"
        )
        
        processed = await tip_service.process_tip_distribution(
            db, distribution.id, processed_by=1
        )
        
        # Adjust one staff member's share
        adjustments = [{
            'staff_id': processed.distributions[0]['staff_id'],
            'new_amount': 40.00  # Give them more
        }]
        
        adjusted = await tip_service.adjust_tip_distribution(
            db,
            distribution.id,
            adjustments,
            adjusted_by=1,
            reason="Extra shift coverage"
        )
        
        assert 'adjustment_history' in adjusted.metadata
        assert len(adjusted.metadata['adjustment_history']) == 1
        
        # Verify adjustment was applied
        adjusted_dist = next(
            d for d in adjusted.distributions
            if d['staff_id'] == adjustments[0]['staff_id']
        )
        assert adjusted_dist['amount'] == 40.00
        assert adjusted_dist.get('adjusted') is True


class TestSplitBillValidation:
    """Test validation and edge cases"""
    
    @pytest.mark.asyncio
    async def test_invalid_percentage_split(self, db: AsyncSession, test_order: Order):
        """Test validation of percentage splits"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        # Percentages don't sum to 100
        split_config = {
            "percentages": {
                "alice@example.com": 60,
                "bob@example.com": 30  # Only 90% total
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            await split_bill_service.create_split(
                db=db,
                order_id=test_order.id,
                split_method=SplitMethod.PERCENTAGE,
                participants=participants,
                split_config=split_config
            )
        
        assert "must sum to 100%" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalid_amount_split(self, db: AsyncSession, test_order: Order):
        """Test validation of amount splits"""
        
        total = test_order.total_amount
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        
        # Amounts don't sum to total
        split_config = {
            "amounts": {
                "alice@example.com": float(total / 2),
                "bob@example.com": float(total / 3)  # Doesn't add up
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            await split_bill_service.create_split(
                db=db,
                order_id=test_order.id,
                split_method=SplitMethod.AMOUNT,
                participants=participants,
                split_config=split_config
            )
        
        assert "must sum to total" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_minimum_participants(self, db: AsyncSession, test_order: Order):
        """Test minimum participant requirement"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"}
        ]
        
        # Should fail with only one participant
        with pytest.raises(ValueError):
            await split_bill_service.create_split(
                db=db,
                order_id=test_order.id,
                split_method=SplitMethod.EQUAL,
                participants=participants
            )
    
    @pytest.mark.asyncio
    async def test_duplicate_participant_emails(self, db: AsyncSession, test_order: Order):
        """Test handling of duplicate participant emails"""
        
        participants = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Alice Smith", "email": "alice@example.com"}  # Same email
        ]
        
        # Should handle or reject duplicates appropriately
        with pytest.raises(Exception):  # Could be IntegrityError or ValueError
            await split_bill_service.create_split(
                db=db,
                order_id=test_order.id,
                split_method=SplitMethod.EQUAL,
                participants=participants
            )