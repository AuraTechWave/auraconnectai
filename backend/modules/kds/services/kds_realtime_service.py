# backend/modules/kds/services/kds_realtime_service.py

"""
Real-time KDS order display and management service
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import logging
from enum import Enum

from ..models.kds_models import (
    KDSOrderItem,
    KitchenStation,
    StationAssignment,
    MenuItemStation,
    DisplayStatus,
    StationType,
    StationStatus,
)
from ..services.kds_websocket_manager import kds_websocket_manager
from modules.orders.models.order_models import Order, OrderItem
from core.menu_models import MenuItem
from modules.staff.models.staff_models import StaffMember

logger = logging.getLogger(__name__)


class CourseType(Enum):
    """Course types for timing coordination"""
    APPETIZER = 1
    SOUP = 2
    SALAD = 3
    ENTREE = 4
    DESSERT = 5
    BEVERAGE = 0  # Can be served anytime


class KDSRealtimeService:
    """Service for real-time KDS operations"""

    def __init__(self, db: Session):
        self.db = db
        self.ws_manager = kds_websocket_manager

    async def process_new_order(self, order_id: int) -> List[KDSOrderItem]:
        """Process a new order and route items to stations"""
        
        # Get order and items
        order = self.db.query(Order).filter_by(id=order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order_items = self.db.query(OrderItem).filter_by(order_id=order_id).all()
        
        kds_items = []
        
        for order_item in order_items:
            # Route item to appropriate stations
            stations = self._route_item_to_stations(order_item)
            
            for station_id, is_primary, sequence in stations:
                # Create KDS display item
                kds_item = self._create_kds_item(
                    order_item=order_item,
                    station_id=station_id,
                    sequence=sequence,
                    is_primary=is_primary,
                    order=order,
                )
                
                self.db.add(kds_item)
                kds_items.append(kds_item)
        
        self.db.commit()
        
        # Send WebSocket notifications
        for kds_item in kds_items:
            await self._notify_new_item(kds_item)
        
        logger.info(f"Processed order {order_id} with {len(kds_items)} KDS items")
        return kds_items

    def _route_item_to_stations(self, order_item: OrderItem) -> List[Tuple[int, bool, int]]:
        """Route an order item to appropriate stations"""
        
        stations = []
        
        # First check direct menu item to station mapping
        menu_item_stations = self.db.query(MenuItemStation).filter_by(
            menu_item_id=order_item.menu_item_id
        ).order_by(MenuItemStation.sequence).all()
        
        if menu_item_stations:
            for mis in menu_item_stations:
                stations.append((mis.station_id, mis.is_primary, mis.sequence))
        else:
            # Fall back to category/tag-based routing
            menu_item = self.db.query(MenuItem).filter_by(
                id=order_item.menu_item_id
            ).first()
            
            if menu_item:
                # Check category assignments
                category_assignments = self.db.query(StationAssignment).filter(
                    StationAssignment.category_name == menu_item.category
                ).order_by(StationAssignment.priority.desc()).all()
                
                for assignment in category_assignments:
                    if self._check_assignment_conditions(assignment):
                        stations.append((
                            assignment.station_id,
                            assignment.is_primary,
                            0
                        ))
                        if assignment.is_primary:
                            break  # Found primary station
        
        # If no stations found, route to default (expo) station
        if not stations:
            default_station = self.db.query(KitchenStation).filter_by(
                station_type=StationType.EXPO
            ).first()
            
            if default_station:
                stations.append((default_station.id, True, 0))
            else:
                logger.warning(f"No routing found for order item {order_item.id}")
        
        return stations

    def _check_assignment_conditions(self, assignment: StationAssignment) -> bool:
        """Check if assignment conditions are met"""
        
        if not assignment.conditions:
            return True
        
        # Check day of week conditions
        if "day_of_week" in assignment.conditions:
            current_day = datetime.utcnow().strftime("%A").lower()
            allowed_days = [d.lower() for d in assignment.conditions["day_of_week"]]
            if current_day not in allowed_days:
                return False
        
        # Check time conditions
        if "time_range" in assignment.conditions:
            current_hour = datetime.utcnow().hour
            time_range = assignment.conditions["time_range"]
            start_hour = time_range.get("start", 0)
            end_hour = time_range.get("end", 24)
            if not (start_hour <= current_hour < end_hour):
                return False
        
        return True

    def _create_kds_item(
        self,
        order_item: OrderItem,
        station_id: int,
        sequence: int,
        is_primary: bool,
        order: Order,
    ) -> KDSOrderItem:
        """Create a KDS display item"""
        
        # Get station for timing configuration
        station = self.db.query(KitchenStation).filter_by(id=station_id).first()
        
        # Calculate target time based on station configuration
        menu_item_station = self.db.query(MenuItemStation).filter_by(
            menu_item_id=order_item.menu_item_id,
            station_id=station_id,
        ).first()
        
        if menu_item_station and menu_item_station.prep_time_minutes:
            base_prep_time = menu_item_station.prep_time_minutes
        else:
            base_prep_time = 15  # Default prep time
        
        # Apply station multiplier
        if station:
            prep_time = base_prep_time * station.prep_time_multiplier
        else:
            prep_time = base_prep_time
        
        target_time = datetime.utcnow() + timedelta(minutes=prep_time)
        
        # Determine course and priority
        course_number = self._determine_course(order_item)
        priority = self._calculate_priority(order, order_item, is_primary)
        
        # Build display name with modifiers
        display_name = self._build_display_name(order_item)
        
        # Extract modifiers and special instructions
        modifiers = []
        special_instructions = None
        
        if hasattr(order_item, "modifiers") and order_item.modifiers:
            modifiers = order_item.modifiers
        
        if hasattr(order_item, "special_instructions") and order_item.special_instructions:
            special_instructions = order_item.special_instructions
        
        kds_item = KDSOrderItem(
            order_item_id=order_item.id,
            station_id=station_id,
            display_name=display_name,
            quantity=order_item.quantity,
            modifiers=modifiers,
            special_instructions=special_instructions,
            status=DisplayStatus.PENDING,
            sequence_number=sequence,
            target_time=target_time,
            priority=priority,
            course_number=course_number,
        )
        
        # Set fire time for coordinated cooking
        if course_number > 1:
            # Delay firing for later courses
            fire_delay = (course_number - 1) * 5  # 5 minutes between courses
            kds_item.fire_time = datetime.utcnow() + timedelta(minutes=fire_delay)
        
        return kds_item

    def _determine_course(self, order_item: OrderItem) -> int:
        """Determine course number for an order item"""
        
        menu_item = self.db.query(MenuItem).filter_by(id=order_item.menu_item_id).first()
        
        if not menu_item:
            return 1
        
        # Map categories to courses
        category_course_map = {
            "appetizer": 1,
            "starter": 1,
            "soup": 2,
            "salad": 3,
            "entree": 4,
            "main": 4,
            "dessert": 5,
            "beverage": 0,
            "drink": 0,
        }
        
        category_lower = menu_item.category.lower() if menu_item.category else ""
        
        for key, course in category_course_map.items():
            if key in category_lower:
                return course
        
        return 1  # Default to first course

    def _calculate_priority(
        self, order: Order, order_item: OrderItem, is_primary: bool
    ) -> int:
        """Calculate priority for a KDS item"""
        
        priority = 0
        
        # Base priority from order
        if hasattr(order, "priority"):
            priority += order.priority * 10
        
        # Increase priority for primary stations
        if is_primary:
            priority += 5
        
        # Increase priority for rush orders
        if hasattr(order, "is_rush") and order.is_rush:
            priority += 20
        
        # Increase priority for long-waiting orders
        wait_time = (datetime.utcnow() - order.created_at).total_seconds() / 60
        if wait_time > 30:
            priority += 15
        elif wait_time > 20:
            priority += 10
        elif wait_time > 10:
            priority += 5
        
        return priority

    def _build_display_name(self, order_item: OrderItem) -> str:
        """Build display name for KDS item"""
        
        menu_item = self.db.query(MenuItem).filter_by(id=order_item.menu_item_id).first()
        
        if menu_item:
            return menu_item.name
        else:
            return f"Item #{order_item.id}"

    async def _notify_new_item(self, kds_item: KDSOrderItem):
        """Send WebSocket notification for new item"""
        
        item_data = {
            "id": kds_item.id,
            "order_item_id": kds_item.order_item_id,
            "display_name": kds_item.display_name,
            "quantity": kds_item.quantity,
            "modifiers": kds_item.modifiers,
            "special_instructions": kds_item.special_instructions,
            "status": kds_item.status.value,
            "priority": kds_item.priority,
            "course_number": kds_item.course_number,
            "received_at": kds_item.received_at.isoformat(),
            "target_time": kds_item.target_time.isoformat() if kds_item.target_time else None,
        }
        
        await self.ws_manager.broadcast_new_item(kds_item.station_id, item_data)

    async def update_item_status(
        self,
        item_id: int,
        new_status: DisplayStatus,
        staff_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> KDSOrderItem:
        """Update status of a KDS item"""
        
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")
        
        old_status = item.status
        item.status = new_status
        
        # Update timestamps and staff tracking
        now = datetime.utcnow()
        
        if new_status == DisplayStatus.IN_PROGRESS:
            item.started_at = now
            item.acknowledged_at = now
            if staff_id:
                item.started_by_id = staff_id
        
        elif new_status == DisplayStatus.COMPLETED:
            item.completed_at = now
            if staff_id:
                item.completed_by_id = staff_id
        
        elif new_status == DisplayStatus.RECALLED:
            item.recall_count += 1
            item.last_recalled_at = now
            item.recall_reason = reason
            item.status = DisplayStatus.PENDING  # Reset to pending
        
        self.db.commit()
        
        # Send WebSocket update
        await self._notify_item_update(item)
        
        # Log status change
        logger.info(
            f"KDS item {item_id} status changed from {old_status.value} to {new_status.value}"
        )
        
        # Check if order is complete
        if new_status == DisplayStatus.COMPLETED:
            await self._check_order_completion(item.order_item_id)
        
        return item

    async def _notify_item_update(self, item: KDSOrderItem):
        """Send WebSocket notification for item update"""
        
        update_data = {
            "status": item.status.value,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "recall_count": item.recall_count,
        }
        
        await self.ws_manager.broadcast_item_update(
            item.station_id, item.id, update_data
        )

    async def _check_order_completion(self, order_item_id: int):
        """Check if all items for an order are complete"""
        
        # Get the order item
        order_item = self.db.query(OrderItem).filter_by(id=order_item_id).first()
        if not order_item:
            return
        
        # Check all KDS items for this order
        order_kds_items = (
            self.db.query(KDSOrderItem)
            .join(OrderItem)
            .filter(OrderItem.order_id == order_item.order_id)
            .all()
        )
        
        all_complete = all(
            item.status == DisplayStatus.COMPLETED for item in order_kds_items
        )
        
        if all_complete:
            # Notify that order is ready
            logger.info(f"Order {order_item.order_id} is complete")
            # Could trigger additional notifications here

    def get_station_display_items(
        self,
        station_id: int,
        include_completed: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get display items for a station"""
        
        from sqlalchemy.orm import joinedload
        
        query = self.db.query(KDSOrderItem).options(
            joinedload(KDSOrderItem.station)
        ).filter(
            KDSOrderItem.station_id == station_id
        )
        
        if not include_completed:
            query = query.filter(
                KDSOrderItem.status.notin_([
                    DisplayStatus.COMPLETED,
                    DisplayStatus.CANCELLED,
                ])
            )
        
        # Order by priority and received time
        query = query.order_by(
            KDSOrderItem.priority.desc(),
            KDSOrderItem.received_at,
        ).limit(limit)
        
        items = query.all()
        
        display_items = []
        for item in items:
            # Get order information
            order_item = self.db.query(OrderItem).filter_by(id=item.order_item_id).first()
            order = None
            if order_item:
                order = self.db.query(Order).filter_by(id=order_item.order_id).first()
            
            # Calculate elapsed time
            elapsed_time = (datetime.utcnow() - item.received_at).total_seconds()
            
            # Determine display status (color coding)
            # Use the preloaded station relationship or fetch if not loaded
            station = item.station if hasattr(item, 'station') and item.station else self.db.query(KitchenStation).filter_by(id=item.station_id).first()
            display_status = "normal"
            
            if station:
                if elapsed_time / 60 > station.critical_time_minutes:
                    display_status = "critical"
                elif elapsed_time / 60 > station.warning_time_minutes:
                    display_status = "warning"
            
            display_item = {
                "id": item.id,
                "order_number": order.order_number if order else "N/A",
                "table_number": order.table_number if order and hasattr(order, "table_number") else None,
                "display_name": item.display_name,
                "quantity": item.quantity,
                "modifiers": item.modifiers,
                "special_instructions": item.special_instructions,
                "status": item.status.value,
                "display_status": display_status,
                "priority": item.priority,
                "course_number": item.course_number,
                "elapsed_time": int(elapsed_time),
                "target_time": item.target_time.isoformat() if item.target_time else None,
                "is_late": item.is_late,
                "recall_count": item.recall_count,
                "fire_time": item.fire_time.isoformat() if item.fire_time else None,
                "can_start": not item.fire_time or datetime.utcnow() >= item.fire_time,
            }
            
            display_items.append(display_item)
        
        return display_items

    async def bump_item(self, item_id: int, staff_id: Optional[int] = None):
        """Mark item as ready and remove from active display"""
        
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"KDS item {item_id} not found")
        
        # Update status to ready
        item.status = DisplayStatus.READY
        item.completed_at = datetime.utcnow()
        if staff_id:
            item.completed_by_id = staff_id
        
        self.db.commit()
        
        # Notify stations
        await self.ws_manager.broadcast_item_update(
            item.station_id,
            item.id,
            {"status": "ready", "completed_at": item.completed_at.isoformat()},
        )
        
        # Auto-complete after delay
        asyncio.create_task(self._auto_complete_item(item.id))

    async def _auto_complete_item(self, item_id: int, delay: int = 30):
        """Auto-complete an item after delay"""
        
        await asyncio.sleep(delay)
        
        item = self.db.query(KDSOrderItem).filter_by(id=item_id).first()
        if item and item.status == DisplayStatus.READY:
            item.status = DisplayStatus.COMPLETED
            self.db.commit()
            
            await self.ws_manager.broadcast_item_removal(item.station_id, item.id)

    def get_station_summary(self, station_id: int) -> Dict[str, Any]:
        """Get summary information for a station"""
        
        station = self.db.query(KitchenStation).filter_by(id=station_id).first()
        if not station:
            raise ValueError(f"Station {station_id} not found")
        
        # Count items by status
        status_counts = {}
        for status in DisplayStatus:
            count = self.db.query(KDSOrderItem).filter(
                and_(
                    KDSOrderItem.station_id == station_id,
                    KDSOrderItem.status == status,
                )
            ).count()
            status_counts[status.value] = count
        
        # Get average wait time for active items
        active_items = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.station_id == station_id,
                KDSOrderItem.status.in_([DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS]),
            )
        ).all()
        
        avg_wait_time = 0
        if active_items:
            wait_times = [
                (datetime.utcnow() - item.received_at).total_seconds() / 60
                for item in active_items
            ]
            avg_wait_time = sum(wait_times) / len(wait_times)
        
        # Get staff info
        staff_info = None
        if station.current_staff_id:
            staff = self.db.query(StaffMember).filter_by(
                id=station.current_staff_id
            ).first()
            if staff:
                staff_info = {
                    "id": staff.id,
                    "name": f"{staff.first_name} {staff.last_name}",
                    "assigned_at": station.staff_assigned_at.isoformat()
                    if station.staff_assigned_at
                    else None,
                }
        
        return {
            "station_id": station.id,
            "station_name": station.name,
            "station_type": station.station_type.value,
            "status": station.status.value,
            "status_counts": status_counts,
            "active_items": status_counts.get("pending", 0) + status_counts.get("in_progress", 0),
            "average_wait_time": round(avg_wait_time, 2),
            "current_staff": staff_info,
            "color_code": station.color_code,
            "warning_threshold": station.warning_time_minutes,
            "critical_threshold": station.critical_time_minutes,
        }

    async def recall_item(
        self, item_id: int, reason: str, staff_id: Optional[int] = None
    ):
        """Recall a completed item back to pending"""
        
        await self.update_item_status(
            item_id,
            DisplayStatus.RECALLED,
            staff_id=staff_id,
            reason=reason,
        )

    def fire_course(self, order_id: int, course_number: int) -> List[KDSOrderItem]:
        """Fire all items for a specific course"""
        
        # Get all KDS items for this order and course
        items = (
            self.db.query(KDSOrderItem)
            .join(OrderItem)
            .filter(
                and_(
                    OrderItem.order_id == order_id,
                    KDSOrderItem.course_number == course_number,
                    KDSOrderItem.status == DisplayStatus.PENDING,
                )
            )
            .all()
        )
        
        # Update fire time to now
        for item in items:
            item.fire_time = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Fired course {course_number} for order {order_id} ({len(items)} items)")
        
        return items