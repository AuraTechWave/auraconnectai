# backend/modules/feedback/services/feedback_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
import logging

from modules.feedback.models.feedback_models import (
    Feedback,
    FeedbackResponse,
    FeedbackCategory,
    FeedbackStatus,
    FeedbackType,
    FeedbackPriority,
    SentimentScore,
)
from modules.feedback.schemas.feedback_schemas import (
    FeedbackCreate,
    FeedbackUpdate,
    FeedbackResponse as FeedbackResponseSchema,
    FeedbackSummary,
    FeedbackFilters,
    FeedbackResponseCreate,
    FeedbackCategoryCreate,
    FeedbackCategoryUpdate,
    PaginatedResponse,
)

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing customer feedback and support tickets"""

    def __init__(self, db: Session):
        self.db = db

    def create_feedback(
        self, feedback_data: FeedbackCreate, auto_categorize: bool = True
    ) -> FeedbackResponseSchema:
        """Create a new feedback entry"""

        try:
            # Create feedback instance
            feedback = Feedback(
                uuid=uuid.uuid4(),
                feedback_type=feedback_data.feedback_type,
                customer_id=feedback_data.customer_id,
                customer_email=feedback_data.customer_email,
                customer_name=feedback_data.customer_name,
                customer_phone=feedback_data.customer_phone,
                order_id=feedback_data.order_id,
                product_id=feedback_data.product_id,
                subject=feedback_data.subject,
                message=feedback_data.message,
                category=feedback_data.category,
                subcategory=feedback_data.subcategory,
                priority=feedback_data.priority,
                source=feedback_data.source,
                metadata=feedback_data.metadata or {},
                tags=feedback_data.tags or [],
                status=FeedbackStatus.NEW,
                follow_up_required=False,
            )

            self.db.add(feedback)
            self.db.flush()

            # Auto-categorize if enabled and no category provided
            if auto_categorize and not feedback_data.category:
                category = self._auto_categorize_feedback(feedback)
                if category:
                    feedback.category = category.name
                    feedback.subcategory = None  # Let admin refine this

                    # Check for auto-escalation rules
                    if category.auto_escalate:
                        feedback.priority = (
                            category.escalation_priority or FeedbackPriority.HIGH
                        )
                        self._auto_escalate_feedback(feedback, category)

            # Set follow-up requirements based on type and priority
            if feedback.feedback_type in [
                FeedbackType.COMPLAINT,
                FeedbackType.BUG_REPORT,
            ]:
                feedback.follow_up_required = True
                if feedback.priority in [
                    FeedbackPriority.HIGH,
                    FeedbackPriority.URGENT,
                ]:
                    feedback.follow_up_date = datetime.utcnow() + timedelta(hours=4)
                else:
                    feedback.follow_up_date = datetime.utcnow() + timedelta(days=1)

            self.db.commit()

            logger.info(
                f"Created feedback {feedback.id} from customer {feedback.customer_id or 'anonymous'}"
            )

            # Schedule sentiment analysis
            self._schedule_sentiment_analysis(feedback.id)

            # Send notifications if high priority
            if feedback.priority in [FeedbackPriority.HIGH, FeedbackPriority.URGENT]:
                self._send_priority_notification(feedback)

            return self._format_feedback_response(feedback)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating feedback: {e}")
            raise

    def get_feedback(self, feedback_id: int) -> FeedbackResponseSchema:
        """Get a specific feedback entry by ID"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        return self._format_feedback_response(feedback)

    def get_feedback_by_uuid(self, feedback_uuid: str) -> FeedbackResponseSchema:
        """Get feedback by UUID"""

        feedback = (
            self.db.query(Feedback).filter(Feedback.uuid == feedback_uuid).first()
        )
        if not feedback:
            raise KeyError(f"Feedback {feedback_uuid} not found")

        return self._format_feedback_response(feedback)

    def update_feedback(
        self,
        feedback_id: int,
        update_data: FeedbackUpdate,
        staff_id: Optional[int] = None,
    ) -> FeedbackResponseSchema:
        """Update an existing feedback entry"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        # Update allowed fields
        if update_data.subject is not None:
            feedback.subject = update_data.subject
        if update_data.message is not None:
            feedback.message = update_data.message
        if update_data.category is not None:
            feedback.category = update_data.category
        if update_data.subcategory is not None:
            feedback.subcategory = update_data.subcategory
        if update_data.priority is not None:
            old_priority = feedback.priority
            feedback.priority = update_data.priority
            # Log priority change
            if old_priority != feedback.priority:
                logger.info(
                    f"Feedback {feedback_id} priority changed: {old_priority} -> {feedback.priority}"
                )
        if update_data.status is not None:
            old_status = feedback.status
            feedback.status = update_data.status
            # Handle status transitions
            if old_status != feedback.status:
                self._handle_status_transition(feedback, old_status, feedback.status)
        if update_data.assigned_to is not None:
            feedback.assigned_to = update_data.assigned_to
            feedback.assigned_at = datetime.utcnow()
        if update_data.follow_up_required is not None:
            feedback.follow_up_required = update_data.follow_up_required
        if update_data.follow_up_date is not None:
            feedback.follow_up_date = update_data.follow_up_date
        if update_data.metadata is not None:
            feedback.metadata = {**(feedback.metadata or {}), **update_data.metadata}
        if update_data.tags is not None:
            feedback.tags = update_data.tags

        self.db.commit()

        logger.info(f"Updated feedback {feedback_id}")

        return self._format_feedback_response(feedback)

    def assign_feedback(
        self, feedback_id: int, assignee_id: int, assigner_id: int
    ) -> FeedbackResponseSchema:
        """Assign feedback to a staff member"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        old_assignee = feedback.assigned_to
        feedback.assigned_to = assignee_id
        feedback.assigned_at = datetime.utcnow()

        # Update status if it's new
        if feedback.status == FeedbackStatus.NEW:
            feedback.status = FeedbackStatus.IN_PROGRESS

        self.db.commit()

        logger.info(
            f"Assigned feedback {feedback_id}: {old_assignee} -> {assignee_id} by {assigner_id}"
        )

        # Send assignment notification
        self._send_assignment_notification(feedback, assignee_id)

        return self._format_feedback_response(feedback)

    def resolve_feedback(
        self, feedback_id: int, resolution_notes: str, resolver_id: int
    ) -> FeedbackResponseSchema:
        """Mark feedback as resolved"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        feedback.status = FeedbackStatus.RESOLVED
        feedback.resolved_at = datetime.utcnow()
        feedback.resolution_notes = resolution_notes
        feedback.follow_up_required = False

        self.db.commit()

        logger.info(f"Resolved feedback {feedback_id} by {resolver_id}")

        # Send resolution notification to customer
        self._send_resolution_notification(feedback)

        return self._format_feedback_response(feedback)

    def escalate_feedback(
        self,
        feedback_id: int,
        escalated_to: int,
        escalator_id: int,
        reason: Optional[str] = None,
    ) -> FeedbackResponseSchema:
        """Escalate feedback to higher level support"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        feedback.status = FeedbackStatus.ESCALATED
        feedback.escalated_at = datetime.utcnow()
        feedback.escalated_to = escalated_to
        feedback.priority = FeedbackPriority.HIGH  # Escalated items get high priority

        # Add escalation note
        if reason:
            escalation_metadata = feedback.metadata or {}
            escalation_metadata["escalation_reason"] = reason
            escalation_metadata["escalated_by"] = escalator_id
            feedback.metadata = escalation_metadata

        self.db.commit()

        logger.info(
            f"Escalated feedback {feedback_id} to {escalated_to} by {escalator_id}"
        )

        # Send escalation notifications
        self._send_escalation_notification(feedback, escalated_to)

        return self._format_feedback_response(feedback)

    def add_feedback_response(
        self, feedback_id: int, response_data: FeedbackResponseCreate
    ) -> Dict[str, Any]:
        """Add a response to feedback"""

        feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise KeyError(f"Feedback {feedback_id} not found")

        # Create feedback response
        response = FeedbackResponse(
            uuid=uuid.uuid4(),
            feedback_id=feedback_id,
            message=response_data.message,
            responder_id=response_data.responder_id,
            responder_name=response_data.responder_name,
            is_internal=response_data.is_internal,
            is_resolution=response_data.is_resolution,
            metadata=response_data.metadata or {},
        )

        self.db.add(response)

        # Update feedback status if this is a resolution response
        if response_data.is_resolution:
            feedback.status = FeedbackStatus.RESOLVED
            feedback.resolved_at = datetime.utcnow()
            feedback.resolution_notes = response_data.message
            feedback.follow_up_required = False
        elif feedback.status == FeedbackStatus.NEW:
            # First response moves to in progress
            feedback.status = FeedbackStatus.IN_PROGRESS

        self.db.commit()

        logger.info(f"Added response to feedback {feedback_id}")

        # Send notification if not internal
        if not response_data.is_internal:
            self._send_response_notification(feedback, response)

        return {
            "success": True,
            "response_id": response.id,
            "response_uuid": str(response.uuid),
            "message": "Response added successfully",
        }

    def list_feedback(
        self,
        filters: Optional[FeedbackFilters] = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse:
        """List feedback with filtering and pagination"""

        query = self.db.query(Feedback)

        # Apply filters
        if filters:
            if filters.feedback_type:
                query = query.filter(Feedback.feedback_type == filters.feedback_type)
            if filters.status:
                query = query.filter(Feedback.status == filters.status)
            if filters.priority:
                query = query.filter(Feedback.priority == filters.priority)
            if filters.category:
                query = query.filter(Feedback.category == filters.category)
            if filters.assigned_to:
                query = query.filter(Feedback.assigned_to == filters.assigned_to)
            if filters.customer_id:
                query = query.filter(Feedback.customer_id == filters.customer_id)
            if filters.date_from:
                query = query.filter(Feedback.created_at >= filters.date_from)
            if filters.date_to:
                query = query.filter(Feedback.created_at <= filters.date_to)
            if filters.sentiment:
                query = query.filter(Feedback.sentiment_score == filters.sentiment)
            if filters.follow_up_required is not None:
                query = query.filter(
                    Feedback.follow_up_required == filters.follow_up_required
                )
            if filters.tags:
                # Filter by tags (JSON contains any of the specified tags)
                tag_conditions = [
                    func.json_extract(Feedback.tags, f"$[{i}]").in_(filters.tags)
                    for i in range(10)  # Check first 10 tag positions
                ]
                query = query.filter(or_(*tag_conditions))

        # Apply sorting
        if hasattr(Feedback, sort_by):
            sort_column = getattr(Feedback, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        feedback_items = query.offset(offset).limit(per_page).all()

        # Format response
        items = [self._format_feedback_summary(feedback) for feedback in feedback_items]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total,
            has_prev=page > 1,
        )

    def get_feedback_analytics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get feedback analytics and metrics"""

        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        base_query = self.db.query(Feedback).filter(
            Feedback.created_at.between(start_date, end_date)
        )

        # Basic metrics
        total_feedback = base_query.count()

        # Feedback by type
        feedback_by_type = {}
        for feedback_type in FeedbackType:
            count = base_query.filter(Feedback.feedback_type == feedback_type).count()
            feedback_by_type[feedback_type.value] = count

        # Feedback by status
        feedback_by_status = {}
        for status in FeedbackStatus:
            count = base_query.filter(Feedback.status == status).count()
            feedback_by_status[status.value] = count

        # Feedback by priority
        feedback_by_priority = {}
        for priority in FeedbackPriority:
            count = base_query.filter(Feedback.priority == priority).count()
            feedback_by_priority[priority.value] = count

        # Resolution metrics
        resolved_feedback = base_query.filter(
            Feedback.status == FeedbackStatus.RESOLVED
        )
        resolution_times = []

        for feedback in resolved_feedback:
            if feedback.resolved_at:
                resolution_time = (
                    feedback.resolved_at - feedback.created_at
                ).total_seconds() / 3600  # hours
                resolution_times.append(resolution_time)

        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )

        # Escalation rate
        escalated_count = base_query.filter(
            Feedback.status == FeedbackStatus.ESCALATED
        ).count()
        escalation_rate = (
            (escalated_count / total_feedback * 100) if total_feedback > 0 else 0
        )

        # Sentiment distribution
        sentiment_distribution = {}
        for sentiment in SentimentScore:
            count = base_query.filter(Feedback.sentiment_score == sentiment).count()
            sentiment_distribution[sentiment.value] = count

        # Daily trends
        daily_trends = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_count = base_query.filter(
                func.date(Feedback.created_at) == current_date
            ).count()
            daily_trends.append({"date": current_date.isoformat(), "count": day_count})
            current_date += timedelta(days=1)

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": (end_date - start_date).days,
            },
            "total_feedback": total_feedback,
            "feedback_by_type": feedback_by_type,
            "feedback_by_status": feedback_by_status,
            "feedback_by_priority": feedback_by_priority,
            "sentiment_distribution": sentiment_distribution,
            "resolution_time_avg": round(avg_resolution_time, 2),
            "escalation_rate": round(escalation_rate, 2),
            "daily_trends": daily_trends,
        }

    # Category management methods

    def create_feedback_category(
        self, category_data: FeedbackCategoryCreate
    ) -> Dict[str, Any]:
        """Create a new feedback category"""

        # Check for duplicate name
        existing = (
            self.db.query(FeedbackCategory)
            .filter(FeedbackCategory.name == category_data.name)
            .first()
        )

        if existing:
            raise ValueError(f"Category '{category_data.name}' already exists")

        category = FeedbackCategory(
            name=category_data.name,
            description=category_data.description,
            parent_id=category_data.parent_id,
            sort_order=category_data.sort_order,
            auto_assign_keywords=category_data.auto_assign_keywords or [],
            auto_escalate=category_data.auto_escalate,
            escalation_priority=category_data.escalation_priority,
            escalation_conditions=category_data.escalation_conditions or {},
        )

        self.db.add(category)
        self.db.commit()

        logger.info(f"Created feedback category: {category.name}")

        return {
            "success": True,
            "category_id": category.id,
            "message": "Category created successfully",
        }

    def list_feedback_categories(
        self, include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """List all feedback categories"""

        query = self.db.query(FeedbackCategory)

        if not include_inactive:
            query = query.filter(FeedbackCategory.is_active == True)

        categories = query.order_by(
            FeedbackCategory.sort_order, FeedbackCategory.name
        ).all()

        return [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "parent_id": cat.parent_id,
                "is_active": cat.is_active,
                "auto_escalate": cat.auto_escalate,
                "sort_order": cat.sort_order,
            }
            for cat in categories
        ]

    # Private helper methods

    def _auto_categorize_feedback(
        self, feedback: Feedback
    ) -> Optional[FeedbackCategory]:
        """Automatically categorize feedback based on keywords"""

        # Get all categories with auto-assign keywords
        categories = (
            self.db.query(FeedbackCategory)
            .filter(
                and_(
                    FeedbackCategory.is_active == True,
                    FeedbackCategory.auto_assign_keywords.isnot(None),
                )
            )
            .all()
        )

        feedback_text = f"{feedback.subject} {feedback.message}".lower()

        for category in categories:
            if category.auto_assign_keywords:
                for keyword in category.auto_assign_keywords:
                    if keyword.lower() in feedback_text:
                        return category

        return None

    def _auto_escalate_feedback(
        self, feedback: Feedback, category: FeedbackCategory
    ) -> None:
        """Auto-escalate feedback based on category rules"""

        if not category.auto_escalate or not category.escalation_conditions:
            return

        conditions = category.escalation_conditions
        should_escalate = False

        # Check escalation conditions
        if "keywords" in conditions:
            feedback_text = f"{feedback.subject} {feedback.message}".lower()
            for keyword in conditions["keywords"]:
                if keyword.lower() in feedback_text:
                    should_escalate = True
                    break

        if "priority" in conditions:
            if feedback.priority.value in conditions["priority"]:
                should_escalate = True

        if should_escalate:
            feedback.status = FeedbackStatus.ESCALATED
            feedback.escalated_at = datetime.utcnow()
            # Would set escalated_to based on category configuration
            logger.info(f"Auto-escalated feedback {feedback.id} due to category rules")

    def _handle_status_transition(
        self, feedback: Feedback, old_status: FeedbackStatus, new_status: FeedbackStatus
    ) -> None:
        """Handle feedback status transitions"""

        if new_status == FeedbackStatus.RESOLVED:
            feedback.resolved_at = datetime.utcnow()
            feedback.follow_up_required = False
        elif new_status == FeedbackStatus.CLOSED:
            if not feedback.resolved_at:
                feedback.resolved_at = datetime.utcnow()
            feedback.follow_up_required = False

        logger.info(f"Feedback {feedback.id} status: {old_status} -> {new_status}")

    def _schedule_sentiment_analysis(self, feedback_id: int) -> None:
        """Schedule sentiment analysis for feedback"""

        # This would integrate with a sentiment analysis service
        logger.info(f"Scheduled sentiment analysis for feedback {feedback_id}")

    def _send_priority_notification(self, feedback: Feedback) -> None:
        """Send notification for high priority feedback"""

        # This would integrate with notification service
        logger.info(f"Sent priority notification for feedback {feedback.id}")

    def _send_assignment_notification(
        self, feedback: Feedback, assignee_id: int
    ) -> None:
        """Send notification about feedback assignment"""

        # This would integrate with notification service
        logger.info(
            f"Sent assignment notification for feedback {feedback.id} to {assignee_id}"
        )

    def _send_resolution_notification(self, feedback: Feedback) -> None:
        """Send resolution notification to customer"""

        # This would integrate with notification service
        logger.info(f"Sent resolution notification for feedback {feedback.id}")

    def _send_escalation_notification(
        self, feedback: Feedback, escalated_to: int
    ) -> None:
        """Send escalation notification"""

        # This would integrate with notification service
        logger.info(
            f"Sent escalation notification for feedback {feedback.id} to {escalated_to}"
        )

    def _send_response_notification(
        self, feedback: Feedback, response: FeedbackResponse
    ) -> None:
        """Send notification about new response"""

        # This would integrate with notification service
        logger.info(f"Sent response notification for feedback {feedback.id}")

    def _format_feedback_response(self, feedback: Feedback) -> FeedbackResponseSchema:
        """Format feedback for API response"""

        return FeedbackResponseSchema(
            id=feedback.id,
            uuid=str(feedback.uuid),
            feedback_type=feedback.feedback_type,
            status=feedback.status,
            priority=feedback.priority,
            source=feedback.source,
            customer_id=feedback.customer_id,
            customer_email=feedback.customer_email,
            customer_name=feedback.customer_name,
            customer_phone=feedback.customer_phone,
            order_id=feedback.order_id,
            product_id=feedback.product_id,
            subject=feedback.subject,
            message=feedback.message,
            category=feedback.category,
            subcategory=feedback.subcategory,
            assigned_to=feedback.assigned_to,
            assigned_at=feedback.assigned_at,
            resolved_at=feedback.resolved_at,
            resolution_notes=feedback.resolution_notes,
            sentiment_score=feedback.sentiment_score,
            sentiment_confidence=feedback.sentiment_confidence,
            follow_up_required=feedback.follow_up_required,
            follow_up_date=feedback.follow_up_date,
            escalated_at=feedback.escalated_at,
            escalated_to=feedback.escalated_to,
            tags=feedback.tags,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )

    def _format_feedback_summary(self, feedback: Feedback) -> FeedbackSummary:
        """Format feedback summary for list responses"""

        return FeedbackSummary(
            id=feedback.id,
            uuid=str(feedback.uuid),
            feedback_type=feedback.feedback_type,
            status=feedback.status,
            priority=feedback.priority,
            subject=feedback.subject,
            customer_id=feedback.customer_id,
            customer_name=feedback.customer_name,
            assigned_to=feedback.assigned_to,
            sentiment_score=feedback.sentiment_score,
            created_at=feedback.created_at,
        )
