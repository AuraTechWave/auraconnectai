import types
from datetime import date, datetime, time
from unittest.mock import Mock

from modules.staff.services.scheduling_service import SchedulingService


class Row:
    def __init__(self, hour, cnt):
        self.hour = hour
        self.cnt = cnt


def build_db_mock(peak=30, roles=None, staff_per_role=3):
    # Mock query chain for orders
    mock_db = Mock()

    # rows representing hourly counts; max peak is `peak`
    rows = [Row(h, h) for h in range(peak)]
    q_orders = Mock()
    q_orders.filter.return_value = q_orders
    q_orders.group_by.return_value = q_orders
    q_orders.all.return_value = rows

    # roles
    class Role:
        def __init__(self, id, name, restaurant_id):
            self.id = id
            self.name = name
            self.restaurant_id = restaurant_id

    role_defs = roles or [
        Role(1, "Manager", 1),
        Role(2, "Chef", 1),
        Role(3, "Server", 1),
        Role(4, "Dishwasher", 1),
    ]

    q_roles = Mock()
    q_roles.filter.return_value = q_roles
    q_roles.all.return_value = role_defs

    # staff
    class Staff:
        def __init__(self, id, role_id, restaurant_id):
            self.id = id
            self.role_id = role_id
            self.restaurant_id = restaurant_id
            self.status = "active"

    staff_list = []
    sid = 10
    for r in role_defs:
        for _ in range(staff_per_role):
            staff_list.append(Staff(sid, r.id, r.restaurant_id))
            sid += 1

    q_staff = Mock()
    q_staff.filter.return_value = q_staff
    q_staff.all.return_value = staff_list

    # query multiplexer
    def query_dispatch(model):
        name = getattr(model, "__name__", str(model))
        if name.endswith("Order"):
            return q_orders
        if name.endswith("Role"):
            return q_roles
        if name.endswith("StaffMember"):
            return q_staff
        raise AssertionError(f"Unexpected model: {name}")

    mock_db.query.side_effect = query_dispatch
    return mock_db


def test_generate_demand_aware_schedule_basic():
    db = build_db_mock(peak=30)
    svc = SchedulingService(db)

    shifts = svc.generate_demand_aware_schedule(
        start_date=date(2025, 8, 18),
        end_date=date(2025, 8, 18),
        location_id=1,
        buffer_percentage=0.0,
    )

    # Should create some shifts for roles mapped
    assert len(shifts) > 0
    # Each shift has staff assigned and role id
    for s in shifts:
        assert s.staff_id is not None
        assert s.role_id is not None


def test_generate_demand_aware_schedule_respects_buffer():
    db = build_db_mock(peak=60)
    svc = SchedulingService(db)

    shifts_no_buf = svc.generate_demand_aware_schedule(
        start_date=date(2025, 8, 18), end_date=date(2025, 8, 18), location_id=1, buffer_percentage=0.0
    )
    shifts_buf = svc.generate_demand_aware_schedule(
        start_date=date(2025, 8, 18), end_date=date(2025, 8, 18), location_id=1, buffer_percentage=50.0
    )

    assert len(shifts_buf) >= len(shifts_no_buf)