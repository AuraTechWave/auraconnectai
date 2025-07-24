from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class POSSyncLog(Base, TimestampMixin):
    __tablename__ = "pos_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(
        Integer, ForeignKey("pos_integrations.id"), nullable=False, index=True
    )
    type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=True)
    order_id = Column(
        Integer, ForeignKey("orders.id"), nullable=True, index=True
    )
    attempt_count = Column(Integer, nullable=False, default=1)
    synced_at = Column(DateTime, nullable=False)

    integration = relationship("POSIntegration", back_populates="sync_logs")
