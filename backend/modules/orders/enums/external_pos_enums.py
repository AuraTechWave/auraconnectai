# backend/modules/orders/enums/external_pos_enums.py

"""
Enums for external POS webhook handling.
"""

from enum import Enum


class ExternalPOSProvider(str, Enum):
    """Supported external POS providers"""
    SQUARE = "square"
    STRIPE = "stripe"
    TOAST = "toast"
    CLOVER = "clover"
    SHOPIFY = "shopify"
    PAYPAL = "paypal"
    CUSTOM = "custom"


class ExternalPOSEventType(str, Enum):
    """Types of events from external POS systems"""
    # Payment events
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_PENDING = "payment.pending"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_PARTIALLY_REFUNDED = "payment.partially_refunded"
    PAYMENT_VOIDED = "payment.voided"
    
    # Order events
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_COMPLETED = "order.completed"
    ORDER_CANCELLED = "order.cancelled"
    
    # Customer events
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    
    # Tip events
    TIP_ADDED = "tip.added"
    TIP_ADJUSTED = "tip.adjusted"
    
    # Other
    TEST_NOTIFICATION = "test.notification"
    UNKNOWN = "unknown"


class WebhookProcessingStatus(str, Enum):
    """Status of webhook event processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRY = "retry"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"


class PaymentStatus(str, Enum):
    """External payment status"""
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    VOIDED = "voided"
    EXPIRED = "expired"


class PaymentMethod(str, Enum):
    """Payment methods from external systems"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CASH = "cash"
    CHECK = "check"
    GIFT_CARD = "gift_card"
    MOBILE_WALLET = "mobile_wallet"
    BANK_TRANSFER = "bank_transfer"
    CRYPTOCURRENCY = "cryptocurrency"
    OTHER = "other"


class AuthenticationType(str, Enum):
    """Types of webhook authentication"""
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"