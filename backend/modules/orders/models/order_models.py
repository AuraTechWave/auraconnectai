from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text, Table, Enum, Boolean, Index)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from ..enums.order_enums import OrderPriority
from typing import Optional
from datetime import datetime


order_tags = Table(
    'order_tags',
    Base.metadata,
    Column('order_id', Integer, ForeignKey('orders.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"),
                      nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"),
                         nullable=True, index=True)
    table_no = Column(Integer, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"),
                         nullable=True, index=True)
    customer_notes = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    scheduled_fulfillment_time = Column(DateTime, nullable=True)
    delay_reason = Column(String, nullable=True)
    delay_requested_at = Column(DateTime, nullable=True)
    priority = Column(
        Enum(OrderPriority),
        nullable=False,
        default=OrderPriority.NORMAL,
        index=True
    )
    priority_updated_at = Column(DateTime(timezone=True), nullable=True)
    external_id = Column(String, nullable=True, index=True)

    fraud_risk_score = Column(Numeric(5, 2), nullable=True, default=0.0)
    fraud_status = Column(String, nullable=False, default="pending")
    fraud_last_check = Column(DateTime, nullable=True)
    fraud_flags = Column(Text, nullable=True)

    order_items = relationship("OrderItem", back_populates="order")
    customer = relationship("Customer", back_populates="orders")
    tags = relationship("Tag", secondary=order_tags, back_populates="orders")
    category = relationship("Category", back_populates="orders")
    payment_reconciliations = relationship(
        "PaymentReconciliation", back_populates="order"
    )
    print_tickets = relationship("PrintTicket", back_populates="order")
    attachments = relationship("OrderAttachment", back_populates="order")

    def update_priority(self, new_priority: OrderPriority,
                        user_id: Optional[int] = None):
        """Update order priority with audit trail."""
        old_priority = self.priority
        self.priority = new_priority
        self.priority_updated_at = datetime.utcnow()

        return {
            "old_priority": old_priority,
            "new_priority": new_priority,
            "updated_at": self.priority_updated_at
        }


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"),
                      nullable=False, index=True)
    menu_item_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    pricing_type = Column(String, nullable=True, default="static")
    pricing_source = Column(String, nullable=True)
    adjustment_reason = Column(String, nullable=True)
    original_price = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    special_instructions = Column(JSONB, nullable=True)

    order = relationship("Order", back_populates="order_items")


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    orders = relationship("Order", secondary=order_tags, back_populates="tags")


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="category")


class PrintTicket(Base, TimestampMixin):
    __tablename__ = "print_tickets"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"),
                      nullable=False, index=True)
    ticket_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    station_id = Column(Integer, ForeignKey("print_stations.id"),
                        nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=1)
    ticket_content = Column(Text, nullable=False)
    printed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    order = relationship("Order", back_populates="print_tickets")
    station = relationship("PrintStation", back_populates="print_tickets")


class PrintStation(Base, TimestampMixin):
    __tablename__ = "print_stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    ticket_types = Column(String, nullable=False)
    printer_config = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    print_tickets = relationship("PrintTicket", back_populates="station")


class OrderAttachment(Base, TimestampMixin):
    __tablename__ = "order_attachments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"),
                      nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="attachments")


class AutoCancellationConfig(Base, TimestampMixin):
    __tablename__ = "auto_cancellation_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    team_id = Column(Integer, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    threshold_minutes = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_by = Column(
        Integer, ForeignKey("staff_members.id"), nullable=False
    )

    updated_by_staff = relationship("StaffMember")

    __table_args__ = (
        Index(
            'idx_auto_cancel_config_unique',
            'tenant_id', 'team_id', 'status',
            unique=True
        ),
    )
