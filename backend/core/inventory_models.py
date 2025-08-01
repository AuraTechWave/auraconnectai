# backend/core/inventory_models.py

from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Float, Text, Boolean, JSON, Enum as SQLEnum)
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from enum import Enum
import uuid


class AlertStatus(str, Enum):
    """Alert status enumeration"""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AdjustmentType(str, Enum):
    """Inventory adjustment types"""
    PURCHASE = "purchase"
    SALE = "sale"
    WASTE = "waste"
    TRANSFER = "transfer"
    CORRECTION = "correction"
    EXPIRED = "expired"
    DAMAGED = "damaged"
    RECOUNT = "recount"


class VendorStatus(str, Enum):
    """Vendor status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"


class Vendor(Base, TimestampMixin):
    """Vendor/supplier management"""
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Contact information
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Address
    address_line1 = Column(String(200), nullable=True)
    address_line2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    
    # Business details
    tax_id = Column(String(50), nullable=True)
    payment_terms = Column(String(100), nullable=True)  # e.g., "Net 30", "COD"
    delivery_lead_time = Column(Integer, nullable=True)  # Days
    minimum_order_amount = Column(Float, nullable=True)
    
    # Status and ratings
    status = Column(SQLEnum(VendorStatus), nullable=False, default=VendorStatus.ACTIVE)
    rating = Column(Float, nullable=True)  # 1-5 rating
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    inventory_items = relationship("Inventory", back_populates="vendor")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor(id={self.id}, name='{self.name}', status='{self.status}')>"


class InventoryAlert(Base, TimestampMixin):
    """Low stock and inventory alerts"""
    __tablename__ = "inventory_alerts"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    alert_type = Column(String(50), nullable=False, index=True)  # low_stock, expired, damaged, etc.
    priority = Column(SQLEnum(AlertPriority), nullable=False, default=AlertPriority.MEDIUM)
    status = Column(SQLEnum(AlertStatus), nullable=False, default=AlertStatus.PENDING)
    
    # Alert details
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    threshold_value = Column(Float, nullable=True)  # The threshold that triggered the alert
    current_value = Column(Float, nullable=True)    # Current value when alert was created
    
    # Resolution
    acknowledged_by = Column(Integer, nullable=True)  # User ID
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, nullable=True)      # User ID
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Auto-resolution
    auto_resolve = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    inventory_item = relationship("Inventory", back_populates="alerts")

    def __repr__(self):
        return f"<InventoryAlert(id={self.id}, type='{self.alert_type}', priority='{self.priority}')>"


class InventoryAdjustment(Base, TimestampMixin):
    """Inventory quantity adjustments and audit log"""
    __tablename__ = "inventory_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    adjustment_type = Column(SQLEnum(AdjustmentType), nullable=False, index=True)
    
    # Quantity changes
    quantity_before = Column(Float, nullable=False)
    quantity_adjusted = Column(Float, nullable=False)  # Can be positive or negative
    quantity_after = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    
    # Cost information
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    
    # Reference information
    reference_type = Column(String(50), nullable=True)  # order, waste_report, manual, etc.
    reference_id = Column(String(100), nullable=True)   # External reference ID
    batch_number = Column(String(100), nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    
    # Details
    reason = Column(String(500), nullable=False)
    notes = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    
    # Approval workflow
    requires_approval = Column(Boolean, nullable=False, default=False)
    approved_by = Column(Integer, nullable=True)  # User ID
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=False)  # User who made the adjustment
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    inventory_item = relationship("Inventory", back_populates="adjustments")

    def __repr__(self):
        return f"<InventoryAdjustment(id={self.id}, type='{self.adjustment_type}', quantity={self.quantity_adjusted})>"


class PurchaseOrder(Base, TimestampMixin):
    """Purchase orders for inventory restocking"""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String(50), nullable=False, unique=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    
    # Order details
    status = Column(String(20), nullable=False, default="draft")  # draft, sent, confirmed, partial, received, cancelled
    order_date = Column(DateTime, nullable=False)
    expected_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    
    # Financial information
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    shipping_cost = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    
    # Delivery information
    delivery_address = Column(Text, nullable=True)
    delivery_instructions = Column(Text, nullable=True)
    tracking_number = Column(String(100), nullable=True)
    
    # Notes and metadata
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Status flags
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order")

    def __repr__(self):
        return f"<PurchaseOrder(id={self.id}, po_number='{self.po_number}', status='{self.status}')>"


class PurchaseOrderItem(Base, TimestampMixin):
    """Items in a purchase order"""
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    
    # Order quantities
    quantity_ordered = Column(Float, nullable=False)
    quantity_received = Column(Float, nullable=False, default=0.0)
    unit = Column(String(20), nullable=False)
    
    # Pricing
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    
    # Quality and condition
    quality_rating = Column(Integer, nullable=True)  # 1-5 rating
    condition_notes = Column(Text, nullable=True)
    
    # Batch information
    batch_number = Column(String(100), nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default="pending")  # pending, received, partial, rejected
    notes = Column(Text, nullable=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    inventory_item = relationship("Inventory", back_populates="purchase_order_items")

    def __repr__(self):
        return f"<PurchaseOrderItem(id={self.id}, inventory_id={self.inventory_id}, quantity={self.quantity_ordered})>"


class InventoryUsageLog(Base, TimestampMixin):
    """Track inventory usage from menu item orders"""
    __tablename__ = "inventory_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True)
    
    # Usage details
    quantity_used = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    
    # Order context
    order_id = Column(Integer, nullable=True)  # Reference to order if applicable
    order_item_id = Column(Integer, nullable=True)  # Reference to order item
    order_date = Column(DateTime, nullable=False)
    
    # Cost tracking
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    
    # Location and context
    location = Column(String(100), nullable=True)
    station = Column(String(50), nullable=True)  # Kitchen station
    shift = Column(String(20), nullable=True)    # Morning, afternoon, evening
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    inventory_item = relationship("Inventory", back_populates="usage_logs")

    def __repr__(self):
        return f"<InventoryUsageLog(id={self.id}, inventory_id={self.inventory_id}, quantity={self.quantity_used})>"


class InventoryCount(Base, TimestampMixin):
    """Physical inventory counts and cycle counting"""
    __tablename__ = "inventory_counts"

    id = Column(Integer, primary_key=True, index=True)
    count_number = Column(String(50), nullable=False, unique=True, index=True)
    count_type = Column(String(20), nullable=False)  # full, cycle, spot, emergency
    
    # Count details
    count_date = Column(DateTime, nullable=False)
    location = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="in_progress")  # planned, in_progress, completed, cancelled
    
    # Count summary
    total_items_counted = Column(Integer, nullable=False, default=0)
    total_discrepancies = Column(Integer, nullable=False, default=0)
    total_value_variance = Column(Float, nullable=False, default=0.0)
    
    # Personnel
    counted_by = Column(Integer, nullable=False)  # User ID
    verified_by = Column(Integer, nullable=True)  # User ID
    approved_by = Column(Integer, nullable=True)  # User ID
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    discrepancy_notes = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    count_items = relationship("InventoryCountItem", back_populates="inventory_count")

    def __repr__(self):
        return f"<InventoryCount(id={self.id}, count_number='{self.count_number}', status='{self.status}')>"


class InventoryCountItem(Base, TimestampMixin):
    """Individual items in an inventory count"""
    __tablename__ = "inventory_count_items"

    id = Column(Integer, primary_key=True, index=True)
    inventory_count_id = Column(Integer, ForeignKey("inventory_counts.id"), nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    
    # Count data
    system_quantity = Column(Float, nullable=False)   # Quantity per system
    counted_quantity = Column(Float, nullable=False)  # Actual counted quantity
    variance = Column(Float, nullable=False)          # Difference
    unit = Column(String(20), nullable=False)
    
    # Cost impact
    unit_cost = Column(Float, nullable=True)
    variance_value = Column(Float, nullable=True)
    
    # Count details
    batch_number = Column(String(100), nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    location = Column(String(100), nullable=True)
    condition = Column(String(50), nullable=True)  # good, damaged, expired
    
    # Personnel and verification
    counted_by = Column(Integer, nullable=False)  # User ID
    verified_by = Column(Integer, nullable=True)  # User ID
    count_timestamp = Column(DateTime, nullable=False)
    
    # Resolution
    adjustment_created = Column(Boolean, nullable=False, default=False)
    adjustment_id = Column(Integer, ForeignKey("inventory_adjustments.id"), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    inventory_count = relationship("InventoryCount", back_populates="count_items")
    inventory_item = relationship("Inventory", back_populates="count_items")

    def __repr__(self):
        return f"<InventoryCountItem(id={self.id}, inventory_id={self.inventory_id}, variance={self.variance})>"


# Enhanced Inventory model with additional relationships
class Inventory(Base, TimestampMixin):
    """Enhanced inventory model with comprehensive tracking"""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    sku = Column(String(50), nullable=True, unique=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    
    # Quantity tracking
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(20), nullable=False)
    threshold = Column(Float, nullable=False, default=0.0)
    reorder_quantity = Column(Float, nullable=True)
    max_quantity = Column(Float, nullable=True)  # Maximum storage capacity
    
    # Cost tracking
    cost_per_unit = Column(Float, nullable=True)
    last_purchase_price = Column(Float, nullable=True)
    average_cost = Column(Float, nullable=True)
    
    # Vendor and sourcing
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    vendor_item_code = Column(String(100), nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    
    # Storage and handling
    storage_location = Column(String(100), nullable=True)
    storage_temperature = Column(String(50), nullable=True)  # refrigerated, frozen, room_temp
    shelf_life_days = Column(Integer, nullable=True)
    
    # Tracking and quality
    track_expiration = Column(Boolean, nullable=False, default=False)
    track_batches = Column(Boolean, nullable=False, default=False)
    perishable = Column(Boolean, nullable=False, default=False)
    
    # Alert settings
    enable_low_stock_alerts = Column(Boolean, nullable=False, default=True)
    alert_threshold_percentage = Column(Float, nullable=True)  # Alternative to fixed threshold
    
    # Status and metadata
    is_active = Column(Boolean, nullable=False, default=True)
    last_counted_at = Column(DateTime, nullable=True)
    last_adjusted_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    vendor = relationship("Vendor", back_populates="inventory_items")
    alerts = relationship("InventoryAlert", back_populates="inventory_item")
    adjustments = relationship("InventoryAdjustment", back_populates="inventory_item")
    usage_logs = relationship("InventoryUsageLog", back_populates="inventory_item")
    count_items = relationship("InventoryCountItem", back_populates="inventory_item")
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="inventory_item")
    menu_mappings = relationship("MenuItemInventory", back_populates="inventory_item")

    def __repr__(self):
        return f"<Inventory(id={self.id}, item_name='{self.item_name}', quantity={self.quantity})>"

    @property
    def is_low_stock(self) -> bool:
        """Check if item is below reorder threshold"""
        if self.threshold > 0:
            return self.quantity <= self.threshold
        elif self.alert_threshold_percentage and self.max_quantity:
            threshold = self.max_quantity * (self.alert_threshold_percentage / 100)
            return self.quantity <= threshold
        return False

    @property
    def stock_percentage(self) -> float:
        """Calculate current stock as percentage of maximum"""
        if self.max_quantity and self.max_quantity > 0:
            return (self.quantity / self.max_quantity) * 100
        return 0.0

    @property
    def days_until_empty(self) -> int:
        """Estimate days until stock is empty based on usage"""
        # This would require calculating average daily usage
        # Implementation depends on usage tracking
        return 0