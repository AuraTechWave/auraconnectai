from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base
from datetime import datetime


class POSSyncSetting(Base):
    __tablename__ = "pos_sync_settings"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True)
    team_id = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(
        Integer, ForeignKey("staff_members.id"), nullable=False
    )

    updated_by_staff = relationship("StaffMember")
