# backend/modules/payments/gateways/__init__.py

from .base import (
    PaymentGatewayInterface,
    PaymentRequest,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
    CustomerRequest,
    CustomerResponse,
    PaymentMethodRequest,
    PaymentMethodResponse,
)
from .stripe_gateway import StripeGateway

# from .square_gateway import SquareGateway  # TODO: Fix Square SDK imports
SquareGateway = None  # Temporary placeholder
from .paypal_gateway import PayPalGateway

__all__ = [
    # Base classes
    "PaymentGatewayInterface",
    "PaymentRequest",
    "PaymentResponse",
    "RefundRequest",
    "RefundResponse",
    "CustomerRequest",
    "CustomerResponse",
    "PaymentMethodRequest",
    "PaymentMethodResponse",
    # Gateway implementations
    "StripeGateway",
    "SquareGateway",
    "PayPalGateway",
]
