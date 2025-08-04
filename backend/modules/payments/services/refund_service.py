# backend/modules/payments/services/refund_service.py

import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.exceptions import ValidationError, AuthorizationError
from ..models.payment_models import Payment, PaymentStatus, Refund, RefundStatus
from ..models.refund_models import (
    RefundRequest, RefundPolicy, RefundAuditLog,
    RefundReason, RefundCategory, RefundApprovalStatus,
    get_refund_category
)
from ..services.payment_service import payment_service
from ...orders.models.order_models import Order, OrderStatus, OrderItem
from ...notifications.services.notification_service import notification_service
from ...orders.utils.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class RefundService:
    """
    Comprehensive refund processing service
    """
    
    def __init__(self):
        self.audit_logger = AuditLogger("refunds")
    
    async def create_refund_request(
        self,
        db: AsyncSession,
        order_id: int,
        payment_id: int,
        requested_amount: Decimal,
        reason_code: RefundReason,
        reason_details: Optional[str] = None,
        customer_info: Optional[Dict[str, Any]] = None,
        refund_items: Optional[List[Dict[str, Any]]] = None,
        evidence_urls: Optional[List[str]] = None,
        priority: str = "normal",
        auto_process: bool = True,
        batch_id: Optional[str] = None,
        batch_notes: Optional[str] = None
    ) -> RefundRequest:
        """
        Create a refund request with validation and policy checks
        
        Args:
            db: Database session
            order_id: Order to refund
            payment_id: Payment to refund
            requested_amount: Amount to refund
            reason_code: Standardized reason code
            reason_details: Additional details
            customer_info: Customer details
            refund_items: Specific items to refund (for partial)
            evidence_urls: Supporting evidence
            priority: Request priority
            auto_process: Attempt automatic processing
            
        Returns:
            Created RefundRequest
        """
        try:
            # Validate payment and order
            payment = await db.get(Payment, payment_id)
            if not payment:
                raise ValidationError(f"Payment {payment_id} not found")
            
            order = await db.get(Order, order_id)
            if not order:
                raise ValidationError(f"Order {order_id} not found")
            
            if payment.order_id != order_id:
                raise ValidationError("Payment does not belong to this order")
            
            # Check payment status
            if payment.status not in [PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED]:
                raise ValidationError(f"Cannot refund payment in status {payment.status}")
            
            # Validate refund amount
            await self._validate_refund_amount(db, payment, requested_amount)
            
            # Get applicable refund policy
            policy = await self._get_refund_policy(db, order.restaurant_id)
            
            # Check time window
            if policy and policy.refund_window_hours:
                time_since_payment = datetime.utcnow() - payment.processed_at
                if time_since_payment > timedelta(hours=policy.refund_window_hours):
                    raise ValidationError(
                        f"Refund window of {policy.refund_window_hours} hours has expired"
                    )
            
            # Create refund request
            request = RefundRequest(
                request_number=f"RR-{secrets.token_hex(8).upper()}",
                order_id=order_id,
                payment_id=payment_id,
                requested_amount=requested_amount,
                reason_code=reason_code,
                category=get_refund_category(reason_code),
                reason_details=reason_details,
                customer_id=order.customer_id,
                customer_name=customer_info.get('name', order.customer_name) if customer_info else order.customer_name,
                customer_email=customer_info.get('email', order.customer_email) if customer_info else order.customer_email,
                customer_phone=customer_info.get('phone', order.customer_phone) if customer_info else order.customer_phone,
                refund_items=refund_items or [],
                evidence_urls=evidence_urls or [],
                priority=priority,
                batch_id=batch_id,
                batch_notes=batch_notes
            )
            
            # Check for automatic approval
            if auto_process and policy:
                if await self._check_auto_approval(request, policy):
                    request.approval_status = RefundApprovalStatus.AUTO_APPROVED
                    request.approved_at = datetime.utcnow()
            
            db.add(request)
            await db.flush()
            
            # Create audit log
            await self._create_audit_log(
                db,
                refund_request_id=request.id,
                action="created",
                actor_id=customer_info.get('user_id') if customer_info else None,
                actor_type="customer",
                reason=f"Refund request created: {reason_code.value}"
            )
            
            # Enhanced audit logging
            user_id = customer_info.get('user_id') if customer_info else 0
            self.audit_logger.log_action(
                action="create_refund_request",
                user_id=user_id,
                resource_type="refund_request",
                resource_id=request.id,
                details={
                    "request_number": request.request_number,
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "requested_amount": float(requested_amount),
                    "reason_code": reason_code.value,
                    "category": request.category.value,
                    "customer_name": request.customer_name,
                    "priority": priority,
                    "auto_approved": request.approval_status == RefundApprovalStatus.AUTO_APPROVED,
                    "batch_id": batch_id,
                    "items_count": len(refund_items) if refund_items else 0
                }
            )
            
            await db.commit()
            
            # Process if auto-approved
            if request.approval_status == RefundApprovalStatus.AUTO_APPROVED:
                try:
                    await self.process_refund_request(db, request.id, system_initiated=True)
                except Exception as e:
                    logger.error(f"Failed to auto-process refund request {request.id}: {e}")
            
            # Send notifications
            await self._send_refund_request_notifications(request)
            
            return request
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create refund request: {e}")
            raise
    
    async def _validate_refund_amount(
        self,
        db: AsyncSession,
        payment: Payment,
        requested_amount: Decimal
    ):
        """Validate the refund amount against payment and existing refunds"""
        
        if requested_amount <= 0:
            raise ValidationError("Refund amount must be positive")
        
        if requested_amount > payment.amount:
            raise ValidationError("Refund amount exceeds payment amount")
        
        # Check existing refunds
        result = await db.execute(
            select(func.sum(Refund.amount))
            .where(
                and_(
                    Refund.payment_id == payment.id,
                    Refund.status.in_([RefundStatus.COMPLETED, RefundStatus.PROCESSING])
                )
            )
        )
        
        total_refunded = result.scalar() or Decimal('0')
        
        if total_refunded + requested_amount > payment.amount:
            available = payment.amount - total_refunded
            raise ValidationError(
                f"Refund amount exceeds available amount. "
                f"Available: ${available:.2f}"
            )
    
    async def _get_refund_policy(
        self,
        db: AsyncSession,
        restaurant_id: int
    ) -> Optional[RefundPolicy]:
        """Get applicable refund policy for restaurant"""
        
        # First try to get default policy
        result = await db.execute(
            select(RefundPolicy)
            .where(
                and_(
                    RefundPolicy.restaurant_id == restaurant_id,
                    RefundPolicy.is_active == True,
                    RefundPolicy.is_default == True
                )
            )
        )
        
        policy = result.scalar_one_or_none()
        
        if not policy:
            # Get any active policy
            result = await db.execute(
                select(RefundPolicy)
                .where(
                    and_(
                        RefundPolicy.restaurant_id == restaurant_id,
                        RefundPolicy.is_active == True
                    )
                )
                .order_by(RefundPolicy.created_at.desc())
                .limit(1)
            )
            policy = result.scalar_one_or_none()
        
        return policy
    
    async def _check_auto_approval(
        self,
        request: RefundRequest,
        policy: RefundPolicy
    ) -> bool:
        """Check if refund qualifies for automatic approval"""
        
        if not policy.auto_approve_enabled:
            return False
        
        if request.requested_amount > policy.auto_approve_threshold:
            return False
        
        # Check reason codes that should not be auto-approved
        manual_review_reasons = [
            RefundReason.DUPLICATE_CHARGE,
            RefundReason.OVERCHARGE,
            RefundReason.PRICE_DISPUTE,
            RefundReason.TEST_REFUND
        ]
        
        if request.reason_code in manual_review_reasons:
            return False
        
        return True
    
    async def approve_refund_request(
        self,
        db: AsyncSession,
        request_id: int,
        approver_id: int,
        notes: Optional[str] = None,
        process_immediately: bool = True
    ) -> RefundRequest:
        """
        Approve a refund request
        
        Args:
            db: Database session
            request_id: Request to approve
            approver_id: User approving the request
            notes: Approval notes
            process_immediately: Process the refund immediately
            
        Returns:
            Updated RefundRequest
        """
        try:
            request = await db.get(RefundRequest, request_id)
            if not request:
                raise ValidationError(f"Refund request {request_id} not found")
            
            if request.approval_status != RefundApprovalStatus.PENDING_APPROVAL:
                raise ValidationError(
                    f"Request is not pending approval (status: {request.approval_status})"
                )
            
            # Update approval status
            request.approval_status = RefundApprovalStatus.APPROVED
            request.approved_by = approver_id
            request.approved_at = datetime.utcnow()
            
            if notes:
                request.notes = (request.notes or "") + f"\nApproval notes: {notes}"
            
            # Create audit log
            await self._create_audit_log(
                db,
                refund_request_id=request.id,
                action="approved",
                actor_id=approver_id,
                actor_type="user",
                reason=notes or "Refund request approved"
            )
            
            # Enhanced audit logging
            self.audit_logger.log_action(
                action="approve_refund_request",
                user_id=approver_id,
                resource_type="refund_request",
                resource_id=request_id,
                details={
                    "request_number": request.request_number,
                    "order_id": request.order_id,
                    "payment_id": request.payment_id,
                    "customer_name": request.customer_name,
                    "requested_amount": float(request.requested_amount),
                    "reason_code": request.reason_code.value,
                    "approval_notes": notes,
                    "process_immediately": process_immediately,
                    "batch_id": request.batch_id
                }
            )
            
            await db.commit()
            
            # Process if requested
            if process_immediately:
                await self.process_refund_request(db, request.id)
            
            return request
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to approve refund request: {e}")
            raise
    
    async def reject_refund_request(
        self,
        db: AsyncSession,
        request_id: int,
        rejector_id: int,
        reason: str
    ) -> RefundRequest:
        """Reject a refund request"""
        
        try:
            request = await db.get(RefundRequest, request_id)
            if not request:
                raise ValidationError(f"Refund request {request_id} not found")
            
            if request.approval_status != RefundApprovalStatus.PENDING_APPROVAL:
                raise ValidationError(
                    f"Request is not pending approval (status: {request.approval_status})"
                )
            
            # Update status
            request.approval_status = RefundApprovalStatus.REJECTED
            request.approved_by = rejector_id
            request.approved_at = datetime.utcnow()
            request.rejection_reason = reason
            
            # Create audit log
            await self._create_audit_log(
                db,
                refund_request_id=request.id,
                action="rejected",
                actor_id=rejector_id,
                actor_type="user",
                reason=f"Refund rejected: {reason}"
            )
            
            # Enhanced audit logging
            self.audit_logger.log_action(
                action="reject_refund_request",
                user_id=rejector_id,
                resource_type="refund_request",
                resource_id=request_id,
                details={
                    "request_number": request.request_number,
                    "order_id": request.order_id,
                    "payment_id": request.payment_id,
                    "customer_name": request.customer_name,
                    "requested_amount": float(request.requested_amount),
                    "reason_code": request.reason_code.value,
                    "rejection_reason": reason,
                    "batch_id": request.batch_id
                }
            )
            
            await db.commit()
            
            # Send rejection notification
            await self._send_refund_rejection_notification(request)
            
            return request
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to reject refund request: {e}")
            raise
    
    async def process_refund_request(
        self,
        db: AsyncSession,
        request_id: int,
        system_initiated: bool = False
    ) -> Tuple[RefundRequest, Refund]:
        """
        Process an approved refund request
        
        Args:
            db: Database session
            request_id: Request to process
            system_initiated: Whether system is processing (vs user)
            
        Returns:
            Tuple of (RefundRequest, Refund)
        """
        try:
            # Get request with payment
            result = await db.execute(
                select(RefundRequest)
                .options(selectinload(RefundRequest.payment))
                .where(RefundRequest.id == request_id)
            )
            request = result.scalar_one_or_none()
            
            if not request:
                raise ValidationError(f"Refund request {request_id} not found")
            
            if request.approval_status not in [
                RefundApprovalStatus.APPROVED,
                RefundApprovalStatus.AUTO_APPROVED
            ]:
                raise ValidationError("Refund request is not approved")
            
            if request.refund_id:
                raise ValidationError("Refund request already processed")
            
            # Create refund via payment service
            refund = await payment_service.create_refund(
                db=db,
                payment_id=request.payment_id,
                amount=request.requested_amount,
                reason=f"{request.reason_code.value}: {request.reason_details or ''}",
                initiated_by=request.approved_by,
                metadata={
                    'refund_request_id': request.id,
                    'reason_code': request.reason_code.value,
                    'category': request.category.value,
                    'refund_items': request.refund_items
                }
            )
            
            # Update request
            request.refund_id = refund.id
            request.processed_at = datetime.utcnow()
            
            # Create audit log
            await self._create_audit_log(
                db,
                refund_id=refund.id,
                refund_request_id=request.id,
                action="processed",
                actor_type="system" if system_initiated else "user",
                reason="Refund processed successfully"
            )
            
            await db.commit()
            
            # Send confirmation
            await self._send_refund_confirmation(request, refund)
            
            return request, refund
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to process refund request: {e}")
            raise
    
    async def get_refund_requests(
        self,
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[RefundRequest], int]:
        """
        Get refund requests with filtering
        
        Args:
            db: Database session
            filters: Filter criteria
            offset: Pagination offset
            limit: Pagination limit
            
        Returns:
            Tuple of (requests, total_count)
        """
        query = select(RefundRequest)
        count_query = select(func.count(RefundRequest.id))
        
        if filters:
            conditions = []
            
            if 'status' in filters:
                conditions.append(RefundRequest.approval_status == filters['status'])
            
            if 'customer_id' in filters:
                conditions.append(RefundRequest.customer_id == filters['customer_id'])
            
            if 'order_id' in filters:
                conditions.append(RefundRequest.order_id == filters['order_id'])
            
            if 'category' in filters:
                conditions.append(RefundRequest.category == filters['category'])
            
            if 'priority' in filters:
                conditions.append(RefundRequest.priority == filters['priority'])
            
            if 'date_from' in filters:
                conditions.append(RefundRequest.created_at >= filters['date_from'])
            
            if 'date_to' in filters:
                conditions.append(RefundRequest.created_at <= filters['date_to'])
            
            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(RefundRequest.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        return requests, total
    
    async def get_refund_statistics(
        self,
        db: AsyncSession,
        restaurant_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get refund statistics for reporting"""
        
        # Base query
        query = select(
            func.count(RefundRequest.id).label('total_requests'),
            func.sum(RefundRequest.requested_amount).label('total_amount'),
            func.avg(RefundRequest.requested_amount).label('avg_amount'),
            RefundRequest.category,
            RefundRequest.approval_status
        ).group_by(
            RefundRequest.category,
            RefundRequest.approval_status
        )
        
        # Apply filters
        conditions = []
        
        if restaurant_id:
            query = query.join(Order).where(Order.restaurant_id == restaurant_id)
        
        if date_from:
            conditions.append(RefundRequest.created_at >= date_from)
        
        if date_to:
            conditions.append(RefundRequest.created_at <= date_to)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        rows = result.all()
        
        # Process results
        stats = {
            'total_requests': 0,
            'total_amount': Decimal('0'),
            'avg_amount': Decimal('0'),
            'by_category': {},
            'by_status': {},
            'by_reason': {}
        }
        
        for row in rows:
            stats['total_requests'] += row.total_requests
            stats['total_amount'] += row.total_amount or Decimal('0')
            
            category = row.category.value if row.category else 'unknown'
            status = row.approval_status.value if row.approval_status else 'unknown'
            
            if category not in stats['by_category']:
                stats['by_category'][category] = {
                    'count': 0,
                    'amount': Decimal('0')
                }
            
            if status not in stats['by_status']:
                stats['by_status'][status] = {
                    'count': 0,
                    'amount': Decimal('0')
                }
            
            stats['by_category'][category]['count'] += row.total_requests
            stats['by_category'][category]['amount'] += row.total_amount or Decimal('0')
            
            stats['by_status'][status]['count'] += row.total_requests
            stats['by_status'][status]['amount'] += row.total_amount or Decimal('0')
        
        if stats['total_requests'] > 0:
            stats['avg_amount'] = stats['total_amount'] / stats['total_requests']
        
        # Get reason breakdown
        reason_query = select(
            RefundRequest.reason_code,
            func.count(RefundRequest.id).label('count'),
            func.sum(RefundRequest.requested_amount).label('amount')
        ).group_by(RefundRequest.reason_code)
        
        if conditions:
            reason_query = reason_query.where(and_(*conditions))
        
        reason_result = await db.execute(reason_query)
        
        for row in reason_result:
            reason = row.reason_code.value if row.reason_code else 'unknown'
            stats['by_reason'][reason] = {
                'count': row.count,
                'amount': float(row.amount or 0)
            }
        
        return stats
    
    async def _create_audit_log(
        self,
        db: AsyncSession,
        action: str,
        actor_id: Optional[int] = None,
        actor_type: str = "system",
        reason: Optional[str] = None,
        refund_id: Optional[int] = None,
        refund_request_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create audit log entry"""
        
        audit_log = RefundAuditLog(
            refund_id=refund_id,
            refund_request_id=refund_request_id,
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            audit_metadata=metadata or {}
        )
        
        db.add(audit_log)
    
    async def _send_refund_request_notifications(self, request: RefundRequest):
        """Send notifications for new refund request"""
        
        try:
            # Notify customer
            if request.customer_email:
                await notification_service.send_email(
                    to_email=request.customer_email,
                    subject=f"Refund Request Received - {request.request_number}",
                    template="refund_request_received",
                    context={
                        'customer_name': request.customer_name,
                        'request_number': request.request_number,
                        'amount': str(request.requested_amount),
                        'reason': request.reason_code.value.replace('_', ' ').title(),
                        'status': request.approval_status.value.replace('_', ' ').title()
                    }
                )
            
            # Notify manager if needed
            # This would be implemented based on policy settings
            
        except Exception as e:
            logger.error(f"Failed to send refund notifications: {e}")
    
    async def _send_refund_rejection_notification(self, request: RefundRequest):
        """Send notification for rejected refund"""
        
        try:
            if request.customer_email:
                await notification_service.send_email(
                    to_email=request.customer_email,
                    subject=f"Refund Request Update - {request.request_number}",
                    template="refund_request_rejected",
                    context={
                        'customer_name': request.customer_name,
                        'request_number': request.request_number,
                        'amount': str(request.requested_amount),
                        'reason': request.rejection_reason
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send rejection notification: {e}")
    
    async def _send_refund_confirmation(self, request: RefundRequest, refund: Refund):
        """Send refund confirmation"""
        
        try:
            if request.customer_email:
                await notification_service.send_email(
                    to_email=request.customer_email,
                    subject=f"Refund Processed - {request.request_number}",
                    template="refund_processed",
                    context={
                        'customer_name': request.customer_name,
                        'request_number': request.request_number,
                        'refund_id': refund.refund_id,
                        'amount': str(refund.amount),
                        'status': refund.status.value,
                        'expected_date': (datetime.utcnow() + timedelta(days=5)).strftime('%Y-%m-%d')
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")


# Global service instance
refund_service = RefundService()