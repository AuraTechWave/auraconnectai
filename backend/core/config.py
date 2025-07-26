"""
Enhanced configuration management for production security.

Addresses security concerns by moving secrets to environment variables
and providing proper configuration validation.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Addresses security concern: "Move secrets and credentials to .env 
    and integrate with a real user system."
    """
    
    # Database Configuration
    database_url: str = "postgresql://user:password@localhost:5432/auraconnect"
    database_test_url: Optional[str] = None
    
    # JWT Authentication - MUST be overridden in production
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # API Security
    api_rate_limit_per_minute: int = 60
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # Payroll Configuration
    default_overtime_threshold_hours: float = 40.0
    default_benefit_proration_factor: float = 0.46
    tax_calculation_timeout_seconds: int = 30
    
    # Redis Configuration (for production job tracking)
    redis_url: Optional[str] = None
    redis_password: Optional[str] = None
    
    # Email Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # Environment Settings
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # File Upload Configuration
    max_upload_size_mb: int = 10
    allowed_file_types: List[str] = ["csv", "xlsx", "pdf"]
    
    # Background Job Configuration
    background_job_timeout_seconds: int = 300
    max_concurrent_payroll_jobs: int = 5
    
    # Multi-tenant Configuration
    default_tenant_id: int = 1
    enable_multi_tenant: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator('jwt_secret_key')
    def validate_jwt_secret(cls, v, values):
        """Ensure JWT secret is not using default in production."""
        if values.get('environment') == 'production' and v == "dev-secret-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value in production")
        return v
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator('allowed_file_types', pre=True)
    def parse_allowed_file_types(cls, v):
        """Parse allowed file types from string or list."""
        if isinstance(v, str):
            return [file_type.strip() for file_type in v.split(",")]
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def redis_enabled(self) -> bool:
        """Check if Redis is configured for job tracking."""
        return self.redis_url is not None
    
    @property
    def email_enabled(self) -> bool:
        """Check if email is configured for notifications."""
        return all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password
        ])


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings (cached).
    
    Returns:
        Settings instance with environment variables loaded
    """
    return Settings()


# Export settings instance for easy import
settings = get_settings()


# Security validation on import
def validate_production_config():
    """Validate configuration for production deployment."""
    if settings.is_production:
        security_issues = []
        
        if settings.jwt_secret_key == "dev-secret-change-in-production":
            security_issues.append("JWT_SECRET_KEY is using default value")
        
        if settings.debug:
            security_issues.append("DEBUG is enabled in production")
        
        if "localhost" in str(settings.database_url):
            security_issues.append("Database URL appears to use localhost")
        
        if not settings.redis_enabled:
            security_issues.append("Redis not configured for job tracking")
        
        if security_issues:
            raise ValueError(
                f"Production security issues detected: {', '.join(security_issues)}"
            )


# Validate on import if in production
if settings.is_production:
    validate_production_config()