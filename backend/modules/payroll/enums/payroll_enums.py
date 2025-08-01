from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CALCULATED = "calculated"
    APPROVED = "approved"
    PROCESSED = "processed"
    PAID = "paid"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"


class TaxType(str, Enum):
    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"
    SOCIAL_SECURITY = "social_security"
    MEDICARE = "medicare"
    UNEMPLOYMENT = "unemployment"
    DISABILITY = "disability"
    WORKERS_COMP = "workers_comp"


class PaymentMethod(str, Enum):
    DIRECT_DEPOSIT = "direct_deposit"
    CHECK = "check"
    CASH = "cash"
    DIGITAL_WALLET = "digital_wallet"


class PayrollJobStatus(str, Enum):
    """Status values for payroll job tracking."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaxRuleType(str, Enum):
    """Types of tax rules."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BRACKETED = "bracketed"
    TIERED = "tiered"


class TaxRuleStatus(str, Enum):
    """Status of tax rules."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    EXPIRED = "expired"
