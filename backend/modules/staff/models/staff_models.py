from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from core.database import Base
from ..enums.staff_enums import StaffStatus


class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    status = Column(Enum(StaffStatus), default=StaffStatus.ACTIVE, nullable=False)
    start_date = Column(DateTime)
    photo_url = Column(String)

    role = relationship("Role", back_populates="staff_members")
    employee_payments = relationship("EmployeePayment", back_populates="staff_member")


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    permissions = Column(String)

    staff_members = relationship("StaffMember", back_populates="role")
