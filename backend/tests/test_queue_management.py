"""
Tests for order queue management system.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from modules.orders.models.queue_models import (
    OrderQueue, QueueItem, QueueItemStatusHistory,
    QueueSequenceRule, QueueMetrics,
    QueueType, QueueStatus, QueueItemStatus
)
from modules.orders.models.order_models import Order, OrderItem, OrderStatus
from modules.orders.schemas.queue_schemas import (
    QueueCreate, QueueUpdate, QueueItemCreate, QueueItemUpdate,
    MoveItemRequest, TransferItemRequest, ExpediteItemRequest,
    HoldItemRequest, BatchStatusUpdateRequest,
    SequenceRuleCreate
)
from modules.orders.services.queue_service import QueueService
from modules.staff.models import StaffMember
from modules.customers.models import Customer


@pytest.fixture
def queue_service(db_session: Session):
    """Create queue service instance."""
    return QueueService(db_session)


@pytest.fixture
def sample_queue(db_session: Session):
    """Create a sample queue."""
    queue = OrderQueue(
        name="Main Kitchen",
        queue_type=QueueType.KITCHEN,
        status=QueueStatus.ACTIVE,
        display_name="Kitchen Queue",
        priority=5,
        max_capacity=50,
        default_prep_time=15,
        warning_threshold=5,
        critical_threshold=10,
        color_code="#FF5733"
    )
    db_session.add(queue)
    db_session.commit()
    return queue


@pytest.fixture
def sample_orders(db_session: Session):
    """Create sample orders."""
    customer = Customer(
        name="Test Customer",
        email="test@example.com",
        phone="555-1234"
    )
    db_session.add(customer)
    db_session.flush()
    
    orders = []
    for i in range(5):
        order = Order(
            customer_id=customer.id,
            table_no=i + 1,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal(f"{20 + i * 10}.00"),
            final_amount=Decimal(f"{20 + i * 10}.00"),
            created_at=datetime.utcnow()
        )
        db_session.add(order)
        orders.append(order)
    
    db_session.commit()
    return orders


@pytest.fixture
def sample_staff(db_session: Session):
    """Create sample staff members."""
    staff = []
    for i in range(3):
        member = StaffMember(
            first_name=f"Staff{i+1}",
            last_name="Member",
            email=f"staff{i+1}@test.com",
            phone=f"555-000{i+1}",
            role="cook",
            is_active=True
        )
        db_session.add(member)
        staff.append(member)
    
    db_session.commit()
    return staff


class TestQueueManagement:
    """Test queue CRUD operations."""
    
    def test_create_queue(self, queue_service, db_session):
        """Test creating a new queue."""
        queue_data = QueueCreate(
            name="Bar Queue",
            queue_type=QueueType.BAR,
            display_name="Bar Orders",
            priority=3,
            max_capacity=20,
            default_prep_time=10,
            color_code="#3498DB"
        )
        
        queue = queue_service.create_queue(queue_data)
        
        assert queue.id is not None
        assert queue.name == "Bar Queue"
        assert queue.queue_type == QueueType.BAR
        assert queue.status == QueueStatus.ACTIVE
        assert queue.current_size == 0
    
    def test_create_duplicate_queue_fails(self, queue_service, db_session, sample_queue):
        """Test that creating a queue with duplicate name fails."""
        queue_data = QueueCreate(
            name=sample_queue.name,  # Duplicate name
            queue_type=QueueType.KITCHEN
        )
        
        with pytest.raises(HTTPException) as exc_info:
            queue_service.create_queue(queue_data)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)
    
    def test_update_queue(self, queue_service, db_session, sample_queue):
        """Test updating queue configuration."""
        update_data = QueueUpdate(
            display_name="Updated Kitchen",
            max_capacity=100,
            status=QueueStatus.PAUSED
        )
        
        updated_queue = queue_service.update_queue(sample_queue.id, update_data)
        
        assert updated_queue.display_name == "Updated Kitchen"
        assert updated_queue.max_capacity == 100
        assert updated_queue.status == QueueStatus.PAUSED
    
    def test_list_queues(self, queue_service, db_session):
        """Test listing queues with filters."""
        # Create multiple queues
        for queue_type in [QueueType.KITCHEN, QueueType.BAR, QueueType.DELIVERY]:
            queue_data = QueueCreate(
                name=f"{queue_type.value.title()} Queue",
                queue_type=queue_type
            )
            queue_service.create_queue(queue_data)
        
        # List all queues
        all_queues = queue_service.list_queues()
        assert len(all_queues) >= 3
        
        # Filter by type
        kitchen_queues = queue_service.list_queues(queue_type=QueueType.KITCHEN)
        assert all(q.queue_type == QueueType.KITCHEN for q in kitchen_queues)
        
        # Filter by status
        active_queues = queue_service.list_queues(status_filter=QueueStatus.ACTIVE)
        assert all(q.status == QueueStatus.ACTIVE for q in active_queues)


class TestQueueItemOperations:
    """Test queue item management."""
    
    def test_add_to_queue(self, queue_service, db_session, sample_queue, sample_orders):
        """Test adding an order to queue."""
        order = sample_orders[0]
        
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=order.id,
            priority=5,
            display_name=f"Order #{order.id}"
        )
        
        item = queue_service.add_to_queue(item_data)
        
        assert item.id is not None
        assert item.queue_id == sample_queue.id
        assert item.order_id == order.id
        assert item.sequence_number == 1
        assert item.status == QueueItemStatus.QUEUED
        
        # Check queue size updated
        db_session.refresh(sample_queue)
        assert sample_queue.current_size == 1
    
    def test_add_to_inactive_queue_fails(self, queue_service, db_session, sample_queue, sample_orders):
        """Test that adding to inactive queue fails."""
        # Make queue inactive
        sample_queue.status = QueueStatus.CLOSED
        db_session.commit()
        
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            queue_service.add_to_queue(item_data)
        
        assert exc_info.value.status_code == 400
        assert "not active" in str(exc_info.value.detail)
    
    def test_queue_capacity_limit(self, queue_service, db_session, sample_queue, sample_orders):
        """Test queue capacity enforcement."""
        # Set small capacity
        sample_queue.max_capacity = 2
        db_session.commit()
        
        # Add items up to capacity
        for i in range(2):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=sample_orders[i].id
            )
            queue_service.add_to_queue(item_data)
        
        # Try to exceed capacity
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[2].id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            queue_service.add_to_queue(item_data)
        
        assert exc_info.value.status_code == 400
        assert "at capacity" in str(exc_info.value.detail)
    
    def test_update_queue_item_status(self, queue_service, db_session, sample_queue, sample_orders):
        """Test updating queue item status."""
        # Add item to queue
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        # Update to in preparation
        update_data = QueueItemUpdate(
            status=QueueItemStatus.IN_PREPARATION,
            assigned_to_id=1
        )
        updated_item = queue_service.update_queue_item(item.id, update_data)
        
        assert updated_item.status == QueueItemStatus.IN_PREPARATION
        assert updated_item.started_at is not None
        
        # Update to ready
        update_data = QueueItemUpdate(status=QueueItemStatus.READY)
        updated_item = queue_service.update_queue_item(item.id, update_data)
        
        assert updated_item.status == QueueItemStatus.READY
        assert updated_item.ready_at is not None
        assert updated_item.prep_time_actual is not None


class TestQueueSequencing:
    """Test queue sequencing and prioritization."""
    
    def test_sequence_number_assignment(self, queue_service, db_session, sample_queue, sample_orders):
        """Test automatic sequence number assignment."""
        items = []
        
        # Add multiple items
        for i, order in enumerate(sample_orders[:3]):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=order.id
            )
            item = queue_service.add_to_queue(item_data)
            items.append(item)
        
        # Check sequence numbers
        assert items[0].sequence_number == 1
        assert items[1].sequence_number == 2
        assert items[2].sequence_number == 3
    
    def test_move_item_in_queue(self, queue_service, db_session, sample_queue, sample_orders):
        """Test moving items within queue."""
        # Add items
        items = []
        for i in range(4):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=sample_orders[i].id
            )
            item = queue_service.add_to_queue(item_data)
            items.append(item)
        
        # Move item from position 4 to position 2
        move_request = MoveItemRequest(
            item_id=items[3].id,
            new_position=2,
            reason="Priority customer"
        )
        moved_item = queue_service.move_item(move_request)
        
        # Check new positions
        assert moved_item.sequence_number == 2
        
        # Check other items shifted
        db_session.refresh(items[1])
        db_session.refresh(items[2])
        assert items[1].sequence_number == 3
        assert items[2].sequence_number == 4
    
    def test_expedite_item(self, queue_service, db_session, sample_queue, sample_orders):
        """Test expediting an item."""
        # Add regular items
        for i in range(3):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=sample_orders[i].id,
                priority=0
            )
            queue_service.add_to_queue(item_data)
        
        # Add item to expedite
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[3].id,
            priority=0
        )
        item = queue_service.add_to_queue(item_data)
        
        # Expedite it
        expedite_request = ExpediteItemRequest(
            item_id=item.id,
            priority_boost=20,
            move_to_front=True,
            reason="VIP customer"
        )
        expedited = queue_service.expedite_item(expedite_request)
        
        assert expedited.priority == 20
        assert expedited.is_expedited == True
        assert expedited.sequence_number == 1  # Moved to front


class TestQueueTransfers:
    """Test transferring items between queues."""
    
    def test_transfer_item_between_queues(self, queue_service, db_session, sample_orders):
        """Test transferring item to another queue."""
        # Create two queues
        queue1_data = QueueCreate(name="Queue 1", queue_type=QueueType.KITCHEN)
        queue2_data = QueueCreate(name="Queue 2", queue_type=QueueType.BAR)
        
        queue1 = queue_service.create_queue(queue1_data)
        queue2 = queue_service.create_queue(queue2_data)
        
        # Add item to first queue
        item_data = QueueItemCreate(
            queue_id=queue1.id,
            order_id=sample_orders[0].id,
            priority=10
        )
        item = queue_service.add_to_queue(item_data)
        
        # Transfer to second queue
        transfer_request = TransferItemRequest(
            item_id=item.id,
            target_queue_id=queue2.id,
            maintain_priority=True,
            reason="Wrong queue initially"
        )
        transferred = queue_service.transfer_item(transfer_request)
        
        assert transferred.queue_id == queue2.id
        assert transferred.priority == 10  # Priority maintained
        
        # Check queue sizes
        db_session.refresh(queue1)
        db_session.refresh(queue2)
        assert queue1.current_size == 0
        assert queue2.current_size == 1


class TestHoldOperations:
    """Test hold/release operations."""
    
    def test_hold_item_with_time(self, queue_service, db_session, sample_queue, sample_orders):
        """Test putting item on hold with specific time."""
        # Add item
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        # Hold until specific time
        hold_until = datetime.utcnow() + timedelta(hours=1)
        hold_request = HoldItemRequest(
            item_id=item.id,
            hold_until=hold_until,
            reason="Customer requested later pickup"
        )
        held_item = queue_service.hold_item(hold_request)
        
        assert held_item.status == QueueItemStatus.ON_HOLD
        assert held_item.hold_until == hold_until
        assert held_item.hold_reason == "Customer requested later pickup"
    
    def test_hold_item_with_duration(self, queue_service, db_session, sample_queue, sample_orders):
        """Test putting item on hold for duration."""
        # Add item
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        # Hold for 30 minutes
        hold_request = HoldItemRequest(
            item_id=item.id,
            hold_minutes=30,
            reason="Waiting for ingredients"
        )
        held_item = queue_service.hold_item(hold_request)
        
        assert held_item.status == QueueItemStatus.ON_HOLD
        assert held_item.hold_until is not None
        expected_time = datetime.utcnow() + timedelta(minutes=30)
        assert abs((held_item.hold_until - expected_time).total_seconds()) < 60  # Within 1 minute
    
    def test_release_hold(self, queue_service, db_session, sample_queue, sample_orders):
        """Test releasing item from hold."""
        # Add and hold item
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        hold_request = HoldItemRequest(
            item_id=item.id,
            hold_minutes=30,
            reason="Test hold"
        )
        queue_service.hold_item(hold_request)
        
        # Release hold
        released = queue_service.release_hold(item.id)
        
        assert released.status == QueueItemStatus.QUEUED
        assert released.hold_until is None
        assert released.hold_reason is None


class TestBatchOperations:
    """Test batch update operations."""
    
    def test_batch_status_update(self, queue_service, db_session, sample_queue, sample_orders):
        """Test updating multiple items at once."""
        # Add multiple items
        item_ids = []
        for i in range(3):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=sample_orders[i].id
            )
            item = queue_service.add_to_queue(item_data)
            item_ids.append(item.id)
        
        # Batch update to in preparation
        batch_request = BatchStatusUpdateRequest(
            item_ids=item_ids,
            new_status=QueueItemStatus.IN_PREPARATION,
            reason="Batch start preparation"
        )
        updated_items = queue_service.batch_update_status(batch_request)
        
        assert len(updated_items) == 3
        assert all(item.status == QueueItemStatus.IN_PREPARATION for item in updated_items)
        assert all(item.started_at is not None for item in updated_items)


class TestSequenceRules:
    """Test automatic sequencing rules."""
    
    def test_sequence_rule_priority_adjustment(self, queue_service, db_session, sample_queue, sample_orders):
        """Test rule that adjusts priority."""
        # Create rule for high-value orders
        rule_data = SequenceRuleCreate(
            queue_id=sample_queue.id,
            name="High Value Priority",
            conditions={"total_amount_gt": 50},
            priority_adjustment=10,
            is_active=True
        )
        rule = queue_service.create_sequence_rule(rule_data)
        
        # Add low-value order
        item_data1 = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id  # $20 order
        )
        item1 = queue_service.add_to_queue(item_data1)
        
        # Add high-value order
        item_data2 = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[4].id  # $60 order
        )
        item2 = queue_service.add_to_queue(item_data2)
        
        # Check priorities
        assert item1.priority == sample_queue.priority  # Default priority
        assert item2.priority == sample_queue.priority + 10  # Boosted priority


class TestQueueMetrics:
    """Test queue metrics and analytics."""
    
    def test_queue_status_summary(self, queue_service, db_session, sample_queue, sample_orders):
        """Test getting queue status summary."""
        # Add items in various states
        for i, status in enumerate([
            QueueItemStatus.QUEUED,
            QueueItemStatus.IN_PREPARATION,
            QueueItemStatus.READY,
            QueueItemStatus.ON_HOLD
        ]):
            item_data = QueueItemCreate(
                queue_id=sample_queue.id,
                order_id=sample_orders[i].id
            )
            item = queue_service.add_to_queue(item_data)
            
            if status != QueueItemStatus.QUEUED:
                update_data = QueueItemUpdate(status=status)
                queue_service.update_queue_item(item.id, update_data)
        
        # Get summary
        summary = queue_service.get_queue_status_summary(sample_queue.id)
        
        assert summary["queue_id"] == sample_queue.id
        assert summary["queue_name"] == sample_queue.name
        assert summary["active_items"] == 2  # Queued + In Preparation
        assert summary["ready_items"] == 1
        assert summary["on_hold_items"] == 1


class TestStatusTransitions:
    """Test status transition validation."""
    
    def test_valid_status_transitions(self, queue_service, db_session, sample_queue, sample_orders):
        """Test valid status transitions."""
        # Add item
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        # Valid transitions
        transitions = [
            (QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION),
            (QueueItemStatus.IN_PREPARATION, QueueItemStatus.READY),
            (QueueItemStatus.READY, QueueItemStatus.COMPLETED)
        ]
        
        for old_status, new_status in transitions:
            # Set to old status first
            item.status = old_status
            db_session.commit()
            
            # Update to new status
            update_data = QueueItemUpdate(status=new_status)
            updated = queue_service.update_queue_item(item.id, update_data)
            assert updated.status == new_status
    
    def test_invalid_status_transition(self, queue_service, db_session, sample_queue, sample_orders):
        """Test invalid status transition."""
        # Add item
        item_data = QueueItemCreate(
            queue_id=sample_queue.id,
            order_id=sample_orders[0].id
        )
        item = queue_service.add_to_queue(item_data)
        
        # Try invalid transition (queued -> completed)
        update_data = QueueItemUpdate(status=QueueItemStatus.COMPLETED)
        
        with pytest.raises(HTTPException) as exc_info:
            queue_service.update_queue_item(item.id, update_data)
        
        assert exc_info.value.status_code == 400
        assert "Invalid status transition" in str(exc_info.value.detail)