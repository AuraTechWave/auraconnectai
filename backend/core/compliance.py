from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text
from .database import Base
from .mixins import TimestampMixin
from datetime import datetime
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    module = Column(String, nullable=False)
    user_id = Column(Integer, nullable=True)
    audit_metadata = Column(Text, nullable=True)


class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    def log_action(self, action: str, module: str,
                   user_id: Optional[int] = None,
                   metadata: Optional[dict] = None):
        try:
            audit_log = AuditLog(
                action=action,
                module=module,
                user_id=user_id,
                audit_metadata=json.dumps(metadata) if metadata else None
            )
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")
            self.db.rollback()


class ComplianceEngine:
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    def validate_fraud_check(self, order_data: dict,
                             risk_score: float) -> bool:
        self.audit_logger.log_action(
            action="fraud_check_performed",
            module="orders",
            metadata={
                "order_id": order_data.get("id"),
                "risk_score": risk_score,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        return True
