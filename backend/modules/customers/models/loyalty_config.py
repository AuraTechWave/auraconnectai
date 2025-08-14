# backend/modules/customers/models/loyalty_config.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from core.database import Base
from core.mixins import TimestampMixin
from datetime import datetime
from typing import Dict, Any, List


class LoyaltyTierConfig(Base, TimestampMixin):
    """Configurable loyalty tier thresholds and benefits"""
    __tablename__ = "loyalty_tier_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    tier_name = Column(String(50), nullable=False, unique=True, index=True)
    tier_order = Column(Integer, nullable=False, index=True)  # 1=Bronze, 2=Silver, etc.
    
    # Threshold Requirements
    min_lifetime_points = Column(Integer, nullable=False, default=0)
    min_total_spent = Column(Float, nullable=True)
    min_orders = Column(Integer, nullable=True)
    min_months_active = Column(Integer, nullable=True)
    
    # Benefits (stored as JSONB for flexibility)
    benefits = Column(JSONB, nullable=True)  # e.g., {"point_multiplier": 1.5, "free_delivery": true}
    
    # Status
    is_active = Column(Boolean, default=True)
    is_auto_upgrade = Column(Boolean, default=True)  # Automatic tier upgrades
    
    # Display Information
    display_name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    icon_url = Column(String(500), nullable=True)
    color_code = Column(String(7), nullable=True)  # Hex color code
    
    def __repr__(self):
        return f"<LoyaltyTierConfig(tier='{self.tier_name}', min_points={self.min_lifetime_points})>"


class LoyaltyPointsConfig(Base, TimestampMixin):
    """Configuration for loyalty points earning rules"""
    __tablename__ = "loyalty_points_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, unique=True)
    
    # Point Earning Rules
    action_type = Column(String(50), nullable=False)  # order, referral, review, birthday, etc.
    points_per_dollar = Column(Float, nullable=True)  # Points per dollar spent
    fixed_points = Column(Integer, nullable=True)  # Fixed points for action
    
    # Conditions (stored as JSONB for flexibility)
    conditions = Column(JSONB, nullable=True)  # e.g., {"min_order_amount": 25, "item_categories": ["entrees"]}
    
    # Limits
    max_points_per_day = Column(Integer, nullable=True)
    max_points_per_transaction = Column(Integer, nullable=True)
    
    # Tier Multipliers
    tier_multipliers = Column(JSONB, nullable=True)  # e.g., {"gold": 1.5, "platinum": 2.0}
    
    # Status
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    # Display Information
    display_name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<LoyaltyPointsConfig(rule='{self.rule_name}', action='{self.action_type}')>"


class LoyaltyService:
    """Service for managing configurable loyalty system"""
    
    def __init__(self, db):
        self.db = db
    
    def get_tier_configs(self) -> List[LoyaltyTierConfig]:
        """Get all active tier configurations ordered by tier_order"""
        return self.db.query(LoyaltyTierConfig).filter(
            LoyaltyTierConfig.is_active == True
        ).order_by(LoyaltyTierConfig.tier_order).all()
    
    def get_points_configs(self) -> List[LoyaltyPointsConfig]:
        """Get all active points earning rules"""
        return self.db.query(LoyaltyPointsConfig).filter(
            LoyaltyPointsConfig.is_active == True
        ).all()
    
    def calculate_tier_for_customer(self, customer) -> str:
        """Calculate appropriate tier for customer based on current configs"""
        tier_configs = self.get_tier_configs()
        
        # Start from highest tier and work down
        for tier_config in reversed(tier_configs):
            if self._customer_meets_tier_requirements(customer, tier_config):
                return tier_config.tier_name
        
        # Default to lowest tier if no requirements met
        return tier_configs[0].tier_name if tier_configs else "bronze"
    
    def _customer_meets_tier_requirements(self, customer, tier_config: LoyaltyTierConfig) -> bool:
        """Check if customer meets requirements for specific tier"""
        # Check lifetime points requirement
        if customer.lifetime_points < tier_config.min_lifetime_points:
            return False
        
        # Check total spent requirement
        if tier_config.min_total_spent and customer.total_spent < tier_config.min_total_spent:
            return False
        
        # Check order count requirement
        if tier_config.min_orders and customer.total_orders < tier_config.min_orders:
            return False
        
        # Check months active requirement
        if tier_config.min_months_active:
            months_active = (datetime.utcnow() - customer.acquisition_date).days / 30
            if months_active < tier_config.min_months_active:
                return False
        
        return True
    
    def calculate_points_earned(self, action_type: str, amount: float = None, customer_tier: str = None, **kwargs) -> int:
        """Calculate points earned for a specific action"""
        points_configs = self.db.query(LoyaltyPointsConfig).filter(
            and_(
                LoyaltyPointsConfig.action_type == action_type,
                LoyaltyPointsConfig.is_active == True,
                or_(
                    LoyaltyPointsConfig.start_date.is_(None),
                    LoyaltyPointsConfig.start_date <= datetime.utcnow()
                ),
                or_(
                    LoyaltyPointsConfig.end_date.is_(None),
                    LoyaltyPointsConfig.end_date >= datetime.utcnow()
                )
            )
        ).all()
        
        total_points = 0
        
        for config in points_configs:
            points = 0
            
            # Calculate base points
            if config.points_per_dollar and amount:
                points += int(amount * config.points_per_dollar)
            
            if config.fixed_points:
                points += config.fixed_points
            
            # Apply tier multiplier
            if customer_tier and config.tier_multipliers and customer_tier in config.tier_multipliers:
                multiplier = config.tier_multipliers[customer_tier]
                points = int(points * multiplier)
            
            # Apply limits
            if config.max_points_per_transaction:
                points = min(points, config.max_points_per_transaction)
            
            # Check conditions
            if self._meets_conditions(config.conditions, **kwargs):
                total_points += points
        
        return total_points
    
    def _meets_conditions(self, conditions: Dict[str, Any], **kwargs) -> bool:
        """Check if action meets the specified conditions"""
        if not conditions:
            return True
        
        # Example condition checks
        if "min_order_amount" in conditions:
            amount = kwargs.get("amount", 0)
            if amount < conditions["min_order_amount"]:
                return False
        
        if "item_categories" in conditions:
            order_categories = kwargs.get("categories", [])
            required_categories = conditions["item_categories"]
            if not any(cat in order_categories for cat in required_categories):
                return False
        
        return True
    
    def get_tier_benefits(self, tier_name: str) -> Dict[str, Any]:
        """Get benefits for a specific tier"""
        tier_config = self.db.query(LoyaltyTierConfig).filter(
            and_(
                LoyaltyTierConfig.tier_name == tier_name,
                LoyaltyTierConfig.is_active == True
            )
        ).first()
        
        return tier_config.benefits if tier_config and tier_config.benefits else {}


# Default configurations for seeding
DEFAULT_TIER_CONFIGS = [
    {
        "tier_name": "bronze",
        "tier_order": 1,
        "min_lifetime_points": 0,
        "display_name": "Bronze",
        "description": "Welcome tier for new customers",
        "benefits": {"point_multiplier": 1.0},
        "color_code": "#CD7F32"
    },
    {
        "tier_name": "silver",
        "tier_order": 2,
        "min_lifetime_points": 2000,
        "display_name": "Silver",
        "description": "For regular customers",
        "benefits": {"point_multiplier": 1.2, "birthday_bonus": 100},
        "color_code": "#C0C0C0"
    },
    {
        "tier_name": "gold",
        "tier_order": 3,
        "min_lifetime_points": 5000,
        "min_total_spent": 500.0,
        "display_name": "Gold",
        "description": "For valued customers",
        "benefits": {"point_multiplier": 1.5, "free_delivery": True, "birthday_bonus": 200},
        "color_code": "#FFD700"
    },
    {
        "tier_name": "platinum",
        "tier_order": 4,
        "min_lifetime_points": 10000,
        "min_total_spent": 1000.0,
        "min_orders": 20,
        "display_name": "Platinum",
        "description": "For our best customers",
        "benefits": {"point_multiplier": 2.0, "free_delivery": True, "priority_support": True, "birthday_bonus": 500},
        "color_code": "#E5E4E2"
    },
    {
        "tier_name": "vip",
        "tier_order": 5,
        "min_lifetime_points": 20000,
        "min_total_spent": 2500.0,
        "min_orders": 50,
        "min_months_active": 12,
        "display_name": "VIP",
        "description": "Exclusive tier for premium customers",
        "benefits": {"point_multiplier": 3.0, "free_delivery": True, "priority_support": True, "exclusive_offers": True, "birthday_bonus": 1000},
        "color_code": "#9932CC"
    }
]

DEFAULT_POINTS_CONFIGS = [
    {
        "rule_name": "order_purchase",
        "action_type": "order",
        "points_per_dollar": 1.0,
        "display_name": "Order Purchase",
        "description": "Earn 1 point per dollar spent on orders",
        "tier_multipliers": {"gold": 1.5, "platinum": 2.0, "vip": 3.0}
    },
    {
        "rule_name": "referral_bonus",
        "action_type": "referral",
        "fixed_points": 500,
        "display_name": "Referral Bonus",
        "description": "Earn 500 points for each successful referral"
    },
    {
        "rule_name": "birthday_bonus",
        "action_type": "birthday",
        "fixed_points": 200,
        "display_name": "Birthday Bonus",
        "description": "Special birthday points bonus",
        "tier_multipliers": {"silver": 1.0, "gold": 2.0, "platinum": 2.5, "vip": 5.0}
    },
    {
        "rule_name": "review_bonus",
        "action_type": "review",
        "fixed_points": 50,
        "max_points_per_day": 150,
        "display_name": "Review Bonus",
        "description": "Earn points for leaving reviews (max 150 per day)"
    }
]