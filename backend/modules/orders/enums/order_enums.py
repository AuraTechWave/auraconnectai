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
