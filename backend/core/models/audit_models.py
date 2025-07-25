from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from sqlalchemy.sql import func
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now()
    )

    __table_args__ = (
        Index('ix_audit_logs_module_entity', 'module', 'entity_id'),
        Index('ix_audit_logs_entity_timestamp', 'entity_id', 'timestamp'),
    )

    def __repr__(self):
        return (f"<AuditLog(id={self.id}, action={self.action}, "
                f"entity_id={self.entity_id})>")
