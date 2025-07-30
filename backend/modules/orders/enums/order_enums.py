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
    ARCHIVED = "archived"
    PAID = "paid"  # Order has been paid externally


class OrderPaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    FAILED = "failed"


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


class SpecialInstructionType(str, Enum):
    ALLERGEN = "allergen"
    PREPARATION = "preparation"
    TIMING = "timing"
    TEMPERATURE = "temperature"
    PRESENTATION = "presentation"
    GENERAL = "general"


class FraudCheckStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class FraudRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CheckpointType(str, Enum):
    VOLUME_CHECK = "volume_check"
    PRICE_CHECK = "price_check"
    TIMING_CHECK = "timing_check"
    PATTERN_CHECK = "pattern_check"


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


class OrderPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class PrintStatus(str, Enum):
    PENDING = "pending"
    PRINTING = "printing"
    PRINTED = "printed"
    FAILED = "failed"


class TicketType(str, Enum):
    KITCHEN = "kitchen"
    BAR = "bar"
    GRILL = "grill"
    COLD_PREP = "cold_prep"
    HOT_PREP = "hot_prep"
