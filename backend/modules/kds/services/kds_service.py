# backend/modules/kds/services/kds_service.py

"""
Main Kitchen Display System service for managing kitchen operations.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import logging

from ..models.kds_models import (
    KitchenStation,
    KitchenDisplay,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from ..schemas.kds_schemas import (
    StationCreate,
    StationUpdate,
    KitchenDisplayCreate,
    KitchenDisplayUpdate,
    OrderItemDisplay,
    StationSummary,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models import StaffMember

logger = logging.getLogger(__name__)


class KDSService:
    """Service for managing Kitchen Display System operations"""

    def __init__(self, db: Session):
        self.db = db

    # Station Management
    def create_station(self, station_data: StationCreate) -> KitchenStation:
        """Create a new kitchen station"""
        station = KitchenStation(
            name=station_data.name,
            station_type=station_data.station_type,
            display_name=station_data.display_name,
            color_code=station_data.color_code,
            priority=station_data.priority,
            max_active_items=station_data.max_active_items,
            prep_time_multiplier=station_data.prep_time_multiplier,
            warning_time_minutes=station_data.warning_time_minutes,
            critical_time_minutes=station_data.critical_time_minutes,
            features=station_data.features,
            printer_id=station_data.printer_id,
        )

        self.db.add(station)
        self.db.commit()
        self.db.refresh(station)

        # Create default display for the station
        self._create_default_display(station.id)

        logger.info(
            f"Created kitchen station: {station.name} ({station.station_type.value})"
        )
        return station

    def _create_default_display(self, station_id: int):
        """Create a default display for a station"""
        display = KitchenDisplay(
            station_id=station_id,
            display_number=1,
            name="Primary Display",
            layout_mode="grid",
            items_per_page=6,
            auto_clear_completed=True,
            auto_clear_delay_seconds=30,
        )
        self.db.add(display)
        self.db.commit()

    def update_station(
        self, station_id: int, update_data: StationUpdate
    ) -> KitchenStation:
        """Update a kitchen station"""
        station = self.db.query(KitchenStation).filter_by(id=station_id).first()
        if not station:
            raise ValueError(f"Station {station_id} not found")

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(station, field, value)

        # Track staff assignment
        if update_data.current_staff_id is not None:
            station.staff_assigned_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(station)

        logger.info(f"Updated station {station_id}")
        return station

    def get_station(self, station_id: int) -> Optional[KitchenStation]:
        """Get a station by ID"""
        return self.db.query(KitchenStation).filter_by(id=station_id).first()

    def get_all_stations(self, include_inactive: bool = False) -> List[KitchenStation]:
        """Get all kitchen stations"""
        query = self.db.query(KitchenStation)
        if not include_inactive:
            query = query.filter(KitchenStation.status != StationStatus.INACTIVE)
        return query.order_by(KitchenStation.priority.desc(), KitchenStation.name).all()

    def get_stations_by_type(self, station_type: StationType) -> List[KitchenStation]:
        """Get all stations of a specific type"""
        return (
            self.db.query(KitchenStation)
            .filter(
                KitchenStation.station_type == station_type,
                KitchenStation.status == StationStatus.ACTIVE,
            )
            .all()
        )

    # Display Management
    def create_display(self, display_data: KitchenDisplayCreate) -> KitchenDisplay:
        """Create a new display for a station"""
        # Check if station exists
        station = self.get_station(display_data.station_id)
        if not station:
            raise ValueError(f"Station {display_data.station_id} not found")

        # Check if display number already exists
        existing = (
            self.db.query(KitchenDisplay)
            .filter(
                KitchenDisplay.station_id == display_data.station_id,
                KitchenDisplay.display_number == display_data.display_number,
            )
            .first()
        )

        if existing:
            raise ValueError(
                f"Display number {display_data.display_number} already exists for this station"
            )

        display = KitchenDisplay(**display_data.dict())
        self.db.add(display)
        self.db.commit()
        self.db.refresh(display)

        logger.info(f"Created display {display.id} for station {station.name}")
        return display

    def update_display(
        self, display_id: int, update_data: KitchenDisplayUpdate
    ) -> KitchenDisplay:
        """Update a kitchen display"""
        display = self.db.query(KitchenDisplay).filter_by(id=display_id).first()
        if not display:
            raise ValueError(f"Display {display_id} not found")

        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(display, field, value)

        self.db.commit()
        self.db.refresh(display)

        return display

    def update_display_heartbeat(self, display_id: int):
        """Update display heartbeat timestamp"""
        display = self.db.query(KitchenDisplay).filter_by(id=display_id).first()
        if display:
            display.last_heartbeat = datetime.utcnow()
            self.db.commit()

    # Order Item Management
    def get_station_items(
        self,
        station_id: int,
        status_filter: Optional[List[DisplayStatus]] = None,
        limit: int = 50,
    ) -> List[KDSOrderItem]:
        """Get order items for a station"""
        query = self.db.query(KDSOrderItem).filter(
            KDSOrderItem.station_id == station_id
        )

        if status_filter:
            query = query.filter(KDSOrderItem.status.in_(status_filter))
        else:
            # Default: exclude completed and cancelled
            query = query.filter(
                ~KDSOrderItem.status.in_(
                    [DisplayStatus.COMPLETED, DisplayStatus.CANCELLED]
                )
            )

        # Order by priority and received time
        items = (
            query.order_by(
                KDSOrderItem.priority.desc(),
                KDSOrderItem.fire_time.nullsfirst(),
                KDSOrderItem.received_at,
            )
            .limit(limit)
            .all()
        )

        return items

    def acknowledge_item(self, item_id: int, staff_id: int) -> KDSOrderItem:
        """Acknowledge an order item (mark as seen)"""
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")

        item.acknowledged_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Item {item_id} acknowledged by staff {staff_id}")
        return item

    def start_item(self, item_id: int, staff_id: int) -> KDSOrderItem:
        """Mark an item as started"""
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")

        if item.status not in [DisplayStatus.PENDING, DisplayStatus.RECALLED]:
            raise ValueError(f"Cannot start item in {item.status.value} status")

        item.status = DisplayStatus.IN_PROGRESS
        item.started_at = datetime.utcnow()
        item.started_by_id = staff_id

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Item {item_id} started by staff {staff_id}")
        return item

    def complete_item(self, item_id: int, staff_id: int) -> KDSOrderItem:
        """Mark an item as completed"""
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")

        if item.status == DisplayStatus.COMPLETED:
            raise ValueError("Item is already completed")

        item.status = DisplayStatus.COMPLETED
        item.completed_at = datetime.utcnow()
        item.completed_by_id = staff_id

        # Check if all items for this order are complete
        self._check_order_completion(item.order_item.order_id)

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Item {item_id} completed by staff {staff_id}")
        return item

    def recall_item(self, item_id: int, reason: Optional[str] = None) -> KDSOrderItem:
        """Recall a completed item"""
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")

        if item.status != DisplayStatus.COMPLETED:
            raise ValueError("Can only recall completed items")

        item.status = DisplayStatus.RECALLED
        item.recall_count += 1
        item.last_recalled_at = datetime.utcnow()
        item.recall_reason = reason

        self.db.commit()
        self.db.refresh(item)

        logger.info(f"Item {item_id} recalled. Reason: {reason}")
        return item

    def _check_order_completion(self, order_id: int):
        """Check if all items for an order are complete"""
        # Get all KDS items for this order
        order_items = self.db.query(OrderItem).filter_by(order_id=order_id).all()
        kds_items = []

        for order_item in order_items:
            items = (
                self.db.query(KDSOrderItem).filter_by(order_item_id=order_item.id).all()
            )
            kds_items.extend(items)

        # Check if all are completed
        if kds_items and all(
            item.status == DisplayStatus.COMPLETED for item in kds_items
        ):
            # Update order status
            order = self.db.query(Order).filter_by(id=order_id).first()
            if order and order.status == "in_progress":
                order.status = "ready"
                self.db.commit()
                logger.info(f"Order {order_id} marked as ready")

    # Station Statistics
    def get_station_summary(self, station_id: int) -> StationSummary:
        """Get summary statistics for a station"""
        station = self.get_station(station_id)
        if not station:
            raise ValueError(f"Station {station_id} not found")

        # Count items by status
        status_counts = (
            self.db.query(KDSOrderItem.status, func.count(KDSOrderItem.id))
            .filter(KDSOrderItem.station_id == station_id)
            .group_by(KDSOrderItem.status)
            .all()
        )

        status_dict = {status: count for status, count in status_counts}

        # Calculate average wait time for completed items today
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        completed_today = (
            self.db.query(KDSOrderItem)
            .filter(
                KDSOrderItem.station_id == station_id,
                KDSOrderItem.status == DisplayStatus.COMPLETED,
                KDSOrderItem.completed_at >= today_start,
            )
            .all()
        )

        avg_wait_time = 0
        if completed_today:
            total_wait = sum(item.wait_time_seconds for item in completed_today)
            avg_wait_time = total_wait / len(completed_today) / 60  # Convert to minutes

        # Count late items
        late_items = (
            self.db.query(func.count(KDSOrderItem.id))
            .filter(
                KDSOrderItem.station_id == station_id,
                KDSOrderItem.status.in_(
                    [DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS]
                ),
                KDSOrderItem.target_time < datetime.utcnow(),
            )
            .scalar()
            or 0
        )

        # Get last activity
        last_item = (
            self.db.query(KDSOrderItem)
            .filter(KDSOrderItem.station_id == station_id)
            .order_by(KDSOrderItem.received_at.desc())
            .first()
        )

        return StationSummary(
            station_id=station.id,
            station_name=station.name,
            station_type=station.station_type,
            status=station.status,
            active_items=status_dict.get(DisplayStatus.IN_PROGRESS, 0),
            pending_items=status_dict.get(DisplayStatus.PENDING, 0),
            completed_today=len(completed_today),
            average_wait_time=round(avg_wait_time, 1),
            late_items=late_items,
            staff_name=station.current_staff.name if station.current_staff else None,
            last_activity=last_item.received_at if last_item else None,
        )

    def get_all_station_summaries(self) -> List[StationSummary]:
        """Get summaries for all active stations"""
        stations = self.get_all_stations()
        summaries = []

        for station in stations:
            try:
                summary = self.get_station_summary(station.id)
                summaries.append(summary)
            except Exception as e:
                logger.error(
                    f"Error getting summary for station {station.id}: {str(e)}"
                )

        return summaries

    # Timing and Performance
    def update_item_timings(self):
        """Update target times for pending items based on current load"""
        stations = self.get_all_stations()

        for station in stations:
            # Get active items
            active_items = (
                self.db.query(KDSOrderItem)
                .filter(
                    KDSOrderItem.station_id == station.id,
                    KDSOrderItem.status.in_(
                        [DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS]
                    ),
                )
                .order_by(KDSOrderItem.priority.desc(), KDSOrderItem.received_at)
                .all()
            )

            # Calculate cumulative prep time
            cumulative_time = 0
            base_time = datetime.utcnow()

            for item in active_items:
                if not item.target_time:
                    # Estimate prep time based on item and station
                    prep_time = self._estimate_prep_time(item, station)
                    item.target_time = base_time + timedelta(
                        minutes=cumulative_time + prep_time
                    )
                    cumulative_time += prep_time

            self.db.commit()

    def _estimate_prep_time(self, item: KDSOrderItem, station: KitchenStation) -> int:
        """Estimate prep time for an item at a station"""
        # This would ideally come from menu item configuration
        base_time = 10  # Default 10 minutes

        # Apply station multiplier
        adjusted_time = base_time * station.prep_time_multiplier

        # Add time for quantity
        if item.quantity > 1:
            adjusted_time += (
                item.quantity - 1
            ) * 2  # 2 extra minutes per additional item

        return int(adjusted_time)
