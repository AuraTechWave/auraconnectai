from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Numeric, Text)
from sqlalchemy.orm import relationship
from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class PaymentReconciliation(Base, TimestampMixin):
    __tablename__ = "payment_reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"),
                      nullable=False, index=True)
    external_payment_reference = Column(String, nullable=False, index=True)
    amount_expected = Column(Numeric(10, 2), nullable=False)
    amount_received = Column(Numeric(10, 2), nullable=False)
    reconciliation_status = Column(String, nullable=False, index=True)
    discrepancy_type = Column(String, nullable=True, index=True)
    discrepancy_details = Column(Text, nullable=True)
    reconciliation_action = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("staff_members.id"),
                         nullable=True, index=True)

    order = relationship("Order", back_populates="payment_reconciliations")
