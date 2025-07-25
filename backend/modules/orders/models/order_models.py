from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text, Table)
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
    scheduled_fulfillment_time = Column(DateTime, nullable=True)
    delay_reason = Column(String, nullable=True)
    delay_requested_at = Column(DateTime, nullable=True)

    order_items = relationship("OrderItem", back_populates="order")
    tags = relationship("Tag", secondary=order_tags, back_populates="orders")
    category = relationship("Category", back_populates="orders")
    payment_reconciliations = relationship(
        "PaymentReconciliation", back_populates="order"
    )


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
