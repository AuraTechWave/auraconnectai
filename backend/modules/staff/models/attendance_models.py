from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Enum, Float
from sqlalchemy.orm import relationship
from core.database import Base
from ..enums.attendance_enums import CheckInMethod, AttendanceStatus


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    __table_args__ = (
        # Add indexes for performance
        {"mysql_engine": "InnoDB"}
    )

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), index=True)
    check_in = Column(DateTime, index=True)
    check_out = Column(DateTime, index=True)
    method = Column(
        Enum(
            CheckInMethod,
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        )
    )
    status = Column(
        Enum(
            AttendanceStatus,
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        )
    )
    location_lat = Column(Float)
    location_lng = Column(Float)
    device_id = Column(String)

    staff_member = relationship("StaffMember", back_populates="attendance_logs")
