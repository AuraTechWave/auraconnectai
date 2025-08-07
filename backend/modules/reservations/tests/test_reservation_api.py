# backend/modules/reservations/tests/test_reservation_api.py

"""
Tests for reservation API endpoints.
"""

import pytest
from datetime import date, time, datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy.orm import Session

from ..models.reservation_models import (
    Reservation, ReservationStatus, TableConfiguration,
    ReservationSettings
)


class TestReservationAPI:
    """Test reservation API endpoints"""
    
    @pytest.fixture
    def customer_headers(self, customer_auth_token):
        """Customer authentication headers"""
        return {"Authorization": f"Bearer {customer_auth_token}"}
    
    @pytest.fixture
    def staff_headers(self, staff_auth_token):
        """Staff authentication headers"""
        return {"Authorization": f"Bearer {staff_auth_token}"}
    
    @pytest.fixture
    def setup_tables(self, db_session: Session):
        """Setup test tables"""
        tables = [
            TableConfiguration(
                table_number="1",
                section="main",
                min_capacity=2,
                max_capacity=4
            ),
            TableConfiguration(
                table_number="2",
                section="main",
                min_capacity=4,
                max_capacity=6
            )
        ]
        for table in tables:
            db_session.add(table)
        
        # Add settings
        settings = ReservationSettings(
            restaurant_id=1,
            operating_hours={
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "10:00", "close": "23:00"},
                "sunday": {"open": "10:00", "close": "21:00"}
            }
        )
        db_session.add(settings)
        db_session.commit()
    
    def test_create_reservation_success(
        self, client: TestClient, customer_headers: dict, setup_tables
    ):
        """Test successful reservation creation"""
        tomorrow = date.today() + timedelta(days=1)
        
        reservation_data = {
            "reservation_date": tomorrow.isoformat(),
            "reservation_time": "19:00:00",
            "party_size": 2,
            "special_requests": "Window seat please",
            "dietary_restrictions": ["vegetarian"],
            "occasion": "anniversary"
        }
        
        response = client.post(
            "/api/v1/reservations",
            json=reservation_data,
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["party_size"] == 2
        assert data["status"] == "pending"
        assert data["confirmation_code"] is not None
        assert data["table_numbers"] is not None
        assert data["special_requests"] == "Window seat please"
        assert "vegetarian" in data["dietary_restrictions"]
        assert data["occasion"] == "anniversary"
    
    def test_create_reservation_no_availability(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test reservation creation when no tables available"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Fill up capacity
        for i in range(5):
            reservation = Reservation(
                customer_id=1,
                reservation_date=tomorrow,
                reservation_time=time(19, 0),
                party_size=4,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}",
                table_ids=[1]
            )
            db_session.add(reservation)
        db_session.commit()
        
        # Try to create another
        reservation_data = {
            "reservation_date": tomorrow.isoformat(),
            "reservation_time": "19:00:00",
            "party_size": 6
        }
        
        response = client.post(
            "/api/v1/reservations",
            json=reservation_data,
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not available" in response.json()["detail"]
    
    def test_get_my_reservations(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test getting customer's reservations"""
        # Create test reservations
        for i in range(3):
            reservation = Reservation(
                customer_id=1,  # Assuming test customer has ID 1
                reservation_date=date.today() + timedelta(days=i+1),
                reservation_time=time(19, 0),
                party_size=2,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}"
            )
            db_session.add(reservation)
        db_session.commit()
        
        response = client.get(
            "/api/v1/reservations/my-reservations",
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["total"] == 3
        assert len(data["reservations"]) == 3
        assert data["page"] == 1
        assert data["has_next"] is False
    
    def test_get_my_reservations_filtered(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test getting filtered reservations"""
        # Create mixed status reservations
        statuses = [ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED, ReservationStatus.CONFIRMED]
        for i, status in enumerate(statuses):
            reservation = Reservation(
                customer_id=1,
                reservation_date=date.today() + timedelta(days=i+1),
                reservation_time=time(19, 0),
                party_size=2,
                status=status,
                confirmation_code=f"TEST-{i:04d}"
            )
            db_session.add(reservation)
        db_session.commit()
        
        # Get only confirmed
        response = client.get(
            "/api/v1/reservations/my-reservations?status=confirmed",
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
    
    def test_check_availability(
        self, client: TestClient, setup_tables
    ):
        """Test checking availability (no auth required)"""
        tomorrow = date.today() + timedelta(days=1)
        
        response = client.get(
            f"/api/v1/reservations/availability?check_date={tomorrow.isoformat()}&party_size=2"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["date"] == tomorrow.isoformat()
        assert data["party_size"] == 2
        assert len(data["time_slots"]) > 0
        assert data["is_fully_booked"] is False
        assert data["waitlist_available"] is True
    
    def test_get_reservation_by_id(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test getting specific reservation"""
        # Create reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        response = client.get(
            f"/api/v1/reservations/{reservation.id}",
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == reservation.id
        assert data["confirmation_code"] == "TEST-1234"
    
    def test_get_reservation_by_code(
        self, client: TestClient, setup_tables, db_session: Session
    ):
        """Test getting reservation by confirmation code (no auth)"""
        # Create reservation
        from modules.customers.models.customer_models import Customer
        customer = Customer(
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )
        db_session.add(customer)
        db_session.flush()
        
        reservation = Reservation(
            customer_id=customer.id,
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        response = client.get("/api/v1/reservations/confirm/TEST-1234")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["confirmation_code"] == "TEST-1234"
        assert data["customer_name"] == "Test User"
    
    def test_update_reservation(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test updating reservation"""
        # Create reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today() + timedelta(days=2),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.PENDING,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        update_data = {
            "party_size": 4,
            "special_requests": "Need high chair"
        }
        
        response = client.put(
            f"/api/v1/reservations/{reservation.id}",
            json=update_data,
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["party_size"] == 4
        assert data["special_requests"] == "Need high chair"
    
    def test_cancel_reservation(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test cancelling reservation"""
        # Create reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        cancel_data = {
            "reason": "Changed plans",
            "cancelled_by": "customer"
        }
        
        response = client.post(
            f"/api/v1/reservations/{reservation.id}/cancel",
            json=cancel_data,
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["cancellation_reason"] == "Changed plans"
        assert data["cancelled_at"] is not None
    
    def test_confirm_reservation(
        self, client: TestClient, customer_headers: dict, setup_tables, db_session: Session
    ):
        """Test confirming reservation"""
        # Create pending reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.PENDING,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        confirm_data = {
            "confirmed": True,
            "special_requests_update": "Allergic to shellfish"
        }
        
        response = client.post(
            f"/api/v1/reservations/{reservation.id}/confirm",
            json=confirm_data,
            headers=customer_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["confirmed_at"] is not None
        assert "Allergic to shellfish" in data["special_requests"]
    
    # Staff endpoint tests
    def test_staff_get_daily_reservations(
        self, client: TestClient, staff_headers: dict, setup_tables, db_session: Session
    ):
        """Test staff getting daily reservations"""
        target_date = date.today() + timedelta(days=1)
        
        # Create test data
        from modules.customers.models.customer_models import Customer
        customer = Customer(
            first_name="Test",
            last_name="Customer",
            email="test@example.com"
        )
        db_session.add(customer)
        db_session.flush()
        
        for i in range(3):
            reservation = Reservation(
                customer_id=customer.id,
                reservation_date=target_date,
                reservation_time=time(18 + i, 0),
                party_size=2,
                status=ReservationStatus.CONFIRMED,
                confirmation_code=f"TEST-{i:04d}"
            )
            db_session.add(reservation)
        db_session.commit()
        
        response = client.get(
            f"/api/v1/reservations/staff/daily?reservation_date={target_date.isoformat()}",
            headers=staff_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
    
    def test_staff_update_reservation_status(
        self, client: TestClient, staff_headers: dict, setup_tables, db_session: Session
    ):
        """Test staff updating reservation status"""
        # Create reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today(),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        update_data = {
            "status": "seated",
            "table_numbers": "5",
            "notes": "VIP customer"
        }
        
        response = client.patch(
            f"/api/v1/reservations/staff/{reservation.id}",
            json=update_data,
            headers=staff_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "seated"
        assert data["table_numbers"] == "5"
    
    def test_staff_mark_as_seated(
        self, client: TestClient, staff_headers: dict, setup_tables, db_session: Session
    ):
        """Test staff marking reservation as seated"""
        # Create confirmed reservation
        reservation = Reservation(
            customer_id=1,
            reservation_date=date.today(),
            reservation_time=time(19, 0),
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            confirmation_code="TEST-1234"
        )
        db_session.add(reservation)
        db_session.commit()
        
        response = client.post(
            f"/api/v1/reservations/staff/{reservation.id}/seat?table_number=3",
            headers=staff_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "seated"
        assert data["table_numbers"] == "3"
        assert data["seated_at"] is not None