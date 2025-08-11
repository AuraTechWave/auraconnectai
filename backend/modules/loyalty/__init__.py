# backend/modules/loyalty/__init__.py

"""
Comprehensive loyalty and rewards module.
"""

from .routes.loyalty_routes import router as loyalty_router
from .models.rewards_models import (
    RewardTemplate, CustomerReward, RewardCampaign,
    RewardRedemption, LoyaltyPointsTransaction,
    RewardType, RewardStatus, TriggerType
)
from .services.loyalty_service import LoyaltyService

__all__ = [
    "loyalty_router",
    "RewardTemplate",
    "CustomerReward",
    "RewardCampaign",
    "RewardRedemption",
    "LoyaltyPointsTransaction",
    "RewardType",
    "RewardStatus",
    "TriggerType",
    "LoyaltyService"
]