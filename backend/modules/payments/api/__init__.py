# backend/modules/payments/api/__init__.py

from .payment_endpoints import router as payment_router

__all__ = ['payment_router']