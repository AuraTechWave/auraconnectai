from enum import Enum


class ShiftStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ShiftType(str, Enum):
    REGULAR = "regular"
    OVERTIME = "overtime"
    HOLIDAY = "holiday"
    TRAINING = "training"
    MEETING = "meeting"


class RecurrenceType(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREFERRED = "preferred"
    LIMITED = "limited"


class SwapStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class BreakType(str, Enum):
    MEAL = "meal"
    REST = "rest"
    PAID = "paid"
    UNPAID = "unpaid"
