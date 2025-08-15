# backend/modules/loyalty/data/default_rewards.py

from typing import List, Dict, Any
from datetime import datetime, timedelta


# Default reward templates for seeding the system
DEFAULT_REWARD_TEMPLATES = [
    {
        "name": "welcome_discount",
        "title": "Welcome to AuraConnect!",
        "subtitle": "Get 10% off your first order",
        "description": "Welcome new customers with a special discount on their first order.",
        "reward_type": "percentage_discount",
        "percentage": 10.0,
        "min_order_amount": 15.0,
        "max_discount_amount": 10.0,
        "max_uses_per_customer": 1,
        "valid_days": 30,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "manual",
        "auto_apply": False,
        "is_active": True,
        "is_featured": True,
        "priority": 100,
        "terms_and_conditions": "Valid for new customers only. Cannot be combined with other offers. Minimum order $15.",
        "icon": "welcome",
    },
    {
        "name": "birthday_special",
        "title": "Happy Birthday!",
        "subtitle": "Enjoy a special birthday treat",
        "description": "Birthday reward automatically given to customers on their special day.",
        "reward_type": "fixed_discount",
        "value": 5.0,
        "max_uses_per_customer": 1,
        "valid_days": 7,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "birthday",
        "auto_apply": True,
        "is_active": True,
        "is_featured": True,
        "priority": 90,
        "terms_and_conditions": "Valid for 7 days from your birthday. Cannot be combined with other discounts.",
        "icon": "birthday",
    },
    {
        "name": "order_milestone_10",
        "title": "10 Orders Milestone!",
        "subtitle": "You've completed 10 orders - here's a reward!",
        "description": "Milestone reward for completing 10 orders.",
        "reward_type": "free_delivery",
        "value": 5.0,
        "max_uses_per_customer": 1,
        "valid_days": 14,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "milestone",
        "trigger_conditions": {"total_orders": 10},
        "auto_apply": False,
        "is_active": True,
        "is_featured": False,
        "priority": 70,
        "terms_and_conditions": "Free delivery on your next order. Valid for 14 days.",
        "icon": "milestone",
    },
    {
        "name": "high_spender_reward",
        "title": "Big Spender Bonus!",
        "subtitle": "Thanks for spending $500+ with us",
        "description": "Special reward for customers who have spent $500 or more.",
        "reward_type": "percentage_discount",
        "percentage": 15.0,
        "max_discount_amount": 25.0,
        "max_uses_per_customer": 1,
        "valid_days": 30,
        "eligible_tiers": ["gold", "platinum", "vip"],
        "trigger_type": "milestone",
        "trigger_conditions": {"total_spent": 500.0},
        "auto_apply": False,
        "is_active": True,
        "is_featured": True,
        "priority": 80,
        "terms_and_conditions": "15% off your next order up to $25 discount. Valid for 30 days.",
        "icon": "vip",
    },
    {
        "name": "tier_upgrade_gold",
        "title": "Welcome to Gold Tier!",
        "subtitle": "Enjoy your tier upgrade bonus",
        "description": "Congratulations reward for reaching Gold tier.",
        "reward_type": "bonus_points",
        "value": 200.0,
        "max_uses_per_customer": 1,
        "valid_days": 1,
        "eligible_tiers": ["gold"],
        "trigger_type": "tier_upgrade",
        "auto_apply": True,
        "is_active": True,
        "is_featured": False,
        "priority": 60,
        "terms_and_conditions": "Bonus points automatically added to your account.",
        "icon": "tier_upgrade",
    },
    {
        "name": "weekend_special",
        "title": "Weekend Special!",
        "subtitle": "10% off weekend orders",
        "description": "Special weekend discount for all customers.",
        "reward_type": "percentage_discount",
        "percentage": 10.0,
        "min_order_amount": 20.0,
        "max_discount_amount": 15.0,
        "valid_days": 30,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "conditional",
        "trigger_conditions": {"day_of_week": ["saturday", "sunday"]},
        "auto_apply": False,
        "is_active": False,  # Disabled by default - can be enabled for campaigns
        "is_featured": False,
        "priority": 50,
        "terms_and_conditions": "Valid on weekend orders only. Minimum order $20.",
        "icon": "weekend",
    },
    {
        "name": "referral_reward",
        "title": "Thanks for the Referral!",
        "subtitle": "You and your friend both get rewarded",
        "description": "Reward for successful customer referrals.",
        "reward_type": "fixed_discount",
        "value": 10.0,
        "max_uses_per_customer": 10,  # Allow multiple referrals
        "valid_days": 60,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "referral_success",
        "auto_apply": False,
        "is_active": True,
        "is_featured": False,
        "priority": 65,
        "terms_and_conditions": "Earned when your referred friend completes their first order. Valid for 60 days.",
        "icon": "referral",
    },
    {
        "name": "large_order_bonus",
        "title": "Large Order Bonus!",
        "subtitle": "Extra points for orders over $50",
        "description": "Bonus points for large orders.",
        "reward_type": "bonus_points",
        "value": 100.0,
        "valid_days": 1,
        "eligible_tiers": ["bronze", "silver", "gold", "platinum", "vip"],
        "trigger_type": "order_complete",
        "trigger_conditions": {"min_order_amount": 50.0},
        "auto_apply": True,
        "is_active": True,
        "is_featured": False,
        "priority": 40,
        "terms_and_conditions": "Bonus points automatically awarded for orders over $50.",
        "icon": "bonus",
    },
    {
        "name": "platinum_exclusive",
        "title": "Platinum Exclusive Deal!",
        "subtitle": "Special 20% discount for Platinum members",
        "description": "Exclusive discount for Platinum and VIP tier customers.",
        "reward_type": "percentage_discount",
        "percentage": 20.0,
        "max_discount_amount": 30.0,
        "max_uses_per_customer": 1,
        "valid_days": 45,
        "eligible_tiers": ["platinum", "vip"],
        "trigger_type": "manual",
        "auto_apply": False,
        "is_active": True,
        "is_featured": True,
        "priority": 95,
        "terms_and_conditions": "Exclusive to Platinum and VIP members. Cannot be combined with other offers.",
        "icon": "exclusive",
    },
    {
        "name": "loyalty_anniversary",
        "title": "Loyalty Anniversary!",
        "subtitle": "Celebrating your first year with us",
        "description": "Special reward for customer loyalty anniversary.",
        "reward_type": "gift_card",
        "value": 25.0,
        "max_uses_per_customer": 1,
        "valid_days": 30,
        "eligible_tiers": ["silver", "gold", "platinum", "vip"],
        "trigger_type": "anniversary",
        "auto_apply": True,
        "is_active": True,
        "is_featured": True,
        "priority": 85,
        "terms_and_conditions": "$25 gift card for completing one year as our customer. Valid for 30 days.",
        "icon": "anniversary",
    },
]


# Default reward campaigns for marketing
DEFAULT_CAMPAIGNS = [
    {
        "name": "New Customer Welcome Campaign",
        "description": "Automatically welcome new customers with a discount",
        "target_criteria": {"max_total_orders": 0},
        "target_tiers": ["bronze"],
        "start_date": datetime.utcnow(),
        "end_date": datetime.utcnow() + timedelta(days=365),
        "max_rewards_per_customer": 1,
        "is_active": True,
        "is_automated": True,
    },
    {
        "name": "Inactive Customer Reactivation",
        "description": "Re-engage customers who haven't ordered in 30 days",
        "target_criteria": {"inactive_days": 30, "min_total_orders": 2},
        "target_tiers": ["bronze", "silver", "gold"],
        "start_date": datetime.utcnow(),
        "end_date": datetime.utcnow() + timedelta(days=90),
        "max_rewards_per_customer": 1,
        "is_active": False,  # Manual activation
        "is_automated": False,
    },
    {
        "name": "VIP Customer Appreciation",
        "description": "Special appreciation campaign for VIP customers",
        "target_criteria": {"min_total_spent": 1000.0},
        "target_tiers": ["vip"],
        "start_date": datetime.utcnow(),
        "end_date": datetime.utcnow() + timedelta(days=30),
        "max_rewards_per_customer": 1,
        "is_active": False,  # Seasonal campaign
        "is_automated": False,
    },
]


def seed_default_rewards(db_session, rewards_engine):
    """Seed the database with default reward templates and campaigns"""
    try:
        from ..models.rewards_models import RewardTemplate, RewardCampaign

        # Create reward templates
        created_templates = []
        for template_data in DEFAULT_REWARD_TEMPLATES:
            existing = (
                db_session.query(RewardTemplate)
                .filter(RewardTemplate.name == template_data["name"])
                .first()
            )

            if not existing:
                template = rewards_engine.create_reward_template(template_data)
                created_templates.append(template)

        # Create campaigns (link to templates by name)
        created_campaigns = []
        for campaign_data in DEFAULT_CAMPAIGNS:
            existing = (
                db_session.query(RewardCampaign)
                .filter(RewardCampaign.name == campaign_data["name"])
                .first()
            )

            if not existing:
                # Find the template to link to (this would need to be implemented based on campaign logic)
                # For now, we'll skip campaign creation in the seed function
                pass

        return {
            "templates_created": len(created_templates),
            "campaigns_created": len(created_campaigns),
        }

    except Exception as e:
        print(f"Error seeding default rewards: {str(e)}")
        return {"error": str(e)}
