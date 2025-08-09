"""
Application startup validation and initialization.

This module performs critical startup checks and initialization
to ensure the application is properly configured before serving requests.
"""

import logging
import sys
from typing import List, Tuple
from core.config_validation import config, validate_configuration
from core.database import engine, Base
from sqlalchemy import text
import sqlalchemy as sa
import warnings

logger = logging.getLogger(__name__)


class StartupValidator:
    """Validates application startup requirements"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def check_database_connection(self) -> bool:
        """Check database connectivity"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("Database connection successful")
            return True
        except Exception as e:
            self.errors.append(f"Database connection failed: {str(e)}")
            return False
    
    def check_redis_connection(self) -> bool:
        """Check Redis connectivity (if configured)"""
        if not config.redis_url:
            if config.ENVIRONMENT == "production":
                self.errors.append("Redis is required in production but not configured")
                return False
            else:
                self.warnings.append("Redis not configured - using in-memory fallback")
                return True
        
        try:
            import redis
            r = redis.from_url(config.redis_url)
            r.ping()
            logger.info("Redis connection successful")
            return True
        except Exception as e:
            if config.ENVIRONMENT == "production":
                self.errors.append(f"Redis connection failed in production: {str(e)}")
                return False
            else:
                self.warnings.append(f"Redis connection failed: {str(e)} - using fallback")
                return True
    
    def check_environment_config(self) -> bool:
        """Validate environment configuration"""
        try:
            validate_configuration()
            
            # Add specific warnings for development
            if config.ENVIRONMENT == "development":
                if "dev-secret" in config.SECRET_KEY:
                    self.warnings.append("Using development SECRET_KEY - change for production")
                if "dev-secret" in config.SESSION_SECRET:
                    self.warnings.append("Using development SESSION_SECRET - change for production")
            
            return True
        except ValueError as e:
            self.errors.append(f"Configuration validation failed: {str(e)}")
            return False
    
    def check_required_tables(self) -> bool:
        """Check if required database tables exist"""
        required_tables = [
            'rbac_users',
            'rbac_roles',
            'rbac_permissions',
            'staff',
            'customers',
            'orders'
        ]
        
        try:
            with engine.connect() as conn:
                # Get list of tables
                inspector = sa.inspect(engine)
                existing_tables = inspector.get_table_names()
                
                missing_tables = [t for t in required_tables if t not in existing_tables]
                
                if missing_tables:
                    self.warnings.append(
                        f"Missing database tables: {', '.join(missing_tables)}. "
                        "Run migrations with: alembic upgrade head"
                    )
                
            return True
        except Exception as e:
            self.warnings.append(f"Could not check database tables: {str(e)}")
            return True
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validation checks"""
        checks = [
            ("Environment Configuration", self.check_environment_config),
            ("Database Connection", self.check_database_connection),
            ("Redis Connection", self.check_redis_connection),
            ("Database Tables", self.check_required_tables),
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            logger.info(f"Running check: {check_name}")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.errors.append(f"{check_name} check failed with error: {str(e)}")
                all_passed = False
        
        return all_passed, self.errors, self.warnings


def run_startup_checks():
    """Run all startup validation checks"""
    logger.info("=" * 60)
    logger.info("Starting AuraConnect Backend")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info("=" * 60)
    
    validator = StartupValidator()
    passed, errors, warnings = validator.validate_all()
    
    # Display warnings
    if warnings:
        logger.warning("Startup Warnings:")
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
    
    # Display errors
    if errors:
        logger.error("Startup Errors:")
        for error in errors:
            logger.error(f"  ❌ {error}")
    
    # Determine if we should continue
    if not passed and config.ENVIRONMENT == "production":
        logger.error("Cannot start in production with errors!")
        sys.exit(1)
    elif not passed:
        logger.warning("Starting in development mode despite errors")
    else:
        logger.info("✅ All startup checks passed")
    
    # Show final status
    logger.info("=" * 60)
    if config.ENVIRONMENT == "production":
        logger.info("🚀 Starting in PRODUCTION mode")
    else:
        logger.info(f"🔧 Starting in {config.ENVIRONMENT.upper()} mode")
    logger.info("=" * 60)
    
    return passed, warnings


# Import this at the end of main.py
def configure_startup_logging():
    """Configure logging for startup"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )