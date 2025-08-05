# backend/modules/payments/gateways/square_gateway.py

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
import uuid
import json
import hmac
import hashlib
from square import Square as Client
from square.models import (
    CreatePaymentRequest, CreatePaymentResponse,
    CreateRefundRequest, CreateCustomerRequest,
    CreateCardRequest, Money
)

from .base import (
    PaymentGatewayInterface, PaymentRequest, PaymentResponse,
    RefundRequest, RefundResponse, CustomerRequest, CustomerResponse,
    PaymentMethodRequest, PaymentMethodResponse
)
from ..models.payment_models import PaymentStatus, PaymentMethod, RefundStatus


logger = logging.getLogger(__name__)


class SquareGateway(PaymentGatewayInterface):
    """Square payment gateway implementation"""
    
    def __init__(self, config: Dict[str, Any], test_mode: bool = True):
        super().__init__(config, test_mode)
        
        # Initialize Square client
        environment = 'sandbox' if test_mode else 'production'
        self.client = Client(
            access_token=config.get('access_token'),
            environment=environment
        )
        
        # Store location ID (required for Square)
        self.location_id = config.get('location_id')
        if not self.location_id:
            raise ValueError("Square location_id is required")
        
        # Store webhook signature key
        self.webhook_signature_key = config.get('webhook_signature_key')
    
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Create a payment with Square"""
        try:
            # Convert amount to cents
            amount_cents = self.format_amount(request.amount, request.currency)
            
            # Create money object
            amount_money = Money(
                amount=amount_cents,
                currency=request.currency
            )
            
            # Build payment request
            payment_request = CreatePaymentRequest(
                source_id=request.payment_method_id,  # This would be a nonce from Square Web Payments SDK
                idempotency_key=request.idempotency_key or str(uuid.uuid4()),
                amount_money=amount_money,
                location_id=self.location_id,
                reference_id=str(request.order_id),
                note=request.description,
                buyer_email_address=request.customer_email
            )
            
            # Add customer if available
            if request.customer_id:
                # Try to get existing Square customer
                customer = await self._get_or_create_customer(request)
                if customer:
                    payment_request.customer_id = customer['id']
            
            # Create payment
            result = self.client.payments.create_payment(payment_request)
            
            if result.is_error():
                errors = result.errors if result.errors else []
                error_message = ', '.join([e.detail for e in errors]) if errors else 'Unknown error'
                return PaymentResponse(
                    success=False,
                    status=PaymentStatus.FAILED,
                    error_code='payment_failed',
                    error_message=error_message
                )
            
            payment = result.body.get('payment', {})
            
            # Calculate fees (will be available after settlement)
            fee, net = self.calculate_fee(request.amount)
            
            # Map Square status
            status = self._map_square_status(payment.get('status'))
            
            # Extract payment details
            card_details = payment.get('card_details', {})
            payment_method_details = None
            if card_details:
                payment_method_details = {
                    'last4': card_details.get('card', {}).get('last_4'),
                    'brand': card_details.get('card', {}).get('card_brand'),
                    'exp_month': card_details.get('card', {}).get('exp_month'),
                    'exp_year': card_details.get('card', {}).get('exp_year')
                }
            
            return PaymentResponse(
                success=True,
                gateway_payment_id=payment.get('id'),
                status=status,
                amount=request.amount,
                currency=request.currency,
                fee_amount=fee,
                net_amount=net,
                payment_method=PaymentMethod.CARD,
                payment_method_details=payment_method_details,
                processed_at=self._parse_timestamp(payment.get('created_at')),
                raw_response=payment
            )
            
        except Exception as e:
            logger.error(f"Square payment error: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code='payment_error',
                error_message=str(e)
            )
    
    async def capture_payment(self, payment_id: str, amount: Optional[Decimal] = None) -> PaymentResponse:
        """Capture a payment (Square captures immediately, so this just retrieves)"""
        return await self.get_payment(payment_id)
    
    async def get_payment(self, payment_id: str) -> PaymentResponse:
        """Get payment details from Square"""
        try:
            result = self.client.payments.get_payment(payment_id)
            
            if result.is_error():
                return PaymentResponse(
                    success=False,
                    error_code='get_payment_error',
                    error_message='Payment not found'
                )
            
            payment = result.body.get('payment', {})
            
            # Extract fee information if available
            fee_amount = None
            net_amount = None
            processing_fee = payment.get('processing_fee')
            if processing_fee:
                fee_money = processing_fee[0].get('amount_money', {})
                fee_amount = self.parse_amount(fee_money.get('amount', 0), fee_money.get('currency', 'USD'))
                
                amount_money = payment.get('amount_money', {})
                total = self.parse_amount(amount_money.get('amount', 0), amount_money.get('currency', 'USD'))
                net_amount = total - fee_amount
            
            return PaymentResponse(
                success=True,
                gateway_payment_id=payment.get('id'),
                status=self._map_square_status(payment.get('status')),
                amount=self.parse_amount(
                    payment.get('amount_money', {}).get('amount', 0),
                    payment.get('amount_money', {}).get('currency', 'USD')
                ),
                currency=payment.get('amount_money', {}).get('currency', 'USD'),
                fee_amount=fee_amount,
                net_amount=net_amount,
                processed_at=self._parse_timestamp(payment.get('created_at')),
                raw_response=payment
            )
            
        except Exception as e:
            logger.error(f"Square get payment error: {e}")
            return PaymentResponse(
                success=False,
                error_code='get_payment_error',
                error_message=str(e)
            )
    
    async def cancel_payment(self, payment_id: str) -> PaymentResponse:
        """Cancel a payment"""
        try:
            result = self.client.payments.cancel_payment(payment_id)
            
            if result.is_error():
                return PaymentResponse(
                    success=False,
                    error_code='cancel_error',
                    error_message='Could not cancel payment'
                )
            
            payment = result.body.get('payment', {})
            
            return PaymentResponse(
                success=True,
                gateway_payment_id=payment.get('id'),
                status=PaymentStatus.CANCELLED,
                raw_response=payment
            )
            
        except Exception as e:
            logger.error(f"Square cancel error: {e}")
            return PaymentResponse(
                success=False,
                error_code='cancel_error',
                error_message=str(e)
            )
    
    async def create_refund(self, request: RefundRequest) -> RefundResponse:
        """Create a refund in Square"""
        try:
            # Get payment to determine amount
            payment_result = self.client.payments.get_payment(request.payment_id)
            if payment_result.is_error():
                return RefundResponse(
                    success=False,
                    status=RefundStatus.FAILED,
                    error_code='payment_not_found',
                    error_message='Original payment not found'
                )
            
            payment = payment_result.body.get('payment', {})
            payment_amount = payment.get('amount_money', {})
            
            # Determine refund amount
            if request.amount:
                amount_cents = self.format_amount(request.amount, payment_amount.get('currency', 'USD'))
            else:
                # Full refund
                amount_cents = payment_amount.get('amount', 0)
            
            # Create refund request
            refund_request = CreateRefundRequest(
                idempotency_key=request.idempotency_key or str(uuid.uuid4()),
                payment_id=request.payment_id,
                amount_money=Money(
                    amount=amount_cents,
                    currency=payment_amount.get('currency', 'USD')
                ),
                reason=request.reason
            )
            
            result = self.client.refunds.refund_payment(refund_request)
            
            if result.is_error():
                errors = result.errors if result.errors else []
                error_message = ', '.join([e.detail for e in errors]) if errors else 'Unknown error'
                return RefundResponse(
                    success=False,
                    status=RefundStatus.FAILED,
                    error_code='refund_failed',
                    error_message=error_message
                )
            
            refund = result.body.get('refund', {})
            
            return RefundResponse(
                success=True,
                gateway_refund_id=refund.get('id'),
                status=self._map_refund_status(refund.get('status')),
                amount=self.parse_amount(
                    refund.get('amount_money', {}).get('amount', 0),
                    refund.get('amount_money', {}).get('currency', 'USD')
                ),
                currency=refund.get('amount_money', {}).get('currency', 'USD'),
                processed_at=self._parse_timestamp(refund.get('created_at')),
                raw_response=refund
            )
            
        except Exception as e:
            logger.error(f"Square refund error: {e}")
            return RefundResponse(
                success=False,
                status=RefundStatus.FAILED,
                error_code='refund_error',
                error_message=str(e)
            )
    
    async def get_refund(self, refund_id: str) -> RefundResponse:
        """Get refund details"""
        try:
            result = self.client.refunds.get_payment_refund(refund_id)
            
            if result.is_error():
                return RefundResponse(
                    success=False,
                    error_code='get_refund_error',
                    error_message='Refund not found'
                )
            
            refund = result.body.get('refund', {})
            
            return RefundResponse(
                success=True,
                gateway_refund_id=refund.get('id'),
                status=self._map_refund_status(refund.get('status')),
                amount=self.parse_amount(
                    refund.get('amount_money', {}).get('amount', 0),
                    refund.get('amount_money', {}).get('currency', 'USD')
                ),
                currency=refund.get('amount_money', {}).get('currency', 'USD'),
                processed_at=self._parse_timestamp(refund.get('created_at')),
                raw_response=refund
            )
            
        except Exception as e:
            logger.error(f"Square get refund error: {e}")
            return RefundResponse(
                success=False,
                error_code='get_refund_error',
                error_message=str(e)
            )
    
    async def create_customer(self, request: CustomerRequest) -> CustomerResponse:
        """Create a Square customer"""
        try:
            customer_request = CreateCustomerRequest(
                given_name=request.name.split()[0] if request.name else None,
                family_name=' '.join(request.name.split()[1:]) if request.name and len(request.name.split()) > 1 else None,
                email_address=request.email,
                phone_number=request.phone,
                reference_id=str(request.customer_id),
                note=f"Customer ID: {request.customer_id}"
            )
            
            result = self.client.customers.create_customer(customer_request)
            
            if result.is_error():
                return CustomerResponse(
                    success=False,
                    error_code='create_customer_error',
                    error_message='Could not create customer'
                )
            
            customer = result.body.get('customer', {})
            
            return CustomerResponse(
                success=True,
                gateway_customer_id=customer.get('id')
            )
            
        except Exception as e:
            logger.error(f"Square create customer error: {e}")
            return CustomerResponse(
                success=False,
                error_code='create_customer_error',
                error_message=str(e)
            )
    
    async def update_customer(self, gateway_customer_id: str, request: CustomerRequest) -> CustomerResponse:
        """Update a Square customer"""
        try:
            # Square requires all fields to be provided in update
            # First get existing customer
            get_result = self.client.customers.retrieve_customer(gateway_customer_id)
            if get_result.is_error():
                return CustomerResponse(
                    success=False,
                    error_code='customer_not_found',
                    error_message='Customer not found'
                )
            
            existing = get_result.body.get('customer', {})
            
            # Build update request with merged data
            update_request = {
                'given_name': request.name.split()[0] if request.name else existing.get('given_name'),
                'family_name': ' '.join(request.name.split()[1:]) if request.name and len(request.name.split()) > 1 else existing.get('family_name'),
                'email_address': request.email or existing.get('email_address'),
                'phone_number': request.phone or existing.get('phone_number')
            }
            
            result = self.client.customers.update_customer(gateway_customer_id, update_request)
            
            if result.is_error():
                return CustomerResponse(
                    success=False,
                    error_code='update_customer_error',
                    error_message='Could not update customer'
                )
            
            return CustomerResponse(
                success=True,
                gateway_customer_id=gateway_customer_id
            )
            
        except Exception as e:
            logger.error(f"Square update customer error: {e}")
            return CustomerResponse(
                success=False,
                error_code='update_customer_error',
                error_message=str(e)
            )
    
    async def save_payment_method(self, request: PaymentMethodRequest) -> PaymentMethodResponse:
        """Save a payment method (card on file)"""
        try:
            # Create card request
            card_request = CreateCardRequest(
                idempotency_key=str(uuid.uuid4()),
                source_id=request.payment_method_token,  # Card nonce from Square Web Payments SDK
                card={
                    'customer_id': request.customer_id
                }
            )
            
            result = self.client.cards.create_card(card_request)
            
            if result.is_error():
                return PaymentMethodResponse(
                    success=False,
                    error_code='save_card_error',
                    error_message='Could not save card'
                )
            
            card = result.body.get('card', {})
            
            return PaymentMethodResponse(
                success=True,
                gateway_payment_method_id=card.get('id'),
                method_type=PaymentMethod.CARD,
                display_name=f"{card.get('card_brand', 'Card')} ending in {card.get('last_4', '****')}",
                card_details={
                    'last4': card.get('last_4'),
                    'brand': card.get('card_brand'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year')
                }
            )
            
        except Exception as e:
            logger.error(f"Square save payment method error: {e}")
            return PaymentMethodResponse(
                success=False,
                error_code='save_payment_method_error',
                error_message=str(e)
            )
    
    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Delete a saved card"""
        try:
            result = self.client.cards.disable_card(payment_method_id)
            return not result.is_error()
        except Exception as e:
            logger.error(f"Square delete payment method error: {e}")
            return False
    
    async def list_payment_methods(self, customer_id: str) -> List[PaymentMethodResponse]:
        """List cards on file for a customer"""
        try:
            result = self.client.cards.list_cards(
                customer_id=customer_id,
                include_disabled=False
            )
            
            if result.is_error():
                return []
            
            cards = result.body.get('cards', [])
            responses = []
            
            for card in cards:
                responses.append(PaymentMethodResponse(
                    success=True,
                    gateway_payment_method_id=card.get('id'),
                    method_type=PaymentMethod.CARD,
                    display_name=f"{card.get('card_brand', 'Card')} ending in {card.get('last_4', '****')}",
                    card_details={
                        'last4': card.get('last_4'),
                        'brand': card.get('card_brand'),
                        'exp_month': card.get('exp_month'),
                        'exp_year': card.get('exp_year')
                    }
                ))
            
            return responses
            
        except Exception as e:
            logger.error(f"Square list payment methods error: {e}")
            return []
    
    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify Square webhook signature"""
        try:
            signature = headers.get('x-square-signature')
            if not signature or not self.webhook_signature_key:
                return False, None
            
            # Calculate expected signature
            string_to_sign = self.webhook_signature_key + body.decode('utf-8')
            expected_signature = hmac.new(
                self.webhook_signature_key.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            if not hmac.compare_digest(signature, expected_signature):
                return False, None
            
            # Parse body
            try:
                payload = json.loads(body)
                return True, payload
            except json.JSONDecodeError:
                return False, None
            
        except Exception as e:
            logger.error(f"Square webhook verification error: {e}")
            return False, None
    
    def get_public_config(self) -> Dict[str, Any]:
        """Get public Square configuration"""
        return {
            'application_id': self.config.get('application_id'),
            'location_id': self.location_id,
            'test_mode': self.test_mode
        }
    
    # Helper methods
    
    async def _get_or_create_customer(self, request: PaymentRequest) -> Optional[Dict[str, Any]]:
        """Get existing Square customer or create new one"""
        if not request.customer_id:
            return None
        
        try:
            # Search for existing customer by reference_id
            result = self.client.customers.search_customers({
                'filter': {
                    'reference_id': {
                        'exact': str(request.customer_id)
                    }
                }
            })
            
            if not result.is_error() and result.body.get('customers'):
                return result.body['customers'][0]
            
            # Create new customer
            customer_request = CustomerRequest(
                customer_id=request.customer_id,
                email=request.customer_email,
                name=request.customer_name
            )
            
            response = await self.create_customer(customer_request)
            if response.success:
                # Retrieve the created customer
                get_result = self.client.customers.retrieve_customer(response.gateway_customer_id)
                if not get_result.is_error():
                    return get_result.body.get('customer')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting/creating Square customer: {e}")
            return None
    
    def _map_square_status(self, square_status: str) -> PaymentStatus:
        """Map Square payment status to our status"""
        mapping = {
            'APPROVED': PaymentStatus.PROCESSING,
            'PENDING': PaymentStatus.PENDING,
            'COMPLETED': PaymentStatus.COMPLETED,
            'CANCELED': PaymentStatus.CANCELLED,
            'FAILED': PaymentStatus.FAILED
        }
        return mapping.get(square_status, PaymentStatus.PENDING)
    
    def _map_refund_status(self, square_status: str) -> RefundStatus:
        """Map Square refund status to our status"""
        mapping = {
            'PENDING': RefundStatus.PENDING,
            'APPROVED': RefundStatus.PROCESSING,
            'COMPLETED': RefundStatus.COMPLETED,
            'REJECTED': RefundStatus.FAILED,
            'FAILED': RefundStatus.FAILED
        }
        return mapping.get(square_status, RefundStatus.PENDING)
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse Square timestamp string to datetime"""
        if not timestamp_str:
            return None
        
        try:
            # Square uses RFC3339 format
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception:
            return None