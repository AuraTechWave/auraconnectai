"""
Enhanced configuration management for production security.

Addresses security concerns by moving secrets to environment variables
and providing proper configuration validation.
"""

import os
from typing import List, Optional

try:
    from pydantic.v1 import BaseSettings, validator
except ImportError:
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

    # API Security & Rate Limiting
    api_rate_limit_per_minute: int = 60
    cors_origins: List[str] = ["http://localhost:3000"]

    # Rate Limiting Configuration
    rate_limit_enabled: bool = True
    default_rate_limit: int = 100  # requests per minute
    auth_rate_limit: int = 5  # login attempts per minute

    # Payroll Configuration
    default_overtime_threshold_hours: float = 40.0
    default_benefit_proration_factor: float = 0.46
    tax_calculation_timeout_seconds: int = 30

    # Redis Configuration (for production job tracking and rate limiting)
    redis_url: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Email Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None

    # Environment Settings
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # External POS Webhook Configuration
    WEBHOOK_MAX_RETRY_ATTEMPTS: int = 3
    WEBHOOK_RETRY_DELAYS: List[int] = [60, 300, 900]  # seconds: 1min, 5min, 15min
    WEBHOOK_RETRY_SCHEDULER_INTERVAL_MINUTES: int = 5
    WEBHOOK_HEALTH_CHECK_INTERVAL_MINUTES: int = 5
    WEBHOOK_CLEANUP_INTERVAL_HOURS: int = 1
    WEBHOOK_RETENTION_DAYS: int = 30
    WEBHOOK_DUPLICATE_WINDOW_MINUTES: int = 60
    WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: int = 300  # 5 minutes
    WEBHOOK_HTTP_TIMEOUT_SECONDS: int = 30
    WEBHOOK_CLEANUP_MAX_DELETE_BATCH: int = 1000
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 60
    WEBHOOK_RETRY_BATCH_SIZE: int = 20  # Max webhooks to retry per batch
    WEBHOOK_ORDER_MATCH_WINDOW_MINUTES: int = 10  # Time window for order matching
    WEBHOOK_RECENT_EVENTS_LIMIT: int = 10  # Number of recent events to display
    WEBHOOK_HEALTH_CHECK_HOURS: int = 24  # Time window for health check stats
    WEBHOOK_HEALTH_DEGRADED_THRESHOLD: int = (
        5  # Failed webhooks before status is degraded
    )
    WEBHOOK_STATS_DEFAULT_HOURS: int = 24  # Default time period for statistics
    WEBHOOK_STATS_MAX_HOURS: int = 168  # Maximum time period for statistics (7 days)
    WEBHOOK_RETRY_API_LIMIT: int = 50  # Maximum webhooks to retry via API
    WEBHOOK_LOG_RESPONSE_TRUNCATE: int = 1000  # Max response body chars to store
    WEBHOOK_SUCCESS_STATUS_MIN: int = 200  # Minimum successful HTTP status code
    WEBHOOK_SUCCESS_STATUS_MAX: int = (
        300  # Maximum successful HTTP status code (exclusive)
    )
    WEBHOOK_CENTS_TO_DOLLARS: int = 100  # Conversion factor for cents to dollars

    # File Upload Configuration
    max_upload_size_mb: int = 10
    allowed_file_types: List[str] = ["csv", "xlsx", "pdf"]

    # Background Job Configuration
    background_job_timeout_seconds: int = 300
    max_concurrent_payroll_jobs: int = 5

    # Multi-tenant Configuration
    default_tenant_id: int = 1
    enable_multi_tenant: bool = True

    # RBAC Configuration
    rbac_admin_override_enabled: bool = (
        True  # Enable admin bypass in dev, disable in prod
    )
    rbac_deny_precedence: bool = True  # Deny permissions always take precedence
    rbac_session_cache_ttl_minutes: int = 15  # Session cache TTL

    # Order Sync Configuration
    CLOUD_SYNC_ENDPOINT: str = "https://api.auraconnect.ai/sync"
    CLOUD_API_KEY: str = ""
    POS_TERMINAL_ID: str = "POS-001"

    # Sync Settings
    SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 10
    SYNC_BATCH_SIZE: int = 50
    SYNC_MAX_RETRIES: int = 3
    SYNC_RETRY_BACKOFF_BASE: float = 2.0  # Exponential backoff base
    SYNC_RETRY_MAX_WAIT_MINUTES: int = 60  # Max retry wait time
    SYNC_CONCURRENT_ORDERS: int = 10  # Max concurrent order syncs
    SYNC_HTTP_TIMEOUT_SECONDS: int = 30  # HTTP request timeout
    SYNC_HEALTH_CHECK_INTERVAL_MINUTES: int = 5  # Health check frequency
    SYNC_CLEANUP_INTERVAL_HOURS: int = 24  # Old log cleanup frequency
    SYNC_LOG_RETENTION_DAYS: int = 30  # How long to keep sync logs
    SYNC_CONFLICT_AUTO_RESOLVE_HOURS: int = 24  # Auto-resolve old conflicts
    SYNC_DASHBOARD_POLL_SECONDS: int = 30  # Frontend polling interval

    # POS Sync configuration
    POS_SYNC_RECENT_HOURS: int = 24  # Hours to consider for recent orders
    POS_SYNC_BATCH_PREFIX: str = "manual"  # Prefix for manual sync batch IDs
    POS_SYNC_DATE_FORMAT: str = "%Y%m%d_%H%M%S"  # Date format for batch IDs
    POS_SYNC_RATE_LIMIT_PER_MINUTE: int = 1  # Max sync requests per minute

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("jwt_secret_key")
    def validate_jwt_secret(cls, v, values):
        """Ensure JWT secret is not using default in production."""
        if (
            values.get("environment") == "production"
            and v == "dev-secret-change-in-production"
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value in production"
            )
        return v

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("allowed_file_types", pre=True)
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
        return all([self.smtp_server, self.smtp_username, self.smtp_password])


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
