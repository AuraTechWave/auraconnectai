from sqlalchemy import Column, Integer, DateTime, ForeignKey
from core.database import Base


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    date = Column(DateTime, nullable=False)
    location_id = Column(Integer)
