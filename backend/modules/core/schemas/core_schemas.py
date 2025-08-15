# backend/modules/core/schemas/core_schemas.py
"""
Pydantic schemas for core models.
"""

from pydantic import BaseModel, Field, EmailStr, validator, root_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from decimal import Decimal
import re

from ..models.core_models import RestaurantStatus, LocationType, FloorStatus


# ========== Restaurant Schemas ==========


class RestaurantBase(BaseModel):
    """Base schema for restaurant"""

    name: str = Field(..., min_length=1, max_length=200, description="Restaurant name")
    legal_name: Optional[str] = Field(
        None, max_length=200, description="Legal business name"
    )
    brand_name: Optional[str] = Field(
        None, max_length=200, description="Brand/franchise name"
    )

    email: EmailStr = Field(..., description="Primary contact email")
    phone: str = Field(..., min_length=10, max_length=20, description="Contact phone")
    website: Optional[str] = Field(None, max_length=500, description="Website URL")

    address_line1: str = Field(
        ..., min_length=1, max_length=255, description="Street address"
    )
    address_line2: Optional[str] = Field(
        None, max_length=255, description="Suite/Apt/Unit"
    )
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(..., min_length=2, max_length=50, description="State/Province")
    postal_code: str = Field(
        ..., min_length=5, max_length=20, description="Postal/ZIP code"
    )
    country: str = Field(
        "US", min_length=2, max_length=2, description="ISO country code"
    )

    timezone: str = Field("America/New_York", description="IANA timezone")
    currency: str = Field(
        "USD", min_length=3, max_length=3, description="ISO currency code"
    )

    @validator("name", "legal_name", "brand_name")
    def validate_names(cls, v):
        if v:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be empty or whitespace only")
        return v

    @validator("phone")
    def validate_phone(cls, v):
        # Remove common formatting characters
        cleaned = re.sub(r"[\s\-\(\)\.]", "", v)
        if not re.match(r"^\+?\d{10,15}$", cleaned):
            raise ValueError("Invalid phone number format")
        return v

    @validator("website")
    def validate_website(cls, v):
        if v:
            if not v.startswith(("http://", "https://")):
                v = f"https://{v}"
            if not re.match(r"^https?://[^\s]+\.[^\s]+$", v):
                raise ValueError("Invalid website URL")
        return v

    @validator("country")
    def validate_country(cls, v):
        return v.upper()


class RestaurantCreate(RestaurantBase):
    """Schema for creating a restaurant"""

    tax_id: Optional[str] = Field(None, max_length=50, description="EIN/Tax ID")
    business_license: Optional[str] = Field(
        None, max_length=100, description="Business license number"
    )

    operating_hours: Optional[Dict[str, Dict[str, str]]] = Field(
        None, description="Operating hours by day"
    )

    @validator("operating_hours")
    def validate_operating_hours(cls, v):
        if v:
            days = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            for day in v:
                if day.lower() not in days:
                    raise ValueError(f"Invalid day: {day}")
                if "open" not in v[day] or "close" not in v[day]:
                    raise ValueError(f"Day {day} must have 'open' and 'close' times")
                # Validate time format
                for time_key in ["open", "close"]:
                    if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", v[day][time_key]):
                        raise ValueError(f"Invalid time format for {day} {time_key}")
        return v


class RestaurantUpdate(BaseModel):
    """Schema for updating a restaurant"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    brand_name: Optional[str] = Field(None, max_length=200)

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    website: Optional[str] = Field(None, max_length=500)

    address_line1: Optional[str] = Field(None, min_length=1, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=50)
    postal_code: Optional[str] = Field(None, min_length=5, max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=2)

    tax_id: Optional[str] = Field(None, max_length=50)
    business_license: Optional[str] = Field(None, max_length=100)

    timezone: Optional[str] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    status: Optional[RestaurantStatus] = None

    operating_hours: Optional[Dict[str, Dict[str, str]]] = None
    features: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None

    subscription_tier: Optional[str] = Field(None, max_length=50)
    subscription_valid_until: Optional[datetime] = None


class RestaurantResponse(RestaurantBase):
    """Response schema for restaurant"""

    id: int
    tax_id: Optional[str]
    business_license: Optional[str]
    status: RestaurantStatus
    operating_hours: Dict[str, Dict[str, str]]
    features: Dict[str, Any]
    settings: Dict[str, Any]
    subscription_tier: str
    subscription_valid_until: Optional[datetime]
    is_active: bool
    full_address: str
    created_at: datetime
    updated_at: Optional[datetime]

    # Counts
    location_count: int = 0
    floor_count: int = 0

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class RestaurantListResponse(BaseModel):
    """Response for restaurant list"""

    items: List[RestaurantResponse]
    total: int
    page: int
    size: int
    pages: int


# ========== Location Schemas ==========


class LocationBase(BaseModel):
    """Base schema for location"""

    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    location_type: LocationType = Field(
        LocationType.RESTAURANT, description="Type of location"
    )
    code: Optional[str] = Field(None, max_length=50, description="Internal code")

    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    manager_name: Optional[str] = Field(None, max_length=200)

    seating_capacity: Optional[int] = Field(None, ge=0, le=10000)
    parking_spaces: Optional[int] = Field(None, ge=0, le=10000)

    @validator("name", "manager_name")
    def validate_names(cls, v):
        if v:
            v = v.strip()
            if not v:
                raise ValueError("Cannot be empty or whitespace only")
        return v


class LocationCreate(LocationBase):
    """Schema for creating a location"""

    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: str = Field("US", min_length=2, max_length=2)

    is_primary: bool = Field(False, description="Set as primary location")
    operating_hours: Optional[Dict[str, Dict[str, str]]] = None
    features: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class LocationUpdate(BaseModel):
    """Schema for updating a location"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    location_type: Optional[LocationType] = None
    code: Optional[str] = Field(None, max_length=50)

    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=2)

    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    manager_name: Optional[str] = Field(None, max_length=200)

    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None

    seating_capacity: Optional[int] = Field(None, ge=0, le=10000)
    parking_spaces: Optional[int] = Field(None, ge=0, le=10000)

    operating_hours: Optional[Dict[str, Dict[str, str]]] = None
    features: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class LocationResponse(LocationBase):
    """Response schema for location"""

    id: int
    restaurant_id: int
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: str
    is_active: bool
    is_primary: bool
    operating_hours: Optional[Dict[str, Dict[str, str]]]
    features: Dict[str, Any]
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class LocationListResponse(BaseModel):
    """Response for location list"""

    items: List[LocationResponse]
    total: int
    page: int
    size: int
    pages: int


# ========== Floor Schemas ==========


class FloorBase(BaseModel):
    """Base schema for floor"""

    name: str = Field(..., min_length=1, max_length=100, description="Floor name")
    display_name: Optional[str] = Field(
        None, max_length=100, description="Display name"
    )
    floor_number: int = Field(1, ge=-10, le=200, description="Floor number")

    width: int = Field(1000, ge=100, le=10000, description="Canvas width in pixels")
    height: int = Field(800, ge=100, le=10000, description="Canvas height in pixels")
    grid_size: int = Field(20, ge=10, le=100, description="Grid snap size")

    max_capacity: Optional[int] = Field(None, ge=0, le=10000)
    allows_reservations: bool = Field(
        True, description="Allow reservations on this floor"
    )
    service_charge_percent: Optional[Decimal] = Field(
        None,
        ge=0,
        le=100,
        decimal_places=2,
        description="Floor-specific service charge",
    )

    @validator("name", "display_name")
    def validate_names(cls, v):
        if v:
            v = v.strip()
            if not v:
                raise ValueError("Cannot be empty or whitespace only")
        return v


class FloorCreate(FloorBase):
    """Schema for creating a floor"""

    location_id: Optional[int] = Field(None, gt=0, description="Specific location ID")
    background_image: Optional[str] = Field(
        None, max_length=500, description="Background image URL"
    )
    is_default: bool = Field(False, description="Set as default floor")
    layout_config: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None


class FloorUpdate(BaseModel):
    """Schema for updating a floor"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    floor_number: Optional[int] = Field(None, ge=-10, le=200)
    location_id: Optional[int] = Field(None, gt=0)

    width: Optional[int] = Field(None, ge=100, le=10000)
    height: Optional[int] = Field(None, ge=100, le=10000)
    background_image: Optional[str] = Field(None, max_length=500)
    grid_size: Optional[int] = Field(None, ge=10, le=100)

    status: Optional[FloorStatus] = None
    is_default: Optional[bool] = None
    max_capacity: Optional[int] = Field(None, ge=0, le=10000)

    allows_reservations: Optional[bool] = None
    service_charge_percent: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=2
    )

    layout_config: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None


class FloorResponse(FloorBase):
    """Response schema for floor"""

    id: int
    restaurant_id: int
    location_id: Optional[int]
    background_image: Optional[str]
    status: FloorStatus
    is_default: bool
    layout_config: Dict[str, Any]
    features: Dict[str, Any]
    is_operational: bool
    created_at: datetime
    updated_at: Optional[datetime]

    # Counts
    table_count: int = 0
    active_table_count: int = 0

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class FloorListResponse(BaseModel):
    """Response for floor list"""

    items: List[FloorResponse]
    total: int
    page: int
    size: int
    pages: int
