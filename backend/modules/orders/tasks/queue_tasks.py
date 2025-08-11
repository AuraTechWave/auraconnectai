"""
Background tasks for queue management.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import SessionLocal
from ..models.queue_models import (
    OrderQueue, QueueItem, QueueMetrics,
    QueueStatus, QueueItemStatus
)
from ..services.queue_service import QueueService

logger = logging.getLogger(__name__)


class QueueMonitor:
    """Monitor queues and update metrics"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
    
    async def start(self):
        """Start queue monitoring tasks"""
        self.running = True
        
        # Start monitoring tasks
        self.tasks.append(asyncio.create_task(self._monitor_hold_releases()))
        self.tasks.append(asyncio.create_task(self._update_queue_metrics()))
        self.tasks.append(asyncio.create_task(self._check_delayed_items()))
        
        logger.info("Queue monitor started")
    
    async def stop(self):
        """Stop monitoring tasks"""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Queue monitor stopped")
    
    async def _monitor_hold_releases(self):
        """Check for items that should be released from hold"""
        while self.running:
            try:
                db = SessionLocal()
                try:
                    # Find items past their hold time
                    expired_holds = db.query(QueueItem).filter(
                        QueueItem.status == QueueItemStatus.ON_HOLD,
                        QueueItem.hold_until.isnot(None),
                        QueueItem.hold_until <= datetime.utcnow()
                    ).all()
                    
                    service = QueueService(db)
                    
                    for item in expired_holds:
                        try:
                            service.release_hold(item.id)
                            logger.info(f"Auto-released item {item.id} from hold")
                        except Exception as e:
                            logger.error(f"Failed to release item {item.id}: {str(e)}")
                    
                    db.commit()
                
                finally:
                    db.close()
                
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in hold release monitor: {str(e)}")
                await asyncio.sleep(60)
    
    async def _update_queue_metrics(self):
        """Update queue performance metrics"""
        while self.running:
            try:
                db = SessionLocal()
                try:
                    # Get all active queues
                    queues = db.query(OrderQueue).filter(
                        OrderQueue.status == QueueStatus.ACTIVE
                    ).all()
                    
                    current_hour = datetime.utcnow().replace(
                        minute=0, second=0, microsecond=0
                    )
                    
                    for queue in queues:
                        # Check if metrics exist for current hour
                        existing = db.query(QueueMetrics).filter(
                            QueueMetrics.queue_id == queue.id,
                            QueueMetrics.metric_date == current_hour,
                            QueueMetrics.hour_of_day == current_hour.hour
                        ).first()
                        
                        if not existing:
                            # Create new metrics entry
                            metrics = self._calculate_queue_metrics(db, queue, current_hour)
                            db.add(metrics)
                    
                    db.commit()
                
                finally:
                    db.close()
                
                # Update every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error updating queue metrics: {str(e)}")
                await asyncio.sleep(300)
    
    async def _check_delayed_items(self):
        """Check for items that are delayed"""
        while self.running:
            try:
                db = SessionLocal()
                try:
                    # Find items past their estimated time
                    delayed_items = db.query(QueueItem).filter(
                        QueueItem.status.in_([
                            QueueItemStatus.QUEUED,
                            QueueItemStatus.IN_PREPARATION
                        ]),
                        QueueItem.estimated_ready_time.isnot(None),
                        QueueItem.estimated_ready_time < datetime.utcnow()
                    ).all()
                    
                    for item in delayed_items:
                        # Calculate delay
                        delay_minutes = int(
                            (datetime.utcnow() - item.estimated_ready_time).total_seconds() / 60
                        )
                        
                        if delay_minutes > 0:
                            item.delay_minutes = delay_minutes
                            
                            # Update substatus if significant delay
                            if delay_minutes >= 10:
                                item.substatus = "significantly_delayed"
                            elif delay_minutes >= 5:
                                item.substatus = "delayed"
                    
                    db.commit()
                
                finally:
                    db.close()
                
                # Check every 2 minutes
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"Error checking delayed items: {str(e)}")
                await asyncio.sleep(120)
    
    def _calculate_queue_metrics(self, db: Session, queue: OrderQueue, metric_date: datetime) -> QueueMetrics:
        """Calculate metrics for a queue"""
        # Time window for metrics
        start_time = metric_date
        end_time = start_time + timedelta(hours=1)
        
        # Get items for this period
        items = db.query(QueueItem).filter(
            QueueItem.queue_id == queue.id,
            QueueItem.queued_at >= start_time,
            QueueItem.queued_at < end_time
        ).all()
        
        # Calculate metrics
        items_queued = len(items)
        items_completed = len([i for i in items if i.status == QueueItemStatus.COMPLETED])
        items_cancelled = len([i for i in items if i.status == QueueItemStatus.CANCELLED])
        items_delayed = len([i for i in items if i.delay_minutes and i.delay_minutes > 0])
        
        # Calculate wait times
        wait_times = []
        prep_times = []
        on_time_count = 0
        
        for item in items:
            if item.wait_time_actual:
                wait_times.append(item.wait_time_actual)
            
            if item.prep_time_actual:
                prep_times.append(item.prep_time_actual)
            
            # Check if completed on time
            if item.status == QueueItemStatus.COMPLETED:
                if item.completed_at and item.estimated_ready_time:
                    if item.completed_at <= item.estimated_ready_time:
                        on_time_count += 1
        
        # Queue size metrics
        queue_sizes = db.query(
            func.count(QueueItem.id)
        ).filter(
            QueueItem.queue_id == queue.id,
            QueueItem.queued_at >= start_time,
            QueueItem.queued_at < end_time,
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ])
        ).group_by(
            func.date_trunc('minute', QueueItem.queued_at)
        ).all()
        
        avg_queue_size = sum(size[0] for size in queue_sizes) / len(queue_sizes) if queue_sizes else 0
        max_queue_size = max((size[0] for size in queue_sizes), default=0)
        
        # Create metrics
        return QueueMetrics(
            queue_id=queue.id,
            metric_date=metric_date,
            hour_of_day=metric_date.hour,
            items_queued=items_queued,
            items_completed=items_completed,
            items_cancelled=items_cancelled,
            items_delayed=items_delayed,
            avg_wait_time=sum(wait_times) / len(wait_times) if wait_times else 0,
            max_wait_time=max(wait_times, default=0),
            min_wait_time=min(wait_times, default=0),
            avg_prep_time=sum(prep_times) / len(prep_times) if prep_times else 0,
            on_time_percentage=(on_time_count / items_completed * 100) if items_completed > 0 else 0,
            expedited_count=len([i for i in items if i.is_expedited]),
            requeue_count=0,  # Would need to track this separately
            max_queue_size=max_queue_size,
            avg_queue_size=avg_queue_size,
            capacity_exceeded_minutes=0  # Would need to track this separately
        )


# Global monitor instance
queue_monitor = QueueMonitor()


async def start_queue_monitor():
    """Start the queue monitoring tasks"""
    await queue_monitor.start()


async def stop_queue_monitor():
    """Stop the queue monitoring tasks"""
    await queue_monitor.stop()