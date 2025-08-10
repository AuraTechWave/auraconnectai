# backend/modules/kds/models/kds_models.py

"""
Kitchen Display System models for managing kitchen stations and order routing.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, 
    Enum, Text, JSON, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum
from datetime import datetime


class StationType(enum.Enum):
    """Types of kitchen stations"""
    GRILL = "grill"
    FRY = "fry"
    SAUTE = "saute"
    SALAD = "salad"
    DESSERT = "dessert"
    BEVERAGE = "beverage"
    EXPO = "expo"  # Expeditor station
    PREP = "prep"
    PIZZA = "pizza"
    SANDWICH = "sandwich"
    SUSHI = "sushi"
    BAR = "bar"


class StationStatus(enum.Enum):
    """Kitchen station status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class DisplayStatus(enum.Enum):
    """Order item display status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    RECALLED = "recalled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class KitchenStation(Base):
    """Kitchen station configuration"""
    __tablename__ = "kitchen_stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    station_type = Column(Enum(StationType, values_callable=lambda obj: [e.value for e in obj], create_type=False), nullable=False, index=True)
    status = Column(Enum(StationStatus, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=StationStatus.ACTIVE, index=True)
    
    # Station configuration
    display_name = Column(String(100))
    color_code = Column(String(7))  # Hex color for UI
    priority = Column(Integer, default=0)  # Higher priority stations get items first
    max_active_items = Column(Integer, default=10)  # Max items shown at once
    
    # Timing configuration
    prep_time_multiplier = Column(Float, default=1.0)  # Adjust prep times for this station
    warning_time_minutes = Column(Integer, default=5)  # When to show warning
    critical_time_minutes = Column(Integer, default=10)  # When to show critical
    
    # Staff assignment
    current_staff_id = Column(Integer, ForeignKey("staff_members.id"))
    staff_assigned_at = Column(DateTime(timezone=True))
    
    # Station features
    features = Column(JSON, default=list)  # ["printer", "buzzer", "dual_screen"]
    printer_id = Column(String(100))  # Printer identifier if available
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    displays = relationship("KitchenDisplay", back_populates="station")
    assignments = relationship("StationAssignment", back_populates="station")
    menu_items = relationship("MenuItemStation", back_populates="station")
    current_staff = relationship("StaffMember", foreign_keys=[current_staff_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_station_type_status', 'station_type', 'status'),
    )


class KitchenDisplay(Base):
    """Individual display screens for kitchen stations"""
    __tablename__ = "kitchen_displays"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id"), nullable=False)
    display_number = Column(Integer, default=1)  # For multi-display stations
    
    # Display configuration
    name = Column(String(100))
    ip_address = Column(String(45))  # For network displays
    last_heartbeat = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Display settings
    layout_mode = Column(String(20), default="grid")  # grid, list, single
    items_per_page = Column(Integer, default=6)
    auto_clear_completed = Column(Boolean, default=True)
    auto_clear_delay_seconds = Column(Integer, default=30)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    station = relationship("KitchenStation", back_populates="displays")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('station_id', 'display_number', name='uq_station_display_number'),
    )


class StationAssignment(Base):
    """Menu category to station assignments for routing"""
    __tablename__ = "station_assignments"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id"), nullable=False)
    
    # Assignment can be by category or specific tags
    category_name = Column(String(100))  # e.g., "Appetizers", "Entrees"
    tag_name = Column(String(100))  # e.g., "grilled", "fried", "cold"
    
    # Routing rules
    priority = Column(Integer, default=0)  # Higher priority assignments checked first
    is_primary = Column(Boolean, default=True)  # Primary vs secondary station
    prep_time_override = Column(Integer)  # Override default prep time in minutes
    
    # Conditions
    conditions = Column(JSON, default=dict)  # {"day_of_week": ["friday", "saturday"]}
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    station = relationship("KitchenStation", back_populates="assignments")
    
    # Indexes
    __table_args__ = (
        Index('idx_assignment_category', 'category_name'),
        Index('idx_assignment_tag', 'tag_name'),
    )


class MenuItemStation(Base):
    """Direct menu item to station mapping"""
    __tablename__ = "menu_item_stations"

    id = Column(Integer, primary_key=True, index=True)
    menu_item_id = Column(Integer, nullable=False, index=True)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id"), nullable=False)
    
    # Routing configuration
    is_primary = Column(Boolean, default=True)
    sequence = Column(Integer, default=0)  # For items that go to multiple stations
    prep_time_minutes = Column(Integer, nullable=False)
    
    # Special instructions
    station_notes = Column(Text)  # Instructions specific to this station
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    station = relationship("KitchenStation", back_populates="menu_items")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('menu_item_id', 'station_id', 'sequence', name='uq_menu_item_station_seq'),
    )


class KDSOrderItem(Base):
    """Order items displayed on kitchen screens"""
    __tablename__ = "kds_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id"), nullable=False)
    
    # Display information
    display_name = Column(String(200), nullable=False)  # What shows on screen
    quantity = Column(Integer, nullable=False)
    modifiers = Column(JSON, default=list)  # List of modifications
    special_instructions = Column(Text)
    
    # Status tracking
    status = Column(Enum(DisplayStatus, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=DisplayStatus.PENDING, index=True)
    sequence_number = Column(Integer)  # For multi-station items
    
    # Timing
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    target_time = Column(DateTime(timezone=True))  # When it should be ready
    completed_at = Column(DateTime(timezone=True))
    acknowledged_at = Column(DateTime(timezone=True))
    
    # Priority and sorting
    priority = Column(Integer, default=0)  # Higher = more urgent
    course_number = Column(Integer, default=1)  # For course timing
    fire_time = Column(DateTime(timezone=True))  # When to start cooking
    
    # Staff tracking
    started_by_id = Column(Integer, ForeignKey("staff_members.id"))
    completed_by_id = Column(Integer, ForeignKey("staff_members.id"))
    
    # Recall tracking
    recall_count = Column(Integer, default=0)
    last_recalled_at = Column(DateTime(timezone=True))
    recall_reason = Column(String(200))
    
    # Relationships
    order_item = relationship("OrderItem")
    station = relationship("KitchenStation")
    started_by = relationship("StaffMember", foreign_keys=[started_by_id])
    completed_by = relationship("StaffMember", foreign_keys=[completed_by_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_kds_order_item_status', 'station_id', 'status'),
        Index('idx_kds_order_item_received', 'station_id', 'received_at'),
        Index('idx_kds_order_item_priority', 'station_id', 'priority', 'received_at'),
    )

    @property
    def wait_time_seconds(self):
        """Calculate wait time in seconds"""
        if self.received_at:
            end_time = self.completed_at or datetime.utcnow()
            return int((end_time - self.received_at).total_seconds())
        return 0

    @property
    def is_late(self):
        """Check if item is past target time"""
        if self.target_time and self.status not in [DisplayStatus.COMPLETED, DisplayStatus.CANCELLED]:
            return datetime.utcnow() > self.target_time
        return False


class StationRoutingRule(Base):
    """Configurable routing rules for directing orders to kitchen stations"""
    __tablename__ = "station_routing_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, nullable=False, index=True)
    
    # Rule conditions (any can be used)
    menu_item_id = Column(Integer, nullable=True, index=True)
    category_id = Column(Integer, nullable=True, index=True)
    tag_name = Column(String(100), nullable=True, index=True)
    
    # Target station
    target_station_id = Column(Integer, ForeignKey("kitchen_stations.id"), nullable=False)
    
    # Rule metadata
    priority = Column(Integer, default=0)  # Higher priority rules are evaluated first
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    station = relationship("KitchenStation", backref="routing_rules")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_routing_rule_restaurant', 'restaurant_id', 'is_active'),
        Index('idx_routing_rule_priority', 'restaurant_id', 'priority', 'is_active'),
    )