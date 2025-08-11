# backend/modules/core/models/core_models.py
"""
Core models for the restaurant management system.
These are fundamental entities that other modules depend on.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, DECIMAL, JSON, Enum as SQLEnum, Text, Time
from sqlalchemy.orm import relationship
from datetime import datetime, time
from enum import Enum

from core.database import Base
from core.mixins import TimestampMixin


class RestaurantStatus(str, Enum):
    """Restaurant operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"  # Pending approval
    CLOSED = "closed"    # Permanently closed


class LocationType(str, Enum):
    """Type of location"""
    RESTAURANT = "restaurant"
    KITCHEN = "kitchen"
    WAREHOUSE = "warehouse"
    OFFICE = "office"
    OTHER = "other"


class FloorStatus(str, Enum):
    """Floor/section status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class Restaurant(Base, TimestampMixin):
    """
    Core restaurant entity that represents a single restaurant location.
    This is the root entity for multi-tenant data isolation.
    """
    __tablename__ = "restaurants"
    
    id = Column(Integer, primary_key=True)
    
    # Basic Information
    name = Column(String(200), nullable=False)
    legal_name = Column(String(200))  # Legal business name
    brand_name = Column(String(200))  # Brand/franchise name
    
    # Contact Information
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20), nullable=False)
    website = Column(String(500))
    
    # Address (denormalized for quick access)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255))
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False, default="US")  # ISO country code
    
    # Business Information
    tax_id = Column(String(50))  # EIN/Tax ID
    business_license = Column(String(100))
    
    # Operational Settings
    timezone = Column(String(50), nullable=False, default="America/New_York")
    currency = Column(String(3), nullable=False, default="USD")  # ISO currency code
    status = Column(SQLEnum(RestaurantStatus), nullable=False, default=RestaurantStatus.PENDING)
    
    # Operating Hours (stored as JSON for flexibility)
    # Format: {"monday": {"open": "09:00", "close": "22:00"}, ...}
    operating_hours = Column(JSON, default={})
    
    # Features and Subscription
    features = Column(JSON, default={})  # Enabled features
    subscription_tier = Column(String(50), default="basic")
    subscription_valid_until = Column(DateTime)
    
    # Settings
    settings = Column(JSON, default={})  # Restaurant-specific settings
    
    # Relationships
    locations = relationship("Location", back_populates="restaurant", cascade="all, delete-orphan")
    floors = relationship("Floor", back_populates="restaurant", cascade="all, delete-orphan")
    
    # Add these relationships as other modules are updated
    # staff_members = relationship("StaffMember", back_populates="restaurant")
    # menu_items = relationship("MenuItem", back_populates="restaurant")
    # orders = relationship("Order", back_populates="restaurant")
    # customers = relationship("Customer", back_populates="restaurant")
    # tables = relationship("Table", back_populates="restaurant")
    
    def __repr__(self):
        return f"<Restaurant(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def is_active(self):
        """Check if restaurant is active and subscription is valid"""
        if self.status != RestaurantStatus.ACTIVE:
            return False
        if self.subscription_valid_until and self.subscription_valid_until < datetime.utcnow():
            return False
        return True
    
    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        parts.append(self.country)
        return ", ".join(parts)


class Location(Base, TimestampMixin):
    """
    Represents different physical locations associated with a restaurant.
    A restaurant can have multiple locations (main dining, kitchen, storage, etc.)
    """
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    
    # Basic Information
    name = Column(String(200), nullable=False)
    location_type = Column(SQLEnum(LocationType), nullable=False, default=LocationType.RESTAURANT)
    code = Column(String(50))  # Internal code/identifier
    
    # Address (can be different from main restaurant)
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(2), default="US")
    
    # Contact
    phone = Column(String(20))
    email = Column(String(255))
    manager_name = Column(String(200))
    
    # Operational
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)  # Primary location for the restaurant
    
    # Capacity and Features
    seating_capacity = Column(Integer)
    parking_spaces = Column(Integer)
    features = Column(JSON, default={})  # Location-specific features
    
    # Operating Hours (can override restaurant hours)
    operating_hours = Column(JSON)
    
    # Settings
    settings = Column(JSON, default={})
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="locations")
    
    # Future relationships
    # inventory_items = relationship("InventoryItem", back_populates="location")
    # equipment = relationship("Equipment", back_populates="location")
    
    __table_args__ = (
        # Ensure only one primary location per restaurant
        # UniqueConstraint('restaurant_id', 'is_primary', name='uix_restaurant_primary_location'),
    )
    
    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', type={self.location_type})>"


class Floor(Base, TimestampMixin):
    """
    Represents a floor or section within a restaurant location.
    Used for table management and layout planning.
    Note: This is defined here as a core model since it's referenced by multiple modules.
    """
    __tablename__ = "floors"
    
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"))  # Optional: specific location
    
    # Basic Information
    name = Column(String(100), nullable=False)
    display_name = Column(String(100))
    floor_number = Column(Integer, default=1)
    
    # Layout Configuration
    width = Column(Integer, nullable=False, default=1000)  # Canvas width in pixels
    height = Column(Integer, nullable=False, default=800)  # Canvas height in pixels
    background_image = Column(String(500))  # Optional background image URL
    grid_size = Column(Integer, default=20)  # Grid snap size for designer
    
    # Status and Settings
    status = Column(SQLEnum(FloorStatus), default=FloorStatus.ACTIVE)
    is_default = Column(Boolean, default=False)
    max_capacity = Column(Integer)
    
    # Service Settings
    allows_reservations = Column(Boolean, default=True)
    service_charge_percent = Column(DECIMAL(5, 2))  # Optional floor-specific service charge
    
    # Metadata
    layout_config = Column(JSON, default={})  # Additional layout settings
    features = Column(JSON, default={})  # Floor-specific features
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="floors")
    location = relationship("Location")
    tables = relationship("Table", back_populates="floor", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Ensure unique floor names within a restaurant
        # UniqueConstraint('restaurant_id', 'name', name='uix_floor_restaurant_name'),
    )
    
    def __repr__(self):
        return f"<Floor(id={self.id}, name='{self.name}', restaurant_id={self.restaurant_id})>"
    
    @property
    def is_operational(self):
        """Check if floor is operational"""
        return self.status == FloorStatus.ACTIVE