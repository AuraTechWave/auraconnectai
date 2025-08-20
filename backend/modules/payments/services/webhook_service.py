# backend/modules/payments/services/webhook_service.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.database import get_db
from ..models.payment_models import (
    Payment,
    Refund,
    PaymentWebhook,
    PaymentGateway,
    PaymentStatus,
    RefundStatus,
)
from .payment_service import payment_service
from ...orders.services.order_tracking_service import OrderTrackingService


logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for handling payment gateway webhooks
    """

    async def process_webhook(
        self,
        db: AsyncSession,
        gateway: PaymentGateway,
        headers: Dict[str, str],
        body: bytes,
    ) -> Dict[str, Any]:
        """
        Process incoming webhook from payment gateway

        Args:
            db: Database session
            gateway: Payment gateway type
            headers: Webhook request headers
            body: Raw webhook body

        Returns:
            Response data
        """
        try:
            # Get gateway instance
            gateway_instance = payment_service.get_gateway(gateway)
            if not gateway_instance:
                logger.error(f"Gateway {gateway} not configured")
                return {"status": "error", "message": "Gateway not configured"}

            # Verify webhook signature
            is_valid, payload = await gateway_instance.verify_webhook(headers, body)

            if not is_valid:
                logger.warning(f"Invalid webhook signature for {gateway}")
                return {"status": "error", "message": "Invalid signature"}

            # Check for duplicate webhook
            gateway_event_id = self._extract_event_id(gateway, payload)
            if gateway_event_id:
                existing = await db.execute(
                    select(PaymentWebhook).where(
                        and_(
                            PaymentWebhook.gateway == gateway,
                            PaymentWebhook.gateway_event_id == gateway_event_id,
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    logger.info(f"Duplicate webhook {gateway_event_id} for {gateway}")
                    return {"status": "success", "message": "Already processed"}

            # Store webhook
            webhook = PaymentWebhook(
                gateway=gateway,
                gateway_event_id=gateway_event_id,
                event_type=self._extract_event_type(gateway, payload),
                headers=dict(headers),
                payload=payload,
            )
            db.add(webhook)
            await db.flush()

            # Process based on gateway
            if gateway == PaymentGateway.STRIPE:
                result = await self._process_stripe_webhook(db, payload, webhook)
            elif gateway == PaymentGateway.SQUARE:
                result = await self._process_square_webhook(db, payload, webhook)
            elif gateway == PaymentGateway.PAYPAL:
                result = await self._process_paypal_webhook(db, payload, webhook)
            else:
                logger.warning(f"No webhook processor for {gateway}")
                result = {"status": "success", "message": "Not implemented"}

            # Mark as processed
            webhook.processed = True
            webhook.processed_at = datetime.utcnow()

            await db.commit()
            return result

        except Exception as e:
            await db.rollback()
            logger.error(f"Webhook processing error: {e}")

            # Store error if webhook was created
            if "webhook" in locals():
                webhook.error_message = str(e)
                webhook.retry_count += 1
                await db.commit()

            return {"status": "error", "message": str(e)}

    async def _process_stripe_webhook(
        self, db: AsyncSession, event: Dict[str, Any], webhook: PaymentWebhook
    ) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})

        try:
            if event_type == "payment_intent.succeeded":
                # Payment completed
                payment_intent_id = data.get("id")
                await self._update_payment_status(
                    db,
                    PaymentGateway.STRIPE,
                    payment_intent_id,
                    PaymentStatus.COMPLETED,
                    webhook.id,
                )

            elif event_type == "payment_intent.payment_failed":
                # Payment failed
                payment_intent_id = data.get("id")
                await self._update_payment_status(
                    db,
                    PaymentGateway.STRIPE,
                    payment_intent_id,
                    PaymentStatus.FAILED,
                    webhook.id,
                    error_code=data.get("last_payment_error", {}).get("code"),
                    error_message=data.get("last_payment_error", {}).get("message"),
                )

            elif event_type == "payment_intent.canceled":
                # Payment cancelled
                payment_intent_id = data.get("id")
                await self._update_payment_status(
                    db,
                    PaymentGateway.STRIPE,
                    payment_intent_id,
                    PaymentStatus.CANCELLED,
                    webhook.id,
                )

            elif event_type == "charge.refunded":
                # Refund processed
                charge_id = data.get("id")
                payment_intent_id = data.get("payment_intent")

                # Get refund details
                refunds = data.get("refunds", {}).get("data", [])
                if refunds:
                    refund_data = refunds[0]  # Get latest refund
                    await self._update_refund_status(
                        db,
                        PaymentGateway.STRIPE,
                        refund_data.get("id"),
                        RefundStatus.COMPLETED,
                        webhook.id,
                    )

            elif event_type == "charge.dispute.created":
                # Payment disputed
                payment_intent_id = data.get("payment_intent")
                await self._update_payment_status(
                    db,
                    PaymentGateway.STRIPE,
                    payment_intent_id,
                    PaymentStatus.DISPUTED,
                    webhook.id,
                )

            else:
                logger.info(f"Unhandled Stripe event type: {event_type}")

            return {"status": "success"}

        except Exception as e:
            logger.error(f"Stripe webhook processing error: {e}")
            raise

    async def _process_square_webhook(
        self, db: AsyncSession, event: Dict[str, Any], webhook: PaymentWebhook
    ) -> Dict[str, Any]:
        """Process Square webhook events"""
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})

        try:
            if event_type == "payment.created" or event_type == "payment.updated":
                # Payment status update
                payment = data.get("payment", {})
                payment_id = payment.get("id")
                status = payment.get("status")

                if status == "COMPLETED":
                    await self._update_payment_status(
                        db,
                        PaymentGateway.SQUARE,
                        payment_id,
                        PaymentStatus.COMPLETED,
                        webhook.id,
                    )
                elif status == "FAILED":
                    await self._update_payment_status(
                        db,
                        PaymentGateway.SQUARE,
                        payment_id,
                        PaymentStatus.FAILED,
                        webhook.id,
                    )
                elif status == "CANCELED":
                    await self._update_payment_status(
                        db,
                        PaymentGateway.SQUARE,
                        payment_id,
                        PaymentStatus.CANCELLED,
                        webhook.id,
                    )

            elif event_type == "refund.created" or event_type == "refund.updated":
                # Refund status update
                refund = data.get("refund", {})
                refund_id = refund.get("id")
                status = refund.get("status")

                if status == "COMPLETED":
                    await self._update_refund_status(
                        db,
                        PaymentGateway.SQUARE,
                        refund_id,
                        RefundStatus.COMPLETED,
                        webhook.id,
                    )
                elif status == "FAILED":
                    await self._update_refund_status(
                        db,
                        PaymentGateway.SQUARE,
                        refund_id,
                        RefundStatus.FAILED,
                        webhook.id,
                    )

            elif event_type == "dispute.created":
                # Payment disputed
                dispute = data.get("dispute", {})
                payment_id = dispute.get("payment_id")
                await self._update_payment_status(
                    db,
                    PaymentGateway.SQUARE,
                    payment_id,
                    PaymentStatus.DISPUTED,
                    webhook.id,
                )

            else:
                logger.info(f"Unhandled Square event type: {event_type}")

            return {"status": "success"}

        except Exception as e:
            logger.error(f"Square webhook processing error: {e}")
            raise

    async def _process_paypal_webhook(
        self, db: AsyncSession, event: Dict[str, Any], webhook: PaymentWebhook
    ) -> Dict[str, Any]:
        """Process PayPal webhook events"""
        event_type = event.get("event_type", "")
        resource = event.get("resource", {})

        try:
            if event_type == "CHECKOUT.ORDER.APPROVED":
                # Order approved by buyer - ready for capture
                order_id = resource.get("id")
                await self._update_payment_status(
                    db,
                    PaymentGateway.PAYPAL,
                    order_id,
                    PaymentStatus.PROCESSING,
                    webhook.id,
                )

            elif event_type == "PAYMENT.CAPTURE.COMPLETED":
                # Payment captured successfully
                order_id = (
                    resource.get("supplementary_data", {})
                    .get("related_ids", {})
                    .get("order_id")
                )
                if order_id:
                    await self._update_payment_status(
                        db,
                        PaymentGateway.PAYPAL,
                        order_id,
                        PaymentStatus.COMPLETED,
                        webhook.id,
                    )

            elif event_type == "PAYMENT.CAPTURE.DENIED":
                # Payment capture denied
                order_id = (
                    resource.get("supplementary_data", {})
                    .get("related_ids", {})
                    .get("order_id")
                )
                if order_id:
                    await self._update_payment_status(
                        db,
                        PaymentGateway.PAYPAL,
                        order_id,
                        PaymentStatus.FAILED,
                        webhook.id,
                        error_message="Payment capture denied",
                    )

            elif event_type == "PAYMENT.CAPTURE.REFUNDED":
                # Refund completed
                refund_id = resource.get("id")
                await self._update_refund_status(
                    db,
                    PaymentGateway.PAYPAL,
                    refund_id,
                    RefundStatus.COMPLETED,
                    webhook.id,
                )

            elif event_type == "CUSTOMER.DISPUTE.CREATED":
                # Payment disputed
                disputed_transaction = resource.get("disputed_transactions", [{}])[0]
                order_id = disputed_transaction.get("seller_transaction_id")
                if order_id:
                    await self._update_payment_status(
                        db,
                        PaymentGateway.PAYPAL,
                        order_id,
                        PaymentStatus.DISPUTED,
                        webhook.id,
                    )

            else:
                logger.info(f"Unhandled PayPal event type: {event_type}")

            return {"status": "success"}

        except Exception as e:
            logger.error(f"PayPal webhook processing error: {e}")
            raise

    async def _update_payment_status(
        self,
        db: AsyncSession,
        gateway: PaymentGateway,
        gateway_payment_id: str,
        status: PaymentStatus,
        webhook_id: int,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update payment status based on webhook"""
        # Find payment
        result = await db.execute(
            select(Payment).where(
                and_(
                    Payment.gateway == gateway,
                    Payment.gateway_payment_id == gateway_payment_id,
                )
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            logger.warning(f"Payment not found: {gateway} {gateway_payment_id}")
            return

        # Update webhook reference
        webhook = await db.get(PaymentWebhook, webhook_id)
        if webhook:
            webhook.payment_id = payment.id

        # Skip if already in final state
        if payment.status in [PaymentStatus.COMPLETED, PaymentStatus.REFUNDED]:
            return

        # Update status
        old_status = payment.status
        payment.status = status

        if error_code:
            payment.failure_code = error_code
        if error_message:
            payment.failure_message = error_message

        if status == PaymentStatus.COMPLETED:
            payment.processed_at = datetime.utcnow()

        logger.info(f"Payment {payment.id} status updated: {old_status} -> {status}")

        # Send order tracking notification if status changed
        if old_status != status:
            from ...orders.services.order_tracking_service import order_tracking_service
            await order_tracking_service.track_payment_event(
                db=db,
                order_id=payment.order_id,
                payment_id=payment.id,
                event_type='payment_status_changed',
                old_status=old_status.value,
                new_status=status.value
            )

    async def _update_refund_status(
        self,
        db: AsyncSession,
        gateway: PaymentGateway,
        gateway_refund_id: str,
        status: RefundStatus,
        webhook_id: int,
    ):
        """Update refund status based on webhook"""
        # Find refund
        result = await db.execute(
            select(Refund).where(
                and_(
                    Refund.gateway == gateway,
                    Refund.gateway_refund_id == gateway_refund_id,
                )
            )
        )
        refund = result.scalar_one_or_none()

        if not refund:
            logger.warning(f"Refund not found: {gateway} {gateway_refund_id}")
            return

        # Skip if already completed
        if refund.status == RefundStatus.COMPLETED:
            return

        # Update status
        old_status = refund.status
        refund.status = status

        if status == RefundStatus.COMPLETED:
            refund.processed_at = datetime.utcnow()

            # Update payment status
            payment = await db.get(Payment, refund.payment_id)
            if payment:
                # Check if fully refunded
                result = await db.execute(
                    select(Refund).where(
                        and_(
                            Refund.payment_id == payment.id,
                            Refund.status == RefundStatus.COMPLETED,
                        )
                    )
                )
                completed_refunds = result.scalars().all()
                total_refunded = sum(r.amount for r in completed_refunds)

                if total_refunded >= payment.amount:
                    payment.status = PaymentStatus.REFUNDED
                else:
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED

        logger.info(f"Refund {refund.id} status updated: {old_status} -> {status}")

    def _extract_event_id(
        self, gateway: PaymentGateway, payload: Dict[str, Any]
    ) -> Optional[str]:
        """Extract unique event ID from webhook payload"""
        if gateway == PaymentGateway.STRIPE:
            return payload.get("id")
        elif gateway == PaymentGateway.SQUARE:
            return payload.get("event_id")
        elif gateway == PaymentGateway.PAYPAL:
            return payload.get("id")
        return None

    def _extract_event_type(
        self, gateway: PaymentGateway, payload: Dict[str, Any]
    ) -> str:
        """Extract event type from webhook payload"""
        if gateway == PaymentGateway.STRIPE:
            return payload.get("type", "unknown")
        elif gateway == PaymentGateway.SQUARE:
            return payload.get("type", "unknown")
        elif gateway == PaymentGateway.PAYPAL:
            return payload.get("event_type", "unknown")
        return "unknown"


# Global service instance
webhook_service = WebhookService()
