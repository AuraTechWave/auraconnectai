from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from backend.core.database import Base

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    method = Column(String)  # manual, QR, faceID
    status = Column(String)
