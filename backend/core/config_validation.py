"""
Configuration validation for environment-specific settings.

This module ensures that critical configuration differences between
development and production environments are properly validated.
"""

import os
import warnings
import logging
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ValidationInfo, ConfigDict
from .secrets import get_required_secret, get_optional_secret

logger = logging.getLogger(__name__)


class EnvironmentConfig(BaseSettings):
    """Environment configuration with validation"""

    # Environment type
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")

    # Redis configuration
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    USE_IN_MEMORY_CACHE: bool = Field(default=False, env="USE_IN_MEMORY_CACHE")

    # Session configuration
    SESSION_SECRET: Optional[str] = Field(default=None, env="SESSION_SECRET")
    SESSION_EXPIRE_MINUTES: int = Field(default=30, env="SESSION_EXPIRE_MINUTES")

    # Data-retention settings (security / compliance)
    DATA_RETENTION_DAYS: int = Field(default=365, env="DATA_RETENTION_DAYS")
    BIOMETRIC_RETENTION_DAYS: int = Field(default=730, env="BIOMETRIC_RETENTION_DAYS")
    ANALYTICS_RETENTION_DAYS: int = Field(default=365, env="ANALYTICS_RETENTION_DAYS")

    # Security settings  
    SECRET_KEY: Optional[str] = Field(default=None, env="SECRET_KEY")
    ALLOW_INSECURE_HTTP: bool = Field(default=True, env="ALLOW_INSECURE_HTTP")

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"  # Allow extra fields from .env
    )

    @field_validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting"""
        valid_environments = ["development", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"ENVIRONMENT must be one of {valid_environments}")
        return v

    @field_validator("REDIS_URL")
    def validate_redis_url(cls, v, info):
        """Validate Redis configuration"""
        env = info.data.get("ENVIRONMENT", "development")

        if env == "production" and not v:
            raise ValueError("REDIS_URL is required in production environment")

        if not v and env != "production":
            logger.warning(
                "Redis URL not configured. Using in-memory session storage. "
                "This is acceptable for development but NOT for production."
            )

        return v

    @field_validator("SESSION_SECRET", "SECRET_KEY")
    def validate_secrets(cls, v, info):
        """Validate secret keys"""
        field_name = info.field_name
        
        # If not set, get from secure secrets management
        if v is None:
            if field_name == "SESSION_SECRET":
                return get_required_secret("Session encryption secret", "SESSION_SECRET")
            elif field_name == "SECRET_KEY":
                return get_required_secret("Application secret key", "SECRET_KEY")
        
        return v

    @field_validator("ALLOW_INSECURE_HTTP")
    def validate_https_requirement(cls, v, info):
        """Validate HTTPS requirement"""
        env = info.data.get("ENVIRONMENT", "development")

        if env == "production" and v:
            raise ValueError("ALLOW_INSECURE_HTTP must be False in production")

        return v

    def validate_for_production(self):
        """Additional validation for production environment"""
        if self.ENVIRONMENT != "production":
            return True

        errors = []

        # Check Redis
        if not self.REDIS_URL:
            errors.append("Redis URL is required for production")

        # Check secrets
        if "dev-secret" in self.SESSION_SECRET:
            errors.append("SESSION_SECRET must be changed from default")

        if "dev-secret" in self.SECRET_KEY:
            errors.append("SECRET_KEY must be changed from default")

        # Check HTTPS
        if self.ALLOW_INSECURE_HTTP:
            errors.append(
                "HTTPS is required for production (set ALLOW_INSECURE_HTTP=false)"
            )

        if errors:
            raise ValueError(f"Production configuration errors: {'; '.join(errors)}")

        return True

    def get_startup_warnings(self) -> list[str]:
        """Get configuration warnings for startup"""
        warnings = []

        if self.ENVIRONMENT == "development":
            if not self.REDIS_URL:
                warnings.append(
                    "Redis not configured - using in-memory session storage"
                )
            if "dev-secret" in self.SESSION_SECRET:
                warnings.append("Using default SESSION_SECRET - change for production")
            if "dev-secret" in self.SECRET_KEY:
                warnings.append("Using default SECRET_KEY - change for production")

        return warnings


# Global configuration instance
config = EnvironmentConfig()


def validate_configuration():
    """Validate configuration on startup"""
    try:
        if config.ENVIRONMENT == "production":
            config.validate_for_production()
            logger.info("Production configuration validated successfully")
        else:
            warnings = config.get_startup_warnings()
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def get_redis_url() -> Optional[str]:
    """Get Redis URL with fallback behavior"""
    if config.REDIS_URL:
        return config.REDIS_URL

    if config.ENVIRONMENT == "production":
        raise ValueError("Redis is required in production environment")

    # Development fallback
    logger.warning("No Redis URL configured, sessions will use in-memory storage")
    return None
