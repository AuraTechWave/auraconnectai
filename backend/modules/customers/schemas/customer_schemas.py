# backend/modules/customers/schemas/customer_schemas.py

from pydantic import BaseModel, EmailStr, Field, field_validator, constr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CustomerStatus(str, Enum):
    """Customer account status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CustomerTier(str, Enum):
    """Customer loyalty tier levels"""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    VIP = "vip"


class CommunicationChannel(str, Enum):
    """Communication channels"""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


# Base schemas
class CustomerAddressBase(BaseModel):
    """Base schema for customer addresses"""

    label: Optional[str] = Field(None, max_length=50)
    address_line1: str = Field(..., max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: str = Field(..., max_length=20)
    country: str = Field("US", max_length=2, pattern="^[A-Z]{2}$")
    delivery_instructions: Optional[str] = None
    is_default: bool = False
    is_billing: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerAddressCreate(CustomerAddressBase):
    """Schema for creating a customer address"""

    pass


class CustomerAddressUpdate(BaseModel):
    """Schema for updating a customer address"""

    label: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=2, pattern="^[A-Z]{2}$")
    delivery_instructions: Optional[str] = None
    is_default: Optional[bool] = None
    is_billing: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerAddress(CustomerAddressBase):
    """Schema for customer address response"""

    id: int
    customer_id: int
    is_verified: bool
    verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


# Customer schemas
class CustomerBase(BaseModel):
    """Base schema for customer"""

    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: Optional[constr(pattern=r"^\+?[1-9]\d{1,14}$")] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = Field(None, max_length=20)
    dietary_preferences: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    communication_preferences: Optional[Dict[str, bool]] = None
    marketing_opt_in: bool = True
    preferred_location_id: Optional[int] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    external_id: Optional[str] = Field(None, max_length=100)


class CustomerCreate(CustomerBase):
    """Schema for creating a customer"""

    password: Optional[str] = Field(None, min_length=8)
    referral_code: Optional[str] = None
    acquisition_source: Optional[str] = Field(None, max_length=100)

    @field_validator("password", mode="after")
    def validate_password(cls, v):
        if v and len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""

    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[constr(pattern=r"^\+?[1-9]\d{1,14}$")] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = Field(None, max_length=20)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    dietary_preferences: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    communication_preferences: Optional[Dict[str, bool]] = None
    marketing_opt_in: Optional[bool] = None
    preferred_location_id: Optional[int] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class CustomerStatusUpdate(BaseModel):
    """Schema for updating customer status"""

    status: CustomerStatus
    reason: Optional[str] = None


class CustomerTierUpdate(BaseModel):
    """Schema for updating customer tier"""

    tier: CustomerTier
    reason: Optional[str] = None


class Customer(CustomerBase):
    """Schema for customer response"""

    id: int
    phone_verified: bool
    email_verified: bool
    status: CustomerStatus
    tier: CustomerTier
    tier_updated_at: Optional[datetime]
    loyalty_points: int
    lifetime_points: int
    points_expiry_date: Optional[datetime]
    referral_code: Optional[str]
    referred_by_customer_id: Optional[int]
    acquisition_date: datetime
    first_order_date: Optional[datetime]
    last_order_date: Optional[datetime]
    total_orders: int
    total_spent: float
    average_order_value: float
    last_login: Optional[datetime]
    login_count: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    # Computed properties
    full_name: str
    is_vip: bool

    class Config:
        from_attributes = True


class CustomerWithAddresses(Customer):
    """Customer response with addresses"""

    addresses: List[CustomerAddress] = []
    default_address: Optional[CustomerAddress] = None


class CustomerProfile(CustomerWithAddresses):
    """Complete customer profile with all related data"""

    payment_methods: List["CustomerPaymentMethod"] = []
    recent_orders: List["OrderSummary"] = []
    favorite_items: List["MenuItemSummary"] = []
    active_rewards: List["CustomerReward"] = []
    preferences: Dict[str, Any] = {}


# Payment method schemas
class CustomerPaymentMethodBase(BaseModel):
    """Base schema for payment methods"""

    type: str = Field(..., max_length=50)
    label: Optional[str] = Field(None, max_length=100)
    is_default: bool = False


class CustomerPaymentMethodCreate(CustomerPaymentMethodBase):
    """Schema for creating a payment method"""

    card_token: Optional[str] = None
    billing_address_id: Optional[int] = None


class CustomerPaymentMethod(CustomerPaymentMethodBase):
    """Schema for payment method response"""

    id: int
    customer_id: int
    card_last4: Optional[str]
    card_brand: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Notification schemas
class CustomerNotificationCreate(BaseModel):
    """Schema for creating a notification"""

    customer_id: int
    type: str = Field(..., max_length=50)
    channel: CommunicationChannel
    subject: Optional[str] = Field(None, max_length=255)
    content: str
    metadata: Optional[Dict[str, Any]] = None


class CustomerNotification(BaseModel):
    """Schema for notification response"""

    id: int
    customer_id: int
    type: str
    channel: str
    subject: Optional[str]
    content: str
    status: str
    sent_at: Optional[datetime]
    read_at: Optional[datetime]
    failed_at: Optional[datetime]
    failure_reason: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# Reward schemas
class CustomerRewardBase(BaseModel):
    """Base schema for rewards"""

    type: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    points_cost: Optional[int] = None
    discount_amount: Optional[float] = None
    discount_percentage: Optional[float] = None
    item_id: Optional[int] = None
    valid_until: Optional[datetime] = None
    min_order_amount: Optional[float] = None
    applicable_categories: Optional[List[int]] = None
    applicable_items: Optional[List[int]] = None


class CustomerRewardCreate(CustomerRewardBase):
    """Schema for creating a reward"""

    customer_id: int


class CustomerReward(CustomerRewardBase):
    """Schema for reward response"""

    id: int
    customer_id: int
    status: str
    code: Optional[str]
    valid_from: datetime
    redeemed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Preference schemas
class CustomerPreferenceCreate(BaseModel):
    """Schema for creating a preference"""

    category: str = Field(..., max_length=50)
    preference_key: str = Field(..., max_length=100)
    preference_value: Any
    source: Optional[str] = Field(None, max_length=50)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)


class CustomerPreference(CustomerPreferenceCreate):
    """Schema for preference response"""

    id: int
    customer_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Analytics schemas
class CustomerAnalytics(BaseModel):
    """Customer analytics and insights"""

    customer_id: int
    total_orders: int
    total_spent: float
    average_order_value: float
    order_frequency_days: Optional[float]  # Average days between orders
    favorite_categories: List[Dict[str, Any]]  # Top categories by order count
    favorite_items: List[Dict[str, Any]]  # Top items by order count
    preferred_order_times: Dict[str, int]  # Order count by hour of day
    preferred_order_days: Dict[str, int]  # Order count by day of week
    lifetime_value: float
    churn_risk_score: Optional[float]  # 0-1 score
    last_order_days_ago: Optional[int]

    class Config:
        from_attributes = True


# Search and filter schemas
class CustomerSearchParams(BaseModel):
    """Parameters for searching customers"""

    query: Optional[str] = Field(None, description="Search in name, email, phone")
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tier: Optional[List[CustomerTier]] = None
    status: Optional[List[CustomerStatus]] = None
    min_orders: Optional[int] = Field(None, ge=0)
    max_orders: Optional[int] = Field(None, ge=0)
    min_spent: Optional[float] = Field(None, ge=0)
    max_spent: Optional[float] = Field(None, ge=0)
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_order_after: Optional[datetime] = None
    last_order_before: Optional[datetime] = None
    has_active_rewards: Optional[bool] = None
    location_id: Optional[int] = None
    tags: Optional[List[str]] = None

    # Pagination
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = Field(
        "created_at",
        pattern="^(created_at|updated_at|last_order_date|total_spent|total_orders)$",
    )
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class CustomerSearchResponse(BaseModel):
    """Response for customer search"""

    customers: List[Customer]
    total: int
    page: int
    page_size: int
    total_pages: int


# Segment schemas
class CustomerSegmentCreate(BaseModel):
    """Schema for creating a customer segment"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    criteria: Dict[str, Any]
    is_dynamic: bool = False


class CustomerSegmentUpdate(BaseModel):
    """Schema for updating a customer segment - all fields optional"""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None
    is_dynamic: Optional[bool] = None
    is_active: Optional[bool] = None


class CustomerSegment(CustomerSegmentCreate):
    """Schema for segment response"""

    id: int
    is_active: bool
    member_count: int
    last_updated: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Order history schemas (simplified)
class OrderSummary(BaseModel):
    """Simplified order information for customer profile"""

    id: int
    order_number: str
    status: str
    total_amount: float
    item_count: int
    created_at: datetime
    fulfilled_at: Optional[datetime]


class MenuItemSummary(BaseModel):
    """Simplified menu item for favorites"""

    id: int
    name: str
    category: str
    price: float
    image_url: Optional[str]
    order_count: int  # How many times customer ordered this


# Import handling
CustomerProfile.model_rebuild()  # Rebuild to handle forward references
