from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    previous_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
