from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Time, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum


class ReservationStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    reservation_date = Column(Date, nullable=False)
    reservation_time = Column(Time, nullable=False)
    party_size = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatus, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=ReservationStatus.PENDING)
    table_number = Column(String(20))
    special_requests = Column(Text)
    confirmation_code = Column(String(10), unique=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="reservations")
    
    def __repr__(self):
        return f"<Reservation {self.id} - {self.customer_id} on {self.reservation_date} at {self.reservation_time}>"