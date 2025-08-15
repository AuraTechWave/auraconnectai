# backend/modules/core/services/core_service.py
"""
Service layer for core models (Restaurant, Location, Floor).
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from ..models import (
    Restaurant,
    Location,
    Floor,
    RestaurantStatus,
    LocationType,
    FloorStatus,
)
from ..schemas import (
    RestaurantCreate,
    RestaurantUpdate,
    LocationCreate,
    LocationUpdate,
    FloorCreate,
    FloorUpdate,
)


class CoreService:
    """Service for managing core entities"""

    def __init__(self, db: Session):
        self.db = db

    # ========== Restaurant Methods ==========

    def get_restaurant(self, restaurant_id: int) -> Optional[Restaurant]:
        """Get restaurant by ID"""
        return self.db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()

    def get_restaurant_by_email(self, email: str) -> Optional[Restaurant]:
        """Get restaurant by email"""
        return self.db.query(Restaurant).filter(Restaurant.email == email).first()

    def get_restaurants(
        self, status: Optional[RestaurantStatus] = None, skip: int = 0, limit: int = 100
    ) -> List[Restaurant]:
        """Get list of restaurants with optional filtering"""
        query = self.db.query(Restaurant)

        if status:
            query = query.filter(Restaurant.status == status)

        return query.offset(skip).limit(limit).all()

    def create_restaurant(self, restaurant_data: RestaurantCreate) -> Restaurant:
        """Create a new restaurant"""
        # Check if email already exists
        existing = self.get_restaurant_by_email(restaurant_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Restaurant with email {restaurant_data.email} already exists",
            )

        restaurant = Restaurant(**restaurant_data.dict())
        self.db.add(restaurant)
        self.db.commit()
        self.db.refresh(restaurant)

        # Create default location
        default_location = Location(
            restaurant_id=restaurant.id,
            name="Main Location",
            location_type=LocationType.RESTAURANT,
            is_primary=True,
            is_active=True,
            address_line1=restaurant.address_line1,
            address_line2=restaurant.address_line2,
            city=restaurant.city,
            state=restaurant.state,
            postal_code=restaurant.postal_code,
            country=restaurant.country,
            phone=restaurant.phone,
            email=restaurant.email,
        )
        self.db.add(default_location)

        # Create default floor
        default_floor = Floor(
            restaurant_id=restaurant.id,
            name="Main Floor",
            display_name="Main Dining Area",
            floor_number=1,
            is_default=True,
            status=FloorStatus.ACTIVE,
        )
        self.db.add(default_floor)

        self.db.commit()

        return restaurant

    def update_restaurant(
        self, restaurant_id: int, update_data: RestaurantUpdate
    ) -> Restaurant:
        """Update restaurant information"""
        restaurant = self.get_restaurant(restaurant_id)
        if not restaurant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant with ID {restaurant_id} not found",
            )

        # Check email uniqueness if being updated
        if update_data.email and update_data.email != restaurant.email:
            existing = self.get_restaurant_by_email(update_data.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email {update_data.email} is already in use",
                )

        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(restaurant, field, value)

        self.db.commit()
        self.db.refresh(restaurant)
        return restaurant

    def delete_restaurant(self, restaurant_id: int, soft_delete: bool = True) -> bool:
        """Delete or deactivate a restaurant"""
        restaurant = self.get_restaurant(restaurant_id)
        if not restaurant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant with ID {restaurant_id} not found",
            )

        if soft_delete:
            restaurant.status = RestaurantStatus.CLOSED
            self.db.commit()
        else:
            self.db.delete(restaurant)
            self.db.commit()

        return True

    # ========== Location Methods ==========

    def get_location(self, location_id: int) -> Optional[Location]:
        """Get location by ID"""
        return self.db.query(Location).filter(Location.id == location_id).first()

    def get_restaurant_locations(
        self,
        restaurant_id: int,
        location_type: Optional[LocationType] = None,
        is_active: Optional[bool] = None,
    ) -> List[Location]:
        """Get all locations for a restaurant"""
        query = self.db.query(Location).filter(Location.restaurant_id == restaurant_id)

        if location_type:
            query = query.filter(Location.location_type == location_type)
        if is_active is not None:
            query = query.filter(Location.is_active == is_active)

        return query.all()

    def create_location(
        self, restaurant_id: int, location_data: LocationCreate
    ) -> Location:
        """Create a new location for a restaurant"""
        # Verify restaurant exists
        restaurant = self.get_restaurant(restaurant_id)
        if not restaurant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant with ID {restaurant_id} not found",
            )

        # If setting as primary, unset other primary locations
        if location_data.is_primary:
            self.db.query(Location).filter(
                Location.restaurant_id == restaurant_id, Location.is_primary == True
            ).update({"is_primary": False})

        location = Location(restaurant_id=restaurant_id, **location_data.dict())
        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)
        return location

    def update_location(
        self, location_id: int, update_data: LocationUpdate
    ) -> Location:
        """Update location information"""
        location = self.get_location(location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location with ID {location_id} not found",
            )

        # Handle primary location update
        if update_data.is_primary is True and not location.is_primary:
            self.db.query(Location).filter(
                Location.restaurant_id == location.restaurant_id,
                Location.is_primary == True,
                Location.id != location_id,
            ).update({"is_primary": False})

        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(location, field, value)

        self.db.commit()
        self.db.refresh(location)
        return location

    def delete_location(self, location_id: int) -> bool:
        """Delete a location (soft delete by deactivating)"""
        location = self.get_location(location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location with ID {location_id} not found",
            )

        if location.is_primary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete primary location",
            )

        location.is_active = False
        self.db.commit()
        return True

    # ========== Floor Methods ==========

    def get_floor(self, floor_id: int) -> Optional[Floor]:
        """Get floor by ID"""
        return self.db.query(Floor).filter(Floor.id == floor_id).first()

    def get_restaurant_floors(
        self,
        restaurant_id: int,
        location_id: Optional[int] = None,
        status: Optional[FloorStatus] = None,
    ) -> List[Floor]:
        """Get all floors for a restaurant"""
        query = self.db.query(Floor).filter(Floor.restaurant_id == restaurant_id)

        if location_id:
            query = query.filter(Floor.location_id == location_id)
        if status:
            query = query.filter(Floor.status == status)

        return query.all()

    def create_floor(self, restaurant_id: int, floor_data: FloorCreate) -> Floor:
        """Create a new floor for a restaurant"""
        # Verify restaurant exists
        restaurant = self.get_restaurant(restaurant_id)
        if not restaurant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant with ID {restaurant_id} not found",
            )

        # Verify location if provided
        if floor_data.location_id:
            location = self.get_location(floor_data.location_id)
            if not location or location.restaurant_id != restaurant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid location ID",
                )

        # Check for duplicate name
        existing = (
            self.db.query(Floor)
            .filter(Floor.restaurant_id == restaurant_id, Floor.name == floor_data.name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Floor with name '{floor_data.name}' already exists",
            )

        # If setting as default, unset other default floors
        if floor_data.is_default:
            self.db.query(Floor).filter(
                Floor.restaurant_id == restaurant_id, Floor.is_default == True
            ).update({"is_default": False})

        floor = Floor(restaurant_id=restaurant_id, **floor_data.dict())
        self.db.add(floor)
        self.db.commit()
        self.db.refresh(floor)
        return floor

    def update_floor(self, floor_id: int, update_data: FloorUpdate) -> Floor:
        """Update floor information"""
        floor = self.get_floor(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor with ID {floor_id} not found",
            )

        # Check name uniqueness if being updated
        if update_data.name and update_data.name != floor.name:
            existing = (
                self.db.query(Floor)
                .filter(
                    Floor.restaurant_id == floor.restaurant_id,
                    Floor.name == update_data.name,
                    Floor.id != floor_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Floor with name '{update_data.name}' already exists",
                )

        # Handle default floor update
        if update_data.is_default is True and not floor.is_default:
            self.db.query(Floor).filter(
                Floor.restaurant_id == floor.restaurant_id,
                Floor.is_default == True,
                Floor.id != floor_id,
            ).update({"is_default": False})

        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(floor, field, value)

        self.db.commit()
        self.db.refresh(floor)
        return floor

    def delete_floor(self, floor_id: int) -> bool:
        """Delete a floor (soft delete by setting inactive)"""
        floor = self.get_floor(floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Floor with ID {floor_id} not found",
            )

        if floor.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete default floor",
            )

        # Check if floor has tables
        if floor.tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete floor with existing tables",
            )

        floor.status = FloorStatus.INACTIVE
        self.db.commit()
        return True
