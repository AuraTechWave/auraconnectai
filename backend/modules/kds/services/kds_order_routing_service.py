# backend/modules/kds/services/kds_order_routing_service.py

"""
Service for routing orders to appropriate kitchen stations.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging
import json

from ..models.kds_models import (
    KitchenStation,
    StationAssignment,
    MenuItemStation,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from ..schemas.kds_schemas import (
    StationAssignmentCreate,
    MenuItemStationCreate,
    OrderItemDisplay,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.menu.models import MenuItem

logger = logging.getLogger(__name__)


class KDSOrderRoutingService:
    """Service for routing orders to kitchen stations"""

    def __init__(self, db: Session):
        self.db = db

    # Station Assignment Management
    def create_station_assignment(
        self, assignment_data: StationAssignmentCreate
    ) -> StationAssignment:
        """Create a new station assignment rule"""
        # Validate station exists
        station = (
            self.db.query(KitchenStation)
            .filter_by(id=assignment_data.station_id)
            .first()
        )
        if not station:
            raise ValueError(f"Station {assignment_data.station_id} not found")

        assignment = StationAssignment(**assignment_data.dict())
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        logger.info(
            f"Created assignment for station {station.name}: "
            f"category={assignment.category_name}, tag={assignment.tag_name}"
        )
        return assignment

    def get_station_assignments(
        self, station_id: Optional[int] = None
    ) -> List[StationAssignment]:
        """Get station assignment rules"""
        query = self.db.query(StationAssignment)
        if station_id:
            query = query.filter(StationAssignment.station_id == station_id)
        return query.order_by(StationAssignment.priority.desc()).all()

    def delete_station_assignment(self, assignment_id: int):
        """Delete a station assignment rule"""
        assignment = (
            self.db.query(StationAssignment).filter_by(id=assignment_id).first()
        )
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")

        self.db.delete(assignment)
        self.db.commit()
        logger.info(f"Deleted assignment {assignment_id}")

    # Menu Item Station Mapping
    def assign_menu_item_to_station(
        self, assignment_data: MenuItemStationCreate
    ) -> MenuItemStation:
        """Assign a menu item to a station"""
        # Validate station exists
        station = (
            self.db.query(KitchenStation)
            .filter_by(id=assignment_data.station_id)
            .first()
        )
        if not station:
            raise ValueError(f"Station {assignment_data.station_id} not found")

        # Check if assignment already exists
        existing = (
            self.db.query(MenuItemStation)
            .filter(
                MenuItemStation.menu_item_id == assignment_data.menu_item_id,
                MenuItemStation.station_id == assignment_data.station_id,
                MenuItemStation.sequence == assignment_data.sequence,
            )
            .first()
        )

        if existing:
            raise ValueError("This menu item station assignment already exists")

        assignment = MenuItemStation(**assignment_data.dict())
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        logger.info(
            f"Assigned menu item {assignment.menu_item_id} to station {station.name}"
        )
        return assignment

    def get_menu_item_stations(self, menu_item_id: int) -> List[MenuItemStation]:
        """Get all station assignments for a menu item"""
        return (
            self.db.query(MenuItemStation)
            .filter(MenuItemStation.menu_item_id == menu_item_id)
            .order_by(MenuItemStation.sequence)
            .all()
        )

    # Order Routing
    def route_order_to_stations(self, order_id: int) -> List[KDSOrderItem]:
        """Route all items in an order to appropriate kitchen stations"""
        order = self.db.query(Order).filter_by(id=order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        routed_items = []

        for order_item in order.order_items:
            # Skip if already routed
            existing = (
                self.db.query(KDSOrderItem)
                .filter_by(order_item_id=order_item.id)
                .first()
            )

            if existing:
                logger.info(f"Order item {order_item.id} already routed")
                continue

            # Route this item
            item_routes = self._route_order_item(order_item, order)
            routed_items.extend(item_routes)

        self.db.commit()
        logger.info(
            f"Routed {len(routed_items)} items from order {order_id} to stations"
        )
        return routed_items

    def _route_order_item(
        self, order_item: OrderItem, order: Order
    ) -> List[KDSOrderItem]:
        """Route a single order item to appropriate stations"""
        # Get menu item details
        menu_item = (
            self.db.query(MenuItem).filter_by(id=order_item.menu_item_id).first()
        )
        if not menu_item:
            logger.warning(f"Menu item {order_item.menu_item_id} not found for routing")
            return []

        # Find stations for this item
        stations = self._find_stations_for_item(menu_item, order_item)

        if not stations:
            logger.warning(f"No stations found for menu item {menu_item.name}")
            return []

        routed_items = []

        for idx, (station, prep_time, notes) in enumerate(stations):
            # Create KDS order item
            kds_item = KDSOrderItem(
                order_item_id=order_item.id,
                station_id=station.id,
                display_name=self._format_display_name(menu_item, order_item),
                quantity=order_item.quantity,
                modifiers=self._extract_modifiers(order_item),
                special_instructions=self._extract_special_instructions(order_item),
                status=DisplayStatus.PENDING,
                sequence_number=idx if len(stations) > 1 else None,
                priority=self._calculate_priority(order),
                course_number=self._determine_course_number(menu_item),
                fire_time=order.scheduled_fulfillment_time,
                target_time=self._calculate_target_time(prep_time, station),
            )

            self.db.add(kds_item)
            routed_items.append(kds_item)

            logger.info(f"Routed '{menu_item.name}' to station {station.name}")

        return routed_items

    def _find_stations_for_item(
        self, menu_item: MenuItem, order_item: OrderItem
    ) -> List[Tuple[KitchenStation, int, Optional[str]]]:
        """Find appropriate stations for a menu item"""
        stations = []

        # First, check direct menu item to station mappings
        item_stations = (
            self.db.query(MenuItemStation)
            .filter(MenuItemStation.menu_item_id == menu_item.id)
            .order_by(MenuItemStation.sequence)
            .all()
        )

        for item_station in item_stations:
            station = (
                self.db.query(KitchenStation)
                .filter_by(id=item_station.station_id)
                .first()
            )
            if station and station.status == StationStatus.ACTIVE:
                stations.append(
                    (
                        station,
                        item_station.prep_time_minutes,
                        item_station.station_notes,
                    )
                )

        # If no direct mapping, use category/tag based routing
        if not stations:
            # Get menu item category and tags
            category_name = (
                menu_item.category.name if hasattr(menu_item, "category") else None
            )
            tags = self._extract_item_tags(menu_item)

            # Find matching assignments
            assignments = self._find_matching_assignments(category_name, tags)

            for assignment in assignments:
                station = (
                    self.db.query(KitchenStation)
                    .filter_by(id=assignment.station_id)
                    .first()
                )
                if station and station.status == StationStatus.ACTIVE:
                    prep_time = (
                        assignment.prep_time_override
                        or self._default_prep_time(menu_item)
                    )
                    stations.append((station, prep_time, None))

                    # If primary station found, we might not need secondary
                    if assignment.is_primary:
                        break

        # If still no stations, use fallback routing
        if not stations:
            stations = self._fallback_routing(menu_item)

        return stations

    def _find_matching_assignments(
        self, category_name: Optional[str], tags: List[str]
    ) -> List[StationAssignment]:
        """Find station assignments matching category or tags"""
        assignments = []

        # Build query
        conditions = []
        if category_name:
            conditions.append(StationAssignment.category_name == category_name)
        for tag in tags:
            conditions.append(StationAssignment.tag_name == tag)

        if conditions:
            assignments = (
                self.db.query(StationAssignment)
                .filter(or_(*conditions))
                .order_by(StationAssignment.priority.desc())
                .all()
            )

        # Filter by conditions (e.g., day of week)
        filtered_assignments = []
        for assignment in assignments:
            if self._check_assignment_conditions(assignment):
                filtered_assignments.append(assignment)

        return filtered_assignments

    def _check_assignment_conditions(self, assignment: StationAssignment) -> bool:
        """Check if assignment conditions are met"""
        if not assignment.conditions:
            return True

        conditions = assignment.conditions
        now = datetime.utcnow()

        # Check day of week
        if "day_of_week" in conditions:
            current_day = now.strftime("%A").lower()
            allowed_days = [day.lower() for day in conditions["day_of_week"]]
            if current_day not in allowed_days:
                return False

        # Check time range
        if "time_range" in conditions:
            current_time = now.time()
            start_time = datetime.strptime(
                conditions["time_range"]["start"], "%H:%M"
            ).time()
            end_time = datetime.strptime(
                conditions["time_range"]["end"], "%H:%M"
            ).time()
            if not (start_time <= current_time <= end_time):
                return False

        return True

    def _fallback_routing(
        self, menu_item: MenuItem
    ) -> List[Tuple[KitchenStation, int, Optional[str]]]:
        """Fallback routing based on common patterns"""
        stations = []

        # Simple keyword matching
        item_name_lower = menu_item.name.lower()

        # Map keywords to station types
        keyword_mapping = {
            StationType.GRILL: ["grill", "burger", "steak", "chicken", "meat"],
            StationType.FRY: ["fry", "fried", "fries", "wings", "nuggets"],
            StationType.SAUTE: ["saute", "pasta", "stir fry", "pan"],
            StationType.SALAD: ["salad", "fresh", "vegetable", "greens"],
            StationType.DESSERT: ["dessert", "cake", "ice cream", "sweet"],
            StationType.BEVERAGE: ["drink", "beverage", "coffee", "tea", "juice"],
            StationType.PIZZA: ["pizza", "calzone", "flatbread"],
            StationType.SANDWICH: ["sandwich", "sub", "wrap", "panini"],
            StationType.SUSHI: ["sushi", "sashimi", "roll", "nigiri"],
            StationType.BAR: ["cocktail", "beer", "wine", "alcohol"],
        }

        for station_type, keywords in keyword_mapping.items():
            if any(keyword in item_name_lower for keyword in keywords):
                type_stations = (
                    self.db.query(KitchenStation)
                    .filter(
                        KitchenStation.station_type == station_type,
                        KitchenStation.status == StationStatus.ACTIVE,
                    )
                    .order_by(KitchenStation.priority.desc())
                    .all()
                )

                if type_stations:
                    prep_time = self._default_prep_time(menu_item)
                    stations.append((type_stations[0], prep_time, None))
                    break

        # If still no match, send to expo station
        if not stations:
            expo_station = (
                self.db.query(KitchenStation)
                .filter(
                    KitchenStation.station_type == StationType.EXPO,
                    KitchenStation.status == StationStatus.ACTIVE,
                )
                .first()
            )

            if expo_station:
                prep_time = self._default_prep_time(menu_item)
                stations.append((expo_station, prep_time, "No specific station found"))

        return stations

    def _extract_item_tags(self, menu_item: MenuItem) -> List[str]:
        """Extract tags from menu item"""
        tags = []

        # Check if menu item has tags relationship
        if hasattr(menu_item, "tags"):
            tags = [tag.name for tag in menu_item.tags]

        # Also extract from description or other fields
        if hasattr(menu_item, "description") and menu_item.description:
            # Simple keyword extraction
            keywords = ["grilled", "fried", "baked", "steamed", "raw", "cold", "hot"]
            desc_lower = menu_item.description.lower()
            for keyword in keywords:
                if keyword in desc_lower:
                    tags.append(keyword)

        return tags

    def _format_display_name(self, menu_item: MenuItem, order_item: OrderItem) -> str:
        """Format the display name for KDS"""
        name = menu_item.name

        # Add quantity if more than 1
        if order_item.quantity > 1:
            name = f"{order_item.quantity}x {name}"

        return name

    def _extract_modifiers(self, order_item: OrderItem) -> List[str]:
        """Extract modifiers from order item"""
        modifiers = []

        # Check special instructions JSON
        if order_item.special_instructions:
            if isinstance(order_item.special_instructions, dict):
                # Extract modifiers from structured data
                if "modifiers" in order_item.special_instructions:
                    modifiers.extend(order_item.special_instructions["modifiers"])
                if "additions" in order_item.special_instructions:
                    modifiers.extend(
                        [
                            f"Add {item}"
                            for item in order_item.special_instructions["additions"]
                        ]
                    )
                if "removals" in order_item.special_instructions:
                    modifiers.extend(
                        [
                            f"No {item}"
                            for item in order_item.special_instructions["removals"]
                        ]
                    )

        return modifiers

    def _extract_special_instructions(self, order_item: OrderItem) -> Optional[str]:
        """Extract special instructions text"""
        if order_item.notes:
            return order_item.notes

        if order_item.special_instructions and isinstance(
            order_item.special_instructions, dict
        ):
            if "notes" in order_item.special_instructions:
                return order_item.special_instructions["notes"]

        return None

    def _calculate_priority(self, order: Order) -> int:
        """Calculate priority for KDS display"""
        priority = 0

        # Order priority
        if hasattr(order, "priority"):
            if order.priority.value == "high":
                priority += 10
            elif order.priority.value == "urgent":
                priority += 20

        # Time-based priority
        if order.created_at:
            minutes_waiting = (
                datetime.utcnow() - order.created_at
            ).total_seconds() / 60
            if minutes_waiting > 15:
                priority += 5
            if minutes_waiting > 30:
                priority += 10

        return priority

    def _determine_course_number(self, menu_item: MenuItem) -> int:
        """Determine course number based on menu item type"""
        # This would ideally come from menu item configuration
        if hasattr(menu_item, "course"):
            return menu_item.course

        # Simple heuristic based on category
        if hasattr(menu_item, "category") and menu_item.category:
            category_lower = menu_item.category.name.lower()
            if "appetizer" in category_lower or "starter" in category_lower:
                return 1
            elif "main" in category_lower or "entree" in category_lower:
                return 2
            elif "dessert" in category_lower:
                return 3

        return 1  # Default to first course

    def _default_prep_time(self, menu_item: MenuItem) -> int:
        """Get default prep time for a menu item"""
        # This would ideally come from menu item configuration
        if hasattr(menu_item, "prep_time"):
            return menu_item.prep_time

        # Default based on category
        if hasattr(menu_item, "category") and menu_item.category:
            category_lower = menu_item.category.name.lower()
            if "appetizer" in category_lower:
                return 10
            elif "main" in category_lower or "entree" in category_lower:
                return 20
            elif "dessert" in category_lower:
                return 15
            elif "salad" in category_lower:
                return 8
            elif "beverage" in category_lower:
                return 5

        return 15  # Default prep time

    def _calculate_target_time(
        self, prep_time: int, station: KitchenStation
    ) -> datetime:
        """Calculate target completion time"""
        from datetime import timedelta

        # Apply station multiplier
        adjusted_time = prep_time * station.prep_time_multiplier

        # Add current station load
        active_items = (
            self.db.query(KDSOrderItem)
            .filter(
                KDSOrderItem.station_id == station.id,
                KDSOrderItem.status == DisplayStatus.IN_PROGRESS,
            )
            .count()
        )

        # Add buffer time based on load
        if active_items > 5:
            adjusted_time += 5
        elif active_items > 10:
            adjusted_time += 10

        return datetime.utcnow() + timedelta(minutes=adjusted_time)
