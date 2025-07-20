from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text)
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"),
                      nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    order_items = relationship("OrderItem", back_populates="order")


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
