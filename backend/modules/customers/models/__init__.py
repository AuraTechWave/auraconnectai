# backend/modules/customers/models/__init__.py

from .customer_models import (
    Customer,
    CustomerStatus,
    CustomerTier,
    CommunicationPreference,
    CustomerAddress,
    CustomerNotification,
    CustomerSegment,
    CustomerReward,
    CustomerPreference,
)

__all__ = [
    "Customer",
    "CustomerStatus",
    "CustomerTier",
    "CommunicationPreference",
    "CustomerAddress",
    "CustomerNotification",
    "CustomerSegment",
    "CustomerReward",
    "CustomerPreference",
]