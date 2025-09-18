# backend/core/email_config.py

"""
Email configuration settings
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field


class EmailSettings(BaseSettings):
    """Email service configuration settings"""
    
    # Email Provider Settings
    EMAIL_DEFAULT_PROVIDER: str = Field(default="sendgrid", env="EMAIL_DEFAULT_PROVIDER")
    EMAIL_FROM_ADDRESS: str = Field(..., env="EMAIL_FROM_ADDRESS")
    EMAIL_FROM_NAME: str = Field(..., env="EMAIL_FROM_NAME")
    
    # SendGrid Settings
    SENDGRID_API_KEY: Optional[str] = Field(None, env="SENDGRID_API_KEY")
    SENDGRID_WEBHOOK_SECRET: Optional[str] = Field(None, env="SENDGRID_WEBHOOK_SECRET")
    
    # AWS SES Settings
    AWS_ACCESS_KEY_ID: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(None, env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    SES_CONFIGURATION_SET: Optional[str] = Field(None, env="SES_CONFIGURATION_SET")
    
    # SMTP Settings (fallback)
    SMTP_HOST: Optional[str] = Field(None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    
    # General Email Settings
    EMAIL_MAX_RETRY_ATTEMPTS: int = Field(default=3, env="EMAIL_MAX_RETRY_ATTEMPTS")
    EMAIL_RETRY_DELAY_MINUTES: int = Field(default=5, env="EMAIL_RETRY_DELAY_MINUTES")
    EMAIL_BATCH_SIZE: int = Field(default=50, env="EMAIL_BATCH_SIZE")
    EMAIL_RATE_LIMIT_PER_MINUTE: int = Field(default=100, env="EMAIL_RATE_LIMIT_PER_MINUTE")
    
    # Template Settings
    EMAIL_TEMPLATE_CACHE_TTL: int = Field(default=3600, env="EMAIL_TEMPLATE_CACHE_TTL")
    
    # Tracking Settings
    EMAIL_TRACK_OPENS: bool = Field(default=True, env="EMAIL_TRACK_OPENS")
    EMAIL_TRACK_CLICKS: bool = Field(default=True, env="EMAIL_TRACK_CLICKS")
    
    # Unsubscribe Settings
    EMAIL_UNSUBSCRIBE_TOKEN_LENGTH: int = Field(default=32, env="EMAIL_UNSUBSCRIBE_TOKEN_LENGTH")
    
    # Restaurant/Business Information
    RESTAURANT_NAME: str = Field(..., env="RESTAURANT_NAME")
    RESTAURANT_ADDRESS: str = Field(..., env="RESTAURANT_ADDRESS")
    RESTAURANT_PHONE: str = Field(..., env="RESTAURANT_PHONE")
    RESTAURANT_EMAIL: str = Field(..., env="RESTAURANT_EMAIL")
    RESTAURANT_WEBSITE: Optional[str] = Field(None, env="RESTAURANT_WEBSITE")
    
    # URLs
    FRONTEND_URL: str = Field(..., env="FRONTEND_URL")
    APP_URL: str = Field(..., env="APP_URL")
    
    # Support Information
    SUPPORT_EMAIL: Optional[str] = Field(None, env="SUPPORT_EMAIL")
    
    # Marketing Settings
    WELCOME_OFFER_ENABLED: bool = Field(default=False, env="WELCOME_OFFER_ENABLED")
    WELCOME_OFFER_DESCRIPTION: Optional[str] = Field(None, env="WELCOME_OFFER_DESCRIPTION")
    WELCOME_OFFER_CODE: Optional[str] = Field(None, env="WELCOME_OFFER_CODE")
    
    # Social Media
    FACEBOOK_URL: Optional[str] = Field(None, env="FACEBOOK_URL")
    INSTAGRAM_URL: Optional[str] = Field(None, env="INSTAGRAM_URL")
    TWITTER_URL: Optional[str] = Field(None, env="TWITTER_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @field_validator("EMAIL_DEFAULT_PROVIDER", mode="after")
    def validate_provider(cls, v):
        """Validate email provider selection"""
        valid_providers = ["sendgrid", "aws_ses", "mailgun", "smtp"]
        if v not in valid_providers:
            raise ValueError(f"Email provider must be one of: {', '.join(valid_providers)}")
        return v
    
    @field_validator("SENDGRID_API_KEY", mode="after")
    def validate_sendgrid_config(cls, v, values):
        """Validate SendGrid configuration if selected"""
        if info.data.get("EMAIL_DEFAULT_PROVIDER") == "sendgrid" and not v:
            raise ValueError("SENDGRID_API_KEY is required when using SendGrid provider")
        return v
    
    @field_validator("AWS_SECRET_ACCESS_KEY", mode="after")
    def validate_ses_config(cls, v, values):
        """Validate AWS SES configuration if selected"""
        if info.data.get("EMAIL_DEFAULT_PROVIDER") == "aws_ses":
            if not v or not info.data.get("AWS_ACCESS_KEY_ID"):
                raise ValueError("AWS credentials are required when using AWS SES provider")
        return v


# Create a cached instance
_email_settings = None

def get_email_settings() -> EmailSettings:
    """Get cached email settings instance"""
    global _email_settings
    if _email_settings is None:
        _email_settings = EmailSettings()
    return _email_settings


# Make settings available at module level
email_settings = get_email_settings()