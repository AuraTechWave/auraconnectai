# backend/modules/kds/tests/test_kds_service.py

"""
Tests for Kitchen Display System service functionality.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from modules.kds.services.kds_service import KDSService
from modules.kds.models.kds_models import (
    KitchenStation,
    KitchenDisplay,
    KDSOrderItem,
    StationType,
    StationStatus,
    DisplayStatus,
)
from modules.kds.schemas.kds_schemas import (
    StationCreate,
    StationUpdate,
    KitchenDisplayCreate,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models import StaffMember


class TestKDSService:
    """Test cases for KDS service"""

    def test_create_station(self, db: Session):
        """Test creating a kitchen station"""
        service = KDSService(db)

        station_data = StationCreate(
            name="Grill Station 1",
            station_type=StationType.GRILL,
            display_name="Grill #1",
            color_code="#FF6B6B",
            priority=10,
            max_active_items=15,
            prep_time_multiplier=1.2,
            warning_time_minutes=7,
            critical_time_minutes=12,
            features=["printer", "buzzer"],
            printer_id="PRINTER_GRILL_01",
        )

        station = service.create_station(station_data)

        assert station.id is not None
        assert station.name == "Grill Station 1"
        assert station.station_type == StationType.GRILL
        assert station.display_name == "Grill #1"
        assert station.color_code == "#FF6B6B"
        assert station.priority == 10
        assert station.status == StationStatus.ACTIVE

        # Check default display was created
        displays = db.query(KitchenDisplay).filter_by(station_id=station.id).all()
        assert len(displays) == 1
        assert displays[0].display_number == 1
        assert displays[0].name == "Primary Display"

    def test_update_station(self, db: Session):
        """Test updating a kitchen station"""
        service = KDSService(db)

        # Create a station
        station_data = StationCreate(name="Fry Station", station_type=StationType.FRY)
        station = service.create_station(station_data)

        # Update it
        update_data = StationUpdate(
            name="Fry Station Updated",
            status=StationStatus.BUSY,
            priority=5,
            color_code="#4ECDC4",
        )

        updated_station = service.update_station(station.id, update_data)

        assert updated_station.name == "Fry Station Updated"
        assert updated_station.status == StationStatus.BUSY
        assert updated_station.priority == 5
        assert updated_station.color_code == "#4ECDC4"
        assert updated_station.station_type == StationType.FRY  # Unchanged

    def test_get_stations_by_type(self, db: Session):
        """Test getting stations by type"""
        service = KDSService(db)

        # Create multiple stations
        grill1 = service.create_station(
            StationCreate(name="Grill 1", station_type=StationType.GRILL)
        )
        grill2 = service.create_station(
            StationCreate(name="Grill 2", station_type=StationType.GRILL)
        )
        salad = service.create_station(
            StationCreate(name="Salad Station", station_type=StationType.SALAD)
        )

        # Get grill stations
        grill_stations = service.get_stations_by_type(StationType.GRILL)
        assert len(grill_stations) == 2
        assert all(s.station_type == StationType.GRILL for s in grill_stations)

        # Get salad stations
        salad_stations = service.get_stations_by_type(StationType.SALAD)
        assert len(salad_stations) == 1
        assert salad_stations[0].name == "Salad Station"

    def test_station_staff_assignment(self, db: Session):
        """Test assigning staff to a station"""
        service = KDSService(db)

        # Create a station
        station = service.create_station(
            StationCreate(name="Pizza Station", station_type=StationType.PIZZA)
        )

        # Create a staff member
        staff = StaffMember(
            name="John Doe",
            email="john@example.com",
            phone="1234567890",
            role="chef",
            is_active=True,
        )
        db.add(staff)
        db.commit()

        # Assign staff
        update_data = StationUpdate(current_staff_id=staff.id)
        updated_station = service.update_station(station.id, update_data)

        assert updated_station.current_staff_id == staff.id
        assert updated_station.staff_assigned_at is not None
        assert updated_station.current_staff.name == "John Doe"

    def test_create_display(self, db: Session):
        """Test creating additional displays for a station"""
        service = KDSService(db)

        # Create a station
        station = service.create_station(
            StationCreate(name="Expo Station", station_type=StationType.EXPO)
        )

        # Create additional display
        display_data = KitchenDisplayCreate(
            station_id=station.id,
            display_number=2,
            name="Secondary Display",
            layout_mode="list",
            items_per_page=10,
        )

        display = service.create_display(display_data)

        assert display.id is not None
        assert display.station_id == station.id
        assert display.display_number == 2
        assert display.name == "Secondary Display"
        assert display.layout_mode == "list"
        assert display.is_active is True

    def test_display_heartbeat(self, db: Session):
        """Test updating display heartbeat"""
        service = KDSService(db)

        # Create station and get default display
        station = service.create_station(
            StationCreate(name="Bar Station", station_type=StationType.BAR)
        )
        display = db.query(KitchenDisplay).filter_by(station_id=station.id).first()

        # Update heartbeat
        service.update_display_heartbeat(display.id)

        db.refresh(display)
        assert display.last_heartbeat is not None
        assert (datetime.utcnow() - display.last_heartbeat).seconds < 5

    def test_order_item_lifecycle(self, db: Session):
        """Test KDS order item status progression"""
        service = KDSService(db)

        # Create station
        station = service.create_station(
            StationCreate(name="Saute Station", station_type=StationType.SAUTE)
        )

        # Create staff
        staff = StaffMember(
            name="Chef Jane",
            email="jane@example.com",
            phone="0987654321",
            role="chef",
            is_active=True,
        )
        db.add(staff)
        db.commit()

        # Create order and order item
        order = Order(staff_id=staff.id, table_no=5, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=1, quantity=2, price=15.99
        )
        db.add(order_item)
        db.commit()

        # Create KDS order item
        kds_item = KDSOrderItem(
            order_item_id=order_item.id,
            station_id=station.id,
            display_name="Pasta Carbonara",
            quantity=2,
            modifiers=["Extra cheese", "No bacon"],
            special_instructions="Make it spicy",
            priority=5,
            course_number=2,
            target_time=datetime.utcnow() + timedelta(minutes=15),
        )
        db.add(kds_item)
        db.commit()

        # Test acknowledge
        acknowledged_item = service.acknowledge_item(kds_item.id, staff.id)
        assert acknowledged_item.acknowledged_at is not None

        # Test start
        started_item = service.start_item(kds_item.id, staff.id)
        assert started_item.status == DisplayStatus.IN_PROGRESS
        assert started_item.started_at is not None
        assert started_item.started_by_id == staff.id

        # Test complete
        completed_item = service.complete_item(kds_item.id, staff.id)
        assert completed_item.status == DisplayStatus.COMPLETED
        assert completed_item.completed_at is not None
        assert completed_item.completed_by_id == staff.id

        # Test recall
        recalled_item = service.recall_item(kds_item.id, "Customer requested changes")
        assert recalled_item.status == DisplayStatus.RECALLED
        assert recalled_item.recall_count == 1
        assert recalled_item.last_recalled_at is not None
        assert recalled_item.recall_reason == "Customer requested changes"

    def test_get_station_items(self, db: Session):
        """Test retrieving items for a station"""
        service = KDSService(db)

        # Create station
        station = service.create_station(
            StationCreate(name="Dessert Station", station_type=StationType.DESSERT)
        )

        # Create multiple KDS items with different statuses
        pending_item = self._create_kds_item(
            db, station.id, DisplayStatus.PENDING, "Chocolate Cake"
        )
        in_progress_item = self._create_kds_item(
            db, station.id, DisplayStatus.IN_PROGRESS, "Ice Cream"
        )
        completed_item = self._create_kds_item(
            db, station.id, DisplayStatus.COMPLETED, "Apple Pie"
        )

        # Get active items (excludes completed)
        active_items = service.get_station_items(station.id)
        assert len(active_items) == 2
        assert all(item.status != DisplayStatus.COMPLETED for item in active_items)

        # Get items with specific status
        pending_items = service.get_station_items(station.id, [DisplayStatus.PENDING])
        assert len(pending_items) == 1
        assert pending_items[0].display_name == "Chocolate Cake"

        # Get all items including completed
        all_items = service.get_station_items(
            station.id,
            [DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS, DisplayStatus.COMPLETED],
        )
        assert len(all_items) == 3

    def test_station_summary(self, db: Session):
        """Test getting station summary statistics"""
        service = KDSService(db)

        # Create station
        station = service.create_station(
            StationCreate(name="Sandwich Station", station_type=StationType.SANDWICH)
        )

        # Create items with various statuses
        self._create_kds_item(db, station.id, DisplayStatus.PENDING, "BLT")
        self._create_kds_item(db, station.id, DisplayStatus.PENDING, "Club Sandwich")
        self._create_kds_item(
            db, station.id, DisplayStatus.IN_PROGRESS, "Grilled Cheese"
        )

        # Create a completed item
        completed_item = self._create_kds_item(
            db, station.id, DisplayStatus.COMPLETED, "Turkey Sub"
        )
        completed_item.completed_at = datetime.utcnow()
        completed_item.received_at = datetime.utcnow() - timedelta(minutes=10)
        db.commit()

        # Get summary
        summary = service.get_station_summary(station.id)

        assert summary.station_id == station.id
        assert summary.station_name == "Sandwich Station"
        assert summary.active_items == 1  # IN_PROGRESS
        assert summary.pending_items == 2  # PENDING
        assert summary.completed_today == 1
        assert summary.average_wait_time == 10.0  # 10 minutes
        assert summary.late_items == 0

    def test_update_item_timings(self, db: Session):
        """Test updating target times for items"""
        service = KDSService(db)

        # Create station with prep time multiplier
        station = service.create_station(
            StationCreate(
                name="Prep Station",
                station_type=StationType.PREP,
                prep_time_multiplier=1.5,
            )
        )

        # Create pending items without target times
        item1 = self._create_kds_item(
            db, station.id, DisplayStatus.PENDING, "Prep Item 1", target_time=None
        )
        item2 = self._create_kds_item(
            db, station.id, DisplayStatus.PENDING, "Prep Item 2", target_time=None
        )

        # Update timings
        service.update_item_timings()

        # Check target times were set
        db.refresh(item1)
        db.refresh(item2)

        assert item1.target_time is not None
        assert item2.target_time is not None
        assert item2.target_time > item1.target_time  # Item 2 should have later target

    def _create_kds_item(
        self,
        db: Session,
        station_id: int,
        status: DisplayStatus,
        display_name: str,
        target_time: datetime = None,
    ) -> KDSOrderItem:
        """Helper to create a KDS order item"""
        # Create dummy order and order item
        order = Order(staff_id=1, table_no=1, status="pending")
        db.add(order)
        db.commit()

        order_item = OrderItem(
            order_id=order.id, menu_item_id=1, quantity=1, price=10.00
        )
        db.add(order_item)
        db.commit()

        kds_item = KDSOrderItem(
            order_item_id=order_item.id,
            station_id=station_id,
            display_name=display_name,
            quantity=1,
            status=status,
            target_time=target_time or (datetime.utcnow() + timedelta(minutes=10)),
        )
        db.add(kds_item)
        db.commit()

        return kds_item

    def test_error_handling(self, db: Session):
        """Test error handling in service methods"""
        service = KDSService(db)

        # Test updating non-existent station
        with pytest.raises(ValueError, match="Station 999 not found"):
            service.update_station(999, StationUpdate(name="Test"))

        # Test creating display for non-existent station
        with pytest.raises(ValueError, match="Station 999 not found"):
            service.create_display(KitchenDisplayCreate(station_id=999))

        # Test starting non-existent item
        with pytest.raises(ValueError, match="KDS item 999 not found"):
            service.start_item(999, 1)

        # Test invalid status transition
        station = service.create_station(
            StationCreate(name="Test Station", station_type=StationType.GRILL)
        )

        completed_item = self._create_kds_item(
            db, station.id, DisplayStatus.COMPLETED, "Test Item"
        )

        with pytest.raises(ValueError, match="Cannot start item in completed status"):
            service.start_item(completed_item.id, 1)
