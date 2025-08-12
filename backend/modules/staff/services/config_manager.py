"""
Configuration management service for payroll calculations.

Addresses the concern about hardcoded values and provides a centralized
way to manage business rules and calculation parameters.
"""

import os
import logging
from decimal import Decimal
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from datetime import datetime

from ...payroll.models.payroll_configuration import PayrollConfiguration, PayrollConfigurationType

logger = logging.getLogger(__name__)


@dataclass
class PayrollConfig:
    """Centralized payroll configuration."""
    # Overtime rules
    daily_overtime_threshold: Decimal = Decimal('8.0')
    weekly_overtime_threshold: Decimal = Decimal('40.0')
    overtime_multiplier: Decimal = Decimal('1.5')
    double_time_threshold: Decimal = Decimal('12.0')  # Daily
    double_time_multiplier: Decimal = Decimal('2.0')
    
    # Tax caps and thresholds
    social_security_wage_cap: Decimal = Decimal('160200.00')  # 2024
    medicare_additional_threshold_single: Decimal = Decimal('200000.00')
    medicare_additional_threshold_joint: Decimal = Decimal('250000.00')
    
    # Benefit proration factors
    monthly_to_weekly_factor: Decimal = Decimal('0.23')      # 52/12 ÷ 4 ≈ 0.23
    monthly_to_biweekly_factor: Decimal = Decimal('0.46')    # 26/12 ÷ 4 ≈ 0.46
    monthly_to_semimonthly_factor: Decimal = Decimal('0.50') # 24/12 ÷ 4 = 0.50
    
    # Tax approximation rates (fallback)
    default_federal_rate: Decimal = Decimal('0.22')
    default_state_rate: Decimal = Decimal('0.08')
    default_local_rate: Decimal = Decimal('0.01')
    default_social_security_rate: Decimal = Decimal('0.062')
    default_medicare_rate: Decimal = Decimal('0.0145')
    default_unemployment_rate: Decimal = Decimal('0.006')
    
    # Background job settings
    job_timeout_minutes: int = 60
    max_concurrent_jobs: int = 5
    job_cleanup_days: int = 7


class ConfigManager:
    """Manages payroll configuration from database and environment variables."""
    
    def __init__(self, db: Session):
        self.db = db
        self._config_cache: Optional[PayrollConfig] = None
        self._cache_timestamp: Optional[float] = None
        self.cache_ttl = 300  # 5 minutes
    
    def get_config(self, location: str = "default") -> PayrollConfig:
        """
        Get payroll configuration with caching.
        
        Args:
            location: Location-specific configuration
            
        Returns:
            PayrollConfig with current settings
        """
        import time
        
        # Check cache validity
        if (self._config_cache is not None and 
            self._cache_timestamp is not None and 
            time.time() - self._cache_timestamp < self.cache_ttl):
            return self._config_cache
        
        # Load fresh configuration
        config = self._load_configuration(location)
        
        # Update cache
        self._config_cache = config
        self._cache_timestamp = time.time()
        
        return config
    
    def get_config_with_cache_key(self, location: str = "default") -> tuple[PayrollConfig, str]:
        """
        Get payroll configuration with cache key for ETag support.
        
        Args:
            location: Location-specific configuration
            
        Returns:
            Tuple of (PayrollConfig, cache_key)
        """
        config = self.get_config(location)
        
        # Generate cache key based on config values
        cache_key = f"config_{location}_{hash(str(config.__dict__))}"
        
        return config, cache_key
    
    def _load_configuration(self, location: str) -> PayrollConfig:
        """Load configuration from database and environment variables."""
        config = PayrollConfig()
        
        # Override with environment variables if present
        config.daily_overtime_threshold = Decimal(
            os.getenv('PAYROLL_DAILY_OT_THRESHOLD', str(config.daily_overtime_threshold))
        )
        config.weekly_overtime_threshold = Decimal(
            os.getenv('PAYROLL_WEEKLY_OT_THRESHOLD', str(config.weekly_overtime_threshold))
        )
        config.overtime_multiplier = Decimal(
            os.getenv('PAYROLL_OT_MULTIPLIER', str(config.overtime_multiplier))
        )
        
        # Load database configurations
        db_configs = self.db.query(PayrollConfiguration).filter(
            PayrollConfiguration.location == location,
            PayrollConfiguration.is_active == True
        ).all()
        
        for db_config in db_configs:
            self._apply_db_config(config, db_config)
        
        return config
    
    def _apply_db_config(self, config: PayrollConfig, db_config: PayrollConfiguration):
        """Apply database configuration to PayrollConfig object."""
        config_value = db_config.config_value
        
        if db_config.config_type == PayrollConfigurationType.OVERTIME_RULES:
            if db_config.config_key == "daily_overtime_threshold":
                config.daily_overtime_threshold = Decimal(str(config_value.get("threshold", config.daily_overtime_threshold)))
            elif db_config.config_key == "weekly_overtime_threshold":
                config.weekly_overtime_threshold = Decimal(str(config_value.get("threshold", config.weekly_overtime_threshold)))
            elif db_config.config_key == "overtime_multiplier":
                config.overtime_multiplier = Decimal(str(config_value.get("multiplier", config.overtime_multiplier)))
        
        elif db_config.config_type == PayrollConfigurationType.BENEFIT_PRORATION:
            if db_config.config_key == "monthly_to_biweekly_factor":
                config.monthly_to_biweekly_factor = Decimal(str(config_value.get("factor", config.monthly_to_biweekly_factor)))
            elif db_config.config_key == "monthly_to_weekly_factor":
                config.monthly_to_weekly_factor = Decimal(str(config_value.get("factor", config.monthly_to_weekly_factor)))
        
        elif db_config.config_type == PayrollConfigurationType.TAX_SETTINGS:
            if db_config.config_key == "social_security_wage_cap":
                config.social_security_wage_cap = Decimal(str(config_value.get("cap", config.social_security_wage_cap)))
            elif db_config.config_key == "medicare_additional_threshold":
                config.medicare_additional_threshold_single = Decimal(str(config_value.get("single", config.medicare_additional_threshold_single)))
                config.medicare_additional_threshold_joint = Decimal(str(config_value.get("joint", config.medicare_additional_threshold_joint)))
    
    def validate_overtime_rules(self, rules: Dict[str, Any]) -> List[str]:
        """
        Validate overtime rules for compliance and reasonableness.
        
        Args:
            rules: Dictionary containing overtime rule values
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Validate daily overtime threshold
        daily_threshold = rules.get('daily_threshold', Decimal('8.0'))
        if not isinstance(daily_threshold, (int, float, Decimal)):
            errors.append("Daily overtime threshold must be a numeric value")
        elif daily_threshold < Decimal('4.0') or daily_threshold > Decimal('12.0'):
            errors.append("Daily overtime threshold should be between 4 and 12 hours")
        
        # Validate weekly overtime threshold
        weekly_threshold = rules.get('weekly_threshold', Decimal('40.0'))
        if not isinstance(weekly_threshold, (int, float, Decimal)):
            errors.append("Weekly overtime threshold must be a numeric value")
        elif weekly_threshold < Decimal('30.0') or weekly_threshold > Decimal('60.0'):
            errors.append("Weekly overtime threshold should be between 30 and 60 hours")
        
        # Validate overtime multiplier
        ot_multiplier = rules.get('overtime_multiplier', Decimal('1.5'))
        if not isinstance(ot_multiplier, (int, float, Decimal)):
            errors.append("Overtime multiplier must be a numeric value")
        elif ot_multiplier < Decimal('1.0') or ot_multiplier > Decimal('3.0'):
            errors.append("Overtime multiplier should be between 1.0 and 3.0")
        
        # Validate double time threshold
        double_time_threshold = rules.get('double_time_threshold', Decimal('12.0'))
        if not isinstance(double_time_threshold, (int, float, Decimal)):
            errors.append("Double time threshold must be a numeric value")
        elif double_time_threshold <= daily_threshold:
            errors.append("Double time threshold must be greater than daily overtime threshold")
        elif double_time_threshold > Decimal('16.0'):
            errors.append("Double time threshold should not exceed 16 hours per day")
        
        # Validate double time multiplier
        double_time_multiplier = rules.get('double_time_multiplier', Decimal('2.0'))
        if not isinstance(double_time_multiplier, (int, float, Decimal)):
            errors.append("Double time multiplier must be a numeric value")
        elif double_time_multiplier <= ot_multiplier:
            errors.append("Double time multiplier must be greater than overtime multiplier")
        elif double_time_multiplier > Decimal('3.0'):
            errors.append("Double time multiplier should not exceed 3.0")
        
        return errors
    
    def get_overtime_rules(self, location: str = "default") -> Dict[str, Decimal]:
        """Get overtime calculation rules."""
        config = self.get_config(location)
        return {
            "daily_threshold": config.daily_overtime_threshold,
            "weekly_threshold": config.weekly_overtime_threshold,
            "overtime_multiplier": config.overtime_multiplier,
            "double_time_threshold": config.double_time_threshold,
            "double_time_multiplier": config.double_time_multiplier
        }
    
    def get_overtime_rules_with_cache_key(self, location: str = "default") -> tuple[Dict[str, Decimal], str]:
        """
        Get overtime rules with cache key for ETag support.
        
        Args:
            location: Location-specific configuration
            
        Returns:
            Tuple of (overtime_rules, cache_key)
        """
        rules = self.get_overtime_rules(location)
        cache_key = f"overtime_rules_{location}_{hash(str(rules))}"
        
        return rules, cache_key
    
    def update_overtime_rules(
        self, 
        rules: Dict[str, Any], 
        location: str = "default",
        description: str = ""
    ) -> List[str]:
        """
        Update overtime rules with validation.
        
        Args:
            rules: Dictionary containing new overtime rule values
            location: Location for the configuration
            description: Human-readable description
            
        Returns:
            List of validation error messages (empty if successful)
        """
        # Validate the rules first
        errors = self.validate_overtime_rules(rules)
        if errors:
            return errors
        
        # Validate location format
        if not isinstance(location, str) or len(location.strip()) == 0:
            errors.append("Location must be a non-empty string")
            return errors
        
        try:
            # Update each rule individually
            for rule_key, rule_value in rules.items():
                if rule_key == "daily_threshold":
                    self.update_configuration(
                        PayrollConfigurationType.OVERTIME_RULES,
                        "daily_overtime_threshold",
                        {"threshold": float(rule_value)},
                        location,
                        description
                    )
                elif rule_key == "weekly_threshold":
                    self.update_configuration(
                        PayrollConfigurationType.OVERTIME_RULES,
                        "weekly_overtime_threshold",
                        {"threshold": float(rule_value)},
                        location,
                        description
                    )
                elif rule_key == "overtime_multiplier":
                    self.update_configuration(
                        PayrollConfigurationType.OVERTIME_RULES,
                        "overtime_multiplier",
                        {"multiplier": float(rule_value)},
                        location,
                        description
                    )
                elif rule_key == "double_time_threshold":
                    self.update_configuration(
                        PayrollConfigurationType.OVERTIME_RULES,
                        "double_time_threshold",
                        {"threshold": float(rule_value)},
                        location,
                        description
                    )
                elif rule_key == "double_time_multiplier":
                    self.update_configuration(
                        PayrollConfigurationType.OVERTIME_RULES,
                        "double_time_multiplier",
                        {"multiplier": float(rule_value)},
                        location,
                        description
                    )
                else:
                    logger.warning(f"Unknown overtime rule key: {rule_key}")
            
            # Clear cache to force reload
            self.invalidate_cache()
            
        except Exception as e:
            logger.error(f"Failed to update overtime rules: {e}")
            errors.append(f"Failed to update configuration: {str(e)}")
        
        return errors
    
    def get_benefit_proration_factors(self, location: str = "default") -> Dict[str, Decimal]:
        """Get benefit proration factors for different pay frequencies."""
        config = self.get_config(location)
        return {
            "weekly": config.monthly_to_weekly_factor,
            "biweekly": config.monthly_to_biweekly_factor,
            "semimonthly": config.monthly_to_semimonthly_factor,
            "monthly": Decimal('1.0')
        }
    
    def get_tax_caps_and_thresholds(self, location: str = "default") -> Dict[str, Decimal]:
        """Get tax-related caps and thresholds."""
        config = self.get_config(location)
        return {
            "social_security_wage_cap": config.social_security_wage_cap,
            "medicare_additional_threshold_single": config.medicare_additional_threshold_single,
            "medicare_additional_threshold_joint": config.medicare_additional_threshold_joint
        }
    
    def get_fallback_tax_rates(self, location: str = "default") -> Dict[str, Decimal]:
        """Get fallback tax rates for approximation calculations."""
        config = self.get_config(location)
        return {
            "federal": config.default_federal_rate,
            "state": config.default_state_rate,
            "local": config.default_local_rate,
            "social_security": config.default_social_security_rate,
            "medicare": config.default_medicare_rate,
            "unemployment": config.default_unemployment_rate
        }
    
    def get_job_settings(self) -> Dict[str, int]:
        """Get background job processing settings."""
        config = self.get_config()
        return {
            "timeout_minutes": config.job_timeout_minutes,
            "max_concurrent_jobs": config.max_concurrent_jobs,
            "cleanup_days": config.job_cleanup_days
        }
    
    def update_configuration(
        self, 
        config_type: PayrollConfigurationType,
        config_key: str,
        config_value: Dict[str, Any],
        location: str = "default",
        description: str = ""
    ) -> None:
        """
        Update or create a configuration setting.
        
        Args:
            config_type: Type of configuration
            config_key: Configuration key
            config_value: Configuration value (as JSON)
            location: Location for the configuration
            description: Human-readable description
        """
        existing_config = self.db.query(PayrollConfiguration).filter(
            PayrollConfiguration.config_type == config_type,
            PayrollConfiguration.config_key == config_key,
            PayrollConfiguration.location == location
        ).first()
        
        if existing_config:
            existing_config.config_value = config_value
            existing_config.description = description or existing_config.description
            existing_config.updated_at = datetime.utcnow()
        else:
            new_config = PayrollConfiguration(
                config_type=config_type,
                config_key=config_key,
                config_value=config_value,
                description=description,
                location=location,
                effective_date=datetime.utcnow(),
                is_active=True
            )
            self.db.add(new_config)
        
        self.db.commit()
        
        # Clear cache to force reload
        self._config_cache = None
        self._cache_timestamp = None
    
    def invalidate_cache(self):
        """Invalidate configuration cache to force reload."""
        self._config_cache = None
        self._cache_timestamp = None