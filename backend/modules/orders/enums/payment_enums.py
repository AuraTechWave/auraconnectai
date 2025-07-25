from enum import Enum


class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    RESOLVED = "resolved"


class DiscrepancyType(str, Enum):
    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_PAYMENT = "missing_payment"
    DUPLICATE_PAYMENT = "duplicate_payment"


class ReconciliationAction(str, Enum):
    AUTO_MATCHED = "auto_matched"
    MANUAL_REVIEW = "manual_review"
    EXCEPTION_HANDLED = "exception_handled"
