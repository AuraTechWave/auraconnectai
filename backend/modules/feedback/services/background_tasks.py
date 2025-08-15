# backend/modules/feedback/services/background_tasks.py

"""
Background task processing for feedback and reviews module.

This module provides asynchronous task processing for:
- Sentiment analysis
- Content moderation
- Analytics calculations
- Review aggregation
- Notification sending
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from core.database import SessionLocal
from modules.feedback.models.feedback_models import (
    Review,
    Feedback,
    ReviewAggregate,
    SentimentScore,
)
from modules.feedback.services.sentiment_service import sentiment_service
from modules.feedback.services.moderation_service import ContentModerationService
from modules.feedback.services.aggregation_service import ReviewAggregationService
from modules.feedback.services.analytics_service import FeedbackAnalyticsService
from modules.feedback.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BackgroundTaskProcessor:
    """Handles background task processing for feedback and reviews"""

    def __init__(self):
        self.is_running = False
        self.task_queue = asyncio.Queue()
        self.workers = []

    async def start_workers(self, num_workers: int = 3):
        """Start background worker tasks"""
        if self.is_running:
            return

        self.is_running = True

        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

        logger.info(f"Started {num_workers} background task workers")

    async def stop_workers(self):
        """Stop all background workers"""
        self.is_running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

        logger.info("Stopped all background task workers")

    async def _worker(self, worker_name: str):
        """Background worker that processes tasks from the queue"""
        logger.info(f"Starting background worker: {worker_name}")

        while self.is_running:
            try:
                # Wait for a task with timeout
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)

                # Process the task
                await self._process_task(task, worker_name)

                # Mark task as done
                self.task_queue.task_done()

            except asyncio.TimeoutError:
                # No task available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Background worker stopped: {worker_name}")

    async def _process_task(self, task: Dict[str, Any], worker_name: str):
        """Process a single background task"""
        task_type = task.get("type")
        task_data = task.get("data", {})

        try:
            start_time = datetime.utcnow()

            if task_type == "sentiment_analysis":
                await self._process_sentiment_analysis(task_data)
            elif task_type == "content_moderation":
                await self._process_content_moderation(task_data)
            elif task_type == "review_aggregation":
                await self._process_review_aggregation(task_data)
            elif task_type == "analytics_calculation":
                await self._process_analytics_calculation(task_data)
            elif task_type == "notification":
                await self._process_notification(task_data)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                return

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Worker {worker_name} completed {task_type} task in {processing_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Worker {worker_name} failed to process {task_type}: {e}")

    async def _process_sentiment_analysis(self, data: Dict[str, Any]):
        """Process sentiment analysis for reviews and feedback"""
        db = SessionLocal()
        try:
            if data.get("review_id"):
                # Analyze review sentiment
                review = db.query(Review).filter(Review.id == data["review_id"]).first()
                if review:
                    result = sentiment_service.analyze_review_sentiment(
                        review, force_reanalysis=True
                    )

                    # Update review with sentiment data
                    review.sentiment_score = result.score
                    review.sentiment_confidence = result.confidence
                    review.sentiment_analysis_data = result.raw_data

                    db.commit()

            elif data.get("feedback_id"):
                # Analyze feedback sentiment
                feedback = (
                    db.query(Feedback)
                    .filter(Feedback.id == data["feedback_id"])
                    .first()
                )
                if feedback:
                    result = sentiment_service.analyze_feedback_sentiment(
                        feedback, force_reanalysis=True
                    )

                    # Update feedback with sentiment data
                    feedback.sentiment_score = result.score
                    feedback.sentiment_confidence = result.confidence
                    feedback.sentiment_analysis_data = result.raw_data

                    db.commit()

        finally:
            db.close()

    async def _process_content_moderation(self, data: Dict[str, Any]):
        """Process content moderation for reviews and feedback"""
        db = SessionLocal()
        try:
            moderation_service = ContentModerationService(db)

            if data.get("review_id"):
                # Moderate review content
                review = db.query(Review).filter(Review.id == data["review_id"]).first()
                if review:
                    result = await moderation_service.moderate_review_content(review)

                    # Update review status if needed
                    if result.get("action_required"):
                        # This would update the review status based on moderation results
                        pass

            elif data.get("feedback_id"):
                # Moderate feedback content
                feedback = (
                    db.query(Feedback)
                    .filter(Feedback.id == data["feedback_id"])
                    .first()
                )
                if feedback:
                    result = await moderation_service.moderate_feedback_content(
                        feedback
                    )

                    # Update feedback based on moderation results
                    if result.get("action_required"):
                        # This would update the feedback based on moderation results
                        pass

        finally:
            db.close()

    async def _process_review_aggregation(self, data: Dict[str, Any]):
        """Process review aggregation calculations"""
        db = SessionLocal()
        try:
            aggregation_service = ReviewAggregationService(db)

            entity_type = data.get("entity_type", "product")
            entity_id = data.get("entity_id")

            if entity_id:
                # Recalculate aggregates for the entity
                aggregates = aggregation_service.calculate_review_aggregates(
                    entity_type, entity_id, force_recalculate=True
                )

                # Update or create aggregate record
                existing = (
                    db.query(ReviewAggregate)
                    .filter(
                        ReviewAggregate.entity_type == entity_type,
                        ReviewAggregate.entity_id == entity_id,
                    )
                    .first()
                )

                if existing:
                    # Update existing record
                    for key, value in aggregates.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.last_calculated_at = datetime.utcnow()
                else:
                    # Create new record
                    aggregate = ReviewAggregate(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        last_calculated_at=datetime.utcnow(),
                        **aggregates,
                    )
                    db.add(aggregate)

                db.commit()

        finally:
            db.close()

    async def _process_analytics_calculation(self, data: Dict[str, Any]):
        """Process analytics calculations"""
        db = SessionLocal()
        try:
            analytics_service = FeedbackAnalyticsService(db)

            calculation_type = data.get("calculation_type")

            if calculation_type == "daily_summary":
                # Calculate daily analytics summary
                date = data.get("date", datetime.utcnow().date())
                await analytics_service.calculate_daily_summary(date)

            elif calculation_type == "trending_entities":
                # Calculate trending products/services
                entity_type = data.get("entity_type", "product")
                await analytics_service.update_trending_entities(entity_type)

            elif calculation_type == "sentiment_trends":
                # Calculate sentiment trend analysis
                entity_type = data.get("entity_type")
                entity_id = data.get("entity_id")
                await analytics_service.calculate_sentiment_trends(
                    entity_type, entity_id
                )

        finally:
            db.close()

    async def _process_notification(self, data: Dict[str, Any]):
        """Process notification sending"""
        db = SessionLocal()
        try:
            notification_service = NotificationService(db)

            notification_type = data.get("notification_type")

            if notification_type == "review_invitation":
                # Send review invitation
                customer_id = data.get("customer_id")
                entity_type = data.get("entity_type")
                entity_id = data.get("entity_id")

                await notification_service.send_review_invitation(
                    customer_id, entity_type, entity_id
                )

            elif notification_type == "feedback_response":
                # Send feedback response notification
                feedback_id = data.get("feedback_id")
                response_id = data.get("response_id")

                await notification_service.send_feedback_response_notification(
                    feedback_id, response_id
                )

            elif notification_type == "review_moderation":
                # Send review moderation notification
                review_id = data.get("review_id")
                action = data.get("action")

                await notification_service.send_review_moderation_notification(
                    review_id, action
                )

        finally:
            db.close()

    async def enqueue_task(self, task_type: str, data: Dict[str, Any]):
        """Add a task to the processing queue"""
        task = {
            "type": task_type,
            "data": data,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.task_queue.put(task)
        logger.debug(f"Enqueued {task_type} task")

    async def enqueue_sentiment_analysis(
        self, review_id: Optional[int] = None, feedback_id: Optional[int] = None
    ):
        """Enqueue sentiment analysis task"""
        data = {}
        if review_id:
            data["review_id"] = review_id
        if feedback_id:
            data["feedback_id"] = feedback_id

        await self.enqueue_task("sentiment_analysis", data)

    async def enqueue_content_moderation(
        self, review_id: Optional[int] = None, feedback_id: Optional[int] = None
    ):
        """Enqueue content moderation task"""
        data = {}
        if review_id:
            data["review_id"] = review_id
        if feedback_id:
            data["feedback_id"] = feedback_id

        await self.enqueue_task("content_moderation", data)

    async def enqueue_review_aggregation(self, entity_type: str, entity_id: int):
        """Enqueue review aggregation task"""
        data = {"entity_type": entity_type, "entity_id": entity_id}
        await self.enqueue_task("review_aggregation", data)

    async def enqueue_analytics_calculation(self, calculation_type: str, **kwargs):
        """Enqueue analytics calculation task"""
        data = {"calculation_type": calculation_type, **kwargs}
        await self.enqueue_task("analytics_calculation", data)

    async def enqueue_notification(self, notification_type: str, **kwargs):
        """Enqueue notification task"""
        data = {"notification_type": notification_type, **kwargs}
        await self.enqueue_task("notification", data)

    async def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.task_queue.qsize()

    async def get_status(self) -> Dict[str, Any]:
        """Get background task processor status"""
        return {
            "is_running": self.is_running,
            "worker_count": len(self.workers),
            "queue_size": await self.get_queue_size(),
            "workers_alive": sum(1 for w in self.workers if not w.done()),
        }


# Global background task processor instance
background_processor = BackgroundTaskProcessor()


# Scheduled task functions
async def schedule_daily_analytics():
    """Schedule daily analytics calculations"""
    if not background_processor.is_running:
        return

    # Calculate daily summary for yesterday
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    await background_processor.enqueue_analytics_calculation(
        "daily_summary", date=yesterday
    )

    # Update trending entities
    for entity_type in ["product", "service"]:
        await background_processor.enqueue_analytics_calculation(
            "trending_entities", entity_type=entity_type
        )


async def schedule_aggregation_refresh():
    """Schedule review aggregation refresh for active entities"""
    if not background_processor.is_running:
        return

    db = SessionLocal()
    try:
        # Get entities that have had recent reviews
        recent_cutoff = datetime.utcnow() - timedelta(hours=1)

        # This would query for entities with recent review activity
        # For now, we'll just refresh a few sample entities
        sample_entities = [("product", 101), ("product", 102), ("service", 201)]

        for entity_type, entity_id in sample_entities:
            await background_processor.enqueue_review_aggregation(
                entity_type, entity_id
            )

    finally:
        db.close()


# Utility functions for integration
async def process_new_review(review_id: int):
    """Process a newly created review"""
    # Schedule sentiment analysis
    await background_processor.enqueue_sentiment_analysis(review_id=review_id)

    # Schedule content moderation
    await background_processor.enqueue_content_moderation(review_id=review_id)

    # Schedule aggregation update (extract entity info from review)
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            if review.product_id:
                await background_processor.enqueue_review_aggregation(
                    "product", review.product_id
                )
            elif review.service_id:
                await background_processor.enqueue_review_aggregation(
                    "service", review.service_id
                )
    finally:
        db.close()


async def process_new_feedback(feedback_id: int):
    """Process newly created feedback"""
    # Schedule sentiment analysis
    await background_processor.enqueue_sentiment_analysis(feedback_id=feedback_id)

    # Schedule content moderation
    await background_processor.enqueue_content_moderation(feedback_id=feedback_id)


# Health check function
async def health_check() -> Dict[str, Any]:
    """Health check for background task system"""
    status = await background_processor.get_status()

    return {
        "status": "healthy" if status["is_running"] else "stopped",
        "background_tasks": status,
        "last_check": datetime.utcnow().isoformat(),
    }
