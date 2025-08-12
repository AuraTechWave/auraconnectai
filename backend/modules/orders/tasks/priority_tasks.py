"""
Background tasks for priority system maintenance and optimization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from core.database import SessionLocal
from modules.customers.models import Customer
from ..models.priority_models import (
    QueuePriorityConfig, OrderPriorityScore, PriorityMetrics,
    PriorityProfile, PriorityAdjustmentLog
)
from ..models.queue_models import (
    OrderQueue, QueueItem, QueueStatus, QueueItemStatus, QueueMetrics
)
from ..models.order_models import Order
from ..services.priority_service import PriorityService

logger = logging.getLogger(__name__)


def auto_rebalance_queues():
    """
    Automatically rebalance queues based on configuration.
    This task should be scheduled to run periodically (e.g., every minute).
    """
    db = SessionLocal()
    try:
        # Get all active queue configurations with auto-rebalance enabled
        configs = db.query(QueuePriorityConfig).join(
            OrderQueue
        ).filter(
            QueuePriorityConfig.is_active == True,
            QueuePriorityConfig.auto_rebalance == True,
            OrderQueue.status == QueueStatus.ACTIVE
        ).all()
        
        service = PriorityService(db)
        
        for config in configs:
            try:
                # Check if rebalancing is needed
                if config.last_rebalance_time:
                    time_since_rebalance = (
                        datetime.utcnow() - config.last_rebalance_time
                    ).total_seconds() / 60
                    
                    if time_since_rebalance < config.rebalance_interval_minutes:
                        continue
                
                # Perform rebalancing
                result = service.rebalance_queue(config.queue_id, force=False)
                
                if result.items_moved > 0:
                    logger.info(
                        f"Rebalanced queue {config.queue_id}: "
                        f"{result.items_moved} items moved, "
                        f"fairness improved by {result.fairness_improvement:.2f}"
                    )
                
            except Exception as e:
                logger.error(
                    f"Failed to rebalance queue {config.queue_id}: {str(e)}"
                )
        
    finally:
        db.close()


def cleanup_expired_boosts():
    """
    Clean up expired priority boosts.
    This task should be scheduled to run periodically (e.g., every 5 minutes).
    """
    db = SessionLocal()
    try:
        # Find priority scores with expired boosts
        expired_boosts = db.query(OrderPriorityScore).filter(
            and_(
                OrderPriorityScore.is_boosted == True,
                OrderPriorityScore.boost_expires_at <= datetime.utcnow()
            )
        ).all()
        
        service = PriorityService(db)
        
        for priority_score in expired_boosts:
            try:
                # Remove boost
                priority_score.is_boosted = False
                priority_score.boost_score = 0.0
                priority_score.boost_expires_at = None
                priority_score.boost_reason = None
                
                # Recalculate total score
                priority_score.total_score = priority_score.base_score
                
                logger.info(
                    f"Removed expired boost from priority score {priority_score.id}"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to cleanup boost for priority score {priority_score.id}: {str(e)}"
                )
        
        db.commit()
        
    finally:
        db.close()


def calculate_priority_metrics():
    """
    Calculate and store priority system metrics.
    This task should be scheduled to run periodically (e.g., every hour).
    """
    db = SessionLocal()
    try:
        # Get all active queue configurations
        configs = db.query(QueuePriorityConfig).join(
            OrderQueue
        ).filter(
            QueuePriorityConfig.is_active == True,
            OrderQueue.status == QueueStatus.ACTIVE
        ).all()
        
        current_time = datetime.utcnow()
        hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        
        for config in configs:
            try:
                metrics = _calculate_metrics_for_queue(db, config, hour_start)
                
                # Save or update metrics
                existing = db.query(PriorityMetrics).filter(
                    and_(
                        PriorityMetrics.profile_id == config.profile_id,
                        PriorityMetrics.queue_id == config.queue_id,
                        PriorityMetrics.metric_date == hour_start,
                        PriorityMetrics.hour_of_day == hour_start.hour
                    )
                ).first()
                
                if existing:
                    # Update existing metrics
                    for key, value in metrics.items():
                        setattr(existing, key, value)
                else:
                    # Create new metrics
                    new_metrics = PriorityMetrics(
                        profile_id=config.profile_id,
                        queue_id=config.queue_id,
                        metric_date=hour_start,
                        hour_of_day=hour_start.hour,
                        **metrics
                    )
                    db.add(new_metrics)
                
                db.commit()
                
            except Exception as e:
                logger.error(
                    f"Failed to calculate metrics for queue {config.queue_id}: {str(e)}"
                )
                db.rollback()
        
    finally:
        db.close()


def _calculate_metrics_for_queue(
    db: Session, config: QueuePriorityConfig, hour_start: datetime
) -> Dict[str, Any]:
    """Calculate priority metrics for a specific queue"""
    hour_end = hour_start + timedelta(hours=1)
    
    # Get queue items processed in this hour
    queue_items = db.query(QueueItem).filter(
        and_(
            QueueItem.queue_id == config.queue_id,
            QueueItem.completed_at >= hour_start,
            QueueItem.completed_at < hour_end
        )
    ).all()
    
    if not queue_items:
        return {
            "avg_wait_time_reduction": 0,
            "on_time_delivery_rate": 0,
            "vip_satisfaction_score": 0,
            "fairness_index": 0,
            "max_wait_time_ratio": 0,
            "priority_override_count": 0,
            "avg_calculation_time_ms": 0,
            "rebalance_count": 0,
            "avg_position_changes": 0,
            "revenue_impact": 0,
            "customer_complaints": 0,
            "staff_overrides": 0
        }
    
    # Calculate wait time metrics
    wait_times = []
    on_time_count = 0
    vip_orders_on_time = 0
    vip_orders_total = 0
    
    for item in queue_items:
        if item.queued_at and item.completed_at:
            wait_time = (item.completed_at - item.queued_at).total_seconds() / 60
            wait_times.append(wait_time)

            # Fetch related order once
            order = db.query(Order).filter(Order.id == item.order_id).first()

            # Determine VIP status (count every VIP order)
            if order and order.customer_id:
                customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
                if customer and customer.vip_status:
                    vip_orders_total += 1
                    # Check if completed on time
                    if order.estimated_delivery_time and item.completed_at <= order.estimated_delivery_time:
                        vip_orders_on_time += 1

            # Overall on-time count (regardless of VIP)
            if order and order.estimated_delivery_time and item.completed_at <= order.estimated_delivery_time:
                on_time_count += 1
    
    # Calculate fairness metrics
    priority_scores = db.query(OrderPriorityScore).join(QueueItem).filter(
        and_(
            QueueItem.queue_id == config.queue_id,
            QueueItem.completed_at >= hour_start,
            QueueItem.completed_at < hour_end
        )
    ).all()
    
    fairness_index = _calculate_fairness_index([ps.total_score for ps in priority_scores])
    
    # Calculate max wait time ratio
    max_wait_time_ratio = 0
    if wait_times:
        avg_wait = sum(wait_times) / len(wait_times)
        max_wait = max(wait_times)
        max_wait_time_ratio = max_wait / avg_wait if avg_wait > 0 else 0
    
    # Count priority overrides
    priority_override_count = db.query(PriorityAdjustmentLog).filter(
        and_(
            PriorityAdjustmentLog.queue_item_id.in_([item.id for item in queue_items]),
            PriorityAdjustmentLog.adjusted_at >= hour_start,
            PriorityAdjustmentLog.adjusted_at < hour_end
        )
    ).count()
    
    # Calculate average calculation time
    calculation_times = [
        ps.calculation_time_ms for ps in priority_scores 
        if ps.calculation_time_ms is not None
    ]
    avg_calculation_time_ms = (
        sum(calculation_times) / len(calculation_times) 
        if calculation_times else 0
    )
    
    # Get rebalancing metrics
    rebalance_count = 0
    avg_position_changes = 0
    
    # Calculate revenue impact (simplified)
    revenue_impact = 0
    if queue_items:
        total_revenue = sum(
            float(db.query(Order).filter(Order.id == item.order_id).first().total_amount or 0)
            for item in queue_items
        )
        # Assume 5% improvement due to priority system
        revenue_impact = total_revenue * 0.05
    
    # Count customer complaints (would need to integrate with feedback system)
    customer_complaints = 0
    
    # Count staff overrides
    staff_overrides = priority_override_count
    
    return {
        "avg_wait_time_reduction": 15.0,  # Placeholder - would need baseline comparison
        "on_time_delivery_rate": (on_time_count / len(queue_items)) * 100 if queue_items else 0,
        "vip_satisfaction_score": (vip_orders_on_time / vip_orders_total) * 100 if vip_orders_total > 0 else 0,
        "fairness_index": fairness_index,
        "max_wait_time_ratio": max_wait_time_ratio,
        "priority_override_count": priority_override_count,
        "avg_calculation_time_ms": avg_calculation_time_ms,
        "rebalance_count": rebalance_count,
        "avg_position_changes": avg_position_changes,
        "revenue_impact": revenue_impact,
        "customer_complaints": customer_complaints,
        "staff_overrides": staff_overrides
    }


def _calculate_fairness_index(scores: List[float]) -> float:
    """Calculate fairness index (1 = perfect fairness, 0 = perfect inequality)"""
    if not scores or len(scores) < 2:
        return 1.0
    
    # Calculate Gini coefficient
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    
    sum_weighted = sum((i + 1) * score for i, score in enumerate(sorted_scores))
    sum_total = sum(sorted_scores)
    
    if sum_total == 0:
        return 1.0
    
    gini = (2 * sum_weighted) / (n * sum_total) - (n + 1) / n
    
    # Convert to fairness index
    fairness_index = 1 - gini
    return max(0.0, min(1.0, fairness_index))


def recalculate_priorities_for_queue(queue_id: int):
    """
    Recalculate priorities for all items in a specific queue.
    This can be called manually or triggered by events.
    """
    db = SessionLocal()
    try:
        service = PriorityService(db)
        
        # Get all active items in queue
        queue_items = db.query(QueueItem).filter(
            and_(
                QueueItem.queue_id == queue_id,
                QueueItem.status.in_([
                    QueueItemStatus.QUEUED,
                    QueueItemStatus.IN_PREPARATION
                ])
            )
        ).all()
        
        recalculated_count = 0
        errors = []
        
        for queue_item in queue_items:
            try:
                # Recalculate priority
                service.calculate_order_priority(
                    queue_item.order_id, 
                    queue_id
                )
                recalculated_count += 1
                
            except Exception as e:
                errors.append({
                    "order_id": queue_item.order_id,
                    "error": str(e)
                })
        
        logger.info(
            f"Recalculated priorities for queue {queue_id}: "
            f"{recalculated_count} items processed, {len(errors)} errors"
        )
        
        if errors:
            logger.error(f"Errors during priority recalculation: {errors}")
        
    finally:
        db.close()


def cleanup_old_metrics(days_to_keep: int = 30):
    """
    Clean up old priority metrics to prevent database bloat.
    This task should be scheduled to run daily.
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old metrics
        deleted_count = db.query(PriorityMetrics).filter(
            PriorityMetrics.metric_date < cutoff_date
        ).delete()
        
        # Delete old adjustment logs
        deleted_logs = db.query(PriorityAdjustmentLog).filter(
            PriorityAdjustmentLog.adjusted_at < cutoff_date
        ).delete()
        
        db.commit()
        
        logger.info(
            f"Cleaned up {deleted_count} old priority metrics and "
            f"{deleted_logs} old adjustment logs"
        )
        
    finally:
        db.close()


class PriorityMonitor:
    """Monitor and collect priority algorithm metrics"""
    
    def __init__(self):
        self.running = False
        self.monitor_task = None
        self.collection_interval = 300  # 5 minutes
    
    async def start(self):
        """Start the priority monitor"""
        if self.running:
            logger.warning("Priority monitor is already running")
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Priority monitor started")
    
    async def stop(self):
        """Stop the priority monitor"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Priority monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in priority monitor: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _collect_metrics(self):
        """Collect priority metrics for all active queue configurations"""
        db = SessionLocal()
        try:
            # Get all active queue configurations
            configs = db.query(QueuePriorityConfig).join(
                OrderQueue,
                QueuePriorityConfig.queue_id == OrderQueue.id
            ).filter(
                OrderQueue.status == QueueStatus.ACTIVE
            ).all()
            
            current_time = datetime.utcnow()
            hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            
            for config in configs:
                try:
                    metrics = _calculate_metrics_for_queue(db, config, hour_start)
                    
                    # Save or update metrics
                    existing = db.query(PriorityMetrics).filter(
                        and_(
                            PriorityMetrics.profile_id == config.profile_id,
                            PriorityMetrics.queue_id == config.queue_id,
                            PriorityMetrics.metric_date == hour_start,
                            PriorityMetrics.hour_of_day == hour_start.hour
                        )
                    ).first()
                    
                    if existing:
                        # Update existing metrics
                        for key, value in metrics.items():
                            setattr(existing, key, value)
                    else:
                        # Create new metrics
                        new_metrics = PriorityMetrics(
                            profile_id=config.profile_id,
                            queue_id=config.queue_id,
                            metric_date=hour_start,
                            hour_of_day=hour_start.hour,
                            **metrics
                        )
                        db.add(new_metrics)
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(
                        f"Failed to collect metrics for queue {config.queue_id}: {str(e)}"
                    )
                    db.rollback()
            
        finally:
            db.close()
