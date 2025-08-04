# backend/modules/payments/gateways/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from ..models.payment_models import PaymentStatus, PaymentMethod, RefundStatus


@dataclass
class PaymentRequest:
    """Standard payment request structure"""
    amount: Decimal
    currency: str = "USD"
    order_id: str = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    description: Optional[str] = None
    statement_descriptor: Optional[str] = None
    payment_method_id: Optional[str] = None  # For saved payment methods
    save_payment_method: bool = False
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    return_url: Optional[str] = None  # For redirect-based payments


@dataclass
class PaymentResponse:
    """Standard payment response structure"""
    success: bool
    gateway_payment_id: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    fee_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    payment_method: Optional[PaymentMethod] = None
    payment_method_details: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None
    requires_action: bool = False
    action_url: Optional[str] = None  # For 3D Secure, PayPal redirect, etc.
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class RefundRequest:
    """Standard refund request structure"""
    payment_id: str  # Gateway payment ID
    amount: Optional[Decimal] = None  # None for full refund
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


@dataclass
class RefundResponse:
    """Standard refund response structure"""
    success: bool
    gateway_refund_id: Optional[str] = None
    status: RefundStatus = RefundStatus.PENDING
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    fee_refunded: Optional[Decimal] = None
    processed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class CustomerRequest:
    """Request to create/update customer at gateway"""
    customer_id: str  # Our internal customer ID
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CustomerResponse:
    """Response from customer creation/update"""
    success: bool
    gateway_customer_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class PaymentMethodRequest:
    """Request to save a payment method"""
    customer_id: str  # Gateway customer ID
    payment_method_token: str  # Token from frontend
    set_as_default: bool = False
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentMethodResponse:
    """Response from saving payment method"""
    success: bool
    gateway_payment_method_id: Optional[str] = None
    method_type: Optional[PaymentMethod] = None
    display_name: Optional[str] = None
    card_details: Optional[Dict[str, Any]] = None  # last4, brand, exp
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class PaymentGatewayInterface(ABC):
    """Abstract interface for payment gateways"""
    
    def __init__(self, config: Dict[str, Any], test_mode: bool = True):
        """
        Initialize payment gateway
        
        Args:
            config: Gateway-specific configuration
            test_mode: Whether to use test/sandbox mode
        """
        self.config = config
        self.test_mode = test_mode
    
    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a payment
        
        Args:
            request: Payment request details
            
        Returns:
            PaymentResponse with transaction details
        """
        pass
    
    @abstractmethod
    async def capture_payment(self, payment_id: str, amount: Optional[Decimal] = None) -> PaymentResponse:
        """
        Capture a previously authorized payment
        
        Args:
            payment_id: Gateway payment ID
            amount: Amount to capture (None for full amount)
            
        Returns:
            PaymentResponse with capture details
        """
        pass
    
    @abstractmethod
    async def get_payment(self, payment_id: str) -> PaymentResponse:
        """
        Get payment details
        
        Args:
            payment_id: Gateway payment ID
            
        Returns:
            PaymentResponse with current payment status
        """
        pass
    
    @abstractmethod
    async def cancel_payment(self, payment_id: str) -> PaymentResponse:
        """
        Cancel/void a payment
        
        Args:
            payment_id: Gateway payment ID
            
        Returns:
            PaymentResponse with cancellation status
        """
        pass
    
    @abstractmethod
    async def create_refund(self, request: RefundRequest) -> RefundResponse:
        """
        Create a refund for a payment
        
        Args:
            request: Refund request details
            
        Returns:
            RefundResponse with refund details
        """
        pass
    
    @abstractmethod
    async def get_refund(self, refund_id: str) -> RefundResponse:
        """
        Get refund details
        
        Args:
            refund_id: Gateway refund ID
            
        Returns:
            RefundResponse with current refund status
        """
        pass
    
    @abstractmethod
    async def create_customer(self, request: CustomerRequest) -> CustomerResponse:
        """
        Create a customer profile at the gateway
        
        Args:
            request: Customer details
            
        Returns:
            CustomerResponse with gateway customer ID
        """
        pass
    
    @abstractmethod
    async def update_customer(self, gateway_customer_id: str, request: CustomerRequest) -> CustomerResponse:
        """
        Update customer profile at the gateway
        
        Args:
            gateway_customer_id: Gateway's customer ID
            request: Updated customer details
            
        Returns:
            CustomerResponse with update status
        """
        pass
    
    @abstractmethod
    async def save_payment_method(self, request: PaymentMethodRequest) -> PaymentMethodResponse:
        """
        Save a payment method for future use
        
        Args:
            request: Payment method details
            
        Returns:
            PaymentMethodResponse with saved method details
        """
        pass
    
    @abstractmethod
    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """
        Delete a saved payment method
        
        Args:
            payment_method_id: Gateway payment method ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def list_payment_methods(self, customer_id: str) -> List[PaymentMethodResponse]:
        """
        List saved payment methods for a customer
        
        Args:
            customer_id: Gateway customer ID
            
        Returns:
            List of payment methods
        """
        pass
    
    @abstractmethod
    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify webhook signature and parse payload
        
        Args:
            headers: Webhook request headers
            body: Raw webhook body
            
        Returns:
            Tuple of (is_valid, parsed_payload)
        """
        pass
    
    @abstractmethod
    def get_public_config(self) -> Dict[str, Any]:
        """
        Get public configuration for frontend
        
        Returns:
            Dict with public keys/config
        """
        pass
    
    def calculate_fee(self, amount: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculate processing fee for an amount
        
        Args:
            amount: Transaction amount
            
        Returns:
            Tuple of (fee_amount, net_amount)
        """
        # Default implementation - override in specific gateways
        fee_percentage = Decimal(str(self.config.get('fee_percentage', 2.9)))
        fee_fixed = Decimal(str(self.config.get('fee_fixed', 0.30)))
        
        fee = (amount * fee_percentage / 100) + fee_fixed
        fee = fee.quantize(Decimal('0.01'))  # Round to cents
        net = amount - fee
        
        return fee, net
    
    def format_amount(self, amount: Decimal, currency: str = "USD") -> int:
        """
        Format amount for gateway (usually convert to cents)
        
        Args:
            amount: Decimal amount
            currency: Currency code
            
        Returns:
            Integer amount in smallest currency unit
        """
        # Most gateways want amounts in cents
        if currency.upper() in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
            return int(amount * 100)
        elif currency.upper() in ['JPY', 'KRW']:
            # Zero decimal currencies
            return int(amount)
        else:
            # Default to 2 decimal places
            return int(amount * 100)
    
    def parse_amount(self, amount: int, currency: str = "USD") -> Decimal:
        """
        Parse amount from gateway format to Decimal
        
        Args:
            amount: Integer amount from gateway
            currency: Currency code
            
        Returns:
            Decimal amount
        """
        if currency.upper() in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
            return Decimal(str(amount)) / 100
        elif currency.upper() in ['JPY', 'KRW']:
            # Zero decimal currencies
            return Decimal(str(amount))
        else:
            # Default to 2 decimal places
            return Decimal(str(amount)) / 100