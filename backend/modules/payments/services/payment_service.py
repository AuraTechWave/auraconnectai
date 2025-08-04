# backend/modules/payments/services/payment_service.py

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.database import get_db
from core.cache import cache_service
from ..models.payment_models import (
    Payment, Refund, PaymentGatewayConfig, CustomerPaymentMethod,
    PaymentGateway, PaymentStatus, PaymentMethod, RefundStatus
)
from ..gateways import (
    PaymentGatewayInterface, StripeGateway, SquareGateway, PayPalGateway,
    PaymentRequest, PaymentResponse, RefundRequest, RefundResponse,
    CustomerRequest, PaymentMethodRequest
)
from ...orders.models.order_models import Order, OrderStatus


logger = logging.getLogger(__name__)


class PaymentService:
    """
    Main payment processing service that manages gateway selection
    and payment lifecycle
    """
    
    def __init__(self):
        self._gateways: Dict[PaymentGateway, PaymentGatewayInterface] = {}
        self._gateway_configs: Dict[PaymentGateway, Dict[str, Any]] = {}
    
    async def initialize(self, db: AsyncSession):
        """Initialize payment gateways from database configuration"""
        try:
            # Load gateway configurations
            result = await db.execute(
                select(PaymentGatewayConfig).where(
                    PaymentGatewayConfig.is_active == True
                )
            )
            configs = result.scalars().all()
            
            for config in configs:
                await self._initialize_gateway(config)
            
            logger.info(f"Initialized {len(self._gateways)} payment gateways")
            
        except Exception as e:
            logger.error(f"Failed to initialize payment service: {e}")
            raise
    
    async def _initialize_gateway(self, config: PaymentGatewayConfig):
        """Initialize a specific payment gateway"""
        try:
            gateway_config = config.config or {}
            
            # Create gateway instance based on type
            if config.gateway == PaymentGateway.STRIPE:
                gateway = StripeGateway(gateway_config, config.is_test_mode)
            elif config.gateway == PaymentGateway.SQUARE:
                gateway = SquareGateway(gateway_config, config.is_test_mode)
            elif config.gateway == PaymentGateway.PAYPAL:
                gateway = PayPalGateway(gateway_config, config.is_test_mode)
            else:
                logger.warning(f"Unsupported gateway type: {config.gateway}")
                return
            
            self._gateways[config.gateway] = gateway
            self._gateway_configs[config.gateway] = {
                'fee_percentage': config.fee_percentage,
                'fee_fixed': config.fee_fixed,
                'supports_refunds': config.supports_refunds,
                'supports_partial_refunds': config.supports_partial_refunds,
                'supports_recurring': config.supports_recurring,
                'supports_save_card': config.supports_save_card
            }
            
            logger.info(f"Initialized {config.gateway} gateway (test_mode={config.is_test_mode})")
            
        except Exception as e:
            logger.error(f"Failed to initialize {config.gateway} gateway: {e}")
    
    def get_available_gateways(self) -> List[PaymentGateway]:
        """Get list of available payment gateways"""
        return list(self._gateways.keys())
    
    def get_gateway(self, gateway: PaymentGateway) -> Optional[PaymentGatewayInterface]:
        """Get gateway instance"""
        return self._gateways.get(gateway)
    
    async def create_payment(
        self,
        db: AsyncSession,
        order_id: int,
        gateway: PaymentGateway,
        amount: Decimal,
        currency: str = "USD",
        payment_method_id: Optional[str] = None,
        save_payment_method: bool = False,
        return_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """
        Create a new payment for an order
        
        Args:
            db: Database session
            order_id: Order ID
            gateway: Payment gateway to use
            amount: Payment amount
            currency: Currency code
            payment_method_id: Saved payment method ID (for returning customers)
            save_payment_method: Whether to save payment method for future use
            return_url: URL to redirect after payment (for PayPal, etc.)
            metadata: Additional metadata
            
        Returns:
            Payment record
        """
        try:
            # Get order
            order = await db.get(Order, order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # Validate amount
            if amount <= 0:
                raise ValueError("Payment amount must be positive")
            
            # Get gateway instance
            gateway_instance = self._gateways.get(gateway)
            if not gateway_instance:
                raise ValueError(f"Gateway {gateway} not available")
            
            # Create payment record
            payment = Payment(
                order_id=order_id,
                gateway=gateway,
                amount=amount,
                currency=currency,
                status=PaymentStatus.PENDING,
                customer_id=order.customer_id,
                customer_email=order.customer_email,
                customer_name=order.customer_name,
                metadata=metadata or {}
            )
            
            db.add(payment)
            await db.flush()  # Get payment ID
            
            # Build gateway request
            gateway_request = PaymentRequest(
                amount=amount,
                currency=currency,
                order_id=str(order_id),
                customer_id=str(order.customer_id) if order.customer_id else None,
                customer_email=order.customer_email,
                customer_name=order.customer_name,
                description=f"Order #{order.order_number}",
                statement_descriptor=f"AURA {order.order_number[:15]}",
                payment_method_id=payment_method_id,
                save_payment_method=save_payment_method,
                metadata={
                    'payment_id': payment.payment_id,
                    'order_number': order.order_number,
                    **(metadata or {})
                },
                idempotency_key=payment.payment_id,
                return_url=return_url
            )
            
            # Process with gateway
            response = await gateway_instance.create_payment(gateway_request)
            
            # Update payment record
            payment.gateway_payment_id = response.gateway_payment_id
            payment.status = response.status
            payment.method = response.payment_method
            payment.payment_method_details = response.payment_method_details
            payment.fee_amount = response.fee_amount
            payment.net_amount = response.net_amount
            payment.processed_at = response.processed_at
            
            if not response.success:
                payment.failure_code = response.error_code
                payment.failure_message = response.error_message
            
            # Handle payment methods that require action (3DS, PayPal redirect)
            if response.requires_action:
                payment.metadata['requires_action'] = True
                payment.metadata['action_url'] = response.action_url
            
            await db.commit()
            
            # Update order status if payment succeeded
            if payment.status == PaymentStatus.COMPLETED:
                await self._update_order_payment_status(db, order, payment)
            
            # Clear order cache
            await cache_service.delete(f"order:{order_id}")
            
            return payment
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Payment creation failed: {e}")
            raise
    
    async def capture_payment(
        self,
        db: AsyncSession,
        payment_id: int,
        amount: Optional[Decimal] = None
    ) -> Payment:
        """Capture a previously authorized payment"""
        try:
            # Get payment
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            # Validate status
            if payment.status not in [PaymentStatus.PROCESSING, PaymentStatus.PENDING]:
                raise ValueError(f"Cannot capture payment in status {payment.status}")
            
            # Get gateway
            gateway = self._gateways.get(payment.gateway)
            if not gateway:
                raise ValueError(f"Gateway {payment.gateway} not available")
            
            # Capture with gateway
            response = await gateway.capture_payment(
                payment.gateway_payment_id,
                amount
            )
            
            # Update payment
            if response.success:
                payment.status = response.status
                payment.processed_at = response.processed_at or datetime.utcnow()
                if amount:
                    payment.amount = amount
                
                # Update order if completed
                if payment.status == PaymentStatus.COMPLETED:
                    order = await db.get(Order, payment.order_id)
                    if order:
                        await self._update_order_payment_status(db, order, payment)
            else:
                payment.status = PaymentStatus.FAILED
                payment.failure_code = response.error_code
                payment.failure_message = response.error_message
            
            await db.commit()
            return payment
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Payment capture failed: {e}")
            raise
    
    async def cancel_payment(
        self,
        db: AsyncSession,
        payment_id: int,
        reason: Optional[str] = None
    ) -> Payment:
        """Cancel a pending payment"""
        try:
            # Get payment
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            # Validate status
            if payment.status in [PaymentStatus.COMPLETED, PaymentStatus.REFUNDED]:
                raise ValueError(f"Cannot cancel payment in status {payment.status}")
            
            # Get gateway
            gateway = self._gateways.get(payment.gateway)
            if not gateway:
                raise ValueError(f"Gateway {payment.gateway} not available")
            
            # Cancel with gateway
            response = await gateway.cancel_payment(payment.gateway_payment_id)
            
            # Update payment
            if response.success:
                payment.status = PaymentStatus.CANCELLED
                if reason:
                    payment.metadata['cancellation_reason'] = reason
            else:
                logger.warning(f"Gateway cancellation failed: {response.error_message}")
            
            await db.commit()
            return payment
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Payment cancellation failed: {e}")
            raise
    
    async def create_refund(
        self,
        db: AsyncSession,
        payment_id: int,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
        initiated_by: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Refund:
        """Create a refund for a payment"""
        try:
            # Get payment
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            # Validate payment status
            if payment.status not in [PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED]:
                raise ValueError(f"Cannot refund payment in status {payment.status}")
            
            # Check gateway config
            gateway_config = self._gateway_configs.get(payment.gateway, {})
            if not gateway_config.get('supports_refunds', True):
                raise ValueError(f"Gateway {payment.gateway} does not support refunds")
            
            # Validate refund amount
            if amount:
                if amount <= 0:
                    raise ValueError("Refund amount must be positive")
                
                # Check for existing refunds
                result = await db.execute(
                    select(Refund).where(
                        and_(
                            Refund.payment_id == payment_id,
                            Refund.status.in_([RefundStatus.PENDING, RefundStatus.PROCESSING, RefundStatus.COMPLETED])
                        )
                    )
                )
                existing_refunds = result.scalars().all()
                
                total_refunded = sum(r.amount for r in existing_refunds)
                if total_refunded + amount > payment.amount:
                    raise ValueError(f"Refund amount exceeds payment amount")
                
                if amount < payment.amount and not gateway_config.get('supports_partial_refunds', True):
                    raise ValueError(f"Gateway {payment.gateway} does not support partial refunds")
            else:
                # Full refund
                amount = payment.amount
            
            # Get gateway
            gateway = self._gateways.get(payment.gateway)
            if not gateway:
                raise ValueError(f"Gateway {payment.gateway} not available")
            
            # Create refund record
            refund = Refund(
                payment_id=payment_id,
                gateway=payment.gateway,
                amount=amount,
                currency=payment.currency,
                status=RefundStatus.PENDING,
                reason=reason,
                initiated_by=initiated_by,
                metadata=metadata or {}
            )
            
            db.add(refund)
            await db.flush()
            
            # Process with gateway
            gateway_request = RefundRequest(
                payment_id=payment.gateway_payment_id,
                amount=amount if amount < payment.amount else None,  # None for full refund
                reason=reason,
                metadata={
                    'refund_id': refund.refund_id,
                    'payment_id': payment.payment_id,
                    **(metadata or {})
                },
                idempotency_key=refund.refund_id
            )
            
            response = await gateway.create_refund(gateway_request)
            
            # Update refund record
            refund.gateway_refund_id = response.gateway_refund_id
            refund.status = response.status
            refund.fee_refunded = response.fee_refunded
            refund.processed_at = response.processed_at
            
            if not response.success:
                refund.failure_code = response.error_code
                refund.failure_message = response.error_message
            
            # Update payment status
            if response.status == RefundStatus.COMPLETED:
                if amount == payment.amount:
                    payment.status = PaymentStatus.REFUNDED
                else:
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED
            
            await db.commit()
            
            # Clear caches
            await cache_service.delete(f"payment:{payment_id}")
            await cache_service.delete(f"order:{payment.order_id}")
            
            return refund
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Refund creation failed: {e}")
            raise
    
    async def sync_payment_status(
        self,
        db: AsyncSession,
        payment_id: int
    ) -> Payment:
        """Sync payment status with gateway"""
        try:
            # Get payment
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            # Get gateway
            gateway = self._gateways.get(payment.gateway)
            if not gateway:
                raise ValueError(f"Gateway {payment.gateway} not available")
            
            # Get current status from gateway
            response = await gateway.get_payment(payment.gateway_payment_id)
            
            if response.success:
                # Update if status changed
                if payment.status != response.status:
                    logger.info(f"Payment {payment_id} status changed: {payment.status} -> {response.status}")
                    
                    payment.status = response.status
                    payment.fee_amount = response.fee_amount or payment.fee_amount
                    payment.net_amount = response.net_amount or payment.net_amount
                    
                    # Update order if payment completed
                    if response.status == PaymentStatus.COMPLETED:
                        order = await db.get(Order, payment.order_id)
                        if order:
                            await self._update_order_payment_status(db, order, payment)
                    
                    await db.commit()
            
            return payment
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Payment sync failed: {e}")
            raise
    
    async def save_payment_method(
        self,
        db: AsyncSession,
        customer_id: int,
        gateway: PaymentGateway,
        payment_method_token: str,
        set_as_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CustomerPaymentMethod:
        """Save a payment method for future use"""
        try:
            # Check gateway support
            gateway_config = self._gateway_configs.get(gateway, {})
            if not gateway_config.get('supports_save_card', True):
                raise ValueError(f"Gateway {gateway} does not support saving payment methods")
            
            # Get gateway instance
            gateway_instance = self._gateways.get(gateway)
            if not gateway_instance:
                raise ValueError(f"Gateway {gateway} not available")
            
            # Get or create gateway customer
            gateway_customer_id = await self._ensure_gateway_customer(
                db, customer_id, gateway, gateway_instance
            )
            
            # Save with gateway
            request = PaymentMethodRequest(
                customer_id=gateway_customer_id,
                payment_method_token=payment_method_token,
                set_as_default=set_as_default,
                metadata=metadata
            )
            
            response = await gateway_instance.save_payment_method(request)
            
            if not response.success:
                raise Exception(f"Failed to save payment method: {response.error_message}")
            
            # Create database record
            payment_method = CustomerPaymentMethod(
                customer_id=customer_id,
                gateway=gateway,
                gateway_payment_method_id=response.gateway_payment_method_id,
                gateway_customer_id=gateway_customer_id,
                method_type=response.method_type,
                display_name=response.display_name,
                is_default=set_as_default,
                metadata=metadata or {}
            )
            
            # Extract card details if available
            if response.card_details:
                payment_method.card_last4 = response.card_details.get('last4')
                payment_method.card_brand = response.card_details.get('brand')
                payment_method.card_exp_month = response.card_details.get('exp_month')
                payment_method.card_exp_year = response.card_details.get('exp_year')
            
            # Update other default methods if needed
            if set_as_default:
                await db.execute(
                    select(CustomerPaymentMethod).where(
                        and_(
                            CustomerPaymentMethod.customer_id == customer_id,
                            CustomerPaymentMethod.is_default == True,
                            CustomerPaymentMethod.gateway == gateway
                        )
                    ).update(is_default=False)
                )
            
            db.add(payment_method)
            await db.commit()
            
            return payment_method
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Save payment method failed: {e}")
            raise
    
    async def list_customer_payment_methods(
        self,
        db: AsyncSession,
        customer_id: int,
        gateway: Optional[PaymentGateway] = None,
        active_only: bool = True
    ) -> List[CustomerPaymentMethod]:
        """List saved payment methods for a customer"""
        query = select(CustomerPaymentMethod).where(
            CustomerPaymentMethod.customer_id == customer_id
        )
        
        if gateway:
            query = query.where(CustomerPaymentMethod.gateway == gateway)
        
        if active_only:
            query = query.where(CustomerPaymentMethod.is_active == True)
        
        result = await db.execute(query.order_by(
            CustomerPaymentMethod.is_default.desc(),
            CustomerPaymentMethod.created_at.desc()
        ))
        
        return result.scalars().all()
    
    async def delete_payment_method(
        self,
        db: AsyncSession,
        payment_method_id: int
    ) -> bool:
        """Delete a saved payment method"""
        try:
            # Get payment method
            payment_method = await db.get(CustomerPaymentMethod, payment_method_id)
            if not payment_method:
                return False
            
            # Get gateway
            gateway = self._gateways.get(payment_method.gateway)
            if gateway:
                # Delete from gateway
                success = await gateway.delete_payment_method(
                    payment_method.gateway_payment_method_id
                )
                if not success:
                    logger.warning(f"Failed to delete payment method from gateway")
            
            # Soft delete in database
            payment_method.is_active = False
            await db.commit()
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Delete payment method failed: {e}")
            return False
    
    def get_public_gateway_config(self, gateway: PaymentGateway) -> Dict[str, Any]:
        """Get public configuration for frontend"""
        gateway_instance = self._gateways.get(gateway)
        if not gateway_instance:
            return {}
        
        config = gateway_instance.get_public_config()
        
        # Add gateway features
        gateway_config = self._gateway_configs.get(gateway, {})
        config['features'] = {
            'supports_refunds': gateway_config.get('supports_refunds', True),
            'supports_partial_refunds': gateway_config.get('supports_partial_refunds', True),
            'supports_recurring': gateway_config.get('supports_recurring', False),
            'supports_save_card': gateway_config.get('supports_save_card', True)
        }
        
        return config
    
    # Helper methods
    
    async def _update_order_payment_status(
        self,
        db: AsyncSession,
        order: Order,
        payment: Payment
    ):
        """Update order status based on payment"""
        try:
            # Calculate total paid
            result = await db.execute(
                select(Payment).where(
                    and_(
                        Payment.order_id == order.id,
                        Payment.status == PaymentStatus.COMPLETED
                    )
                )
            )
            payments = result.scalars().all()
            
            total_paid = sum(p.amount for p in payments)
            
            # Update order payment status
            if total_paid >= order.total_amount:
                order.payment_status = 'paid'
                if order.status == OrderStatus.PENDING:
                    order.status = OrderStatus.CONFIRMED
            else:
                order.payment_status = 'partial'
            
            # Store payment info
            order.metadata['last_payment_id'] = payment.payment_id
            order.metadata['last_payment_date'] = payment.processed_at.isoformat()
            
        except Exception as e:
            logger.error(f"Failed to update order payment status: {e}")
    
    async def _ensure_gateway_customer(
        self,
        db: AsyncSession,
        customer_id: int,
        gateway: PaymentGateway,
        gateway_instance: PaymentGatewayInterface
    ) -> str:
        """Ensure customer exists at gateway and return gateway customer ID"""
        # Check if we have existing gateway customer ID
        result = await db.execute(
            select(CustomerPaymentMethod).where(
                and_(
                    CustomerPaymentMethod.customer_id == customer_id,
                    CustomerPaymentMethod.gateway == gateway
                )
            ).limit(1)
        )
        existing = result.scalar_one_or_none()
        
        if existing and existing.gateway_customer_id:
            return existing.gateway_customer_id
        
        # Get customer details
        from ...customers.models.customer_models import Customer
        customer = await db.get(Customer, customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Create at gateway
        request = CustomerRequest(
            customer_id=str(customer_id),
            email=customer.email,
            name=customer.name,
            phone=customer.phone
        )
        
        response = await gateway_instance.create_customer(request)
        if not response.success:
            raise Exception(f"Failed to create gateway customer: {response.error_message}")
        
        return response.gateway_customer_id


# Global service instance
payment_service = PaymentService()


# Initialize on startup
async def initialize_payment_service():
    """Initialize payment service on application startup"""
    async for db in get_db():
        await payment_service.initialize(db)
        break