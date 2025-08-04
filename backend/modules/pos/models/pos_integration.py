from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin


class POSIntegration(Base, TimestampMixin):
    __tablename__ = "pos_integrations"

    id = Column(Integer, primary_key=True, index=True)
    vendor = Column(String, nullable=False, index=True)
    credentials = Column(JSONB, nullable=False)
    connected_on = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, index=True)

    sync_logs = relationship("POSSyncLog", back_populates="integration")
