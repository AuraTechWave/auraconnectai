"""
Order queue management models for centralized order tracking and sequencing.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, 
    Numeric, Text, Boolean, Enum, JSON, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
import enum


class QueueType(enum.Enum):
    """Types of order queues"""
    KITCHEN = "kitchen"           # Main kitchen queue
    BAR = "bar"                  # Bar orders
    DELIVERY = "delivery"        # Delivery pickup queue
    TAKEOUT = "takeout"          # Takeout pickup queue
    DINE_IN = "dine_in"         # Dine-in service queue
    CATERING = "catering"        # Catering orders
    DRIVE_THRU = "drive_thru"    # Drive-thru orders
    CUSTOM = "custom"            # Custom queue type


class QueueStatus(enum.Enum):
    """Queue operational status"""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


class QueueItemStatus(enum.Enum):
    """Status of items in queue"""
    QUEUED = "queued"            # Waiting to be started
    IN_PREPARATION = "in_preparation"  # Being prepared
    READY = "ready"              # Ready for pickup/service
    ON_HOLD = "on_hold"          # Temporarily held
    COMPLETED = "completed"       # Finished and delivered
    CANCELLED = "cancelled"       # Cancelled
    DELAYED = "delayed"          # Delayed for later


class OrderQueue(Base, TimestampMixin):
    """Central order queue configuration"""
    __tablename__ = "order_queues"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    queue_type = Column(
        Enum(QueueType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    status = Column(
        Enum(QueueStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=QueueStatus.ACTIVE,
        index=True
    )
    
    # Queue configuration
    display_name = Column(String(100))
    description = Column(Text)
    priority = Column(Integer, default=0)  # Default priority for items
    max_capacity = Column(Integer)  # Max items in queue
    auto_sequence = Column(Boolean, default=True)  # Auto-assign sequence numbers
    
    # Time settings
    default_prep_time = Column(Integer, default=15)  # Default prep time in minutes
    warning_threshold = Column(Integer, default=5)  # Minutes before showing warning
    critical_threshold = Column(Integer, default=10)  # Minutes before critical
    
    # Display settings
    color_code = Column(String(7))  # Hex color for UI
    icon = Column(String(50))  # Icon identifier
    display_columns = Column(JSON, default=list)  # Which fields to show
    
    # Operational settings
    operating_hours = Column(JSON)  # Schedule configuration
    station_assignments = Column(JSON, default=list)  # Which stations serve this queue
    routing_rules = Column(JSON)  # Custom routing logic
    
    # Metrics
    current_size = Column(Integer, default=0)
    avg_wait_time = Column(Float)  # Rolling average in minutes
    items_completed_today = Column(Integer, default=0)
    
    # Relationships
    queue_items = relationship("QueueItem", back_populates="queue", cascade="all, delete-orphan")
    queue_metrics = relationship("QueueMetrics", back_populates="queue")
    
    # Indexes
    __table_args__ = (
        Index('idx_queue_type_status', 'queue_type', 'status'),
    )


class QueueItem(Base, TimestampMixin):
    """Individual items in the order queue"""
    __tablename__ = "queue_items"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Queue position
    sequence_number = Column(Integer, nullable=False)  # Position in queue
    priority = Column(Integer, default=0)  # Override queue default
    is_expedited = Column(Boolean, default=False)  # Rush order
    
    # Status tracking
    status = Column(
        Enum(QueueItemStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=QueueItemStatus.QUEUED,
        index=True
    )
    substatus = Column(String(50))  # Additional status detail
    
    # Timing
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    ready_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_ready_time = Column(DateTime(timezone=True))
    
    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("staff_members.id"))
    assigned_at = Column(DateTime(timezone=True))
    station_id = Column(Integer, ForeignKey("kitchen_stations.id"))
    
    # Hold/Delay information
    hold_until = Column(DateTime(timezone=True))
    hold_reason = Column(String(200))
    delay_minutes = Column(Integer)
    
    # Display information
    display_name = Column(String(200))  # What to show on queue display
    display_details = Column(JSON)  # Additional display info
    customer_name = Column(String(100))  # For pickup queues
    
    # Metrics
    prep_time_actual = Column(Integer)  # Actual prep time in minutes
    wait_time_actual = Column(Integer)  # Actual wait time in minutes
    
    # Relationships
    queue = relationship("OrderQueue", back_populates="queue_items")
    order = relationship("Order")
    assigned_to = relationship("StaffMember", foreign_keys=[assigned_to_id])
    station = relationship("KitchenStation")
    status_history = relationship("QueueItemStatusHistory", back_populates="queue_item")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('queue_id', 'sequence_number', name='uq_queue_sequence'),
        Index('idx_queue_item_status', 'queue_id', 'status'),
        Index('idx_queue_item_priority', 'queue_id', 'priority', 'sequence_number'),
        Index('idx_queue_item_order', 'order_id'),
    )


class QueueItemStatusHistory(Base):
    """Track status changes for queue items"""
    __tablename__ = "queue_item_status_history"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_item_id = Column(Integer, ForeignKey("queue_items.id"), nullable=False, index=True)
    
    # Status change
    old_status = Column(
        Enum(QueueItemStatus, values_callable=lambda obj: [e.value for e in obj])
    )
    new_status = Column(
        Enum(QueueItemStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    
    # Change details
    changed_by_id = Column(Integer, ForeignKey("staff_members.id"))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(String(200))
    notes = Column(Text)
    
    # Relationships
    queue_item = relationship("QueueItem", back_populates="status_history")
    changed_by = relationship("StaffMember")


class QueueSequenceRule(Base):
    """Rules for queue sequencing and prioritization"""
    __tablename__ = "queue_sequence_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    
    # Rule configuration
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Rule evaluation order
    
    # Conditions (JSON structure for flexibility)
    conditions = Column(JSON, nullable=False)
    # Example: {
    #   "order_type": ["delivery", "takeout"],
    #   "total_amount_gt": 100,
    #   "vip_customer": true
    # }
    
    # Actions
    priority_adjustment = Column(Integer, default=0)  # Add to item priority
    sequence_adjustment = Column(Integer, default=0)  # Move in queue
    auto_expedite = Column(Boolean, default=False)
    assign_to_station = Column(Integer, ForeignKey("kitchen_stations.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    queue = relationship("OrderQueue")
    station = relationship("KitchenStation")


class QueueMetrics(Base):
    """Queue performance metrics"""
    __tablename__ = "queue_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("order_queues.id"), nullable=False, index=True)
    
    # Time period
    metric_date = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Integer)  # 0-23
    
    # Volume metrics
    items_queued = Column(Integer, default=0)
    items_completed = Column(Integer, default=0)
    items_cancelled = Column(Integer, default=0)
    items_delayed = Column(Integer, default=0)
    
    # Time metrics (in minutes)
    avg_wait_time = Column(Float)
    max_wait_time = Column(Float)
    min_wait_time = Column(Float)
    avg_prep_time = Column(Float)
    
    # Performance metrics
    on_time_percentage = Column(Float)  # % completed within target
    expedited_count = Column(Integer, default=0)
    requeue_count = Column(Integer, default=0)
    
    # Capacity metrics
    max_queue_size = Column(Integer)
    avg_queue_size = Column(Float)
    capacity_exceeded_minutes = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    queue = relationship("OrderQueue", back_populates="queue_metrics")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('queue_id', 'metric_date', 'hour_of_day', name='uq_queue_metrics_period'),
        Index('idx_queue_metrics_date', 'queue_id', 'metric_date'),
    )


class QueueDisplay(Base):
    """Display configuration for queue monitors"""
    __tablename__ = "queue_displays"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    display_type = Column(String(50), nullable=False)  # customer, kitchen, pickup
    
    # Display settings
    queues_shown = Column(JSON, nullable=False)  # List of queue IDs
    layout = Column(String(50), default="grid")  # grid, list, board
    items_per_page = Column(Integer, default=20)
    refresh_interval = Column(Integer, default=30)  # Seconds
    
    # Filtering
    status_filter = Column(JSON, default=list)  # Which statuses to show
    hide_completed_after = Column(Integer, default=300)  # Seconds
    
    # Appearance
    theme = Column(String(50), default="light")
    font_size = Column(String(20), default="medium")
    show_images = Column(Boolean, default=True)
    show_prep_time = Column(Boolean, default=True)
    show_customer_info = Column(Boolean, default=False)
    
    # Audio alerts
    enable_sound = Column(Boolean, default=True)
    alert_new_item = Column(Boolean, default=True)
    alert_ready = Column(Boolean, default=True)
    alert_delayed = Column(Boolean, default=True)
    
    # Access
    location = Column(String(100))  # Physical location
    ip_address = Column(String(45))  # For device identification
    last_active = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())