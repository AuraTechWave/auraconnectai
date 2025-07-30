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


class SquareEventType(str, Enum):
    """Square-specific webhook event types"""
    PAYMENT_UPDATED = "payment.updated"
    PAYMENT_CREATED = "payment.created"


class StripeEventType(str, Enum):
    """Stripe-specific webhook event types"""
    PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_INTENT_PAYMENT_FAILED = "payment_intent.payment_failed"
    PAYMENT_INTENT_CREATED = "payment_intent.created"
    PAYMENT_INTENT_CANCELED = "payment_intent.canceled"


class ToastEventType(str, Enum):
    """Toast-specific webhook event types"""
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_VOIDED = "payment.voided"


class CloverEventType(str, Enum):
    """Clover-specific webhook event types"""
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_REFUNDED = "payment.refunded"


class WebhookLogType(str, Enum):
    """Types of webhook log entries"""
    PROCESSING = "processing"
    PAYMENT_PROCESSING = "payment_processing"
    AUTHENTICATION = "authentication"
    ERROR = "error"
    DEBUG = "debug"


class WebhookLogLevel(str, Enum):
    """Log levels for webhook events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Mapping of provider-specific events to generic event types
PROVIDER_EVENT_MAPPING = {
    ExternalPOSProvider.SQUARE: {
        SquareEventType.PAYMENT_UPDATED: ExternalPOSEventType.PAYMENT_COMPLETED,
        SquareEventType.PAYMENT_CREATED: ExternalPOSEventType.PAYMENT_PENDING,
    },
    ExternalPOSProvider.STRIPE: {
        StripeEventType.PAYMENT_INTENT_SUCCEEDED: ExternalPOSEventType.PAYMENT_COMPLETED,
        StripeEventType.PAYMENT_INTENT_PAYMENT_FAILED: ExternalPOSEventType.PAYMENT_FAILED,
        StripeEventType.PAYMENT_INTENT_CREATED: ExternalPOSEventType.PAYMENT_PENDING,
        StripeEventType.PAYMENT_INTENT_CANCELED: ExternalPOSEventType.PAYMENT_CANCELLED,
    },
    ExternalPOSProvider.TOAST: {
        ToastEventType.PAYMENT_COMPLETED: ExternalPOSEventType.PAYMENT_COMPLETED,
        ToastEventType.PAYMENT_VOIDED: ExternalPOSEventType.PAYMENT_VOIDED,
    },
    ExternalPOSProvider.CLOVER: {
        CloverEventType.PAYMENT_PROCESSED: ExternalPOSEventType.PAYMENT_COMPLETED,
        CloverEventType.PAYMENT_REFUNDED: ExternalPOSEventType.PAYMENT_REFUNDED,
    },
}