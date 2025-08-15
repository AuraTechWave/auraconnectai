# backend/modules/kds/tests/test_kds_routing.py

"""
Tests for KDS order routing functionality.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from modules.kds.services.kds_order_routing_service import KDSOrderRoutingService
from modules.kds.services.kds_service import KDSService
from modules.kds.models.kds_models import (
    KitchenStation,
    StationAssignment,
    MenuItemStation,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from modules.kds.schemas.kds_schemas import (
    StationCreate,
    StationAssignmentCreate,
    MenuItemStationCreate,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.menu.models import MenuItem, MenuCategory
from modules.staff.models import StaffMember


class TestKDSOrderRouting:
    """Test cases for KDS order routing"""

    @pytest.fixture
    def setup_test_data(self, db: Session):
        """Set up test data for routing tests"""
        # Create staff
        staff = StaffMember(
            name="Test Server",
            email="server@test.com",
            phone="1234567890",
            role="server",
            is_active=True,
        )
        db.add(staff)

        # Create menu categories
        appetizer_cat = MenuCategory(name="Appetizers", description="Starters")
        entree_cat = MenuCategory(name="Entrees", description="Main dishes")
        dessert_cat = MenuCategory(name="Desserts", description="Sweet treats")
        db.add_all([appetizer_cat, entree_cat, dessert_cat])
        db.commit()

        # Create stations
        kds_service = KDSService(db)
        grill_station = kds_service.create_station(
            StationCreate(
                name="Grill Station", station_type=StationType.GRILL, priority=10
            )
        )
        salad_station = kds_service.create_station(
            StationCreate(
                name="Salad Station", station_type=StationType.SALAD, priority=5
            )
        )
        dessert_station = kds_service.create_station(
            StationCreate(
                name="Dessert Station", station_type=StationType.DESSERT, priority=3
            )
        )
        expo_station = kds_service.create_station(
            StationCreate(
                name="Expo Station", station_type=StationType.EXPO, priority=1
            )
        )

        # Create menu items
        burger = MenuItem(
            name="Classic Burger",
            description="Grilled beef patty with lettuce and tomato",
            category_id=entree_cat.id,
            price=12.99,
            is_available=True,
        )
        salad = MenuItem(
            name="Caesar Salad",
            description="Fresh romaine with caesar dressing",
            category_id=appetizer_cat.id,
            price=8.99,
            is_available=True,
        )
        cake = MenuItem(
            name="Chocolate Cake",
            description="Rich chocolate layer cake",
            category_id=dessert_cat.id,
            price=6.99,
            is_available=True,
        )
        db.add_all([burger, salad, cake])
        db.commit()

        return {
            "staff": staff,
            "categories": {
                "appetizer": appetizer_cat,
                "entree": entree_cat,
                "dessert": dessert_cat,
            },
            "stations": {
                "grill": grill_station,
                "salad": salad_station,
                "dessert": dessert_station,
                "expo": expo_station,
            },
            "menu_items": {"burger": burger, "salad": salad, "cake": cake},
        }

    def test_create_station_assignment_by_category(self, db: Session, setup_test_data):
        """Test creating station assignment rules by category"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Assign entrees to grill station
        assignment = routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["grill"].id,
                category_name="Entrees",
                priority=10,
                is_primary=True,
                prep_time_override=20,
            )
        )

        assert assignment.id is not None
        assert assignment.station_id == data["stations"]["grill"].id
        assert assignment.category_name == "Entrees"
        assert assignment.prep_time_override == 20

    def test_create_station_assignment_by_tag(self, db: Session, setup_test_data):
        """Test creating station assignment rules by tag"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Assign items tagged as "grilled" to grill station
        assignment = routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["grill"].id,
                tag_name="grilled",
                priority=15,
                is_primary=True,
            )
        )

        assert assignment.tag_name == "grilled"
        assert assignment.category_name is None

    def test_direct_menu_item_assignment(self, db: Session, setup_test_data):
        """Test direct menu item to station assignment"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Assign burger directly to grill station
        assignment = routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["burger"].id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=15,
                station_notes="Cook to customer preference",
            )
        )

        assert assignment.menu_item_id == data["menu_items"]["burger"].id
        assert assignment.station_id == data["stations"]["grill"].id
        assert assignment.prep_time_minutes == 15
        assert assignment.station_notes == "Cook to customer preference"

    def test_route_order_with_direct_assignments(self, db: Session, setup_test_data):
        """Test routing an order with direct menu item assignments"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create direct assignments
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["burger"].id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=15,
            )
        )
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["salad"].id,
                station_id=data["stations"]["salad"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=8,
            )
        )

        # Create order
        order = Order(staff_id=data["staff"].id, table_no=10, status="pending")
        db.add(order)
        db.commit()

        # Add order items
        burger_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["burger"].id,
            quantity=2,
            price=12.99,
        )
        salad_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["salad"].id,
            quantity=1,
            price=8.99,
        )
        db.add_all([burger_item, salad_item])
        db.commit()

        # Route the order
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 2

        # Check burger routing
        burger_kds = next(
            (item for item in routed_items if item.order_item_id == burger_item.id),
            None,
        )
        assert burger_kds is not None
        assert burger_kds.station_id == data["stations"]["grill"].id
        assert burger_kds.display_name == "2x Classic Burger"
        assert burger_kds.quantity == 2

        # Check salad routing
        salad_kds = next(
            (item for item in routed_items if item.order_item_id == salad_item.id), None
        )
        assert salad_kds is not None
        assert salad_kds.station_id == data["stations"]["salad"].id
        assert salad_kds.display_name == "Caesar Salad"
        assert salad_kds.quantity == 1

    def test_route_order_with_category_assignments(self, db: Session, setup_test_data):
        """Test routing an order using category-based assignments"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create category assignments
        routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["salad"].id,
                category_name="Appetizers",
                priority=10,
                is_primary=True,
            )
        )
        routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["dessert"].id,
                category_name="Desserts",
                priority=10,
                is_primary=True,
            )
        )

        # Create order with dessert
        order = Order(staff_id=data["staff"].id, table_no=15, status="pending")
        db.add(order)
        db.commit()

        cake_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["cake"].id,
            quantity=1,
            price=6.99,
            notes="Add birthday candle",
        )
        db.add(cake_item)
        db.commit()

        # Route the order
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 1
        assert routed_items[0].station_id == data["stations"]["dessert"].id
        assert routed_items[0].special_instructions == "Add birthday candle"

    def test_fallback_routing(self, db: Session, setup_test_data):
        """Test fallback routing when no specific assignments exist"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create a menu item with no assignments
        mystery_item = MenuItem(
            name="Mystery Special",
            description="Chef's special creation",
            category_id=data["categories"]["entree"].id,
            price=19.99,
            is_available=True,
        )
        db.add(mystery_item)
        db.commit()

        # Create order
        order = Order(staff_id=data["staff"].id, table_no=20, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=mystery_item.id, quantity=1, price=19.99
        )
        db.add(order_item)
        db.commit()

        # Route the order - should go to expo as fallback
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 1
        assert routed_items[0].station_id == data["stations"]["expo"].id
        assert "No specific station found" in (
            routed_items[0].special_instructions or ""
        )

    def test_multi_station_routing(self, db: Session, setup_test_data):
        """Test routing an item to multiple stations in sequence"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create a complex item that needs multiple stations
        combo_item = MenuItem(
            name="Steak and Lobster",
            description="Grilled steak with steamed lobster",
            category_id=data["categories"]["entree"].id,
            price=39.99,
            is_available=True,
        )
        db.add(combo_item)
        db.commit()

        # Assign to multiple stations
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=combo_item.id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=20,
                station_notes="Grill steak to order",
            )
        )
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=combo_item.id,
                station_id=data["stations"][
                    "salad"
                ].id,  # Using salad station for seafood
                is_primary=False,
                sequence=1,
                prep_time_minutes=15,
                station_notes="Steam lobster",
            )
        )

        # Create order
        order = Order(staff_id=data["staff"].id, table_no=25, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=combo_item.id, quantity=1, price=39.99
        )
        db.add(order_item)
        db.commit()

        # Route the order
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 2

        # Check sequencing
        grill_item = next(
            (
                item
                for item in routed_items
                if item.station_id == data["stations"]["grill"].id
            ),
            None,
        )
        salad_item = next(
            (
                item
                for item in routed_items
                if item.station_id == data["stations"]["salad"].id
            ),
            None,
        )

        assert grill_item is not None
        assert salad_item is not None
        assert grill_item.sequence_number == 0
        assert salad_item.sequence_number == 1

    def test_conditional_routing(self, db: Session, setup_test_data):
        """Test conditional routing based on time/day"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create conditional assignment (e.g., salads go to different station on weekends)
        weekend_assignment = routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["expo"].id,
                category_name="Appetizers",
                priority=20,  # Higher priority than regular assignment
                is_primary=True,
                conditions={"day_of_week": ["saturday", "sunday"]},
            )
        )

        # Create regular assignment
        regular_assignment = routing_service.create_station_assignment(
            StationAssignmentCreate(
                station_id=data["stations"]["salad"].id,
                category_name="Appetizers",
                priority=10,
                is_primary=True,
            )
        )

        # The actual day-based routing would depend on current date
        # For testing, we verify the assignments were created correctly
        assignments = routing_service.get_station_assignments()

        assert len([a for a in assignments if a.category_name == "Appetizers"]) == 2
        assert weekend_assignment.conditions["day_of_week"] == ["saturday", "sunday"]

    def test_special_instructions_extraction(self, db: Session, setup_test_data):
        """Test extraction of special instructions and modifiers"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Route burger to grill
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["burger"].id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=15,
            )
        )

        # Create order with special instructions
        order = Order(staff_id=data["staff"].id, table_no=30, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["burger"].id,
            quantity=1,
            price=12.99,
            notes="Medium rare, extra pickles",
            special_instructions={
                "modifiers": ["No onions", "Extra cheese"],
                "additions": ["Bacon", "Avocado"],
                "removals": ["Tomato"],
                "notes": "Gluten-free bun please",
            },
        )
        db.add(order_item)
        db.commit()

        # Route the order
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 1
        kds_item = routed_items[0]

        # Check modifiers were extracted
        assert "No onions" in kds_item.modifiers
        assert "Add Bacon" in kds_item.modifiers
        assert "Add Avocado" in kds_item.modifiers
        assert "No Tomato" in kds_item.modifiers

        # Check special instructions
        assert kds_item.special_instructions == "Gluten-free bun please"

    def test_priority_calculation(self, db: Session, setup_test_data):
        """Test priority calculation for KDS items"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create assignment
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["burger"].id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=15,
            )
        )

        # Create high priority order
        order = Order(
            staff_id=data["staff"].id,
            table_no=1,
            status="pending",
            priority="high",
            created_at=datetime.utcnow(),
        )
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["burger"].id,
            quantity=1,
            price=12.99,
        )
        db.add(order_item)
        db.commit()

        # Route the order
        routed_items = routing_service.route_order_to_stations(order.id)

        assert len(routed_items) == 1
        # Priority should be elevated due to high priority order
        assert routed_items[0].priority >= 10

    def test_duplicate_routing_prevention(self, db: Session, setup_test_data):
        """Test that items aren't routed twice"""
        routing_service = KDSOrderRoutingService(db)
        data = setup_test_data

        # Create assignment
        routing_service.assign_menu_item_to_station(
            MenuItemStationCreate(
                menu_item_id=data["menu_items"]["burger"].id,
                station_id=data["stations"]["grill"].id,
                is_primary=True,
                sequence=0,
                prep_time_minutes=15,
            )
        )

        # Create order
        order = Order(staff_id=data["staff"].id, table_no=35, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=data["menu_items"]["burger"].id,
            quantity=1,
            price=12.99,
        )
        db.add(order_item)
        db.commit()

        # Route the order twice
        first_routing = routing_service.route_order_to_stations(order.id)
        second_routing = routing_service.route_order_to_stations(order.id)

        assert len(first_routing) == 1
        assert len(second_routing) == 0  # Should not route again
