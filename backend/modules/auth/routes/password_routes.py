"""
Password Security Routes

This module provides secure password management endpoints including:
- Password reset workflow
- Password change functionality
- Password strength validation
- Security audit logging
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field
import logging

from core.database import get_db
from core.auth import get_current_user
from core.rbac_service import get_rbac_service, RBACService
from core.auth import User
from core.password_security import (
    password_security, 
    PasswordValidationResult, 
    PasswordStrength,
    validate_email_address
)
from core.password_models import PasswordResetToken, PasswordHistory, SecurityAuditLog
from core.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/password", tags=["Password Security"])
security = HTTPBearer(auto_error=False)


# Request/Response Models

class PasswordResetRequestModel(BaseModel):
    """Request model for password reset."""
    email: str = Field(..., description="User's email address")
    
    @validator('email')
    def validate_email(cls, v):
        if not validate_email_address(v):
            raise ValueError('Invalid email address format')
        return v.lower().strip()


class PasswordResetConfirmModel(BaseModel):
    """Request model for password reset confirmation."""
    token: str = Field(..., min_length=32, description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordChangeModel(BaseModel):
    """Request model for password change."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordValidationModel(BaseModel):
    """Request model for password validation."""
    password: str = Field(..., description="Password to validate")
    email: Optional[str] = Field(None, description="User's email for personal info check")


class PasswordStrengthResponse(BaseModel):
    """Response model for password strength validation."""
    is_valid: bool
    strength: PasswordStrength
    score: int
    errors: list[str] = []
    suggestions: list[str] = []


class PasswordResetResponse(BaseModel):
    """Response model for password reset request."""
    message: str
    email: str
    rate_limit_remaining: Optional[int] = None


class SecurityEventResponse(BaseModel):
    """Response model for security events."""
    success: bool
    message: str
    event_id: Optional[int] = None


# Helper Functions

def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract client IP and User-Agent from request."""
    ip_address = None
    user_agent = None
    
    if request:
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else None
        
        user_agent = request.headers.get("user-agent")
    
    return ip_address, user_agent


def log_security_event(
    db: Session,
    event_type: str,
    success: bool,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    event_details: Optional[dict] = None,
    risk_score: int = 0,
    session_id: Optional[str] = None
) -> SecurityAuditLog:
    """Log a security event to the audit log."""
    
    audit_log = SecurityAuditLog(
        user_id=user_id,
        event_type=event_type,
        success=success,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        event_details=json.dumps(event_details) if event_details else None,
        risk_score=risk_score,
        session_id=session_id,
        timestamp=datetime.utcnow()
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    logger.info(f"Security event logged: {event_type}, user_id={user_id}, success={success}")
    return audit_log


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def add_password_to_history(
    db: Session,
    user_id: int,
    password_hash: str,
    algorithm: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Add password to user's password history."""
    
    history_entry = PasswordHistory(
        user_id=user_id,
        password_hash=password_hash,
        algorithm=algorithm,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.utcnow()
    )
    
    db.add(history_entry)
    
    # Clean up old password history (keep only last N passwords)
    old_passwords = db.query(PasswordHistory)\
        .filter(PasswordHistory.user_id == user_id)\
        .order_by(PasswordHistory.created_at.desc())\
        .offset(5)\
        .all()
    
    for old_password in old_passwords:
        db.delete(old_password)
    
    db.commit()


def check_password_reuse(db: Session, user_id: int, new_password: str) -> bool:
    """Check if password was used recently."""
    
    recent_passwords = db.query(PasswordHistory)\
        .filter(PasswordHistory.user_id == user_id)\
        .order_by(PasswordHistory.created_at.desc())\
        .limit(5)\
        .all()
    
    for history_entry in recent_passwords:
        if password_security.verify_password(new_password, history_entry.password_hash):
            return True
    
    return False


# API Endpoints

@router.post("/validate", response_model=PasswordStrengthResponse)
async def validate_password_strength(
    request: PasswordValidationModel,
    db: Session = Depends(get_db)
) -> PasswordStrengthResponse:
    """
    Validate password strength and policy compliance.
    
    This endpoint provides real-time password validation without storing
    or logging the password.
    """
    
    validation_result = password_security.validate_password(
        request.password, 
        request.email
    )
    
    return PasswordStrengthResponse(
        is_valid=validation_result.is_valid,
        strength=validation_result.strength,
        score=validation_result.score,
        errors=validation_result.errors,
        suggestions=validation_result.suggestions
    )


@router.post("/reset/request", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequestModel,
    http_request: Request,
    db: Session = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> PasswordResetResponse:
    """
    Request a password reset token.
    
    This endpoint will always return success to prevent email enumeration,
    but will only send reset emails to valid registered email addresses.
    """
    
    ip_address, user_agent = get_client_info(http_request)
    
    # Look up user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    if user:
        # Generate reset token
        reset_token = password_security.generate_reset_token(user.id, request.email)
        
        if reset_token:
            # Store token in database
            token_hash = hash_token(reset_token)
            
            db_token = PasswordResetToken(
                token_hash=token_hash,
                user_id=user.id,
                email=request.email,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=30),
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            db.add(db_token)
            db.commit()
            
            # Log security event
            log_security_event(
                db=db,
                event_type="password_reset_requested",
                success=True,
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                event_details={"token_id": db_token.id}
            )
            
            # Send email with reset token
            email_sent = email_service.send_password_reset_email(
                email=request.email,
                reset_token=reset_token,
                expires_in_minutes=30
            )
            
            if email_sent:
                logger.info(f"Password reset email sent to {request.email}")
            else:
                logger.error(f"Failed to send password reset email to {request.email}")
                
            # For security, we don't reveal email sending failures to the user
            logger.info(f"Password reset token generated for user {user.id}")
            
        else:
            # Rate limited
            log_security_event(
                db=db,
                event_type="password_reset_rate_limited",
                success=False,
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                risk_score=30
            )
    else:
        # Log failed attempt (no valid user)
        log_security_event(
            db=db,
            event_type="password_reset_invalid_email",
            success=False,
            email=request.email,
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=20
        )
    
    # Always return success to prevent email enumeration
    return PasswordResetResponse(
        message="If the email address is registered, you will receive a password reset link.",
        email=request.email
    )


@router.post("/reset/confirm", response_model=SecurityEventResponse)
async def confirm_password_reset(
    request: PasswordResetConfirmModel,
    http_request: Request,
    db: Session = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> SecurityEventResponse:
    """
    Confirm password reset with token and set new password.
    """
    
    ip_address, user_agent = get_client_info(http_request)
    token_hash = hash_token(request.token)
    
    # Find and validate reset token
    db_token = db.query(PasswordResetToken)\
        .filter(PasswordResetToken.token_hash == token_hash)\
        .filter(PasswordResetToken.is_used == False)\
        .filter(PasswordResetToken.expires_at > datetime.utcnow())\
        .first()
    
    if not db_token:
        # Log failed attempt
        log_security_event(
            db=db,
            event_type="password_reset_invalid_token",
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            event_details={"token_prefix": request.token[:8]},
            risk_score=50
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate new password
    validation_result = password_security.validate_password(request.new_password, user.email)
    if not validation_result.is_valid:
        log_security_event(
            db=db,
            event_type="password_reset_weak_password",
            success=False,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_details={"validation_errors": validation_result.errors},
            risk_score=20
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password does not meet security requirements: {', '.join(validation_result.errors)}"
        )
    
    # Check password reuse
    if check_password_reuse(db, user.id, request.new_password):
        log_security_event(
            db=db,
            event_type="password_reset_reused_password",
            success=False,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=30
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reuse a recent password. Please choose a different password."
        )
    
    # Hash new password
    new_password_hash = password_security.hash_password(request.new_password)
    algorithm_info = password_security.get_algorithm_info(new_password_hash)
    
    # Add current password to history before changing
    if user.hashed_password:
        current_algorithm_info = password_security.get_algorithm_info(user.hashed_password)
        add_password_to_history(
            db=db,
            user_id=user.id,
            password_hash=user.hashed_password,
            algorithm=current_algorithm_info.get("algorithm", "unknown"),
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    # Update user password
    user.hashed_password = new_password_hash
    user.password_changed_at = datetime.utcnow()
    user.last_password_reset = datetime.utcnow()
    user.password_reset_required = False
    user.failed_login_attempts = 0
    user.locked_until = None
    
    # Mark token as used
    db_token.is_used = True
    db_token.used_at = datetime.utcnow()
    db_token.attempt_count += 1
    
    # Clean up other reset tokens for this user
    other_tokens = db.query(PasswordResetToken)\
        .filter(PasswordResetToken.user_id == user.id)\
        .filter(PasswordResetToken.id != db_token.id)\
        .filter(PasswordResetToken.is_used == False)\
        .all()
    
    for token in other_tokens:
        token.is_used = True
    
    db.commit()
    
    # Log successful password reset
    audit_log = log_security_event(
        db=db,
        event_type="password_reset_completed",
        success=True,
        user_id=user.id,
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        event_details={
            "token_id": db_token.id,
            "algorithm": algorithm_info.get("algorithm", "unknown"),
            "password_strength": validation_result.strength.value,
            "password_score": validation_result.score
        }
    )
    
    # Send password changed notification
    email_service.send_password_changed_notification(
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    logger.info(f"Password successfully reset for user {user.id}")
    
    return SecurityEventResponse(
        success=True,
        message="Password has been successfully reset. You can now log in with your new password.",
        event_id=audit_log.id
    )


@router.post("/change", response_model=SecurityEventResponse)
async def change_password(
    request: PasswordChangeModel,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> SecurityEventResponse:
    """
    Change password for authenticated user.
    """
    
    ip_address, user_agent = get_client_info(http_request)
    
    # Verify current password
    if not password_security.verify_password(request.current_password, current_user.hashed_password):
        log_security_event(
            db=db,
            event_type="password_change_wrong_current",
            success=False,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=40
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    validation_result = password_security.validate_password(request.new_password, current_user.email)
    if not validation_result.is_valid:
        log_security_event(
            db=db,
            event_type="password_change_weak_password",
            success=False,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_details={"validation_errors": validation_result.errors},
            risk_score=20
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password does not meet security requirements: {', '.join(validation_result.errors)}"
        )
    
    # Check if new password is same as current
    if password_security.verify_password(request.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Check password reuse
    if check_password_reuse(db, current_user.id, request.new_password):
        log_security_event(
            db=db,
            event_type="password_change_reused_password",
            success=False,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            risk_score=30
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reuse a recent password. Please choose a different password."
        )
    
    # Hash new password
    new_password_hash = password_security.hash_password(request.new_password)
    algorithm_info = password_security.get_algorithm_info(new_password_hash)
    
    # Add current password to history
    current_algorithm_info = password_security.get_algorithm_info(current_user.hashed_password)
    add_password_to_history(
        db=db,
        user_id=current_user.id,
        password_hash=current_user.hashed_password,
        algorithm=current_algorithm_info.get("algorithm", "unknown"),
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Update user password
    user = db.query(User).filter(User.id == current_user.id).first()
    user.hashed_password = new_password_hash
    user.password_changed_at = datetime.utcnow()
    user.password_reset_required = False
    
    db.commit()
    
    # Log successful password change
    audit_log = log_security_event(
        db=db,
        event_type="password_changed",
        success=True,
        user_id=current_user.id,
        email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        event_details={
            "algorithm": algorithm_info.get("algorithm", "unknown"),
            "password_strength": validation_result.strength.value,
            "password_score": validation_result.score
        }
    )
    
    # Send password changed notification
    email_service.send_password_changed_notification(
        email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    logger.info(f"Password successfully changed for user {current_user.id}")
    
    return SecurityEventResponse(
        success=True,
        message="Password has been successfully changed.",
        event_id=audit_log.id
    )


@router.get("/history")
async def get_password_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get password change history for the current user.
    """
    
    history = db.query(PasswordHistory)\
        .filter(PasswordHistory.user_id == current_user.id)\
        .order_by(PasswordHistory.created_at.desc())\
        .limit(10)\
        .all()
    
    return {
        "user_id": current_user.id,
        "password_changed_at": current_user.password_changed_at,
        "last_password_reset": current_user.last_password_reset,
        "history": [
            {
                "id": entry.id,
                "created_at": entry.created_at,
                "algorithm": entry.algorithm,
                "ip_address": entry.ip_address
            }
            for entry in history
        ]
    }


@router.post("/generate")
async def generate_secure_password(
    length: int = 16,
    current_user: User = Depends(get_current_user)
):
    """
    Generate a cryptographically secure password.
    """
    
    if length < 8 or length > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password length must be between 8 and 128 characters"
        )
    
    generated_password = password_security.generate_secure_password(length)
    validation_result = password_security.validate_password(generated_password, current_user.email)
    
    return {
        "password": generated_password,
        "strength": validation_result.strength,
        "score": validation_result.score,
        "length": len(generated_password)
    }