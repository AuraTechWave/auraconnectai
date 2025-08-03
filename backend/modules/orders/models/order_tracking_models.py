# backend/modules/orders/models/order_tracking_models.py

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index, 
    Float, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from enum import Enum
from typing import Optional


class TrackingEventType(str, Enum):
    """Types of order tracking events"""
    ORDER_PLACED = "order_placed"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_IN_KITCHEN = "order_in_kitchen"
    ORDER_BEING_PREPARED = "order_being_prepared"
    ORDER_READY = "order_ready"
    ORDER_SERVED = "order_served"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_DELAYED = "order_delayed"
    ORDER_PICKED_UP = "order_picked_up"
    ORDER_OUT_FOR_DELIVERY = "order_out_for_delivery"
    ORDER_DELIVERED = "order_delivered"
    PAYMENT_RECEIVED = "payment_received"
    CUSTOM_EVENT = "custom_event"


class NotificationChannel(str, Enum):
    """Channels for sending notifications"""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class OrderTrackingEvent(Base, TimestampMixin):
    """Track all order status changes and significant events"""
    __tablename__ = "order_tracking_events"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    event_type = Column(SQLEnum(TrackingEventType), nullable=False, index=True)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    # Location tracking for delivery orders
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)  # meters
    
    # Additional event metadata
    metadata = Column(JSONB, nullable=True, default={})
    
    # Who triggered the event
    triggered_by_type = Column(String, nullable=False, default="system")  # system, staff, customer, api
    triggered_by_id = Column(Integer, nullable=True)
    triggered_by_name = Column(String, nullable=True)
    
    # Estimated times
    estimated_completion_time = Column(DateTime, nullable=True)
    actual_completion_time = Column(DateTime, nullable=True)
    
    # Relations
    order = relationship("Order", back_populates="tracking_events")
    notifications = relationship("OrderNotification", back_populates="tracking_event")
    
    __table_args__ = (
        Index('idx_order_tracking_order_created', 'order_id', 'created_at'),
        Index('idx_order_tracking_event_type', 'event_type', 'created_at'),
    )


class CustomerOrderTracking(Base, TimestampMixin):
    """Customer-specific tracking preferences and access tokens"""
    __tablename__ = "customer_order_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    
    # Tracking access
    tracking_code = Column(String(20), nullable=False, unique=True, index=True)
    tracking_url = Column(String, nullable=True)
    access_token = Column(String, nullable=True, unique=True, index=True)  # For anonymous tracking
    
    # Notification preferences
    enable_push = Column(Boolean, default=True)
    enable_email = Column(Boolean, default=True)
    enable_sms = Column(Boolean, default=False)
    
    # Contact info for notifications (especially for guest orders)
    notification_email = Column(String, nullable=True)
    notification_phone = Column(String, nullable=True)
    push_token = Column(String, nullable=True)
    
    # Tracking activity
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    
    # Real-time connection
    websocket_connected = Column(Boolean, default=False)
    websocket_session_id = Column(String, nullable=True)
    
    # Relations
    order = relationship("Order", back_populates="customer_tracking")
    customer = relationship("Customer", back_populates="order_trackings")


class OrderNotification(Base, TimestampMixin):
    """Track notifications sent for order events"""
    __tablename__ = "order_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    tracking_event_id = Column(Integer, ForeignKey("order_tracking_events.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    
    channel = Column(SQLEnum(NotificationChannel), nullable=False, index=True)
    recipient = Column(String, nullable=False)  # email, phone, push token, etc.
    
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    
    # Delivery status
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # External references
    external_id = Column(String, nullable=True)  # e.g., Firebase message ID, SendGrid ID
    
    # Additional data
    metadata = Column(JSONB, nullable=True, default={})
    
    # Relations
    order = relationship("Order", back_populates="notifications")
    tracking_event = relationship("OrderTrackingEvent", back_populates="notifications")
    customer = relationship("Customer", back_populates="order_notifications")
    
    __table_args__ = (
        Index('idx_order_notifications_order_channel', 'order_id', 'channel'),
        Index('idx_order_notifications_sent_at', 'sent_at'),
    )


class OrderTrackingTemplate(Base, TimestampMixin):
    """Templates for notification messages"""
    __tablename__ = "order_tracking_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(SQLEnum(TrackingEventType), nullable=False, index=True)
    channel = Column(SQLEnum(NotificationChannel), nullable=False, index=True)
    language = Column(String(5), nullable=False, default="en")
    
    subject_template = Column(String, nullable=True)  # For email
    message_template = Column(Text, nullable=False)
    
    # Template variables available: {order_id}, {customer_name}, {estimated_time}, etc.
    available_variables = Column(JSONB, nullable=True)
    
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority templates are used first
    
    __table_args__ = (
        Index('idx_tracking_template_lookup', 'event_type', 'channel', 'language', 'is_active'),
    )


# Add relationships to existing Order model
# This would be added to the Order model in order_models.py:
# tracking_events = relationship("OrderTrackingEvent", back_populates="order", order_by="OrderTrackingEvent.created_at")
# customer_tracking = relationship("CustomerOrderTracking", back_populates="order", uselist=False)
# notifications = relationship("OrderNotification", back_populates="order")