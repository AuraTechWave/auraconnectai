from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    PAID = "PAID"
