from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_KITCHEN = "in_kitchen"
    READY = "ready"
    SERVED = "served"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELAYED = "delayed"
    SCHEDULED = "scheduled"
    AWAITING_FULFILLMENT = "awaiting_fulfillment"


class OrderItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    COMPLETED = "completed"


class DelayReason(str, Enum):
    CUSTOMER_REQUEST = "customer_request"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    SCHEDULED_ORDER = "scheduled_order"
    OTHER = "other"


class MultiItemRuleType(str, Enum):
    COMBO = "combo"
    BULK_DISCOUNT = "bulk_discount"
    COMPATIBILITY = "compatibility"
