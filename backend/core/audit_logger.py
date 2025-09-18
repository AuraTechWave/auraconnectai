"""
Audit logging system for security-sensitive operations.

This module provides comprehensive audit logging for compliance and security monitoring.
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
import aiofiles

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .database import Base
from .security_config import IS_PRODUCTION, sanitize_log_data

logger = logging.getLogger(__name__)

# Audit log directory
AUDIT_LOG_DIR = Path("/var/log/auraconnect/audit") if IS_PRODUCTION else Path("./logs/audit")
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)


class AuditLog(Base):
    """Database model for audit logs."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    operation_type = Column(String(50), index=True)
    user_id = Column(Integer, nullable=True, index=True)
    client_ip = Column(String(45))  # Support IPv6
    request_id = Column(String(100), unique=True, index=True)
    status = Column(String(20))  # started, completed, failed
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    request_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    audit_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index("idx_audit_user_operation", "user_id", "operation_type"),
        Index("idx_audit_timestamp_operation", "timestamp", "operation_type"),
    )


class AuditLogger:
    """
    Audit logger for security-sensitive operations.
    
    Logs to both database and files for redundancy and compliance.
    """
    
    def __init__(self):
        self.file_logger = self._setup_file_logger()
        self._db_session = None
        self._write_queue = asyncio.Queue(maxsize=1000)
        self._writer_task = None
    
    def _setup_file_logger(self) -> logging.Logger:
        """Set up file-based audit logger."""
        file_logger = logging.getLogger("audit_file")
        file_logger.setLevel(logging.INFO)
        
        # Create handler with daily rotation
        from logging.handlers import TimedRotatingFileHandler
        handler = TimedRotatingFileHandler(
            filename=AUDIT_LOG_DIR / "audit.log",
            when="midnight",
            interval=1,
            backupCount=365,  # Keep 1 year of logs
            encoding="utf-8"
        )
        
        # Set format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        file_logger.addHandler(handler)
        return file_logger
    
    async def initialize(self, database_url: str):
        """Initialize database connection for audit logs."""
        try:
            # Create async engine
            engine = create_async_engine(
                database_url.replace("postgresql://", "postgresql+asyncpg://"),
                echo=False,
                pool_size=5,
                max_overflow=10
            )
            
            # Create session factory
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            self._db_session = async_session
            
            # Start background writer
            self._writer_task = asyncio.create_task(self._background_writer())
            
        except Exception as e:
            logger.error(f"Failed to initialize audit database: {e}")
            # Continue with file-only logging
    
    async def close(self):
        """Close audit logger and flush pending logs."""
        if self._writer_task:
            # Signal writer to stop
            await self._write_queue.put(None)
            await self._writer_task
    
    async def log_operation_start(
        self,
        operation_type: str,
        user_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        request_id: Optional[str] = None,
        request_data: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ):
        """Log the start of a sensitive operation."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation_type": operation_type,
            "user_id": user_id,
            "client_ip": client_ip,
            "request_id": request_id,
            "status": "started",
            "request_data": request_data,
            "audit_metadata": metadata
        }
        
        # Log to file immediately
        self.file_logger.info(f"AUDIT_START: {json.dumps(log_entry)}")
        
        # Queue for database write
        try:
            self._write_queue.put_nowait(("start", log_entry))
        except asyncio.QueueFull:
            logger.warning("Audit write queue full, dropping database write")
    
    async def log_operation_complete(
        self,
        operation_type: str,
        request_id: str,
        status_code: int,
        duration_ms: int,
        response_data: Optional[Dict] = None
    ):
        """Log the completion of a sensitive operation."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation_type": operation_type,
            "request_id": request_id,
            "status": "completed",
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_data": sanitize_log_data(response_data) if response_data else None
        }
        
        # Log to file immediately
        self.file_logger.info(f"AUDIT_COMPLETE: {json.dumps(log_entry)}")
        
        # Queue for database write
        try:
            self._write_queue.put_nowait(("complete", log_entry))
        except asyncio.QueueFull:
            logger.warning("Audit write queue full, dropping database write")
    
    async def log_operation_failure(
        self,
        operation_type: str,
        request_id: str,
        error: str,
        duration_ms: int
    ):
        """Log the failure of a sensitive operation."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation_type": operation_type,
            "request_id": request_id,
            "status": "failed",
            "error_message": error,
            "duration_ms": duration_ms
        }
        
        # Log to file immediately
        self.file_logger.error(f"AUDIT_FAILURE: {json.dumps(log_entry)}")
        
        # Queue for database write
        try:
            self._write_queue.put_nowait(("failure", log_entry))
        except asyncio.QueueFull:
            logger.warning("Audit write queue full, dropping database write")
    
    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log a security event (failed auth, suspicious activity, etc)."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "description": description,
            "user_id": user_id,
            "client_ip": client_ip,
            "audit_metadata": metadata
        }
        
        # Log to file immediately
        level = logging.ERROR if severity == "high" else logging.WARNING
        self.file_logger.log(level, f"SECURITY_EVENT: {json.dumps(log_entry)}")
        
        # Also log to application logger for monitoring
        logger.warning(f"Security event: {event_type} - {description}")
    
    async def _background_writer(self):
        """Background task to write audit logs to database."""
        while True:
            try:
                # Get item from queue
                item = await self._write_queue.get()
                
                # Check for shutdown signal
                if item is None:
                    break
                
                operation, log_entry = item
                
                # Skip if no database session
                if not self._db_session:
                    continue
                
                # Write to database
                async with self._db_session() as session:
                    if operation == "start":
                        audit_log = AuditLog(
                            timestamp=datetime.fromisoformat(log_entry["timestamp"]),
                            operation_type=log_entry["operation_type"],
                            user_id=log_entry.get("user_id"),
                            client_ip=log_entry.get("client_ip"),
                            request_id=log_entry.get("request_id"),
                            status="started",
                            request_data=log_entry.get("request_data"),
                            metadata=log_entry.get("metadata")
                        )
                        session.add(audit_log)
                    
                    elif operation in ["complete", "failure"]:
                        # Update existing log entry
                        result = await session.execute(
                            "UPDATE audit_logs SET status = :status, "
                            "status_code = :status_code, duration_ms = :duration_ms, "
                            "response_data = :response_data, error_message = :error_message "
                            "WHERE request_id = :request_id",
                            {
                                "status": log_entry["status"],
                                "status_code": log_entry.get("status_code"),
                                "duration_ms": log_entry.get("duration_ms"),
                                "response_data": log_entry.get("response_data"),
                                "error_message": log_entry.get("error_message"),
                                "request_id": log_entry["request_id"]
                            }
                        )
                        
                        # If no existing entry, create new one
                        if result.rowcount == 0:
                            audit_log = AuditLog(
                                timestamp=datetime.fromisoformat(log_entry["timestamp"]),
                                operation_type=log_entry["operation_type"],
                                request_id=log_entry["request_id"],
                                status=log_entry["status"],
                                status_code=log_entry.get("status_code"),
                                duration_ms=log_entry.get("duration_ms"),
                                response_data=log_entry.get("response_data"),
                                error_message=log_entry.get("error_message")
                            )
                            session.add(audit_log)
                    
                    await session.commit()
                    
            except Exception as e:
                logger.error(f"Failed to write audit log to database: {e}")
                # Continue processing other items


# Global audit logger instance
audit_logger = AuditLogger()