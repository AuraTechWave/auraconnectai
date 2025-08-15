# backend/modules/customers/services/security_service.py

import bcrypt
import secrets
import string
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)


class CustomerSecurityService:
    """Enhanced security service for customer authentication and data protection"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt with salt rounds
        Never store plain text passwords
        """
        if not password:
            raise ValueError("Password cannot be empty")

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)  # Higher rounds for better security
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        if not password or not hashed_password:
            return False

        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength according to security best practices
        Returns validation result with recommendations
        """
        errors = []
        score = 0

        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        elif len(password) >= 12:
            score += 2
        else:
            score += 1

        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        else:
            score += 1

        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        else:
            score += 1

        if not re.search(r"\d", password):
            errors.append("Password must contain at least one number")
        else:
            score += 1

        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\?]', password):
            errors.append("Password must contain at least one special character")
        else:
            score += 2

        # Check for common patterns
        if re.search(r"(.)\1{2,}", password):  # Repeated characters
            errors.append("Password should not contain repeated characters")
            score -= 1

        # Common passwords check (simplified)
        common_passwords = ["password", "123456", "qwerty", "abc123", "password123"]
        if password.lower() in common_passwords:
            errors.append("Password is too common")
            score -= 2

        strength = "weak"
        if score >= 6:
            strength = "strong"
        elif score >= 4:
            strength = "medium"

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "score": max(0, score),
            "strength": strength,
            "recommendations": (
                [
                    "Use at least 12 characters",
                    "Include uppercase and lowercase letters",
                    "Include numbers and special characters",
                    "Avoid common passwords and personal information",
                ]
                if errors
                else []
            ),
        }

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_referral_code(length: int = 8) -> str:
        """Generate unique referral code"""
        # Use uppercase letters and numbers for readability
        alphabet = string.ascii_uppercase + string.digits
        # Exclude confusing characters
        alphabet = (
            alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I")
        )
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
        """Mask sensitive data leaving only last few characters visible"""
        if not data or len(data) <= visible_chars:
            return "*" * len(data) if data else ""

        return "*" * (len(data) - visible_chars) + data[-visible_chars:]

    @staticmethod
    def sanitize_customer_response(customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove all sensitive fields from customer response
        This ensures no sensitive data is accidentally exposed in API responses
        """
        sensitive_fields = [
            "password_hash",
            "password",
            "reset_token",
            "verification_token",
            "two_factor_secret",
            "api_key",
            "session_token",
        ]

        # Create a copy to avoid modifying original
        sanitized = customer_data.copy()

        # Remove sensitive fields
        for field in sensitive_fields:
            sanitized.pop(field, None)

        # Mask partial sensitive data
        if "phone" in sanitized and sanitized["phone"]:
            sanitized["phone_masked"] = CustomerSecurityService.mask_sensitive_data(
                sanitized["phone"], visible_chars=4
            )

        if "email" in sanitized and sanitized["email"]:
            email_parts = sanitized["email"].split("@")
            if len(email_parts) == 2:
                sanitized["email_masked"] = (
                    CustomerSecurityService.mask_sensitive_data(
                        email_parts[0], visible_chars=2
                    )
                    + "@"
                    + email_parts[1]
                )

        return sanitized

    @staticmethod
    def log_security_event(
        customer_id: Optional[int],
        event_type: str,
        details: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log security-related events for audit purposes"""
        logger.info(
            f"Security Event - Customer: {customer_id}, "
            f"Type: {event_type}, Details: {details}, "
            f"IP: {ip_address}, UserAgent: {user_agent}"
        )

    @staticmethod
    def check_account_lockout(
        failed_attempts: int,
        last_failed_attempt: Optional[datetime],
        lockout_duration_minutes: int = 30,
        max_attempts: int = 5,
    ) -> Dict[str, Any]:
        """
        Check if account should be locked due to failed login attempts
        Returns lockout status and remaining time
        """
        if failed_attempts < max_attempts:
            return {
                "is_locked": False,
                "remaining_attempts": max_attempts - failed_attempts,
                "lockout_until": None,
            }

        if not last_failed_attempt:
            return {"is_locked": False, "remaining_attempts": 0, "lockout_until": None}

        lockout_until = last_failed_attempt + timedelta(
            minutes=lockout_duration_minutes
        )
        is_locked = datetime.utcnow() < lockout_until

        return {
            "is_locked": is_locked,
            "remaining_attempts": 0,
            "lockout_until": lockout_until if is_locked else None,
            "minutes_remaining": (
                int((lockout_until - datetime.utcnow()).total_seconds() / 60)
                if is_locked
                else 0
            ),
        }

    @staticmethod
    def validate_data_retention_compliance(
        customer_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check data retention compliance for customer data
        Helps with GDPR and other privacy regulations
        """
        last_activity = customer_data.get("last_login") or customer_data.get(
            "updated_at"
        )
        if not last_activity:
            return {"compliant": True, "action_required": None}

        # Check if customer has been inactive for more than 2 years (example policy)
        inactive_threshold = datetime.utcnow() - timedelta(days=730)

        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))

        if last_activity < inactive_threshold:
            return {
                "compliant": False,
                "action_required": "data_retention_review",
                "inactive_days": (datetime.utcnow() - last_activity).days,
                "recommendation": "Consider customer reactivation or data anonymization",
            }

        return {"compliant": True, "action_required": None}
