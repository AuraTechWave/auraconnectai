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


class TagType(str, Enum):
    PRIORITY = "priority"
    DIETARY = "dietary"
    SPECIAL = "special"
    CUSTOM = "custom"


class CategoryType(str, Enum):
    DINE_IN = "dine_in"
    TAKEOUT = "takeout"
    DELIVERY = "delivery"
    CATERING = "catering"
