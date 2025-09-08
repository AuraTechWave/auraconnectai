# backend/modules/payments/config/payment_config.py

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from enum import Enum


class PaymentEnvironment(str, Enum):
    """Payment system environment"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class PaymentConfig(BaseSettings):
    """Payment system configuration with validation"""

    # Environment
    PAYMENT_ENVIRONMENT: PaymentEnvironment = Field(
        default=PaymentEnvironment.DEVELOPMENT, description="Payment system environment"
    )

    # Redis Configuration
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for queue and caching",
    )
    REDIS_MAX_CONNECTIONS: int = Field(
        default=50, description="Maximum Redis connections"
    )
    REDIS_SOCKET_TIMEOUT: int = Field(
        default=5, description="Redis socket timeout in seconds"
    )

    # Queue Configuration
    WEBHOOK_QUEUE_NAME: str = Field(
        default="payment_webhooks", description="Queue name for webhook processing"
    )
    WEBHOOK_MAX_RETRIES: int = Field(
        default=3, description="Maximum webhook retry attempts"
    )
    WEBHOOK_RETRY_DELAY: int = Field(
        default=60, description="Delay between webhook retries in seconds"
    )
    WEBHOOK_WORKER_CONCURRENCY: int = Field(
        default=10, description="Number of concurrent webhook workers"
    )

    # Prometheus Configuration
    PROMETHEUS_ENABLED: bool = Field(
        default=True, description="Enable Prometheus metrics"
    )
    PROMETHEUS_PORT: int = Field(
        default=8001, description="Port for Prometheus metrics endpoint"
    )
    PROMETHEUS_PATH: str = Field(
        default="/metrics", description="Path for Prometheus metrics"
    )

    # Payment Gateway Timeouts
    GATEWAY_TIMEOUT_SECONDS: int = Field(
        default=30, description="Default gateway API timeout"
    )
    GATEWAY_CONNECT_TIMEOUT: int = Field(
        default=10, description="Gateway connection timeout"
    )

    # Action Expiration
    PAYMENT_ACTION_EXPIRY_MINUTES: int = Field(
        default=30, description="Minutes before payment actions expire"
    )
    ACTION_CHECK_INTERVAL_MINUTES: int = Field(
        default=5, description="Interval for checking expired actions"
    )

    # Security
    WEBHOOK_SIGNATURE_TOLERANCE_SECONDS: int = Field(
        default=300, description="Webhook signature time tolerance"
    )
    MAX_PAYMENT_AMOUNT: float = Field(
        default=99999.99, description="Maximum allowed payment amount"
    )
    MIN_PAYMENT_AMOUNT: float = Field(
        default=0.50, description="Minimum allowed payment amount"
    )

    # Feature Flags
    ENABLE_WEBHOOK_QUEUE: bool = Field(
        default=True, description="Enable webhook queue processing"
    )
    ENABLE_AUTO_RETRY: bool = Field(
        default=True, description="Enable automatic gateway retry"
    )
    ENABLE_METRICS: bool = Field(default=True, description="Enable metrics collection")

    # Alerting (for Prometheus AlertManager)
    ALERT_PAYMENT_FAILURE_THRESHOLD: float = Field(
        default=0.05, description="Payment failure rate threshold (5%)"
    )
    ALERT_GATEWAY_LATENCY_THRESHOLD: float = Field(
        default=5.0, description="Gateway latency threshold in seconds"
    )
    ALERT_WEBHOOK_BACKLOG_THRESHOLD: int = Field(
        default=100, description="Webhook backlog size threshold"
    )

    class Config:
        env_prefix = "PAYMENT_"
        case_sensitive = False

    @field_validator("REDIS_URL", mode="after")
    def validate_redis_url(cls, v: str, values: dict) -> str:
        """Validate Redis URL format"""
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("Invalid Redis URL format")

        # Ensure production uses secure Redis
        env = info.data.get("PAYMENT_ENVIRONMENT")
        if env == PaymentEnvironment.PRODUCTION and not v.startswith("rediss://"):
            raise ValueError("Production must use secure Redis (rediss://)")

        return v

    @field_validator("PROMETHEUS_PORT", mode="after")
    def validate_prometheus_port(cls, v: int) -> int:
        """Validate Prometheus port"""
        if not 1024 <= v <= 65535:
            raise ValueError("Prometheus port must be between 1024 and 65535")
        return v

    @field_validator("MAX_PAYMENT_AMOUNT", mode="after")
    def validate_max_amount(cls, v: float, values: dict) -> float:
        """Validate maximum payment amount"""
        min_amount = info.data.get("MIN_PAYMENT_AMOUNT", 0.50)
        if v <= min_amount:
            raise ValueError("Maximum payment amount must be greater than minimum")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate production-specific settings"""
        if self.PAYMENT_ENVIRONMENT == PaymentEnvironment.PRODUCTION:
            # Ensure critical features are enabled in production
            required_features = [
                "ENABLE_WEBHOOK_QUEUE",
                "ENABLE_AUTO_RETRY",
                "ENABLE_METRICS",
                "PROMETHEUS_ENABLED",
            ]

            for feature in required_features:
                if not getattr(self, feature, False):
                    raise ValueError(f"{feature} must be enabled in production")

            # Ensure reasonable timeout values
            if self.GATEWAY_TIMEOUT_SECONDS < 10:
                raise ValueError("Gateway timeout too low for production")

            # Ensure webhook security
            if self.WEBHOOK_SIGNATURE_TOLERANCE_SECONDS > 600:
                raise ValueError("Webhook signature tolerance too high for production")

        return self

    def get_redis_settings(self) -> Dict[str, Any]:
        """Get Redis connection settings"""
        return {
            "url": self.REDIS_URL,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": self.REDIS_SOCKET_TIMEOUT,
            "decode_responses": True,
        }

    def get_worker_settings(self) -> Dict[str, Any]:
        """Get queue worker settings"""
        return {
            "queue_name": self.WEBHOOK_QUEUE_NAME,
            "max_jobs": self.WEBHOOK_WORKER_CONCURRENCY,
            "job_timeout": self.GATEWAY_TIMEOUT_SECONDS,
            "job_retries": self.WEBHOOK_MAX_RETRIES,
            "retry_delay": self.WEBHOOK_RETRY_DELAY,
        }

    def get_alert_thresholds(self) -> Dict[str, Any]:
        """Get alerting thresholds for monitoring"""
        return {
            "payment_failure_rate": self.ALERT_PAYMENT_FAILURE_THRESHOLD,
            "gateway_latency": self.ALERT_GATEWAY_LATENCY_THRESHOLD,
            "webhook_backlog": self.ALERT_WEBHOOK_BACKLOG_THRESHOLD,
        }

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.PAYMENT_ENVIRONMENT == PaymentEnvironment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.PAYMENT_ENVIRONMENT == PaymentEnvironment.DEVELOPMENT


# Global configuration instance
payment_config = PaymentConfig()


# Validation helper
def validate_payment_config():
    """Validate payment configuration on startup"""
    try:
        config = PaymentConfig()

        # Log configuration summary
        import logging

        logger = logging.getLogger(__name__)

        logger.info(f"Payment system configuration loaded:")
        logger.info(f"  Environment: {config.PAYMENT_ENVIRONMENT}")
        logger.info(f"  Redis URL: {config.REDIS_URL[:20]}...")
        logger.info(
            f"  Webhook Queue: {'Enabled' if config.ENABLE_WEBHOOK_QUEUE else 'Disabled'}"
        )
        logger.info(
            f"  Auto Retry: {'Enabled' if config.ENABLE_AUTO_RETRY else 'Disabled'}"
        )
        logger.info(f"  Metrics: {'Enabled' if config.ENABLE_METRICS else 'Disabled'}")

        if config.is_production():
            logger.info("Running in PRODUCTION mode - all safety checks enabled")

        return True

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Payment configuration validation failed: {e}")
        raise
