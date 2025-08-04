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
    

class DayOfWeek(int, Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
    

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