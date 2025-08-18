"""
Secure secret management utility for production environments.

This module provides fail-safe secret retrieval with proper validation
to prevent hardcoded credentials from reaching production.
"""

import os
import sys
import logging
from typing import Optional, NoReturn

logger = logging.getLogger(__name__)


class SecretError(Exception):
    """Raised when a required secret is missing or invalid."""
    pass


def _fail_without_secret(secret_name: str) -> NoReturn:
    """
    Fail the application when a required secret is missing.
    
    Args:
        secret_name: Name of the missing secret
        
    Raises:
        SecretError: Always raises with details about the missing secret
    """
    error_msg = (
        f"CRITICAL SECURITY ERROR: Required secret '{secret_name}' is not set. "
        f"This secret must be configured in environment variables before running the application. "
        f"Please check your deployment configuration."
    )
    logger.critical(error_msg)
    
    # In production, we want to fail fast and loud
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        # Exit the application immediately in production
        sys.exit(1)
    
    raise SecretError(error_msg)


def get_required_secret(
    secret_name: str,
    env_var: Optional[str] = None,
    allow_empty: bool = False
) -> str:
    """
    Get a required secret from environment variables with validation.
    
    Args:
        secret_name: Descriptive name of the secret (for error messages)
        env_var: Environment variable name (defaults to secret_name)
        allow_empty: Whether to allow empty string values
        
    Returns:
        The secret value
        
    Raises:
        SecretError: If the secret is missing or invalid
    """
    if env_var is None:
        env_var = secret_name
    
    value = os.getenv(env_var)
    
    # Check if value exists
    if value is None:
        _fail_without_secret(secret_name)
    
    # Check for empty values
    if not allow_empty and not value.strip():
        logger.error(f"Secret '{secret_name}' is empty")
        _fail_without_secret(secret_name)
    
    # Check for development defaults in production
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        dangerous_defaults = [
            "development", "dev", "default", "change-me", 
            "change-in-production", "secret", "password",
            "123456", "admin", "test"
        ]
        
        value_lower = value.lower()
        for dangerous in dangerous_defaults:
            if dangerous in value_lower:
                logger.error(
                    f"Secret '{secret_name}' contains dangerous default value: {dangerous}"
                )
                _fail_without_secret(secret_name)
    
    return value


def get_optional_secret(
    secret_name: str,
    env_var: Optional[str] = None,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Get an optional secret from environment variables.
    
    Args:
        secret_name: Descriptive name of the secret
        env_var: Environment variable name (defaults to secret_name)
        default: Default value if not set (None for optional secrets)
        
    Returns:
        The secret value or default
    """
    if env_var is None:
        env_var = secret_name
    
    value = os.getenv(env_var, default)
    
    # Warn if using default in production
    if value == default and default is not None:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            logger.warning(
                f"Optional secret '{secret_name}' is using default value in production"
            )
    
    return value


def validate_all_secrets():
    """
    Validate all required secrets at application startup.
    
    This should be called early in the application lifecycle to ensure
    all required secrets are properly configured.
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    logger.info(f"Validating secrets for environment: {environment}")
    
    required_secrets = [
        ("JWT_SECRET_KEY", "JWT secret key for token signing"),
        ("DATABASE_URL", "Database connection string"),
    ]
    
    # Additional required secrets for production
    if environment == "production":
        required_secrets.extend([
            ("SESSION_SECRET", "Session encryption secret"),
            ("REDIS_URL", "Redis connection string"),
        ])
    
    errors = []
    for env_var, description in required_secrets:
        try:
            get_required_secret(description, env_var)
            logger.debug(f"✓ {env_var} is properly configured")
        except SecretError as e:
            errors.append(str(e))
    
    if errors:
        logger.critical(f"Found {len(errors)} secret configuration errors")
        for error in errors:
            logger.critical(error)
        
        if environment == "production":
            sys.exit(1)
        else:
            logger.warning("Running in development mode with missing secrets")
    else:
        logger.info("All required secrets are properly configured")