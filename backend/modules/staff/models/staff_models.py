from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from core.database import Base
from ..enums.staff_enums import StaffStatus


class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    status = Column(Enum(StaffStatus, values_callable=lambda obj: [e.value for e in obj], create_type=False), default=StaffStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    photo_url = Column(String)
    notification_preferences = Column(JSON, default={})

    role = relationship("Role", back_populates="staff_members")
    employee_payments = relationship("EmployeePayment", back_populates="staff_member")
    pay_policies = relationship("StaffPayPolicy", back_populates="staff_member")
    attendance_logs = relationship("AttendanceLog", back_populates="staff_member")
    biometric_data = relationship("StaffBiometric", back_populates="staff_member", uselist=False)
    schedules = relationship("Schedule", foreign_keys="Schedule.staff_id", back_populates="staff")


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    permissions = Column(JSON, default=[])
    department_id = Column(Integer)

    staff_members = relationship("StaffMember", back_populates="role")


# For compatibility, create aliases
Staff = StaffMember
StaffRole = Role
