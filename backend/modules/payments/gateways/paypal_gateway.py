# backend/modules/payments/gateways/paypal_gateway.py

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
import uuid
import json
import base64
import hashlib
import hmac
from urllib.parse import parse_qs
import httpx

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


logger = logging.getLogger(__name__)


class PayPalGateway(PaymentGatewayInterface):
    """PayPal payment gateway implementation"""

    def __init__(self, config: Dict[str, Any], test_mode: bool = True):
        super().__init__(config, test_mode)

        # PayPal API configuration
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")

        if not self.client_id or not self.client_secret:
            raise ValueError("PayPal client_id and client_secret are required")

        # Set API base URL
        if test_mode:
            self.api_base = "https://api-m.sandbox.paypal.com"
        else:
            self.api_base = "https://api-m.paypal.com"

        # Store webhook ID for verification
        self.webhook_id = config.get("webhook_id")

        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Access token cache
        self._access_token = None
        self._token_expires_at = None

    async def _get_access_token(self) -> str:
        """Get PayPal access token with caching"""
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at:
                return self._access_token

        # Get new token
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        response = await self.http_client.post(
            f"{self.api_base}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {auth_encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get PayPal access token: {response.text}")

        data = response.json()
        self._access_token = data["access_token"]

        # Cache token with expiry (subtract 60 seconds for safety)
        expires_in = data.get("expires_in", 3600) - 60
        self._token_expires_at = datetime.utcnow().replace(
            second=datetime.utcnow().second + expires_in
        )

        return self._access_token

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to PayPal API"""
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        url = f"{self.api_base}{endpoint}"

        response = await self.http_client.request(
            method=method, url=url, headers=headers, json=data if data else None
        )

        if response.status_code >= 400:
            error_data = response.json() if response.text else {}
            logger.error(f"PayPal API error: {response.status_code} - {error_data}")
            raise Exception(f"PayPal API error: {error_data}")

        return response.json() if response.text else {}

    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Create a payment with PayPal"""
        try:
            # Build order request
            order_data = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": str(request.order_id),
                        "description": request.description
                        or f"Order {request.order_id}",
                        "amount": {
                            "currency_code": request.currency,
                            "value": str(request.amount),
                        },
                        "payee": (
                            {"email_address": self.config.get("payee_email")}
                            if self.config.get("payee_email")
                            else None
                        ),
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                            "brand_name": self.config.get("brand_name", "AuraConnect"),
                            "locale": "en-US",
                            "landing_page": "LOGIN",
                            "user_action": "PAY_NOW",
                            "return_url": request.return_url
                            or f"{self.config.get('base_url', '')}/payment/success",
                            "cancel_url": f"{self.config.get('base_url', '')}/payment/cancel",
                        }
                    }
                },
            }

            # Add customer email if available
            if request.customer_email:
                order_data["payment_source"]["paypal"][
                    "email_address"
                ] = request.customer_email

            # Create order
            result = await self._make_request(
                "POST", "/v2/checkout/orders", order_data, request.idempotency_key
            )

            # Extract approval URL
            approval_url = None
            for link in result.get("links", []):
                if link.get("rel") == "approve":
                    approval_url = link.get("href")
                    break

            # Calculate fees (estimate)
            fee, net = self.calculate_fee(request.amount)

            return PaymentResponse(
                success=True,
                gateway_payment_id=result.get("id"),
                status=self._map_paypal_status(result.get("status")),
                amount=request.amount,
                currency=request.currency,
                fee_amount=fee,
                net_amount=net,
                payment_method=PaymentMethod.PAYPAL,
                requires_action=True,
                action_url=approval_url,
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"PayPal payment error: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code="payment_error",
                error_message=str(e),
            )

    async def capture_payment(
        self, payment_id: str, amount: Optional[Decimal] = None
    ) -> PaymentResponse:
        """Capture a PayPal payment after approval"""
        try:
            # First get the order details
            order = await self._make_request("GET", f"/v2/checkout/orders/{payment_id}")

            # Check if already captured
            if order.get("status") == "COMPLETED":
                return await self.get_payment(payment_id)

            # Capture the payment
            capture_data = {}
            if amount:
                # For partial capture (if supported)
                capture_data = {"payment_source": {"paypal": {}}}

            result = await self._make_request(
                "POST", f"/v2/checkout/orders/{payment_id}/capture", capture_data
            )

            # Extract capture details
            capture_id = None
            captured_amount = None
            fee_amount = None
            net_amount = None

            for unit in result.get("purchase_units", []):
                for capture in unit.get("payments", {}).get("captures", []):
                    capture_id = capture.get("id")

                    # Get amounts
                    gross = capture.get("amount", {})
                    captured_amount = self.parse_amount(
                        int(float(gross.get("value", 0)) * 100),
                        gross.get("currency_code", "USD"),
                    )

                    # Get fee from seller receivable breakdown
                    breakdown = capture.get("seller_receivable_breakdown", {})
                    if breakdown:
                        paypal_fee = breakdown.get("paypal_fee", {})
                        fee_amount = self.parse_amount(
                            int(float(paypal_fee.get("value", 0)) * 100),
                            paypal_fee.get("currency_code", "USD"),
                        )

                        net = breakdown.get("net_amount", {})
                        net_amount = self.parse_amount(
                            int(float(net.get("value", 0)) * 100),
                            net.get("currency_code", "USD"),
                        )

                    break

            return PaymentResponse(
                success=True,
                gateway_payment_id=payment_id,
                status=PaymentStatus.COMPLETED,
                amount=captured_amount or request.amount,
                currency=result.get("purchase_units", [{}])[0]
                .get("amount", {})
                .get("currency_code", "USD"),
                fee_amount=fee_amount,
                net_amount=net_amount,
                payment_method=PaymentMethod.PAYPAL,
                processed_at=datetime.utcnow(),
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"PayPal capture error: {e}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                error_code="capture_error",
                error_message=str(e),
            )

    async def get_payment(self, payment_id: str) -> PaymentResponse:
        """Get payment details from PayPal"""
        try:
            result = await self._make_request(
                "GET", f"/v2/checkout/orders/{payment_id}"
            )

            # Extract payment details
            amount = None
            currency = "USD"
            status = self._map_paypal_status(result.get("status"))

            for unit in result.get("purchase_units", []):
                amount_obj = unit.get("amount", {})
                amount = self.parse_amount(
                    int(float(amount_obj.get("value", 0)) * 100),
                    amount_obj.get("currency_code", "USD"),
                )
                currency = amount_obj.get("currency_code", "USD")
                break

            return PaymentResponse(
                success=True,
                gateway_payment_id=payment_id,
                status=status,
                amount=amount,
                currency=currency,
                payment_method=PaymentMethod.PAYPAL,
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"PayPal get payment error: {e}")
            return PaymentResponse(
                success=False, error_code="get_payment_error", error_message=str(e)
            )

    async def cancel_payment(self, payment_id: str) -> PaymentResponse:
        """Cancel a PayPal order (before capture)"""
        try:
            # PayPal doesn't have a direct cancel endpoint
            # Orders expire automatically if not captured
            # Just return the current status
            return await self.get_payment(payment_id)

        except Exception as e:
            logger.error(f"PayPal cancel error: {e}")
            return PaymentResponse(
                success=False, error_code="cancel_error", error_message=str(e)
            )

    async def create_refund(self, request: RefundRequest) -> RefundResponse:
        """Create a refund in PayPal"""
        try:
            # Get the original order to find capture ID
            order = await self._make_request(
                "GET", f"/v2/checkout/orders/{request.payment_id}"
            )

            # Find the capture ID
            capture_id = None
            captured_amount = None
            currency = "USD"

            for unit in order.get("purchase_units", []):
                for capture in unit.get("payments", {}).get("captures", []):
                    capture_id = capture.get("id")
                    amount_obj = capture.get("amount", {})
                    captured_amount = self.parse_amount(
                        int(float(amount_obj.get("value", 0)) * 100),
                        amount_obj.get("currency_code", "USD"),
                    )
                    currency = amount_obj.get("currency_code", "USD")
                    break

            if not capture_id:
                return RefundResponse(
                    success=False,
                    status=RefundStatus.FAILED,
                    error_code="capture_not_found",
                    error_message="No capture found for this order",
                )

            # Build refund request
            refund_data = {}
            if request.amount and request.amount < captured_amount:
                # Partial refund
                refund_data["amount"] = {
                    "value": str(request.amount),
                    "currency_code": currency,
                }

            if request.reason:
                refund_data["note_to_payer"] = request.reason

            # Create refund
            result = await self._make_request(
                "POST",
                f"/v2/payments/captures/{capture_id}/refund",
                refund_data if refund_data else None,
                request.idempotency_key,
            )

            # Extract refund amount
            refund_amount = None
            if result.get("amount"):
                refund_amount = self.parse_amount(
                    int(float(result["amount"].get("value", 0)) * 100),
                    result["amount"].get("currency_code", "USD"),
                )

            return RefundResponse(
                success=True,
                gateway_refund_id=result.get("id"),
                status=self._map_refund_status(result.get("status")),
                amount=refund_amount or request.amount,
                currency=result.get("amount", {}).get("currency_code", "USD"),
                processed_at=self._parse_timestamp(result.get("create_time")),
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"PayPal refund error: {e}")
            return RefundResponse(
                success=False,
                status=RefundStatus.FAILED,
                error_code="refund_error",
                error_message=str(e),
            )

    async def get_refund(self, refund_id: str) -> RefundResponse:
        """Get refund details"""
        try:
            result = await self._make_request(
                "GET", f"/v2/payments/refunds/{refund_id}"
            )

            # Extract amount
            refund_amount = None
            if result.get("amount"):
                refund_amount = self.parse_amount(
                    int(float(result["amount"].get("value", 0)) * 100),
                    result["amount"].get("currency_code", "USD"),
                )

            return RefundResponse(
                success=True,
                gateway_refund_id=refund_id,
                status=self._map_refund_status(result.get("status")),
                amount=refund_amount,
                currency=result.get("amount", {}).get("currency_code", "USD"),
                processed_at=self._parse_timestamp(result.get("create_time")),
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"PayPal get refund error: {e}")
            return RefundResponse(
                success=False, error_code="get_refund_error", error_message=str(e)
            )

    async def create_customer(self, request: CustomerRequest) -> CustomerResponse:
        """PayPal doesn't have traditional customer profiles"""
        # PayPal uses buyer accounts, not merchant-managed customers
        # Return success but no gateway_customer_id
        return CustomerResponse(success=True, gateway_customer_id=None)

    async def update_customer(
        self, gateway_customer_id: str, request: CustomerRequest
    ) -> CustomerResponse:
        """PayPal doesn't support customer updates"""
        return CustomerResponse(success=True, gateway_customer_id=None)

    async def save_payment_method(
        self, request: PaymentMethodRequest
    ) -> PaymentMethodResponse:
        """Save PayPal billing agreement"""
        try:
            # PayPal uses billing agreements for recurring payments
            # This would require a different flow with billing agreement tokens
            # For now, return unsupported
            return PaymentMethodResponse(
                success=False,
                error_code="not_supported",
                error_message="PayPal saved payment methods require billing agreements",
            )

        except Exception as e:
            logger.error(f"PayPal save payment method error: {e}")
            return PaymentMethodResponse(
                success=False,
                error_code="save_payment_method_error",
                error_message=str(e),
            )

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Delete PayPal billing agreement"""
        # Would need to cancel billing agreement
        return False

    async def list_payment_methods(
        self, customer_id: str
    ) -> List[PaymentMethodResponse]:
        """List PayPal billing agreements"""
        # Would need to list billing agreements
        return []

    async def verify_webhook(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify PayPal webhook signature"""
        try:
            # Get required headers
            transmission_id = headers.get("paypal-transmission-id")
            transmission_time = headers.get("paypal-transmission-time")
            cert_url = headers.get("paypal-cert-url")
            transmission_sig = headers.get("paypal-transmission-sig")
            auth_algo = headers.get("paypal-auth-algo")

            if not all(
                [
                    transmission_id,
                    transmission_time,
                    cert_url,
                    transmission_sig,
                    auth_algo,
                ]
            ):
                logger.warning("Missing PayPal webhook headers")
                return False, None

            # Build verification request
            verification_data = {
                "auth_algo": auth_algo,
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": transmission_sig,
                "transmission_time": transmission_time,
                "webhook_id": self.webhook_id,
                "webhook_event": json.loads(body),
            }

            # Verify with PayPal
            result = await self._make_request(
                "POST", "/v1/notifications/verify-webhook-signature", verification_data
            )

            if result.get("verification_status") == "SUCCESS":
                return True, json.loads(body)
            else:
                logger.warning(f"PayPal webhook verification failed: {result}")
                return False, None

        except Exception as e:
            logger.error(f"PayPal webhook verification error: {e}")
            return False, None

    def get_public_config(self) -> Dict[str, Any]:
        """Get public PayPal configuration"""
        return {
            "client_id": self.client_id,
            "test_mode": self.test_mode,
            "currency": self.config.get("currency", "USD"),
            "locale": self.config.get("locale", "en_US"),
        }

    # Helper methods

    def _map_paypal_status(self, paypal_status: str) -> PaymentStatus:
        """Map PayPal order status to our status"""
        mapping = {
            "CREATED": PaymentStatus.PENDING,
            "SAVED": PaymentStatus.PENDING,
            "APPROVED": PaymentStatus.PROCESSING,
            "VOIDED": PaymentStatus.CANCELLED,
            "COMPLETED": PaymentStatus.COMPLETED,
            "PAYER_ACTION_REQUIRED": PaymentStatus.REQUIRES_ACTION,
        }
        return mapping.get(paypal_status, PaymentStatus.PENDING)

    def _map_refund_status(self, paypal_status: str) -> RefundStatus:
        """Map PayPal refund status to our status"""
        mapping = {
            "CANCELLED": RefundStatus.CANCELLED,
            "PENDING": RefundStatus.PENDING,
            "COMPLETED": RefundStatus.COMPLETED,
            "FAILED": RefundStatus.FAILED,
        }
        return mapping.get(paypal_status, RefundStatus.PENDING)

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse PayPal timestamp to datetime"""
        if not timestamp_str:
            return None

        try:
            # PayPal uses ISO 8601 format
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except Exception:
            return None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup HTTP client"""
        await self.http_client.aclose()
