# backend/modules/orders/services/external_pos_webhook_service.py

"""
Service for processing external POS webhook events.

Handles payment updates from external systems and reconciles them
with local orders.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from modules.orders.models.external_pos_models import (
    ExternalPOSWebhookEvent, ExternalPOSPaymentUpdate,
    ExternalPOSWebhookLog, ExternalPOSProvider
)
from modules.orders.models.order_models import Order
from modules.orders.models.payment_reconciliation_models import PaymentReconciliation
from modules.orders.enums.external_pos_enums import (
    WebhookProcessingStatus, ExternalPOSEventType,
    PaymentStatus, PaymentMethod, ExternalPOSProvider as POSProviderEnum,
    WebhookLogType, WebhookLogLevel
)
from modules.orders.enums.payment_enums import ReconciliationStatus, DiscrepancyType
from modules.orders.enums.order_enums import OrderStatus, OrderPaymentStatus
from modules.orders.utils.security_utils import mask_sensitive_dict, mask_headers
from core.config import settings

logger = logging.getLogger(__name__)


class ExternalPOSWebhookService:
    """Service for processing webhooks from external POS systems"""
    
    def __init__(self, db: Session):
        self.db = db
        self.max_processing_attempts = settings.WEBHOOK_MAX_RETRY_ATTEMPTS
        
    async def process_webhook_event(self, webhook_event_id: int) -> bool:
        """
        Process a webhook event.
        
        Returns:
            True if successfully processed, False otherwise
        """
        webhook_event = self.db.query(ExternalPOSWebhookEvent).filter(
            ExternalPOSWebhookEvent.id == webhook_event_id
        ).first()
        
        if not webhook_event:
            logger.error(f"Webhook event {webhook_event_id} not found")
            return False
            
        # Check if already processed
        if webhook_event.processing_status in [
            WebhookProcessingStatus.PROCESSED,
            WebhookProcessingStatus.DUPLICATE
        ]:
            logger.info(f"Webhook event {webhook_event_id} already processed")
            return True
            
        # Update status to processing
        webhook_event.processing_status = WebhookProcessingStatus.PROCESSING
        webhook_event.processing_attempts += 1
        self.db.commit()
        
        try:
            # Log processing start
            self._log_webhook_event(
                webhook_event_id,
                WebhookLogLevel.INFO.value,
                WebhookLogType.PROCESSING.value,
                "Starting webhook processing"
            )
            
            # Check for duplicate events
            if await self._is_duplicate_event(webhook_event):
                webhook_event.processing_status = WebhookProcessingStatus.DUPLICATE
                webhook_event.processed_at = datetime.utcnow()
                self.db.commit()
                
                self._log_webhook_event(
                    webhook_event_id,
                    WebhookLogLevel.WARNING.value,
                    WebhookLogType.PROCESSING.value,
                    "Duplicate event detected"
                )
                return True
            
            # Route to appropriate handler based on event type
            event_type = webhook_event.event_type
            provider = webhook_event.provider
            
            if event_type in [
                ExternalPOSEventType.PAYMENT_COMPLETED,
                ExternalPOSEventType.PAYMENT_FAILED,
                ExternalPOSEventType.PAYMENT_PENDING,
                ExternalPOSEventType.PAYMENT_REFUNDED,
                ExternalPOSEventType.PAYMENT_PARTIALLY_REFUNDED
            ]:
                success = await self._process_payment_event(webhook_event)
            else:
                # Log unsupported event type
                self._log_webhook_event(
                    webhook_event_id,
                    WebhookLogLevel.WARNING.value,
                    WebhookLogType.PROCESSING.value,
                    f"Unsupported event type: {event_type}"
                )
                webhook_event.processing_status = WebhookProcessingStatus.IGNORED
                webhook_event.processed_at = datetime.utcnow()
                self.db.commit()
                return True
                
            if success:
                webhook_event.processing_status = WebhookProcessingStatus.PROCESSED
                webhook_event.processed_at = datetime.utcnow()
                self.db.commit()
                
                self._log_webhook_event(
                    webhook_event_id,
                    WebhookLogLevel.INFO.value,
                    WebhookLogType.PROCESSING.value,
                    "Successfully processed webhook event"
                )
                return True
            else:
                raise Exception("Failed to process webhook event")
                
        except Exception as e:
            logger.error(
                f"Error processing webhook {webhook_event_id}: {str(e)}",
                exc_info=True
            )
            
            webhook_event.last_error = str(e)
            
            # Check if we should retry
            if webhook_event.processing_attempts < self.max_processing_attempts:
                webhook_event.processing_status = WebhookProcessingStatus.RETRY
                self._log_webhook_event(
                    webhook_event_id,
                    WebhookLogLevel.ERROR.value,
                    WebhookLogType.PROCESSING.value,
                    f"Processing failed, will retry: {str(e)}"
                )
            else:
                webhook_event.processing_status = WebhookProcessingStatus.FAILED
                self._log_webhook_event(
                    webhook_event_id,
                    WebhookLogLevel.ERROR.value,
                    WebhookLogType.PROCESSING.value,
                    f"Processing failed after {webhook_event.processing_attempts} attempts: {str(e)}"
                )
                
            self.db.commit()
            return False
    
    async def _process_payment_event(self, webhook_event: ExternalPOSWebhookEvent) -> bool:
        """Process payment-related webhook events"""
        provider = webhook_event.provider
        body = webhook_event.request_body
        
        # Extract payment data based on provider
        payment_data = self._extract_payment_data(provider.provider_code, body)
        
        if not payment_data:
            raise ValueError("Could not extract payment data from webhook")
            
        # Create payment update record
        payment_update = ExternalPOSPaymentUpdate(
            webhook_event_id=webhook_event.id,
            external_transaction_id=payment_data["transaction_id"],
            external_order_id=payment_data.get("order_id"),
            external_payment_id=payment_data.get("payment_id"),
            payment_status=payment_data["status"],
            payment_method=payment_data["method"],
            payment_amount=Decimal(str(payment_data["amount"])),
            currency=payment_data.get("currency", "USD"),
            tip_amount=Decimal(str(payment_data.get("tip_amount", 0))),
            tax_amount=Decimal(str(payment_data.get("tax_amount", 0))),
            discount_amount=Decimal(str(payment_data.get("discount_amount", 0))),
            card_last_four=payment_data.get("card_last_four"),
            card_brand=payment_data.get("card_brand"),
            customer_email=payment_data.get("customer_email"),
            customer_phone=payment_data.get("customer_phone"),
            raw_payment_data=body
        )
        
        self.db.add(payment_update)
        self.db.flush()
        
        # Try to match with local order
        order = await self._match_order(payment_update)
        
        if order:
            payment_update.order_id = order.id
            
            # Create or update payment reconciliation
            await self._create_payment_reconciliation(order, payment_update)
            
            # Update order status if payment completed
            if payment_update.payment_status == PaymentStatus.COMPLETED:
                await self._update_order_payment_status(order, payment_update)
                
            payment_update.is_processed = True
            payment_update.processed_at = datetime.utcnow()
            payment_update.processing_notes = "Successfully matched and processed"
            
            self._log_webhook_event(
                webhook_event.id,
                WebhookLogLevel.INFO.value,
                WebhookLogType.PAYMENT_PROCESSING.value,
                f"Payment matched to order {order.id}",
                {"order_id": order.id, "payment_amount": str(payment_update.payment_amount)}
            )
        else:
            payment_update.processing_notes = "Could not match to local order"
            
            self._log_webhook_event(
                webhook_event.id,
                WebhookLogLevel.WARNING.value,
                WebhookLogType.PAYMENT_PROCESSING.value,
                "Payment could not be matched to any order",
                {"external_order_id": payment_update.external_order_id}
            )
            
        self.db.commit()
        return True
    
    def _extract_payment_data(self, provider_code: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract standardized payment data from provider-specific webhook"""
        if provider_code == POSProviderEnum.SQUARE:
            return self._extract_square_payment_data(body)
        elif provider_code == POSProviderEnum.STRIPE:
            return self._extract_stripe_payment_data(body)
        elif provider_code == POSProviderEnum.TOAST:
            return self._extract_toast_payment_data(body)
        else:
            # Generic extraction
            return self._extract_generic_payment_data(body)
    
    def _extract_square_payment_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract payment data from Square webhook"""
        data = body.get("data", {})
        payment = data.get("object", {}).get("payment", {})
        
        if not payment:
            return None
            
        amount_money = payment.get("amount_money", {})
        
        return {
            "transaction_id": payment.get("id"),
            "payment_id": payment.get("id"),
            "order_id": payment.get("order_id"),
            "status": self._map_square_status(payment.get("status")),
            "method": self._map_square_card_details(payment.get("card_details", {})),
            "amount": amount_money.get("amount", 0) / settings.WEBHOOK_CENTS_TO_DOLLARS,  # Square uses cents
            "currency": amount_money.get("currency", "USD"),
            "card_last_four": payment.get("card_details", {}).get("card", {}).get("last_4"),
            "card_brand": payment.get("card_details", {}).get("card", {}).get("card_brand"),
            "customer_email": payment.get("buyer_email_address"),
            "tip_amount": payment.get("tip_money", {}).get("amount", 0) / settings.WEBHOOK_CENTS_TO_DOLLARS
        }
    
    def _extract_stripe_payment_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract payment data from Stripe webhook"""
        data = body.get("data", {})
        payment_intent = data.get("object", {})
        
        if payment_intent.get("object") != "payment_intent":
            return None
            
        metadata = payment_intent.get("metadata", {})
        
        return {
            "transaction_id": payment_intent.get("id"),
            "payment_id": payment_intent.get("id"),
            "order_id": metadata.get("order_id"),
            "status": self._map_stripe_status(payment_intent.get("status")),
            "method": self._map_stripe_payment_method(payment_intent.get("payment_method_types", [])),
            "amount": payment_intent.get("amount", 0) / settings.WEBHOOK_CENTS_TO_DOLLARS,  # Stripe uses cents
            "currency": payment_intent.get("currency", "usd").upper(),
            "customer_email": payment_intent.get("receipt_email"),
            "tip_amount": metadata.get("tip_amount", 0)
        }
    
    def _extract_toast_payment_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract payment data from Toast webhook"""
        # Toast specific extraction logic
        payment = body.get("payment", {})
        
        return {
            "transaction_id": payment.get("guid"),
            "payment_id": payment.get("guid"),
            "order_id": payment.get("orderGuid"),
            "status": self._map_toast_status(payment.get("paymentStatus")),
            "method": payment.get("type", "UNKNOWN"),
            "amount": payment.get("totalAmount", 0),
            "currency": "USD",
            "tip_amount": payment.get("tipAmount", 0)
        }
    
    def _extract_generic_payment_data(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract payment data from generic webhook format"""
        data = body.get("data", body)
        
        return {
            "transaction_id": (
                data.get("transaction_id") or 
                data.get("payment_id") or 
                data.get("id")
            ),
            "payment_id": data.get("payment_id"),
            "order_id": data.get("order_id"),
            "status": PaymentStatus.COMPLETED if data.get("status") == "completed" else PaymentStatus.PENDING,
            "method": data.get("payment_method", "UNKNOWN"),
            "amount": data.get("amount", 0),
            "currency": data.get("currency", "USD"),
            "customer_email": data.get("customer_email"),
            "tip_amount": data.get("tip_amount", 0)
        }
    
    # Status mapping functions
    def _map_square_status(self, status: str) -> str:
        mapping = {
            "COMPLETED": PaymentStatus.COMPLETED,
            "PENDING": PaymentStatus.PENDING,
            "FAILED": PaymentStatus.FAILED,
            "CANCELED": PaymentStatus.CANCELLED
        }
        return mapping.get(status, PaymentStatus.PENDING)
    
    def _map_stripe_status(self, status: str) -> str:
        mapping = {
            "succeeded": PaymentStatus.COMPLETED,
            "processing": PaymentStatus.PENDING,
            "requires_payment_method": PaymentStatus.FAILED,
            "canceled": PaymentStatus.CANCELLED
        }
        return mapping.get(status, PaymentStatus.PENDING)
    
    def _map_toast_status(self, status: str) -> str:
        mapping = {
            "CAPTURED": PaymentStatus.COMPLETED,
            "AUTHORIZED": PaymentStatus.PENDING,
            "FAILED": PaymentStatus.FAILED,
            "VOIDED": PaymentStatus.VOIDED
        }
        return mapping.get(status, PaymentStatus.PENDING)
    
    def _map_square_card_details(self, card_details: Dict[str, Any]) -> str:
        if card_details:
            return PaymentMethod.CREDIT_CARD
        return PaymentMethod.OTHER
    
    def _map_stripe_payment_method(self, payment_methods: List[str]) -> str:
        if "card" in payment_methods:
            return PaymentMethod.CREDIT_CARD
        return PaymentMethod.OTHER
    
    async def _match_order(self, payment_update: ExternalPOSPaymentUpdate) -> Optional[Order]:
        """Try to match payment update to a local order"""
        # First try direct external ID match
        if payment_update.external_order_id:
            order = self.db.query(Order).filter(
                Order.external_id == payment_update.external_order_id
            ).first()
            
            if order:
                return order
                
        # Try to match by amount and time window
        # Look for orders created within time window of payment
        time_window_start = payment_update.created_at - timedelta(minutes=settings.WEBHOOK_DUPLICATE_WINDOW_MINUTES)
        time_window_end = payment_update.created_at + timedelta(minutes=settings.WEBHOOK_ORDER_MATCH_WINDOW_MINUTES)
        
        potential_orders = self.db.query(Order).filter(
            and_(
                Order.created_at >= time_window_start,
                Order.created_at <= time_window_end,
                Order.status.in_([
                    OrderStatus.PENDING.value,
                    OrderStatus.IN_PROGRESS.value,
                    OrderStatus.IN_KITCHEN.value
                ])
            )
        ).all()
        
        # Try to match by amount
        for order in potential_orders:
            # Calculate order total (would need order items relationship)
            # For now, we'll skip exact matching
            # In production, you'd calculate order.total_amount
            pass
            
        return None
    
    async def _create_payment_reconciliation(
        self, 
        order: Order, 
        payment_update: ExternalPOSPaymentUpdate
    ):
        """Create or update payment reconciliation record"""
        # Check if reconciliation already exists
        existing = self.db.query(PaymentReconciliation).filter(
            PaymentReconciliation.order_id == order.id,
            PaymentReconciliation.external_payment_reference == payment_update.external_transaction_id
        ).first()
        
        if existing:
            # Update existing reconciliation
            existing.amount_received = payment_update.payment_amount
            existing.reconciliation_status = ReconciliationStatus.MATCHED
            existing.resolved_at = datetime.utcnow()
        else:
            # Create new reconciliation
            reconciliation = PaymentReconciliation(
                order_id=order.id,
                external_payment_reference=payment_update.external_transaction_id,
                amount_expected=payment_update.payment_amount,  # Assuming full payment
                amount_received=payment_update.payment_amount,
                reconciliation_status=ReconciliationStatus.MATCHED,
                resolved_at=datetime.utcnow()
            )
            self.db.add(reconciliation)
    
    async def _update_order_payment_status(
        self, 
        order: Order, 
        payment_update: ExternalPOSPaymentUpdate
    ):
        """Update order status based on payment completion"""
        # Update order as paid
        if hasattr(order, 'payment_status'):
            order.payment_status = OrderPaymentStatus.PAID.value
        
        # Update order status if still pending
        if order.status in [OrderStatus.PENDING.value, OrderStatus.IN_PROGRESS.value]:
            order.status = OrderStatus.PAID.value
            
        # Store payment reference
        if hasattr(order, 'external_payment_id'):
            order.external_payment_id = payment_update.external_payment_id
            
    async def _is_duplicate_event(self, webhook_event: ExternalPOSWebhookEvent) -> bool:
        """Check if this is a duplicate event"""
        # Look for similar events in the duplicate window
        duplicate_window = datetime.utcnow() - timedelta(minutes=settings.WEBHOOK_DUPLICATE_WINDOW_MINUTES)
        
        duplicate = self.db.query(ExternalPOSWebhookEvent).filter(
            and_(
                ExternalPOSWebhookEvent.id != webhook_event.id,
                ExternalPOSWebhookEvent.provider_id == webhook_event.provider_id,
                ExternalPOSWebhookEvent.event_type == webhook_event.event_type,
                ExternalPOSWebhookEvent.request_body == webhook_event.request_body,
                ExternalPOSWebhookEvent.created_at >= duplicate_window,
                ExternalPOSWebhookEvent.processing_status.in_([
                    WebhookProcessingStatus.PROCESSED,
                    WebhookProcessingStatus.DUPLICATE
                ])
            )
        ).first()
        
        return duplicate is not None
    
    def _log_webhook_event(
        self,
        webhook_event_id: int,
        log_level: str,
        log_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Create a webhook processing log entry"""
        # Mask sensitive data in details before logging
        safe_details = mask_sensitive_dict(details) if details else None
        
        log_entry = ExternalPOSWebhookLog(
            webhook_event_id=webhook_event_id,
            log_level=log_level,
            log_type=log_type,
            message=message,
            details=safe_details,
            occurred_at=datetime.utcnow()
        )
        self.db.add(log_entry)
        self.db.flush()
        
        # Also log to Python logger with masked data
        log_message = f"Webhook {webhook_event_id}: {message}"
        if safe_details:
            log_message += f" Details: {safe_details}"
            
        if log_level == WebhookLogLevel.ERROR.value:
            logger.error(log_message)
        elif log_level == WebhookLogLevel.WARNING.value:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    async def retry_failed_webhooks(self, limit: int = settings.WEBHOOK_RECENT_EVENTS_LIMIT) -> int:
        """Retry failed webhook events"""
        failed_events = self.db.query(ExternalPOSWebhookEvent).filter(
            ExternalPOSWebhookEvent.processing_status == WebhookProcessingStatus.RETRY,
            ExternalPOSWebhookEvent.processing_attempts < self.max_processing_attempts
        ).order_by(
            ExternalPOSWebhookEvent.created_at.asc()
        ).limit(limit).all()
        
        processed_count = 0
        
        for event in failed_events:
            try:
                success = await self.process_webhook_event(event.id)
                if success:
                    processed_count += 1
            except Exception as e:
                logger.error(f"Error retrying webhook {event.id}: {str(e)}")
                
        return processed_count