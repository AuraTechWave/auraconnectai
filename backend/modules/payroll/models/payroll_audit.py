# backend/modules/payroll/models/payroll_audit.py

"""
Audit trail models for payroll operations.

Provides comprehensive audit logging for compliance,
security, and troubleshooting.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON,
    Index, Enum as SQLEnum
)
from backend.core.database import Base
from backend.core.mixins import TimestampMixin
from ..schemas.audit_schemas import AuditEventType


class PayrollAuditLog(Base, TimestampMixin):
    """
    Audit log for all payroll-related operations.
    
    Tracks who did what, when, and what changed for compliance
    and security purposes.
    """
    __tablename__ = "payroll_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Event information
    event_type = Column(
        SQLEnum(AuditEventType),
        nullable=False,
        index=True
    )
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Entity information
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    
    # User information
    user_id = Column(Integer, nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Action details
    action = Column(Text, nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Additional context
    audit_metadata = Column(JSON, nullable=True)
    session_id = Column(String(100), nullable=True, index=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Multi-tenant support
    tenant_id = Column(Integer, nullable=True, index=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_event_timestamp', 'event_type', 'timestamp'),
        Index('idx_audit_tenant_timestamp', 'tenant_id', 'timestamp'),
        {'comment': 'Comprehensive audit trail for payroll operations'}
    )


class PayrollAuditArchive(Base):
    """
    Archive table for old audit logs.
    
    Stores audit logs older than retention period for
    long-term compliance requirements.
    """
    __tablename__ = "payroll_audit_archive"
    
    id = Column(Integer, primary_key=True)
    original_id = Column(Integer, nullable=False, index=True)
    
    # Archived from PayrollAuditLog
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=False)
    user_email = Column(String(255), nullable=False)
    action = Column(Text, nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    archive_metadata = Column(JSON, nullable=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    
    # Archive metadata
    archived_at = Column(DateTime, nullable=False, index=True)
    archive_reason = Column(String(100), nullable=True)
    
    __table_args__ = (
        Index('idx_archive_timestamp', 'timestamp'),
        Index('idx_archive_tenant', 'tenant_id', 'timestamp'),
        {'comment': 'Long-term archive for audit logs'}
    )