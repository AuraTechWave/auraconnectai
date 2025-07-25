from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text, Table, Boolean)
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


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
    table_no = Column(Integer, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"),
                         nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True)

    order_items = relationship("OrderItem", back_populates="order")
    tags = relationship("Tag", secondary=order_tags, back_populates="orders")
    category = relationship("Category", back_populates="orders")
    print_tickets = relationship("PrintTicket", back_populates="order")


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"),
                      nullable=False, index=True)
    menu_item_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text, nullable=True)

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
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    ticket_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    station_id = Column(Integer, ForeignKey("print_stations.id"), nullable=True, index=True)
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
