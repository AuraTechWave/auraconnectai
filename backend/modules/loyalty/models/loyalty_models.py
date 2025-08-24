# backend/modules/loyalty/models/loyalty_models.py

"""
Loyalty program models
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Numeric,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin


class LoyaltyProgram(Base, TimestampMixin):
    """Loyalty program configuration"""
    __tablename__ = "loyalty_programs"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    points_per_dollar = Column(Numeric(10, 2), default=1.0)
    is_active = Column(Boolean, default=True)
    rules = Column(JSON, default={})
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="loyalty_programs")
    
    def __repr__(self):
        return f"<LoyaltyProgram(id={self.id}, name='{self.name}')>"