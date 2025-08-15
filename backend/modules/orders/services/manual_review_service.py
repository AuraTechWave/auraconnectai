# backend/modules/orders/services/manual_review_service.py

from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import HTTPException

from ..models.manual_review_models import (
    ManualReviewQueue,
    InventoryAdjustmentAttempt,
    ReviewReason,
    ReviewStatus,
)
from ..models.order_models import Order
from ..enums.order_enums import OrderStatus
from ..exceptions.inventory_exceptions import InventoryDeductionError
from ..utils.inventory_logging import InventoryLogger
from ..utils.audit_logger import AuditLogger, audit_action
from core.notification_service import NotificationService


class ManualReviewService:
    """Service for handling manual review processes for failed inventory deductions"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = InventoryLogger("manual_review")
        self.audit_logger = AuditLogger("manual_review")
        self.notification_service = NotificationService(db)

    async def create_review_request(
        self,
        order_id: int,
        reason: ReviewReason,
        error: Optional[InventoryDeductionError] = None,
        error_details: Optional[Dict] = None,
        priority: int = 0,
    ) -> ManualReviewQueue:
        """
        Create a manual review request for an order

        Args:
            order_id: Order requiring review
            reason: Reason for manual review
            error: Original error that triggered the review
            error_details: Additional error details
            priority: Priority level (0-10, higher = more urgent)

        Returns:
            ManualReviewQueue entry
        """
        try:
            # Check if review already exists
            existing = (
                self.db.query(ManualReviewQueue)
                .filter(
                    ManualReviewQueue.order_id == order_id,
                    ManualReviewQueue.status.in_(
                        [ReviewStatus.PENDING, ReviewStatus.IN_REVIEW]
                    ),
                )
                .first()
            )

            if existing:
                # Update priority if higher
                if priority > existing.priority:
                    existing.priority = priority
                    self.db.commit()
                return existing

            # Create review entry
            review = ManualReviewQueue(
                order_id=order_id,
                reason=reason,
                status=ReviewStatus.PENDING,
                error_details=error.details if error else error_details,
                error_message=str(error) if error else None,
                priority=priority,
                created_at=datetime.utcnow(),
            )

            self.db.add(review)

            # Update order status to indicate review needed
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.requires_manual_review = True
                order.review_reason = reason.value

            self.db.commit()

            # Log the review request
            self.logger.log_manual_review_required(
                order_id=order_id,
                reason=reason.value,
                details=error.details if error else error_details,
            )

            # Send notification to managers
            await self._notify_managers_of_review(review, order)

            return review

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error creating manual review request: {str(e)}",
            )

    async def log_deduction_attempt(
        self,
        order_id: int,
        user_id: int,
        error: Exception,
        attempted_deductions: List[Dict],
        menu_items_affected: List[Dict],
    ) -> InventoryAdjustmentAttempt:
        """
        Log a failed inventory adjustment attempt

        Args:
            order_id: Order ID
            user_id: User who attempted the adjustment
            error: The error that occurred
            attempted_deductions: What deductions were attempted
            menu_items_affected: Menu items that couldn't be processed

        Returns:
            InventoryAdjustmentAttempt entry
        """
        try:
            # Count previous attempts
            attempt_count = (
                self.db.query(InventoryAdjustmentAttempt)
                .filter(InventoryAdjustmentAttempt.order_id == order_id)
                .count()
            )

            # Create attempt log
            attempt = InventoryAdjustmentAttempt(
                order_id=order_id,
                attempt_number=attempt_count + 1,
                error_type=error.__class__.__name__,
                error_message=str(error),
                error_details=getattr(error, "details", None),
                attempted_deductions=attempted_deductions,
                menu_items_affected=menu_items_affected,
                attempted_by=user_id,
                attempted_at=datetime.utcnow(),
            )

            self.db.add(attempt)
            self.db.commit()

            return attempt

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error logging deduction attempt: {str(e)}"
            )

    async def get_pending_reviews(
        self, limit: int = 50, offset: int = 0, priority_threshold: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get pending manual reviews

        Args:
            limit: Maximum number of reviews to return
            offset: Offset for pagination
            priority_threshold: Only return reviews with priority >= threshold

        Returns:
            Dict with reviews and metadata
        """
        query = self.db.query(ManualReviewQueue).filter(
            ManualReviewQueue.status == ReviewStatus.PENDING
        )

        if priority_threshold is not None:
            query = query.filter(ManualReviewQueue.priority >= priority_threshold)

        # Order by priority (descending) and creation date
        query = query.order_by(
            ManualReviewQueue.priority.desc(), ManualReviewQueue.created_at.asc()
        )

        total = query.count()
        reviews = query.offset(offset).limit(limit).all()

        return {
            "reviews": reviews,
            "total": total,
            "has_more": total > offset + limit,
            "high_priority_count": self.db.query(ManualReviewQueue)
            .filter(
                ManualReviewQueue.status == ReviewStatus.PENDING,
                ManualReviewQueue.priority >= 7,
            )
            .count(),
        }

    @audit_action("assign_review", "manual_review")
    async def assign_review(
        self, review_id: int, assignee_id: int, assigned_by: Optional[int] = None
    ) -> ManualReviewQueue:
        """Assign a review to a user"""
        review = (
            self.db.query(ManualReviewQueue)
            .filter(ManualReviewQueue.id == review_id)
            .first()
        )

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        old_assignee = review.assigned_to
        review.assigned_to = assignee_id
        review.assigned_at = datetime.utcnow()
        review.status = ReviewStatus.IN_REVIEW

        self.db.commit()

        # Audit log the assignment
        self.audit_logger.log_action(
            action="assign_review",
            user_id=assigned_by or assignee_id,
            resource_type="manual_review",
            resource_id=review_id,
            details={
                "order_id": review.order_id,
                "assignee_id": assignee_id,
                "old_assignee_id": old_assignee,
                "reason": review.reason.value,
                "priority": review.priority,
            },
        )

        return review

    @audit_action("resolve_review", "manual_review")
    async def resolve_review(
        self,
        review_id: int,
        reviewer_id: int,
        resolution_action: str,
        notes: Optional[str] = None,
        mark_order_completed: bool = False,
    ) -> ManualReviewQueue:
        """
        Resolve a manual review

        Args:
            review_id: Review to resolve
            reviewer_id: User resolving the review
            resolution_action: Action taken to resolve
            notes: Additional notes
            mark_order_completed: Whether to mark the order as completed

        Returns:
            Updated review
        """
        review = (
            self.db.query(ManualReviewQueue)
            .filter(ManualReviewQueue.id == review_id)
            .first()
        )

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # Store old status for audit
        old_status = review.status
        old_order_status = review.order.status if review.order else None

        review.reviewed_by = reviewer_id
        review.reviewed_at = datetime.utcnow()
        review.resolved_at = datetime.utcnow()
        review.status = ReviewStatus.RESOLVED
        review.resolution_action = resolution_action
        review.review_notes = notes

        # Update order if requested
        order_updated = False
        if mark_order_completed:
            order = review.order
            if order:
                order.requires_manual_review = False
                order.review_reason = None
                if order.status not in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
                    order.status = OrderStatus.COMPLETED
                    order_updated = True

        self.db.commit()

        # Comprehensive audit logging
        self.audit_logger.log_action(
            action="resolve_review",
            user_id=reviewer_id,
            resource_type="manual_review",
            resource_id=review_id,
            details={
                "order_id": review.order_id,
                "reason": review.reason.value,
                "old_status": old_status.value,
                "new_status": review.status.value,
                "resolution_action": resolution_action,
                "notes_provided": notes is not None,
                "order_updated": order_updated,
                "old_order_status": (
                    old_order_status.value if old_order_status else None
                ),
                "new_order_status": review.order.status.value if review.order else None,
                "review_duration_hours": (
                    (review.resolved_at - review.created_at).total_seconds() / 3600
                    if review.resolved_at and review.created_at
                    else None
                ),
            },
        )

        # Log resolution
        self.logger.logger.info(
            f"Manual review resolved for order {review.order_id}",
            extra=self.logger._format_extra_data(
                event="review_resolved",
                review_id=review_id,
                order_id=review.order_id,
                resolution_action=resolution_action,
                reviewer_id=reviewer_id,
            ),
        )

        return review

    @audit_action("escalate_review", "manual_review")
    async def escalate_review(
        self, review_id: int, escalation_reason: str, escalated_by: int
    ) -> ManualReviewQueue:
        """Escalate a review to higher management"""
        review = (
            self.db.query(ManualReviewQueue)
            .filter(ManualReviewQueue.id == review_id)
            .first()
        )

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # Store old values for audit
        old_status = review.status
        old_priority = review.priority

        review.escalated = True
        review.escalation_reason = escalation_reason
        review.status = ReviewStatus.ESCALATED
        review.priority = max(review.priority, 8)  # Ensure high priority

        self.db.commit()

        # Audit log the escalation
        self.audit_logger.log_action(
            action="escalate_review",
            user_id=escalated_by,
            resource_type="manual_review",
            resource_id=review_id,
            details={
                "order_id": review.order_id,
                "reason": review.reason.value,
                "escalation_reason": escalation_reason,
                "old_status": old_status.value,
                "new_status": review.status.value,
                "old_priority": old_priority,
                "new_priority": review.priority,
                "time_before_escalation_hours": (
                    (datetime.utcnow() - review.created_at).total_seconds() / 3600
                    if review.created_at
                    else None
                ),
            },
        )

        # Log security event for escalations
        self.audit_logger.log_security_event(
            event_type="review_escalated",
            user_id=escalated_by,
            details={
                "review_id": review_id,
                "order_id": review.order_id,
                "escalation_reason": escalation_reason,
            },
            severity="high",
        )

        # Send escalation notification
        await self._notify_escalation(review, escalated_by)

        return review

    async def get_review_statistics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get statistics about manual reviews"""
        query = self.db.query(ManualReviewQueue)

        if start_date:
            query = query.filter(ManualReviewQueue.created_at >= start_date)
        if end_date:
            query = query.filter(ManualReviewQueue.created_at <= end_date)

        total_reviews = query.count()

        # Get counts by status
        status_counts = {}
        for status in ReviewStatus:
            count = query.filter(ManualReviewQueue.status == status).count()
            status_counts[status.value] = count

        # Get counts by reason
        reason_counts = {}
        for reason in ReviewReason:
            count = query.filter(ManualReviewQueue.reason == reason).count()
            reason_counts[reason.value] = count

        # Calculate average resolution time
        resolved_reviews = query.filter(
            ManualReviewQueue.status == ReviewStatus.RESOLVED,
            ManualReviewQueue.resolved_at.isnot(None),
        ).all()

        avg_resolution_time = None
        if resolved_reviews:
            total_time = sum(
                (r.resolved_at - r.created_at).total_seconds() for r in resolved_reviews
            )
            avg_resolution_time = total_time / len(resolved_reviews) / 3600  # In hours

        return {
            "total_reviews": total_reviews,
            "status_breakdown": status_counts,
            "reason_breakdown": reason_counts,
            "average_resolution_time_hours": avg_resolution_time,
            "escalation_rate": (
                status_counts.get(ReviewStatus.ESCALATED.value, 0) / total_reviews * 100
                if total_reviews > 0
                else 0
            ),
        }

    async def _notify_managers_of_review(self, review: ManualReviewQueue, order: Order):
        """Send notification to managers about new review request"""
        try:
            message = (
                f"Manual review required for Order #{order.order_number}\n"
                f"Reason: {review.reason.value.replace('_', ' ').title()}\n"
                f"Priority: {review.priority}/10\n"
                f"Error: {review.error_message[:100] if review.error_message else 'N/A'}"
            )

            await self.notification_service.send_role_notification(
                role="manager",
                subject=f"Manual Review Required - Order #{order.order_number}",
                message=message,
                priority="high" if review.priority >= 7 else "normal",
            )
        except Exception as e:
            self.logger.logger.error(f"Failed to send review notification: {str(e)}")

    async def _notify_escalation(self, review: ManualReviewQueue, escalated_by: int):
        """Send notification about escalated review"""
        try:
            order = review.order
            message = (
                f"Review ESCALATED for Order #{order.order_number}\n"
                f"Original Reason: {review.reason.value.replace('_', ' ').title()}\n"
                f"Escalation Reason: {review.escalation_reason}\n"
                f"Escalated By: User {escalated_by}\n"
                f"Created: {review.created_at.strftime('%Y-%m-%d %H:%M')}"
            )

            await self.notification_service.send_role_notification(
                role="admin",
                subject=f"ESCALATED: Manual Review - Order #{order.order_number}",
                message=message,
                priority="urgent",
            )
        except Exception as e:
            self.logger.logger.error(
                f"Failed to send escalation notification: {str(e)}"
            )
