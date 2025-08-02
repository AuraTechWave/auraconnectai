from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Enum, Float
from sqlalchemy.orm import relationship
from core.database import Base
from ..enums.attendance_enums import CheckInMethod, AttendanceStatus


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    method = Column(Enum(CheckInMethod))
    status = Column(Enum(AttendanceStatus))
    location_lat = Column(Float)
    location_lng = Column(Float)
    device_id = Column(String)
    
    staff_member = relationship("StaffMember", back_populates="attendance_logs")
