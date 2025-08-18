"""
Application startup validation for security configurations.

This module ensures all required secrets and configurations are
properly set before the application starts.
"""

import os
import sys
import logging
from .secrets import validate_all_secrets
from .config import get_settings

logger = logging.getLogger(__name__)


def validate_startup_security():
    """
    Perform security validation at application startup.
    
    This should be called early in the application lifecycle,
    ideally in the main.py file before starting the server.
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    logger.info(f"Starting security validation for environment: {environment}")
    
    # Validate all required secrets
    try:
        validate_all_secrets()
        logger.info("✓ All required secrets validated")
    except Exception as e:
        logger.critical(f"Secret validation failed: {e}")
        if environment == "production":
            sys.exit(1)
        else:
            logger.warning("Continuing in development mode despite missing secrets")
    
    # Validate configuration settings
    try:
        settings = get_settings()
        
        # Check for dangerous configurations in production
        if environment == "production":
            issues = []
            
            if settings.debug:
                issues.append("DEBUG mode is enabled")
            
            if "localhost" in str(settings.database_url):
                issues.append("Database URL contains localhost")
            
            if not settings.redis_url:
                issues.append("Redis is not configured")
            
            if settings.cors_origins == ["http://localhost:3000"]:
                issues.append("CORS origins still set to localhost")
            
            if issues:
                logger.critical(f"Production configuration issues: {', '.join(issues)}")
                sys.exit(1)
        
        logger.info("✓ Configuration validation passed")
        
    except Exception as e:
        logger.critical(f"Configuration validation failed: {e}")
        if environment == "production":
            sys.exit(1)
    
    # Log security summary
    logger.info("=" * 60)
    logger.info("SECURITY VALIDATION SUMMARY")
    logger.info(f"Environment: {environment}")
    logger.info(f"Debug Mode: {'ENABLED' if settings.debug else 'DISABLED'}")
    logger.info(f"Redis: {'CONFIGURED' if settings.redis_url else 'NOT CONFIGURED'}")
    logger.info(f"Email: {'CONFIGURED' if settings.email_enabled else 'NOT CONFIGURED'}")
    logger.info("=" * 60)
    
    return True