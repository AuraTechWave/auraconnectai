"""
Password Security Database Models

This module contains database models for password security features:
- Password reset tokens
- Password history tracking
- Security audit logs
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from .database import Base

class PasswordResetToken(Base):
    """
    Password reset token model for secure password reset workflow.
    """
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)  # SHA-256 hash of token
    user_id = Column(Integer, ForeignKey("rbac_users.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    
    # Token lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False, nullable=False, index=True)
    
    # Security tracking
    attempt_count = Column(Integer, default=0, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("RBACUser", back_populates="password_reset_tokens")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_password_reset_user_active', 'user_id', 'is_used', 'expires_at'),
        Index('idx_password_reset_email_active', 'email', 'is_used', 'expires_at'),
        Index('idx_password_reset_cleanup', 'expires_at', 'is_used'),
    )
    
    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, is_used={self.is_used})>"


class PasswordHistory(Base):
    """
    Password history model to prevent password reuse.
    """
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("rbac_users.id"), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    algorithm = Column(String(50), nullable=False)  # bcrypt, argon2, etc.
    
    # Security tracking
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("RBACUser", back_populates="password_history")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_password_history_user_created', 'user_id', 'created_at'),
        Index('idx_password_history_cleanup', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PasswordHistory(id={self.id}, user_id={self.user_id}, algorithm={self.algorithm})>"


class SecurityAuditLog(Base):
    """
    Security audit log for password-related events.
    """
    __tablename__ = "security_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("rbac_users.id"), nullable=True, index=True)  # Nullable for failed attempts
    
    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # password_reset_requested, password_changed, etc.
    event_details = Column(Text, nullable=True)  # JSON details
    
    # Request metadata
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    
    # Security flags
    success = Column(Boolean, nullable=False, index=True)
    risk_score = Column(Integer, default=0, nullable=False)  # 0-100 risk assessment
    
    # Additional context
    email = Column(String(255), nullable=True, index=True)  # For failed attempts
    session_id = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("RBACUser", back_populates="security_audit_logs")
    
    # Indexes for performance and security monitoring
    __table_args__ = (
        Index('idx_security_audit_user_event', 'user_id', 'event_type', 'timestamp'),
        Index('idx_security_audit_ip_event', 'ip_address', 'event_type', 'timestamp'),
        Index('idx_security_audit_email_event', 'email', 'event_type', 'timestamp'),
        Index('idx_security_audit_risk', 'risk_score', 'timestamp'),
        Index('idx_security_audit_failed', 'success', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<SecurityAuditLog(id={self.id}, event_type={self.event_type}, success={self.success})>"


# Add relationships to the RBACUser model
# Note: This would typically be done by modifying rbac_models.py, but we'll handle this in the migration