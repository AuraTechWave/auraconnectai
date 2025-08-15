# backend/modules/payments/gateways/stripe_gateway.py

import stripe
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
import json

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
from ..models.payment_models import PaymentStatus, PaymentMethod, RefundStatus
from ..utils import payment_retry


logger = logging.getLogger(__name__)


class StripeGateway(PaymentGatewayInterface):
    """Stripe payment gateway implementation"""

    def __init__(self, config: Dict[str, Any], test_mode: bool = True):
        super().__init__(config, test_mode)

        # Set Stripe API key
        stripe.api_key = config.get("secret_key")

        # Configure Stripe
        stripe.api_version = "2023-10-16"
        stripe.max_network_retries = 2

        # Store webhook secret
        self.webhook_secret = config.get("webhook_secret")

    @payment_retry(max_attempts=3)
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Create a payment with Stripe"""
        try:
            # Convert amount to cents
            amount_cents = self.format_amount(request.amount, request.currency)

            # Build payment intent parameters
            params = {
                "amount": amount_cents,
                "currency": request.currency.lower(),
                "description": request.description,
                "metadata": {
                    "order_id": str(request.order_id),
                    "customer_id": (
                        str(request.customer_id) if request.customer_id else None
                    ),
                    **(request.metadata or {}),
                },
            }

            # Add customer if available
            if request.customer_id:
                # Try to get existing Stripe customer
                customer = await self._get_or_create_customer(request)
                if customer:
                    params["customer"] = customer.id

            # Add payment method if provided
            if request.payment_method_id:
                params["payment_method"] = request.payment_method_id
                params["confirm"] = True  # Automatically confirm
                params["off_session"] = True  # For saved cards
            else:
                # For new payments, don't confirm yet
                params["automatic_payment_methods"] = {"enabled": True}

            # Add statement descriptor
            if request.statement_descriptor:
                params["statement_descriptor"] = request.statement_descriptor[
                    :22
                ]  # Stripe limit

            # Add return URL for redirect-based payments
            if request.return_url:
                params["return_url"] = request.return_url

            # Set idempotency key
            idempotency_key = request.idempotency_key

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                **params, idempotency_key=idempotency_key
            )

            # Calculate fees (estimate for now)
            fee, net = self.calculate_fee(request.amount)

            # Map Stripe status to our status
            status = self._map_stripe_status(intent.status)

            # Check if requires action
            requires_action = intent.status == "requires_action"
            action_url = None
            if requires_action and intent.next_action:
                if intent.next_action.type == "redirect_to_url":
                    action_url = intent.next_action.redirect_to_url.url

            # Extract payment method details
            payment_method_details = None
            payment_method_type = None
            if intent.payment_method:
                pm = stripe.PaymentMethod.retrieve(intent.payment_method)
                payment_method_type = self._map_payment_method(pm.type)
                payment_method_details = self._extract_payment_method_details(pm)

            return PaymentResponse(
                success=True,
                gateway_payment_id=intent.id,
                status=status,
                amount=request.amount,
                currency=request.currency,
                fee_amount=fee,
                net_amount=net,
                payment_method=payment_method_type,
                payment_method_details=payment_method_details,
                processed_at=(
                    datetime.fromtimestamp(intent.created) if intent.created else None
                ),
                requires_action=requires_action,
                action_url=action_url,
                raw_response=intent.to_dict(),
            )

        except stripe.error.CardError as e:
            # Card was declined
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code=e.code,
                error_message=e.user_message,
                raw_response={"error": e.json_body},
            )
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters
            logger.error(f"Stripe invalid request: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code="invalid_request",
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Stripe payment error: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code="payment_error",
                error_message=str(e),
            )

    @payment_retry(max_attempts=3)
    async def capture_payment(
        self, payment_id: str, amount: Optional[Decimal] = None
    ) -> PaymentResponse:
        """Capture a previously authorized payment"""
        try:
            params = {}
            if amount:
                params["amount_to_capture"] = self.format_amount(amount, "USD")

            intent = stripe.PaymentIntent.capture(payment_id, **params)

            return PaymentResponse(
                success=True,
                gateway_payment_id=intent.id,
                status=self._map_stripe_status(intent.status),
                amount=self.parse_amount(intent.amount_received, intent.currency),
                currency=intent.currency.upper(),
                processed_at=datetime.now(),
                raw_response=intent.to_dict(),
            )

        except Exception as e:
            logger.error(f"Stripe capture error: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code="capture_error",
                error_message=str(e),
            )

    async def get_payment(self, payment_id: str) -> PaymentResponse:
        """Get payment details from Stripe"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_id)

            # Extract charge details for fees
            fee_amount = None
            net_amount = None
            if intent.charges and intent.charges.data:
                charge = intent.charges.data[0]
                if charge.balance_transaction:
                    txn = stripe.BalanceTransaction.retrieve(charge.balance_transaction)
                    fee_amount = self.parse_amount(txn.fee, txn.currency)
                    net_amount = self.parse_amount(txn.net, txn.currency)

            return PaymentResponse(
                success=True,
                gateway_payment_id=intent.id,
                status=self._map_stripe_status(intent.status),
                amount=self.parse_amount(intent.amount, intent.currency),
                currency=intent.currency.upper(),
                fee_amount=fee_amount,
                net_amount=net_amount,
                processed_at=(
                    datetime.fromtimestamp(intent.created) if intent.created else None
                ),
                raw_response=intent.to_dict(),
            )

        except Exception as e:
            logger.error(f"Stripe get payment error: {e}")
            return PaymentResponse(
                success=False, error_code="get_payment_error", error_message=str(e)
            )

    async def cancel_payment(self, payment_id: str) -> PaymentResponse:
        """Cancel a payment intent"""
        try:
            intent = stripe.PaymentIntent.cancel(payment_id)

            return PaymentResponse(
                success=True,
                gateway_payment_id=intent.id,
                status=PaymentStatus.CANCELLED,
                raw_response=intent.to_dict(),
            )

        except Exception as e:
            logger.error(f"Stripe cancel error: {e}")
            return PaymentResponse(
                success=False, error_code="cancel_error", error_message=str(e)
            )

    @payment_retry(max_attempts=3)
    async def create_refund(self, request: RefundRequest) -> RefundResponse:
        """Create a refund in Stripe"""
        try:
            params = {
                "payment_intent": request.payment_id,
                "reason": self._map_refund_reason(request.reason),
                "metadata": request.metadata or {},
            }

            if request.amount:
                params["amount"] = self.format_amount(request.amount, "USD")

            refund = stripe.Refund.create(
                **params, idempotency_key=request.idempotency_key
            )

            return RefundResponse(
                success=True,
                gateway_refund_id=refund.id,
                status=self._map_refund_status(refund.status),
                amount=self.parse_amount(refund.amount, refund.currency),
                currency=refund.currency.upper(),
                processed_at=(
                    datetime.fromtimestamp(refund.created) if refund.created else None
                ),
                raw_response=refund.to_dict(),
            )

        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return RefundResponse(
                success=False,
                status=RefundStatus.FAILED,
                error_code="refund_error",
                error_message=str(e),
            )

    async def get_refund(self, refund_id: str) -> RefundResponse:
        """Get refund details"""
        try:
            refund = stripe.Refund.retrieve(refund_id)

            return RefundResponse(
                success=True,
                gateway_refund_id=refund.id,
                status=self._map_refund_status(refund.status),
                amount=self.parse_amount(refund.amount, refund.currency),
                currency=refund.currency.upper(),
                processed_at=(
                    datetime.fromtimestamp(refund.created) if refund.created else None
                ),
                raw_response=refund.to_dict(),
            )

        except Exception as e:
            logger.error(f"Stripe get refund error: {e}")
            return RefundResponse(
                success=False, error_code="get_refund_error", error_message=str(e)
            )

    async def create_customer(self, request: CustomerRequest) -> CustomerResponse:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=request.email,
                name=request.name,
                phone=request.phone,
                metadata={
                    "customer_id": str(request.customer_id),
                    **(request.metadata or {}),
                },
            )

            return CustomerResponse(success=True, gateway_customer_id=customer.id)

        except Exception as e:
            logger.error(f"Stripe create customer error: {e}")
            return CustomerResponse(
                success=False, error_code="create_customer_error", error_message=str(e)
            )

    async def update_customer(
        self, gateway_customer_id: str, request: CustomerRequest
    ) -> CustomerResponse:
        """Update a Stripe customer"""
        try:
            params = {}
            if request.email:
                params["email"] = request.email
            if request.name:
                params["name"] = request.name
            if request.phone:
                params["phone"] = request.phone
            if request.metadata:
                params["metadata"] = request.metadata

            customer = stripe.Customer.modify(gateway_customer_id, **params)

            return CustomerResponse(success=True, gateway_customer_id=customer.id)

        except Exception as e:
            logger.error(f"Stripe update customer error: {e}")
            return CustomerResponse(
                success=False, error_code="update_customer_error", error_message=str(e)
            )

    async def save_payment_method(
        self, request: PaymentMethodRequest
    ) -> PaymentMethodResponse:
        """Save a payment method to a customer"""
        try:
            # Attach payment method to customer
            pm = stripe.PaymentMethod.attach(
                request.payment_method_token, customer=request.customer_id
            )

            # Set as default if requested
            if request.set_as_default:
                stripe.Customer.modify(
                    request.customer_id,
                    invoice_settings={"default_payment_method": pm.id},
                )

            # Extract details
            method_type = self._map_payment_method(pm.type)
            display_name = self._get_display_name(pm)
            card_details = self._extract_payment_method_details(pm)

            return PaymentMethodResponse(
                success=True,
                gateway_payment_method_id=pm.id,
                method_type=method_type,
                display_name=display_name,
                card_details=card_details,
            )

        except Exception as e:
            logger.error(f"Stripe save payment method error: {e}")
            return PaymentMethodResponse(
                success=False,
                error_code="save_payment_method_error",
                error_message=str(e),
            )

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Delete a payment method"""
        try:
            stripe.PaymentMethod.detach(payment_method_id)
            return True
        except Exception as e:
            logger.error(f"Stripe delete payment method error: {e}")
            return False

    async def list_payment_methods(
        self, customer_id: str
    ) -> List[PaymentMethodResponse]:
        """List payment methods for a customer"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id, type="card"  # Can be expanded to other types
            )

            responses = []
            for pm in payment_methods.data:
                responses.append(
                    PaymentMethodResponse(
                        success=True,
                        gateway_payment_method_id=pm.id,
                        method_type=self._map_payment_method(pm.type),
                        display_name=self._get_display_name(pm),
                        card_details=self._extract_payment_method_details(pm),
                    )
                )

            return responses

        except Exception as e:
            logger.error(f"Stripe list payment methods error: {e}")
            return []

    async def verify_webhook(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify Stripe webhook signature"""
        try:
            sig_header = headers.get("stripe-signature")
            if not sig_header or not self.webhook_secret:
                return False, None

            event = stripe.Webhook.construct_event(
                body, sig_header, self.webhook_secret
            )

            return True, event

        except ValueError:
            # Invalid payload
            return False, None
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return False, None

    def get_public_config(self) -> Dict[str, Any]:
        """Get public Stripe configuration"""
        return {
            "publishable_key": self.config.get("publishable_key"),
            "test_mode": self.test_mode,
        }

    # Helper methods

    async def _get_or_create_customer(self, request: PaymentRequest) -> Optional[Any]:
        """Get existing Stripe customer or create new one"""
        if not request.customer_id:
            return None

        try:
            # Search for existing customer by metadata
            customers = stripe.Customer.list(email=request.customer_email, limit=1)

            if customers.data:
                return customers.data[0]

            # Create new customer
            customer_request = CustomerRequest(
                customer_id=request.customer_id,
                email=request.customer_email,
                name=request.customer_name,
            )

            response = await self.create_customer(customer_request)
            if response.success:
                return stripe.Customer.retrieve(response.gateway_customer_id)

            return None

        except Exception as e:
            logger.error(f"Error getting/creating Stripe customer: {e}")
            return None

    def _map_stripe_status(self, stripe_status: str) -> PaymentStatus:
        """Map Stripe payment intent status to our status"""
        mapping = {
            "requires_payment_method": PaymentStatus.PENDING,
            "requires_confirmation": PaymentStatus.PENDING,
            "requires_action": PaymentStatus.REQUIRES_ACTION,
            "processing": PaymentStatus.PROCESSING,
            "requires_capture": PaymentStatus.PROCESSING,
            "canceled": PaymentStatus.CANCELLED,
            "succeeded": PaymentStatus.COMPLETED,
            "failed": PaymentStatus.FAILED,
        }
        return mapping.get(stripe_status, PaymentStatus.PENDING)

    def _map_refund_status(self, stripe_status: str) -> RefundStatus:
        """Map Stripe refund status to our status"""
        mapping = {
            "pending": RefundStatus.PENDING,
            "succeeded": RefundStatus.COMPLETED,
            "failed": RefundStatus.FAILED,
            "canceled": RefundStatus.CANCELLED,
        }
        return mapping.get(stripe_status, RefundStatus.PENDING)

    def _map_payment_method(self, stripe_type: str) -> PaymentMethod:
        """Map Stripe payment method type to our type"""
        mapping = {
            "card": PaymentMethod.CARD,
            "bank_transfer": PaymentMethod.BANK_TRANSFER,
            "apple_pay": PaymentMethod.WALLET,
            "google_pay": PaymentMethod.WALLET,
        }
        return mapping.get(stripe_type, PaymentMethod.CARD)

    def _map_refund_reason(self, reason: Optional[str]) -> str:
        """Map our refund reason to Stripe reason"""
        if not reason:
            return "requested_by_customer"

        reason_lower = reason.lower()
        if "duplicate" in reason_lower:
            return "duplicate"
        elif "fraud" in reason_lower:
            return "fraudulent"
        else:
            return "requested_by_customer"

    def _extract_payment_method_details(self, pm: Any) -> Dict[str, Any]:
        """Extract payment method details from Stripe PaymentMethod"""
        details = {}

        if pm.type == "card" and pm.card:
            details = {
                "last4": pm.card.last4,
                "brand": pm.card.brand,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "funding": pm.card.funding,
            }

        return details

    def _get_display_name(self, pm: Any) -> str:
        """Get display name for payment method"""
        if pm.type == "card" and pm.card:
            return f"{pm.card.brand.title()} ending in {pm.card.last4}"
        return pm.type.replace("_", " ").title()
