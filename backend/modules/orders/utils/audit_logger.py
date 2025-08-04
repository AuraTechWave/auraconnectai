# backend/modules/orders/utils/audit_logger.py

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
from sqlalchemy.orm import Session

from core.models import User


class AuditLogger:
    """
    Specialized logger for auditing sensitive operations
    
    Provides structured logging for compliance and security auditing
    """
    
    def __init__(self, name: str = "audit"):
        self.logger = logging.getLogger(f"{name}.audit")
        self.logger.setLevel(logging.INFO)
        
        # Ensure audit logs are always written
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - AUDIT - %(levelname)s - %(message)s - %(audit_data)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _format_audit_data(self, **kwargs) -> Dict:
        """Format audit data for structured logging"""
        return {
            'audit_data': json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': 'audit',
                **kwargs
            }, default=str)
        }
    
    def log_action(
        self,
        action: str,
        user_id: int,
        resource_type: str,
        resource_id: Any,
        details: Optional[Dict] = None,
        result: str = "success",
        ip_address: Optional[str] = None
    ):
        """
        Log a user action for audit purposes
        
        Args:
            action: The action performed (e.g., "resolve_review", "escalate_review")
            user_id: ID of the user performing the action
            resource_type: Type of resource (e.g., "manual_review", "order")
            resource_id: ID of the resource
            details: Additional action details
            result: Result of the action (success, failure, partial)
            ip_address: IP address of the user (if available)
        """
        self.logger.info(
            f"AUDIT: User {user_id} performed {action} on {resource_type} {resource_id}",
            extra=self._format_audit_data(
                action=action,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                result=result,
                ip_address=ip_address
            )
        )
    
    def log_data_access(
        self,
        user_id: int,
        resource_type: str,
        resource_ids: list,
        operation: str,
        query_params: Optional[Dict] = None,
        result_count: Optional[int] = None
    ):
        """
        Log data access for compliance
        
        Args:
            user_id: ID of the user accessing data
            resource_type: Type of resource accessed
            resource_ids: IDs of resources accessed (empty list for queries)
            operation: Operation performed (read, list, search)
            query_params: Query parameters used
            result_count: Number of results returned
        """
        self.logger.info(
            f"DATA ACCESS: User {user_id} performed {operation} on {resource_type}",
            extra=self._format_audit_data(
                event_subtype="data_access",
                user_id=user_id,
                resource_type=resource_type,
                resource_ids=resource_ids[:10] if resource_ids else [],  # Limit logged IDs
                resource_count=len(resource_ids) if resource_ids else result_count,
                operation=operation,
                query_params=query_params or {}
            )
        )
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int],
        details: Dict,
        severity: str = "medium",
        ip_address: Optional[str] = None
    ):
        """
        Log security-related events
        
        Args:
            event_type: Type of security event
            user_id: User involved (if applicable)
            details: Event details
            severity: Event severity (low, medium, high, critical)
            ip_address: Source IP address
        """
        log_level = {
            "low": logging.INFO,
            "medium": logging.WARNING,
            "high": logging.ERROR,
            "critical": logging.CRITICAL
        }.get(severity, logging.WARNING)
        
        self.logger.log(
            log_level,
            f"SECURITY EVENT: {event_type}",
            extra=self._format_audit_data(
                event_subtype="security",
                event_type=event_type,
                user_id=user_id,
                severity=severity,
                details=details,
                ip_address=ip_address
            )
        )
    
    def log_configuration_change(
        self,
        user_id: int,
        config_type: str,
        old_value: Any,
        new_value: Any,
        reason: Optional[str] = None
    ):
        """
        Log configuration changes
        
        Args:
            user_id: User making the change
            config_type: Type of configuration changed
            old_value: Previous value
            new_value: New value
            reason: Reason for change
        """
        self.logger.warning(
            f"CONFIG CHANGE: User {user_id} changed {config_type}",
            extra=self._format_audit_data(
                event_subtype="configuration_change",
                user_id=user_id,
                config_type=config_type,
                old_value=str(old_value)[:100],  # Limit logged value size
                new_value=str(new_value)[:100],
                reason=reason
            )
        )


def audit_action(
    action: str,
    resource_type: str,
    include_result: bool = True,
    include_ip: bool = True
):
    """
    Decorator for auditing function calls
    
    Args:
        action: The action being performed
        resource_type: Type of resource being acted upon
        include_result: Whether to log the function result
        include_ip: Whether to attempt to log IP address
    
    Example:
        @audit_action("resolve_review", "manual_review")
        async def resolve_review(self, review_id: int, user_id: int, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            audit_logger = AuditLogger()
            
            # Extract common parameters
            user_id = kwargs.get('user_id') or kwargs.get('current_user', {}).get('id')
            resource_id = kwargs.get('review_id') or kwargs.get('order_id') or kwargs.get('id')
            
            # Extract IP if available (from request context)
            ip_address = None
            if include_ip:
                # This would need to be extracted from the request context
                # For now, we'll leave it as None
                pass
            
            # Prepare audit details
            audit_details = {
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            }
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Log successful action
                audit_logger.log_action(
                    action=action,
                    user_id=user_id or 0,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=audit_details,
                    result="success",
                    ip_address=ip_address
                )
                
                return result
                
            except Exception as e:
                # Log failed action
                audit_details['error'] = str(e)
                audit_details['error_type'] = e.__class__.__name__
                
                audit_logger.log_action(
                    action=action,
                    user_id=user_id or 0,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=audit_details,
                    result="failure",
                    ip_address=ip_address
                )
                
                # Re-raise the exception
                raise
        
        return wrapper
    return decorator


class AuditContext:
    """
    Context manager for audit logging within a scope
    
    Example:
        async with AuditContext(user_id=123, ip_address="192.168.1.1") as audit:
            # All audit logs within this context will include user_id and ip_address
            audit.log_action("view_sensitive_data", "order", 456)
    """
    
    def __init__(self, user_id: int, ip_address: Optional[str] = None, session: Optional[Session] = None):
        self.user_id = user_id
        self.ip_address = ip_address
        self.session = session
        self.audit_logger = AuditLogger()
        self._start_time = None
    
    async def __aenter__(self):
        self._start_time = datetime.utcnow()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
        
        if exc_val:
            self.audit_logger.log_action(
                action="context_error",
                user_id=self.user_id,
                resource_type="audit_context",
                resource_id="N/A",
                details={
                    "duration_ms": duration_ms,
                    "error": str(exc_val),
                    "error_type": exc_type.__name__ if exc_type else None
                },
                result="failure",
                ip_address=self.ip_address
            )
    
    def log_action(self, action: str, resource_type: str, resource_id: Any, details: Optional[Dict] = None):
        """Log an action within this audit context"""
        self.audit_logger.log_action(
            action=action,
            user_id=self.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=self.ip_address
        )
    
    def log_bulk_action(self, action: str, resource_type: str, resource_ids: list, details: Optional[Dict] = None):
        """Log a bulk action affecting multiple resources"""
        self.audit_logger.log_action(
            action=f"bulk_{action}",
            user_id=self.user_id,
            resource_type=resource_type,
            resource_id=f"bulk_{len(resource_ids)}",
            details={
                "resource_ids": resource_ids[:10],  # Log first 10 IDs
                "total_count": len(resource_ids),
                **(details or {})
            },
            ip_address=self.ip_address
        )