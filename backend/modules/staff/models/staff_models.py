from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base

class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    status = Column(String)
    start_date = Column(DateTime)
    photo_url = Column(String)

    role = relationship("Role", back_populates="staff_members")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    permissions = Column(String)

    staff_members = relationship("StaffMember", back_populates="role")
