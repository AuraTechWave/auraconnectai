from sqlalchemy import Column, Integer, String, Numeric
from core.database import Base
from core.mixins import TimestampMixin


class TaxRule(Base, TimestampMixin):
    __tablename__ = "tax_rules"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    rate_percent = Column(Numeric(5, 4), nullable=False)
