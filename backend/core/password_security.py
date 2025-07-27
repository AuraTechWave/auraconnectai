"""
Enhanced Password Security System

This module provides comprehensive password security features including:
- Secure password hashing with multiple algorithms
- Password strength validation
- Password reset workflow with secure tokens
- Password history tracking
- Rate limiting for security operations
"""

import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from enum import Enum
import logging

from passlib.context import CryptContext
from passlib.hash import argon2, bcrypt
from pydantic import BaseModel, validator
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)

# Security Configuration
ARGON2_ENABLED = os.getenv("ARGON2_ENABLED", "true").lower() == "true"
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
ARGON2_TIME_COST = int(os.getenv("ARGON2_TIME_COST", "3"))
ARGON2_MEMORY_COST = int(os.getenv("ARGON2_MEMORY_COST", "65536"))  # 64MB
ARGON2_PARALLELISM = int(os.getenv("ARGON2_PARALLELISM", "2"))

# Password Reset Configuration
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))
RESET_TOKEN_LENGTH = int(os.getenv("RESET_TOKEN_LENGTH", "32"))
MAX_RESET_ATTEMPTS_PER_HOUR = int(os.getenv("MAX_RESET_ATTEMPTS_PER_HOUR", "5"))

# Password Policy Configuration
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
MAX_PASSWORD_LENGTH = int(os.getenv("MAX_PASSWORD_LENGTH", "128"))
REQUIRE_UPPERCASE = os.getenv("REQUIRE_UPPERCASE", "true").lower() == "true"
REQUIRE_LOWERCASE = os.getenv("REQUIRE_LOWERCASE", "true").lower() == "true"
REQUIRE_NUMBERS = os.getenv("REQUIRE_NUMBERS", "true").lower() == "true"
REQUIRE_SYMBOLS = os.getenv("REQUIRE_SYMBOLS", "true").lower() == "true"
PREVENT_PASSWORD_REUSE = int(os.getenv("PREVENT_PASSWORD_REUSE", "5"))  # Last N passwords


class PasswordAlgorithm(str, Enum):
    """Supported password hashing algorithms."""
    ARGON2 = "argon2"
    BCRYPT = "bcrypt"


class PasswordStrength(str, Enum):
    """Password strength levels."""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    FAIR = "fair"
    GOOD = "good"
    STRONG = "strong"


class PasswordValidationResult(BaseModel):
    """Result of password validation."""
    is_valid: bool
    strength: PasswordStrength
    score: int  # 0-100
    errors: List[str] = []
    suggestions: List[str] = []


class PasswordResetToken(BaseModel):
    """Password reset token model."""
    token: str
    user_id: int
    email: str
    expires_at: datetime
    created_at: datetime
    is_used: bool = False
    attempt_count: int = 0


class EnhancedPasswordSecurity:
    """Enhanced password security manager."""
    
    def __init__(self):
        """Initialize password security with multiple algorithms."""
        
        # Configure password context with multiple algorithms
        schemes = ["bcrypt"]
        if ARGON2_ENABLED:
            schemes.insert(0, "argon2")  # Prefer Argon2 if available
        
        self.pwd_context = CryptContext(
            schemes=schemes,
            deprecated="auto",
            # Bcrypt configuration
            bcrypt__rounds=BCRYPT_ROUNDS,
            # Argon2 configuration (if enabled)
            argon2__time_cost=ARGON2_TIME_COST,
            argon2__memory_cost=ARGON2_MEMORY_COST,
            argon2__parallelism=ARGON2_PARALLELISM,
        )
        
        # In-memory storage for reset tokens (in production, use Redis or database)
        self._reset_tokens: Dict[str, PasswordResetToken] = {}
        self._rate_limit_cache: Dict[str, List[datetime]] = {}
        
        logger.info(f"Password security initialized with schemes: {schemes}")
    
    def hash_password(self, password: str, algorithm: Optional[PasswordAlgorithm] = None) -> str:
        """
        Hash a password using the specified or default algorithm.
        
        Args:
            password: Plain text password
            algorithm: Specific algorithm to use (optional)
            
        Returns:
            Hashed password string
        """
        if algorithm == PasswordAlgorithm.BCRYPT:
            return self.pwd_context.hash(password, scheme="bcrypt")
        elif algorithm == PasswordAlgorithm.ARGON2 and ARGON2_ENABLED:
            return self.pwd_context.hash(password, scheme="argon2")
        else:
            # Use default (preferred) algorithm
            return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Stored password hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if a password hash needs to be rehashed.
        
        Args:
            hashed_password: Stored password hash
            
        Returns:
            True if rehashing is recommended, False otherwise
        """
        return self.pwd_context.needs_update(hashed_password)
    
    def validate_password(self, password: str, user_email: Optional[str] = None) -> PasswordValidationResult:
        """
        Validate password strength and policy compliance.
        
        Args:
            password: Password to validate
            user_email: User's email for personal info check
            
        Returns:
            PasswordValidationResult with validation details
        """
        errors = []
        suggestions = []
        score = 0
        
        # Length validation
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
        elif len(password) < 12:
            suggestions.append("Consider using a longer password (12+ characters)")
            score += 10
        else:
            score += 25
        
        if len(password) > MAX_PASSWORD_LENGTH:
            errors.append(f"Password must be no longer than {MAX_PASSWORD_LENGTH} characters")
        
        # Character type validation
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_number = bool(re.search(r'\d', password))
        has_symbol = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        
        if REQUIRE_UPPERCASE and not has_upper:
            errors.append("Password must contain at least one uppercase letter")
        elif has_upper:
            score += 15
        
        if REQUIRE_LOWERCASE and not has_lower:
            errors.append("Password must contain at least one lowercase letter")
        elif has_lower:
            score += 15
        
        if REQUIRE_NUMBERS and not has_number:
            errors.append("Password must contain at least one number")
        elif has_number:
            score += 15
        
        if REQUIRE_SYMBOLS and not has_symbol:
            errors.append("Password must contain at least one special character")
        elif has_symbol:
            score += 20
        
        # Advanced checks
        if len(set(password)) < len(password) * 0.7:
            suggestions.append("Avoid repeating characters")
            score -= 10
        
        # Check for common patterns
        if re.search(r'(.)\1{2,}', password):  # 3+ repeated characters
            suggestions.append("Avoid repeating the same character consecutively")
            score -= 5
        
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            suggestions.append("Avoid sequential numbers")
            score -= 10
        
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):
            suggestions.append("Avoid sequential letters")
            score -= 10
        
        # Check against personal information
        if user_email:
            email_parts = user_email.lower().split('@')[0].split('.')
            for part in email_parts:
                if len(part) > 3 and part in password.lower():
                    suggestions.append("Avoid using parts of your email address")
                    score -= 15
                    break
        
        # Common password patterns
        common_patterns = [
            'password', '123456', 'qwerty', 'admin', 'login',
            'welcome', 'monkey', 'dragon', 'master', 'shadow'
        ]
        for pattern in common_patterns:
            if pattern in password.lower():
                errors.append("Password contains common words or patterns")
                score -= 20
                break
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        # Determine strength
        if score < 30:
            strength = PasswordStrength.VERY_WEAK
        elif score < 50:
            strength = PasswordStrength.WEAK
        elif score < 70:
            strength = PasswordStrength.FAIR
        elif score < 85:
            strength = PasswordStrength.GOOD
        else:
            strength = PasswordStrength.STRONG
        
        # Add suggestions based on strength
        if strength in [PasswordStrength.VERY_WEAK, PasswordStrength.WEAK]:
            suggestions.append("Consider using a passphrase with multiple words")
            suggestions.append("Mix uppercase, lowercase, numbers, and symbols")
        
        return PasswordValidationResult(
            is_valid=len(errors) == 0,
            strength=strength,
            score=score,
            errors=errors,
            suggestions=suggestions
        )
    
    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a cryptographically secure password.
        
        Args:
            length: Desired password length
            
        Returns:
            Generated secure password
        """
        # Character sets
        lowercase = 'abcdefghijklmnopqrstuvwxyz'
        uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        numbers = '0123456789'
        symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        # Ensure at least one character from each required set
        password = []
        all_chars = lowercase
        
        if REQUIRE_UPPERCASE:
            password.append(secrets.choice(uppercase))
            all_chars += uppercase
        
        if REQUIRE_LOWERCASE:
            password.append(secrets.choice(lowercase))
        
        if REQUIRE_NUMBERS:
            password.append(secrets.choice(numbers))
            all_chars += numbers
        
        if REQUIRE_SYMBOLS:
            password.append(secrets.choice(symbols))
            all_chars += symbols
        
        # Fill remaining length with random characters
        remaining_length = length - len(password)
        password.extend(secrets.choice(all_chars) for _ in range(remaining_length))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)
    
    def generate_reset_token(self, user_id: int, email: str) -> Optional[str]:
        """
        Generate a secure password reset token.
        
        Args:
            user_id: User ID requesting reset
            email: User's email address
            
        Returns:
            Reset token string or None if rate limited
        """
        # Check rate limiting
        if not self._check_rate_limit(f"reset_{user_id}"):
            logger.warning(f"Rate limit exceeded for password reset: user_id={user_id}")
            return None
        
        # Generate secure token
        token = secrets.token_urlsafe(RESET_TOKEN_LENGTH)
        
        # Create reset token record
        reset_token = PasswordResetToken(
            token=token,
            user_id=user_id,
            email=email,
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
            created_at=datetime.utcnow()
        )
        
        # Store token (in production, use Redis or database)
        self._reset_tokens[token] = reset_token
        
        # Clean up expired tokens
        self._cleanup_expired_tokens()
        
        logger.info(f"Generated password reset token for user_id={user_id}")
        return token
    
    def validate_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        """
        Validate a password reset token.
        
        Args:
            token: Reset token to validate
            
        Returns:
            PasswordResetToken if valid, None otherwise
        """
        reset_token = self._reset_tokens.get(token)
        
        if not reset_token:
            return None
        
        if reset_token.is_used:
            logger.warning(f"Attempted reuse of password reset token: {token[:8]}...")
            return None
        
        if reset_token.expires_at < datetime.utcnow():
            logger.warning(f"Expired password reset token used: {token[:8]}...")
            return None
        
        return reset_token
    
    def use_reset_token(self, token: str) -> bool:
        """
        Mark a reset token as used.
        
        Args:
            token: Reset token to mark as used
            
        Returns:
            True if successfully marked as used, False otherwise
        """
        reset_token = self._reset_tokens.get(token)
        
        if not reset_token:
            return False
        
        reset_token.is_used = True
        reset_token.attempt_count += 1
        
        logger.info(f"Password reset token used: user_id={reset_token.user_id}")
        return True
    
    def cleanup_user_reset_tokens(self, user_id: int) -> None:
        """
        Clean up all reset tokens for a specific user.
        
        Args:
            user_id: User ID to clean up tokens for
        """
        tokens_to_remove = [
            token for token, reset_token in self._reset_tokens.items()
            if reset_token.user_id == user_id
        ]
        
        for token in tokens_to_remove:
            del self._reset_tokens[token]
        
        if tokens_to_remove:
            logger.info(f"Cleaned up {len(tokens_to_remove)} reset tokens for user_id={user_id}")
    
    def _check_rate_limit(self, key: str) -> bool:
        """
        Check if operation is within rate limits.
        
        Args:
            key: Rate limit key
            
        Returns:
            True if within limits, False otherwise
        """
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Get or create rate limit history
        attempts = self._rate_limit_cache.get(key, [])
        
        # Remove old attempts
        attempts = [attempt for attempt in attempts if attempt > hour_ago]
        
        # Check if within limit
        if len(attempts) >= MAX_RESET_ATTEMPTS_PER_HOUR:
            return False
        
        # Add current attempt
        attempts.append(now)
        self._rate_limit_cache[key] = attempts
        
        return True
    
    def _cleanup_expired_tokens(self) -> None:
        """Clean up expired reset tokens."""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, reset_token in self._reset_tokens.items()
            if reset_token.expires_at < now
        ]
        
        for token in expired_tokens:
            del self._reset_tokens[token]
        
        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired reset tokens")
    
    def get_algorithm_info(self, hashed_password: str) -> Dict[str, str]:
        """
        Get information about the algorithm used for a hash.
        
        Args:
            hashed_password: Password hash to analyze
            
        Returns:
            Dictionary with algorithm information
        """
        try:
            info = self.pwd_context.identify(hashed_password)
            return {
                "algorithm": info or "unknown",
                "needs_rehash": str(self.needs_rehash(hashed_password))
            }
        except Exception as e:
            logger.error(f"Failed to identify hash algorithm: {e}")
            return {"algorithm": "unknown", "needs_rehash": "unknown"}


# Global instance
password_security = EnhancedPasswordSecurity()


# Convenience functions for backward compatibility
def hash_password(password: str) -> str:
    """Hash a password using the default algorithm."""
    return password_security.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return password_security.verify_password(plain_password, hashed_password)


def validate_email_address(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False