# backend/modules/payments/services/payment_action_service.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ..models.payment_models import Payment, PaymentStatus, PaymentGateway
from ...orders.services.order_tracking_service import OrderTrackingService
from ...orders.models.order_tracking_models import TrackingEventType


logger = logging.getLogger(__name__)

# TODO: Create proper instance when service is initialized
# order_tracking_service = OrderTrackingService()


class PaymentActionService:
    """
    Service for handling payment actions (3D Secure, PayPal redirects, etc.)
    """
    
    async def handle_requires_action(
        self,
        db: AsyncSession,
        payment: Payment,
        action_url: str,
        action_type: str = "redirect"
    ) -> Dict[str, Any]:
        """
        Handle a payment that requires user action
        
        Args:
            db: Database session
            payment: Payment record
            action_url: URL for user action (3DS, PayPal approval)
            action_type: Type of action required
            
        Returns:
            Action details for frontend
        """
        try:
            # Store action details in payment metadata
            if not payment.metadata:
                payment.metadata = {}
            
            payment.metadata['action_required'] = {
                'type': action_type,
                'url': action_url,
                'requested_at': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(minutes=30)).isoformat()
            }
            
            # Track the event
            # TODO: Fix order_tracking_service instance
            # await order_tracking_service.track_payment_event(
            #     db=db,
            #     order_id=payment.order_id,
            #     payment_id=payment.id,
            #     event_type='payment_action_required',
            #     action_type=action_type,
            #     action_url=action_url
            # )
            
            await db.commit()
            
            # Return action details for frontend
            return {
                'payment_id': payment.payment_id,
                'action_required': True,
                'action_type': action_type,
                'action_url': action_url,
                'expires_at': payment.metadata['action_required']['expires_at'],
                'instructions': self._get_action_instructions(payment.gateway, action_type)
            }
            
        except Exception as e:
            logger.error(f"Failed to handle payment action: {e}")
            raise
    
    async def complete_action(
        self,
        db: AsyncSession,
        payment_id: int,
        success: bool,
        action_data: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """
        Complete a payment action
        
        Args:
            db: Database session
            payment_id: Payment ID
            success: Whether action was successful
            action_data: Additional data from action completion
            
        Returns:
            Updated payment
        """
        try:
            # Get payment
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            
            # Update metadata
            if payment.metadata and 'action_required' in payment.metadata:
                payment.metadata['action_required']['completed_at'] = datetime.utcnow().isoformat()
                payment.metadata['action_required']['success'] = success
                if action_data:
                    payment.metadata['action_required']['completion_data'] = action_data
            
            # Update status based on success
            if success:
                # Status will be updated by webhook or next status check
                payment.status = PaymentStatus.PROCESSING
            else:
                payment.status = PaymentStatus.FAILED
                payment.failure_code = 'action_failed'
                payment.failure_message = 'User action was not completed successfully'
            
            # Track the event
            # TODO: Fix order_tracking_service instance
            # await order_tracking_service.track_payment_event(
            #     db=db,
            #     order_id=payment.order_id,
            #     payment_id=payment.id,
            #     event_type='payment_action_completed',
            #     success=success
            # )
            
            await db.commit()
            return payment
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to complete payment action: {e}")
            raise
    
    async def check_expired_actions(
        self,
        db: AsyncSession,
        cancel_expired: bool = True
    ) -> List[Payment]:
        """
        Check for payments with expired actions
        
        Args:
            db: Database session
            cancel_expired: Whether to cancel expired payments
            
        Returns:
            List of expired payments
        """
        try:
            # Find payments requiring action
            result = await db.execute(
                select(Payment).where(
                    and_(
                        Payment.status == PaymentStatus.REQUIRES_ACTION,
                        Payment.created_at < datetime.utcnow() - timedelta(minutes=30)
                    )
                )
            )
            
            expired_payments = result.scalars().all()
            
            if cancel_expired:
                for payment in expired_payments:
                    payment.status = PaymentStatus.CANCELLED
                    payment.failure_code = 'action_expired'
                    payment.failure_message = 'Payment action expired'
                    
                    # Track cancellation
                    # TODO: Fix order_tracking_service instance
                    # await order_tracking_service.track_payment_event(
                    #     db=db,
                    #     order_id=payment.order_id,
                    #     payment_id=payment.id,
                    #     event_type='payment_cancelled',
                    #     reason='action_expired'
                    # )
                
                await db.commit()
            
            return expired_payments
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to check expired actions: {e}")
            raise
    
    def _get_action_instructions(
        self,
        gateway: PaymentGateway,
        action_type: str
    ) -> Dict[str, str]:
        """Get user-friendly instructions for payment actions"""
        
        instructions = {
            PaymentGateway.STRIPE: {
                'redirect': {
                    'title': 'Verify Your Payment',
                    'description': 'Your bank requires additional verification. You will be redirected to complete this step.',
                    'button_text': 'Verify Payment'
                },
                '3d_secure': {
                    'title': '3D Secure Verification Required',
                    'description': 'Your card issuer requires additional authentication for this payment.',
                    'button_text': 'Complete Verification'
                }
            },
            PaymentGateway.PAYPAL: {
                'redirect': {
                    'title': 'Complete Payment with PayPal',
                    'description': 'You will be redirected to PayPal to approve this payment.',
                    'button_text': 'Continue to PayPal'
                },
                'approval': {
                    'title': 'PayPal Approval Required',
                    'description': 'Please log in to PayPal and approve this payment to continue.',
                    'button_text': 'Approve Payment'
                }
            },
            PaymentGateway.SQUARE: {
                'redirect': {
                    'title': 'Additional Verification Required',
                    'description': 'Please complete the verification process to proceed with your payment.',
                    'button_text': 'Verify Payment'
                }
            }
        }
        
        gateway_instructions = instructions.get(gateway, {})
        action_instructions = gateway_instructions.get(action_type, {})
        
        # Default instructions if not found
        if not action_instructions:
            action_instructions = {
                'title': 'Action Required',
                'description': 'Additional steps are required to complete your payment.',
                'button_text': 'Continue'
            }
        
        return action_instructions
    
    async def get_pending_actions(
        self,
        db: AsyncSession,
        customer_id: Optional[int] = None,
        order_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all pending payment actions
        
        Args:
            db: Database session
            customer_id: Filter by customer
            order_id: Filter by order
            
        Returns:
            List of pending actions
        """
        try:
            query = select(Payment).where(
                Payment.status == PaymentStatus.REQUIRES_ACTION
            )
            
            if customer_id:
                query = query.where(Payment.customer_id == customer_id)
            if order_id:
                query = query.where(Payment.order_id == order_id)
            
            result = await db.execute(query)
            payments = result.scalars().all()
            
            pending_actions = []
            for payment in payments:
                if payment.metadata and 'action_required' in payment.metadata:
                    action_data = payment.metadata['action_required']
                    
                    # Check if expired
                    expires_at = datetime.fromisoformat(action_data['expires_at'])
                    is_expired = datetime.utcnow() > expires_at
                    
                    pending_actions.append({
                        'payment_id': payment.payment_id,
                        'order_id': payment.order_id,
                        'amount': float(payment.amount),
                        'currency': payment.currency,
                        'gateway': payment.gateway,
                        'action_type': action_data['type'],
                        'action_url': action_data['url'],
                        'requested_at': action_data['requested_at'],
                        'expires_at': action_data['expires_at'],
                        'is_expired': is_expired,
                        'instructions': self._get_action_instructions(
                            payment.gateway,
                            action_data['type']
                        )
                    })
            
            return pending_actions
            
        except Exception as e:
            logger.error(f"Failed to get pending actions: {e}")
            raise


# Global service instance
payment_action_service = PaymentActionService()


# Background task to check expired actions
async def check_expired_payment_actions(ctx: dict) -> Dict[str, Any]:
    """
    Periodic task to check and cancel expired payment actions
    
    This runs every 5 minutes
    """
    from core.database import get_db
    
    cancelled_count = 0
    
    try:
        async for db in get_db():
            try:
                expired_payments = await payment_action_service.check_expired_actions(
                    db=db,
                    cancel_expired=True
                )
                
                cancelled_count = len(expired_payments)
                
                if cancelled_count > 0:
                    logger.info(f"Cancelled {cancelled_count} expired payment actions")
                
            finally:
                await db.close()
        
        return {
            'status': 'success',
            'cancelled_count': cancelled_count,
            'processed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to check expired payment actions: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'cancelled_count': cancelled_count
        }