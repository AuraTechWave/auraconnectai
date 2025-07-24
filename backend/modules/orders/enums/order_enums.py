from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_KITCHEN = "in_kitchen"
    READY = "ready"
    SERVED = "served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    COMPLETED = "completed"


class MultiItemRuleType(str, Enum):
    COMBO = "combo"
    BULK_DISCOUNT = "bulk_discount"
    COMPATIBILITY = "compatibility"


class PricingType(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"


class PricingAdjustmentReason(str, Enum):
    DEMAND = "demand"
    TIME_BASED = "time_based"
    INVENTORY = "inventory"
    AI_RECOMMENDATION = "ai_recommendation"
    WEATHER = "weather"
    SPECIAL_EVENT = "special_event"
