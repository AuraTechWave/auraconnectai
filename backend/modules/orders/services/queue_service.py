"""
Order queue management service for centralized queue operations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, case
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException, status

from ..models.queue_models import (
    OrderQueue,
    QueueItem,
    QueueItemStatusHistory,
    QueueSequenceRule,
    QueueMetrics,
    QueueDisplay,
    QueueType,
    QueueStatus,
    QueueItemStatus,
)
from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from ..models.priority_models import OrderPriorityScore, QueuePriorityConfig
from ..schemas.queue_schemas import (
    QueueCreate,
    QueueUpdate,
    QueueItemCreate,
    QueueItemUpdate,
    MoveItemRequest,
    TransferItemRequest,
    ExpediteItemRequest,
    HoldItemRequest,
    BatchStatusUpdateRequest,
    QueueMetricsRequest,
    SequenceRuleCreate,
    SequenceRuleUpdate,
)
from ...staff.models import StaffMember
from modules.kds.models.kds_models import KitchenStation
from .priority_service import PriorityService

logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing order queues"""

    def __init__(self, db: Session):
        self.db = db

    # Queue Management
    def create_queue(self, queue_data: QueueCreate) -> OrderQueue:
        """Create a new order queue"""
        try:
            # Check for duplicate name
            existing = (
                self.db.query(OrderQueue)
                .filter(OrderQueue.name == queue_data.name)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Queue with name '{queue_data.name}' already exists",
                )

            queue = OrderQueue(**queue_data.dict())
            self.db.add(queue)
            self.db.commit()
            self.db.refresh(queue)

            logger.info(f"Created queue '{queue.name}' of type {queue.queue_type}")
            return queue

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create queue",
            )

    def update_queue(self, queue_id: int, update_data: QueueUpdate) -> OrderQueue:
        """Update queue configuration"""
        queue = self.get_queue(queue_id)

        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(queue, field, value)

        self.db.commit()
        self.db.refresh(queue)

        logger.info(f"Updated queue {queue_id}")
        return queue

    def get_queue(self, queue_id: int) -> OrderQueue:
        """Get queue by ID"""
        queue = self.db.query(OrderQueue).filter(OrderQueue.id == queue_id).first()

        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue {queue_id} not found",
            )

        return queue

    def list_queues(
        self,
        queue_type: Optional[QueueType] = None,
        status_filter: Optional[QueueStatus] = None,
        include_metrics: bool = False,
    ) -> List[OrderQueue]:
        """List all queues with optional filters"""
        query = self.db.query(OrderQueue)

        if queue_type:
            query = query.filter(OrderQueue.queue_type == queue_type)

        if status_filter:
            query = query.filter(OrderQueue.status == status_filter)

        if include_metrics:
            query = query.options(joinedload(OrderQueue.queue_metrics))

        return query.all()

    # Queue Item Management
    def add_to_queue(
        self, item_data: QueueItemCreate, user_id: Optional[int] = None
    ) -> QueueItem:
        """Add an order to a queue"""
        try:
            # Verify queue exists and is active
            queue = self.get_queue(item_data.queue_id)
            if queue.status != QueueStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Queue '{queue.name}' is not active",
                )

            # Check capacity
            if queue.max_capacity and queue.current_size >= queue.max_capacity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Queue '{queue.name}' is at capacity",
                )

            # Verify order exists
            order = self.db.query(Order).filter(Order.id == item_data.order_id).first()
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {item_data.order_id} not found",
                )

            # Check if order already in any queue
            existing_item = (
                self.db.query(QueueItem)
                .filter(
                    QueueItem.order_id == item_data.order_id,
                    QueueItem.status.notin_(
                        [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]
                    ),
                )
                .first()
            )
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Order {item_data.order_id} is already in queue",
                )

            # Calculate priority using priority service
            priority_service = PriorityService(self.db)
            try:
                priority_score = priority_service.calculate_order_priority(
                    order_id=item_data.order_id, queue_id=item_data.queue_id
                )
                calculated_priority = priority_score.normalized_score
            except Exception as e:
                logger.warning(f"Failed to calculate priority, using default: {str(e)}")
                calculated_priority = item_data.priority or queue.priority or 0

            # Apply sequencing rules with calculated priority
            priority, sequence_adjustment = self._apply_sequence_rules(
                queue, order, item_data, calculated_priority
            )

            # Get appropriate sequence number based on priority
            if queue.auto_sequence:
                sequence_number = self._get_priority_based_sequence(queue.id, priority)
            else:
                sequence_number = self._get_next_sequence_number(queue.id)

            # Create queue item
            queue_item = QueueItem(
                queue_id=item_data.queue_id,
                order_id=item_data.order_id,
                sequence_number=sequence_number + sequence_adjustment,
                priority=priority,
                is_expedited=item_data.is_expedited,
                display_name=item_data.display_name
                or self._generate_display_name(order),
                display_details=item_data.display_details,
                customer_name=item_data.customer_name or self._get_customer_name(order),
                assigned_to_id=item_data.assign_to_id,
                station_id=item_data.station_id,
                hold_until=item_data.hold_until,
                hold_reason=item_data.hold_reason,
                estimated_ready_time=item_data.estimated_ready_time
                or self._calculate_estimated_time(queue, order),
            )

            if item_data.hold_until:
                queue_item.status = QueueItemStatus.ON_HOLD

            self.db.add(queue_item)

            # Update queue size
            queue.current_size += 1

            # Create status history
            self._add_status_history(
                queue_item, None, QueueItemStatus.QUEUED, user_id, "Added to queue"
            )

            self.db.commit()
            self.db.refresh(queue_item)

            logger.info(
                f"Added order {item_data.order_id} to queue {queue.name} at position {queue_item.sequence_number}"
            )
            return queue_item

        except IntegrityError as e:
            self.db.rollback()
            if "uq_queue_sequence" in str(e):
                # Sequence number conflict, retry with recalculated sequence
                return self.add_to_queue(item_data, user_id)
            raise
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add item to queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add item to queue",
            )

    def update_queue_item(
        self, item_id: int, update_data: QueueItemUpdate, user_id: Optional[int] = None
    ) -> QueueItem:
        """Update a queue item"""
        item = self.get_queue_item(item_id)
        old_status = item.status

        update_dict = update_data.dict(exclude_unset=True)

        # Handle status changes
        if "status" in update_dict:
            new_status = update_dict["status"]
            self._validate_status_transition(old_status, new_status)

            # Update timestamps based on status
            if new_status == QueueItemStatus.IN_PREPARATION:
                item.started_at = datetime.utcnow()
            elif new_status == QueueItemStatus.READY:
                item.ready_at = datetime.utcnow()
                if item.started_at:
                    item.prep_time_actual = int(
                        (item.ready_at - item.started_at).total_seconds() / 60
                    )
            elif new_status == QueueItemStatus.COMPLETED:
                item.completed_at = datetime.utcnow()
                if item.queued_at:
                    item.wait_time_actual = int(
                        (item.completed_at - item.queued_at).total_seconds() / 60
                    )

        # Update fields
        for field, value in update_dict.items():
            setattr(item, field, value)

        # Add status history if changed
        if old_status != item.status:
            self._add_status_history(item, old_status, item.status, user_id)

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Updated queue item {item_id}")
        return item

    def get_queue_item(self, item_id: int) -> QueueItem:
        """Get queue item by ID"""
        item = self.db.query(QueueItem).filter(QueueItem.id == item_id).first()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue item {item_id} not found",
            )

        return item

    def get_queue_items(
        self,
        queue_id: int,
        status_filter: Optional[List[QueueItemStatus]] = None,
        include_completed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueueItem]:
        """Get items in a queue"""
        query = self.db.query(QueueItem).filter(QueueItem.queue_id == queue_id)

        if status_filter:
            query = query.filter(QueueItem.status.in_(status_filter))
        elif not include_completed:
            query = query.filter(
                QueueItem.status.notin_(
                    [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]
                )
            )

        # Order by priority desc, sequence asc
        query = query.order_by(
            QueueItem.priority.desc(), QueueItem.sequence_number.asc()
        )

        return query.offset(offset).limit(limit).all()

    # Queue Operations
    def move_item(
        self, move_request: MoveItemRequest, user_id: Optional[int] = None
    ) -> QueueItem:
        """Move item to new position in queue"""
        item = self.get_queue_item(move_request.item_id)

        if item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move completed or cancelled items",
            )

        old_position = item.sequence_number
        new_position = move_request.new_position

        if old_position == new_position:
            return item

        # Get all items that need to be resequenced
        if new_position < old_position:
            # Moving up - shift items down
            affected_items = (
                self.db.query(QueueItem)
                .filter(
                    QueueItem.queue_id == item.queue_id,
                    QueueItem.sequence_number >= new_position,
                    QueueItem.sequence_number < old_position,
                    QueueItem.id != item.id,
                )
                .all()
            )

            for affected in affected_items:
                affected.sequence_number += 1
        else:
            # Moving down - shift items up
            affected_items = (
                self.db.query(QueueItem)
                .filter(
                    QueueItem.queue_id == item.queue_id,
                    QueueItem.sequence_number > old_position,
                    QueueItem.sequence_number <= new_position,
                    QueueItem.id != item.id,
                )
                .all()
            )

            for affected in affected_items:
                affected.sequence_number -= 1

        # Update item position
        item.sequence_number = new_position

        # Log the move
        if move_request.reason:
            self._add_status_history(
                item,
                item.status,
                item.status,
                user_id,
                f"Moved from position {old_position} to {new_position}: {move_request.reason}",
            )

        self.db.commit()
        self.db.refresh(item)

        logger.info(
            f"Moved queue item {item.id} from position {old_position} to {new_position}"
        )
        return item

    def transfer_item(
        self, transfer_request: TransferItemRequest, user_id: Optional[int] = None
    ) -> QueueItem:
        """Transfer item to another queue"""
        item = self.get_queue_item(transfer_request.item_id)
        target_queue = self.get_queue(transfer_request.target_queue_id)

        if target_queue.status != QueueStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target queue '{target_queue.name}' is not active",
            )

        old_queue_id = item.queue_id

        # Remove from old queue
        old_queue = self.get_queue(old_queue_id)
        old_queue.current_size -= 1

        # Add to new queue
        item.queue_id = transfer_request.target_queue_id
        item.sequence_number = self._get_next_sequence_number(target_queue.id)

        if not transfer_request.maintain_priority:
            item.priority = target_queue.priority

        target_queue.current_size += 1

        # Log transfer
        self._add_status_history(
            item,
            item.status,
            item.status,
            user_id,
            f"Transferred from '{old_queue.name}' to '{target_queue.name}': {transfer_request.reason}",
        )

        self.db.commit()
        self.db.refresh(item)

        logger.info(
            f"Transferred item {item.id} from queue {old_queue_id} to {target_queue.id}"
        )
        return item

    def expedite_item(
        self, expedite_request: ExpediteItemRequest, user_id: Optional[int] = None
    ) -> QueueItem:
        """Expedite an item in the queue"""
        item = self.get_queue_item(expedite_request.item_id)

        if item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot expedite completed or cancelled items",
            )

        # Update priority
        old_priority = item.priority
        item.priority += expedite_request.priority_boost
        item.is_expedited = True

        # Move to front if requested
        if expedite_request.move_to_front:
            # Find the first non-expedited item
            first_position = (
                self.db.query(func.min(QueueItem.sequence_number))
                .filter(
                    QueueItem.queue_id == item.queue_id,
                    QueueItem.status.notin_(
                        [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]
                    ),
                )
                .scalar()
                or 1
            )

            if item.sequence_number > first_position:
                move_request = MoveItemRequest(
                    item_id=item.id,
                    new_position=first_position,
                    reason=f"Expedited: {expedite_request.reason}",
                )
                return self.move_item(move_request, user_id)

        # Log expedite
        self._add_status_history(
            item,
            item.status,
            item.status,
            user_id,
            f"Expedited (priority {old_priority} → {item.priority}): {expedite_request.reason}",
        )

        self.db.commit()
        self.db.refresh(item)

        logger.info(
            f"Expedited item {item.id} with priority boost {expedite_request.priority_boost}"
        )
        return item

    def hold_item(
        self, hold_request: HoldItemRequest, user_id: Optional[int] = None
    ) -> QueueItem:
        """Put an item on hold"""
        item = self.get_queue_item(hold_request.item_id)

        if item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot hold completed or cancelled items",
            )

        old_status = item.status
        item.status = QueueItemStatus.ON_HOLD
        item.hold_reason = hold_request.reason

        if hold_request.hold_until:
            item.hold_until = hold_request.hold_until
        elif hold_request.hold_minutes:
            item.hold_until = datetime.utcnow() + timedelta(
                minutes=hold_request.hold_minutes
            )

        # Add status history
        self._add_status_history(
            item,
            old_status,
            QueueItemStatus.ON_HOLD,
            user_id,
            f"Hold until {item.hold_until}: {hold_request.reason}",
        )

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Put item {item.id} on hold until {item.hold_until}")
        return item

    def release_hold(self, item_id: int, user_id: Optional[int] = None) -> QueueItem:
        """Release an item from hold"""
        item = self.get_queue_item(item_id)

        if item.status != QueueItemStatus.ON_HOLD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Item is not on hold"
            )

        item.status = QueueItemStatus.QUEUED
        item.hold_until = None
        item.hold_reason = None

        # Add status history
        self._add_status_history(
            item,
            QueueItemStatus.ON_HOLD,
            QueueItemStatus.QUEUED,
            user_id,
            "Released from hold",
        )

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Released item {item.id} from hold")
        return item

    def batch_update_status(
        self, batch_request: BatchStatusUpdateRequest, user_id: Optional[int] = None
    ) -> List[QueueItem]:
        """Update status of multiple items"""
        items = (
            self.db.query(QueueItem)
            .filter(QueueItem.id.in_(batch_request.item_ids))
            .all()
        )

        if len(items) != len(batch_request.item_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more items not found",
            )

        updated_items = []
        for item in items:
            old_status = item.status

            # Validate transition
            self._validate_status_transition(old_status, batch_request.new_status)

            # Update status
            item.status = batch_request.new_status

            # Update timestamps
            if batch_request.new_status == QueueItemStatus.IN_PREPARATION:
                item.started_at = datetime.utcnow()
            elif batch_request.new_status == QueueItemStatus.READY:
                item.ready_at = datetime.utcnow()
            elif batch_request.new_status == QueueItemStatus.COMPLETED:
                item.completed_at = datetime.utcnow()

            # Add history
            self._add_status_history(
                item,
                old_status,
                batch_request.new_status,
                user_id,
                batch_request.reason or "Batch status update",
            )

            updated_items.append(item)

        self.db.commit()

        logger.info(
            f"Batch updated {len(items)} items to status {batch_request.new_status}"
        )
        return updated_items

    # Queue Analytics
    def get_queue_metrics(self, metrics_request: QueueMetricsRequest) -> Dict[str, Any]:
        """Get queue performance metrics"""
        query = self.db.query(QueueMetrics)

        if metrics_request.queue_id:
            query = query.filter(QueueMetrics.queue_id == metrics_request.queue_id)

        query = query.filter(
            QueueMetrics.metric_date >= metrics_request.start_date,
            QueueMetrics.metric_date <= metrics_request.end_date,
        )

        metrics = query.all()

        # Aggregate metrics based on granularity
        return self._aggregate_metrics(metrics, metrics_request.granularity)

    def get_queue_status_summary(self, queue_id: int) -> Dict[str, Any]:
        """Get current queue status summary"""
        queue = self.get_queue(queue_id)

        # Get item counts by status
        status_counts = (
            self.db.query(QueueItem.status, func.count(QueueItem.id))
            .filter(QueueItem.queue_id == queue_id)
            .group_by(QueueItem.status)
            .all()
        )

        status_dict = {status.value: count for status, count in status_counts}

        # Get current wait times
        active_items = (
            self.db.query(QueueItem)
            .filter(
                QueueItem.queue_id == queue_id,
                QueueItem.status.in_(
                    [QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION]
                ),
            )
            .all()
        )

        wait_times = []
        for item in active_items:
            wait_time = (datetime.utcnow() - item.queued_at).total_seconds() / 60
            wait_times.append(wait_time)

        # Calculate metrics
        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
        max_wait = max(wait_times) if wait_times else 0

        # Get next ready time
        next_ready = (
            self.db.query(func.min(QueueItem.estimated_ready_time))
            .filter(
                QueueItem.queue_id == queue_id,
                QueueItem.status == QueueItemStatus.IN_PREPARATION,
            )
            .scalar()
        )

        # Get staff count
        staff_count = (
            self.db.query(func.count(func.distinct(QueueItem.assigned_to_id)))
            .filter(
                QueueItem.queue_id == queue_id,
                QueueItem.status == QueueItemStatus.IN_PREPARATION,
                QueueItem.assigned_to_id.isnot(None),
            )
            .scalar()
            or 0
        )

        return {
            "queue_id": queue.id,
            "queue_name": queue.name,
            "status": queue.status.value,
            "current_size": queue.current_size,
            "active_items": status_dict.get(QueueItemStatus.QUEUED.value, 0)
            + status_dict.get(QueueItemStatus.IN_PREPARATION.value, 0),
            "ready_items": status_dict.get(QueueItemStatus.READY.value, 0),
            "on_hold_items": status_dict.get(QueueItemStatus.ON_HOLD.value, 0),
            "avg_wait_time": round(avg_wait, 1),
            "longest_wait_time": round(max_wait, 1),
            "next_ready_time": next_ready,
            "staff_assigned": staff_count,
            "capacity_percentage": (
                (queue.current_size / queue.max_capacity * 100)
                if queue.max_capacity
                else 0
            ),
        }

    # Sequence Rules
    def create_sequence_rule(self, rule_data: SequenceRuleCreate) -> QueueSequenceRule:
        """Create a new sequence rule"""
        rule = QueueSequenceRule(**rule_data.dict())
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        logger.info(f"Created sequence rule '{rule.name}' for queue {rule.queue_id}")
        return rule

    def update_sequence_rule(
        self, rule_id: int, update_data: SequenceRuleUpdate
    ) -> QueueSequenceRule:
        """Update a sequence rule"""
        rule = (
            self.db.query(QueueSequenceRule)
            .filter(QueueSequenceRule.id == rule_id)
            .first()
        )

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sequence rule {rule_id} not found",
            )

        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)

        self.db.commit()
        self.db.refresh(rule)

        return rule

    # Helper Methods
    def _get_next_sequence_number(self, queue_id: int) -> int:
        """Get next available sequence number for queue"""
        max_seq = (
            self.db.query(func.max(QueueItem.sequence_number))
            .filter(QueueItem.queue_id == queue_id)
            .scalar()
            or 0
        )

        return max_seq + 1

    def _get_priority_based_sequence(self, queue_id: int, priority: float) -> int:
        """Get sequence number based on priority score"""
        # Get all active items in queue ordered by sequence
        items = (
            self.db.query(QueueItem)
            .filter(
                and_(
                    QueueItem.queue_id == queue_id,
                    QueueItem.status.in_(
                        [QueueItemStatus.QUEUED, QueueItemStatus.ON_HOLD]
                    ),
                )
            )
            .order_by(QueueItem.sequence_number)
            .all()
        )

        if not items:
            return 1

        # Find appropriate position based on priority
        for i, item in enumerate(items):
            if priority > item.priority:
                # Insert before this item
                return item.sequence_number

        # If priority is lowest, add at end
        return items[-1].sequence_number + 1

    def _apply_sequence_rules(
        self,
        queue: OrderQueue,
        order: Order,
        item_data: QueueItemCreate,
        calculated_priority: float = None,
    ) -> Tuple[int, int]:
        """Apply sequence rules and return priority and sequence adjustment"""
        priority = (
            calculated_priority
            if calculated_priority is not None
            else (item_data.priority or queue.priority)
        )
        sequence_adjustment = 0

        # Get active rules for queue
        rules = (
            self.db.query(QueueSequenceRule)
            .filter(
                QueueSequenceRule.queue_id == queue.id,
                QueueSequenceRule.is_active == True,
            )
            .order_by(QueueSequenceRule.priority.desc())
            .all()
        )

        for rule in rules:
            if self._evaluate_rule_conditions(rule.conditions, order):
                priority += rule.priority_adjustment
                sequence_adjustment += rule.sequence_adjustment

                if rule.auto_expedite:
                    item_data.is_expedited = True

                if rule.assign_to_station:
                    item_data.station_id = rule.assign_to_station

                logger.info(f"Applied sequence rule '{rule.name}' to order {order.id}")

        return priority, sequence_adjustment

    def _evaluate_rule_conditions(
        self, conditions: Dict[str, Any], order: Order
    ) -> bool:
        """Evaluate rule conditions against order"""
        # Simple condition evaluation - can be enhanced
        for field, expected in conditions.items():
            if field == "order_type":
                order_type = self._determine_order_type(order)
                if isinstance(expected, list):
                    if order_type not in expected:
                        return False
                elif order_type != expected:
                    return False

            elif field == "total_amount_gt":
                if float(order.final_amount or 0) <= expected:
                    return False

            elif field == "vip_customer":
                if order.customer:
                    is_vip = getattr(order.customer, "vip_status", False)
                    if is_vip != expected:
                        return False

        return True

    def _determine_order_type(self, order: Order) -> str:
        """Determine order type from order data"""
        if order.table_no:
            return "dine_in"
        # Add more logic based on order attributes
        return "takeout"

    def _generate_display_name(self, order: Order) -> str:
        """Generate display name for queue item"""
        items = (
            self.db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .limit(3)
            .all()
        )

        if not items:
            return f"Order #{order.id}"

        item_names = [
            item.menu_item.name if hasattr(item, "menu_item") else f"Item {item.id}"
            for item in items
        ]

        display = f"Order #{order.id}: {', '.join(item_names[:2])}"
        if len(items) > 2:
            display += f" +{len(items) - 2} more"

        return display

    def _get_customer_name(self, order: Order) -> Optional[str]:
        """Get customer name from order"""
        if order.customer:
            return order.customer.name
        return None

    def _calculate_estimated_time(self, queue: OrderQueue, order: Order) -> datetime:
        """Calculate estimated ready time"""
        # Get current queue load
        active_items = (
            self.db.query(func.count(QueueItem.id))
            .filter(
                QueueItem.queue_id == queue.id,
                QueueItem.status.in_(
                    [QueueItemStatus.QUEUED, QueueItemStatus.IN_PREPARATION]
                ),
            )
            .scalar()
            or 0
        )

        # Simple calculation - can be enhanced with ML
        prep_time = queue.default_prep_time
        wait_time = active_items * 5  # 5 minutes per item in queue

        return datetime.utcnow() + timedelta(minutes=prep_time + wait_time)

    def _validate_status_transition(
        self, old_status: QueueItemStatus, new_status: QueueItemStatus
    ):
        """Validate status transition is allowed"""
        valid_transitions = {
            QueueItemStatus.QUEUED: [
                QueueItemStatus.IN_PREPARATION,
                QueueItemStatus.ON_HOLD,
                QueueItemStatus.CANCELLED,
            ],
            QueueItemStatus.IN_PREPARATION: [
                QueueItemStatus.READY,
                QueueItemStatus.ON_HOLD,
                QueueItemStatus.CANCELLED,
            ],
            QueueItemStatus.READY: [QueueItemStatus.COMPLETED, QueueItemStatus.ON_HOLD],
            QueueItemStatus.ON_HOLD: [
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION,
                QueueItemStatus.CANCELLED,
            ],
            QueueItemStatus.COMPLETED: [],
            QueueItemStatus.CANCELLED: [],
            QueueItemStatus.DELAYED: [
                QueueItemStatus.QUEUED,
                QueueItemStatus.CANCELLED,
            ],
        }

        if new_status not in valid_transitions.get(old_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {old_status.value} to {new_status.value}",
            )

    def _add_status_history(
        self,
        item: QueueItem,
        old_status: Optional[QueueItemStatus],
        new_status: QueueItemStatus,
        user_id: Optional[int],
        reason: Optional[str] = None,
    ):
        """Add status history entry"""
        history = QueueItemStatusHistory(
            queue_item_id=item.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=user_id,
            reason=reason,
        )
        self.db.add(history)

    def _aggregate_metrics(
        self, metrics: List[QueueMetrics], granularity: str
    ) -> Dict[str, Any]:
        """Aggregate metrics based on granularity"""
        # Implementation depends on specific requirements
        # This is a simplified version
        if not metrics:
            return {}

        total_queued = sum(m.items_queued for m in metrics)
        total_completed = sum(m.items_completed for m in metrics)
        avg_wait = (
            sum(m.avg_wait_time for m in metrics) / len(metrics) if metrics else 0
        )

        return {
            "period": {
                "start": min(m.metric_date for m in metrics),
                "end": max(m.metric_date for m in metrics),
            },
            "volume": {
                "items_queued": total_queued,
                "items_completed": total_completed,
                "completion_rate": (
                    (total_completed / total_queued * 100) if total_queued else 0
                ),
            },
            "timing": {
                "avg_wait_time": round(avg_wait, 1),
                "max_wait_time": max((m.max_wait_time for m in metrics), default=0),
            },
        }

    def rebalance_queue_priorities(
        self, queue_id: int, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Rebalance queue items based on current priorities"""
        try:
            # Check if priority-based rebalancing is enabled
            config = (
                self.db.query(QueuePriorityConfig)
                .filter(QueuePriorityConfig.queue_id == queue_id)
                .first()
            )

            if not config or not config.rebalance_enabled:
                return {
                    "success": False,
                    "message": "Priority rebalancing is not enabled for this queue",
                }

            # Use priority service to rebalance
            priority_service = PriorityService(self.db)
            result = priority_service.rebalance_queue(queue_id)

            # Log the rebalance action
            if result.get("rebalanced") and result.get("changes"):
                logger.info(
                    f"Queue {queue_id} rebalanced by user {user_id}. "
                    f"{result['items_reordered']} items reordered."
                )

            return {
                "success": result.get("rebalanced", False),
                "message": result.get("reason", "Rebalancing completed"),
                "items_reordered": result.get("items_reordered", 0),
                "changes": result.get("changes", []),
            }

        except Exception as e:
            logger.error(f"Failed to rebalance queue {queue_id}: {str(e)}")
            return {"success": False, "message": f"Failed to rebalance queue: {str(e)}"}
