# backend/modules/customers/models/customer_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime, 
                        Float, Text, Boolean, JSON, Enum as SQLEnum, Index, UniqueConstraint, Table)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from core.database import Base
from core.mixins import TimestampMixin
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


class CommunicationPreference(str, Enum):
    """Customer communication preferences"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    NONE = "none"


class Customer(Base, TimestampMixin):
    """Customer profile with comprehensive information"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True, index=True)
    phone_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    
    # Authentication (optional - for registered customers)
    password_hash = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0)
    
    # Profile Information
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(20), nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    
    # Status and Tier
    status = Column(SQLEnum(CustomerStatus), nullable=False, default=CustomerStatus.ACTIVE, index=True)
    tier = Column(SQLEnum(CustomerTier), nullable=False, default=CustomerTier.BRONZE, index=True)
    tier_updated_at = Column(DateTime, nullable=True)
    
    # Location Information
    default_address_id = Column(Integer, ForeignKey("customer_addresses.id"), nullable=True)
    preferred_location_id = Column(Integer, nullable=True)  # Preferred restaurant location
    
    # Preferences
    dietary_preferences = Column(JSONB, nullable=True)  # vegetarian, vegan, gluten-free, etc.
    allergens = Column(JSONB, nullable=True)  # List of allergens
    favorite_items = Column(JSONB, nullable=True)  # List of favorite menu item IDs
    communication_preferences = Column(JSONB, nullable=True)  # Email, SMS, Push preferences
    marketing_opt_in = Column(Boolean, default=True)
    
    # Loyalty and Rewards
    loyalty_points = Column(Integer, default=0)
    lifetime_points = Column(Integer, default=0)
    points_expiry_date = Column(DateTime, nullable=True)
    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    
    # Analytics and Tracking
    acquisition_source = Column(String(100), nullable=True)  # web, app, in-store, referral
    acquisition_date = Column(DateTime, default=datetime.utcnow)
    first_order_date = Column(DateTime, nullable=True)
    last_order_date = Column(DateTime, nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    average_order_value = Column(Float, default=0.0)
    
    # Metadata
    notes = Column(Text, nullable=True)  # Internal notes about the customer
    tags = Column(JSONB, nullable=True)  # Custom tags for segmentation
    custom_fields = Column(JSONB, nullable=True)  # Flexible custom data
    external_id = Column(String(100), nullable=True, index=True)  # ID from external systems
    
    # Soft Delete
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, nullable=True)
    
    # Relationships
    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    payment_methods = relationship("CustomerPaymentMethod", back_populates="customer", cascade="all, delete-orphan")
    notifications = relationship("CustomerNotification", back_populates="customer", cascade="all, delete-orphan")
    segments = relationship("CustomerSegment", secondary="customer_segment_members", back_populates="customers")
    rewards = relationship("CustomerReward", back_populates="customer", cascade="all, delete-orphan")
    preferences = relationship("CustomerPreference", back_populates="customer", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="customer", cascade="all, delete-orphan")
    
    # Order tracking relationships
    order_trackings = relationship("CustomerOrderTracking", back_populates="customer")
    order_notifications = relationship("OrderNotification", back_populates="customer")
    referred_customers = relationship("Customer", backref="referrer")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_customers_name', 'first_name', 'last_name'),
        Index('ix_customers_tier_status', 'tier', 'status'),
        Index('ix_customers_location', 'preferred_location_id'),
        Index('ix_customers_acquisition', 'acquisition_source', 'acquisition_date'),
    )
    
    @property
    def full_name(self):
        """Return customer's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_vip(self):
        """Check if customer is VIP tier"""
        return self.tier in [CustomerTier.PLATINUM, CustomerTier.VIP]
    
    def __repr__(self):
        return f"<Customer(id={self.id}, email='{self.email}', tier='{self.tier}')>"


class CustomerAddress(Base, TimestampMixin):
    """Customer delivery/billing addresses"""
    __tablename__ = "customer_addresses"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Address Information
    label = Column(String(50), nullable=True)  # Home, Work, etc.
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False, default="US")  # ISO country code
    
    # Delivery Information
    delivery_instructions = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    is_billing = Column(Boolean, default=False)
    
    # Geolocation
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Validation
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Soft Delete
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="addresses")
    
    def __repr__(self):
        return f"<CustomerAddress(id={self.id}, label='{self.label}', city='{self.city}')>"


class CustomerPaymentMethod(Base, TimestampMixin):
    """Customer saved payment methods"""
    __tablename__ = "customer_payment_methods"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Payment Method Information
    type = Column(String(50), nullable=False)  # card, paypal, apple_pay, etc.
    label = Column(String(100), nullable=True)  # User-friendly name
    
    # Card Information (encrypted/tokenized)
    card_token = Column(String(255), nullable=True)  # Payment processor token
    card_last4 = Column(String(4), nullable=True)
    card_brand = Column(String(50), nullable=True)  # visa, mastercard, etc.
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    
    # Digital Wallet
    wallet_id = Column(String(255), nullable=True)
    
    # Billing Address
    billing_address_id = Column(Integer, ForeignKey("customer_addresses.id"), nullable=True)
    
    # Status
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Soft Delete
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="payment_methods")
    billing_address = relationship("CustomerAddress")
    
    def __repr__(self):
        return f"<CustomerPaymentMethod(id={self.id}, type='{self.type}', last4='{self.card_last4}')>"


class CustomerNotification(Base, TimestampMixin):
    """Customer notification history"""
    __tablename__ = "customer_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Notification Details
    type = Column(String(50), nullable=False)  # order_status, promotion, etc.
    channel = Column(String(50), nullable=False)  # email, sms, push
    subject = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    
    # Status
    status = Column(String(50), nullable=False, default="pending")  # pending, sent, failed, read
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Metadata
    notification_metadata = Column(JSONB, nullable=True)  # Additional data like order_id, promotion_id
    
    # Relationships
    customer = relationship("Customer", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('ix_customer_notifications_status', 'customer_id', 'status'),
        Index('ix_customer_notifications_type', 'type', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CustomerNotification(id={self.id}, type='{self.type}', status='{self.status}')>"


class CustomerSegment(Base, TimestampMixin):
    """Customer segmentation for targeted marketing"""
    __tablename__ = "customer_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Segment Criteria (stored as JSON for flexibility)
    criteria = Column(JSONB, nullable=True)  # e.g., {"min_orders": 5, "tier": ["gold", "platinum"]}
    
    # Status
    is_active = Column(Boolean, default=True)
    is_dynamic = Column(Boolean, default=False)  # Auto-update membership based on criteria
    
    # Statistics
    member_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customers = relationship("Customer", secondary="customer_segment_members", back_populates="segments")
    
    def __repr__(self):
        return f"<CustomerSegment(id={self.id}, name='{self.name}', members={self.member_count})>"


# Association table for customer segments
customer_segment_members = Table('customer_segment_members', Base.metadata,
    Column('customer_id', Integer, ForeignKey('customers.id'), primary_key=True),
    Column('segment_id', Integer, ForeignKey('customer_segments.id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.utcnow),
    Column('expires_at', DateTime, nullable=True)
)


class CustomerReward(Base, TimestampMixin):
    """Customer rewards and loyalty benefits"""
    __tablename__ = "customer_rewards"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Reward Details
    type = Column(String(50), nullable=False)  # points, discount, free_item, etc.
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Value
    points_cost = Column(Integer, nullable=True)  # Points required to redeem
    discount_amount = Column(Float, nullable=True)  # For discount rewards
    discount_percentage = Column(Float, nullable=True)
    item_id = Column(Integer, nullable=True)  # For free item rewards
    
    # Status
    status = Column(String(50), nullable=False, default="available")  # available, redeemed, expired
    code = Column(String(50), unique=True, nullable=True)  # Redemption code
    
    # Validity
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    
    # Usage Restrictions
    min_order_amount = Column(Float, nullable=True)
    applicable_categories = Column(JSONB, nullable=True)
    applicable_items = Column(JSONB, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="rewards")
    
    # Indexes
    __table_args__ = (
        Index('ix_customer_rewards_status', 'customer_id', 'status'),
        Index('ix_customer_rewards_validity', 'valid_from', 'valid_until'),
    )
    
    def __repr__(self):
        return f"<CustomerReward(id={self.id}, type='{self.type}', status='{self.status}')>"


class CustomerPreference(Base, TimestampMixin):
    """Detailed customer preferences"""
    __tablename__ = "customer_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Preference Details
    category = Column(String(50), nullable=False)  # dietary, communication, ordering, etc.
    preference_key = Column(String(100), nullable=False)
    preference_value = Column(JSONB, nullable=True)
    
    # Metadata
    source = Column(String(50), nullable=True)  # app, web, staff, inferred
    confidence_score = Column(Float, nullable=True)  # For inferred preferences
    
    # Relationships
    customer = relationship("Customer", back_populates="preferences")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('customer_id', 'category', 'preference_key'),
        Index('ix_customer_preferences_category', 'category', 'preference_key'),
    )
    
    def __repr__(self):
        return f"<CustomerPreference(id={self.id}, category='{self.category}', key='{self.preference_key}')>"


# Update Order model to include customer relationship
def update_order_model():
    """
    This function should be called to add customer_id to the Order model.
    In a real implementation, this would be done through a migration.
    """
    # This is a placeholder - the actual implementation would modify the Order model
    # to add: customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    # and: customer = relationship("Customer", back_populates="orders")
    pass