"""
Background tasks for priority analytics and monitoring.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from core.database import SessionLocal
from ..models.priority_models import (
    PriorityProfile, QueuePriorityConfig, PriorityMetrics,
    OrderPriorityScore
)
from ..models.queue_models import QueueItem, OrderQueue, QueueItemStatus, QueueMetrics, QueueStatus
from ..models.order_models import Order
from ..services.priority_service import PriorityService

logger = logging.getLogger(__name__)


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
                    metrics = self._calculate_metrics_for_queue(
                        db, config, hour_start
                    )
                    
                    # Save or update metrics
                    existing = db.query(PriorityMetrics).filter(
                        and_(
                            PriorityMetrics.profile_id == config.priority_profile_id,
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
                            profile_id=config.priority_profile_id,
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
    
    def _calculate_metrics_for_queue(
        self, db: Session, config: QueuePriorityConfig, hour_start: datetime
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
                
                # Check if delivered on time
                order = db.query(Order).filter(Order.id == item.order_id).first()
                if order and order.scheduled_fulfillment_time:
                    if item.completed_at <= order.scheduled_fulfillment_time:
                        on_time_count += 1
                    
                    # Check VIP orders
                    if order.customer_id:
                        # Simplified VIP check - would need to join with Customer table
                        vip_orders_total += 1
                        if item.completed_at <= order.scheduled_fulfillment_time:
                            vip_orders_on_time += 1
        
        # Calculate metrics
        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
        max_wait_time = max(wait_times) if wait_times else 0
        min_wait_time = min(wait_times) if wait_times else 0
        
        # Calculate fairness index (simplified Gini coefficient)
        fairness_index = self._calculate_fairness_index(wait_times)
        
        # Get comparison with FIFO baseline
        baseline_wait_time = self._get_baseline_wait_time(db, config.queue_id, hour_start)
        wait_time_reduction = 0
        if baseline_wait_time > 0:
            wait_time_reduction = ((baseline_wait_time - avg_wait_time) / baseline_wait_time) * 100
        
        # Count priority overrides
        override_count = db.query(func.count()).filter(
            and_(
                QueueItem.queue_id == config.queue_id,
                QueueItem.created_at >= hour_start,
                QueueItem.created_at < hour_end,
                QueueItem.priority != QueueItem.sequence_number  # Simplified check
            )
        ).scalar() or 0
        
        # Count rebalances (would need a separate rebalance log table)
        rebalance_count = 0  # Placeholder
        
        return {
            "avg_wait_time_reduction": wait_time_reduction,
            "on_time_delivery_rate": (on_time_count / len(queue_items) * 100) if queue_items else 0,
            "vip_satisfaction_score": (vip_orders_on_time / vip_orders_total * 100) if vip_orders_total else 100,
            "fairness_index": fairness_index,
            "max_wait_time_ratio": max_wait_time / avg_wait_time if avg_wait_time > 0 else 1,
            "priority_override_count": override_count,
            "avg_calculation_time_ms": 50,  # Placeholder - would need actual timing
            "rebalance_count": rebalance_count,
            "avg_position_changes": 2.5,  # Placeholder
            "revenue_impact": 0,  # Would need business logic
            "customer_complaints": 0,  # Would need complaint tracking
            "staff_overrides": override_count
        }
    
    def _calculate_fairness_index(self, wait_times: list) -> float:
        """Calculate fairness index (0-1, where 1 is perfectly fair)"""
        if not wait_times or len(wait_times) < 2:
            return 1.0
        
        # Sort wait times
        sorted_times = sorted(wait_times)
        n = len(sorted_times)
        
        # Calculate Gini coefficient
        index = 0
        for i in range(n):
            index += (2 * (i + 1) - n - 1) * sorted_times[i]
        
        gini = index / (n * sum(sorted_times))
        
        # Convert to fairness index (1 - Gini)
        return 1 - abs(gini)
    
    def _get_baseline_wait_time(self, db: Session, queue_id: int, hour_start: datetime) -> float:
        """Get baseline wait time for FIFO comparison"""
        # Look for historical metrics when priority was not used
        # This is a simplified approach - would need proper baseline tracking
        baseline_metrics = db.query(QueueMetrics).filter(
            and_(
                QueueMetrics.queue_id == queue_id,
                QueueMetrics.metric_date >= hour_start - timedelta(days=7),
                QueueMetrics.metric_date < hour_start
            )
        ).all()
        
        if baseline_metrics:
            avg_waits = [m.avg_wait_time for m in baseline_metrics if m.avg_wait_time]
            return sum(avg_waits) / len(avg_waits) if avg_waits else 20  # Default 20 minutes
        
        return 20  # Default baseline


# Global monitor instance
priority_monitor = PriorityMonitor()


async def start_priority_monitor():
    """Start the priority monitoring task"""
    await priority_monitor.start()


async def stop_priority_monitor():
    """Stop the priority monitoring task"""
    await priority_monitor.stop()


def calculate_priority_batch(order_ids: list, queue_id: int) -> Dict[int, float]:
    """Calculate priorities for a batch of orders"""
    db = SessionLocal()
    priority_service = PriorityService(db)
    results = {}
    
    try:
        for order_id in order_ids:
            try:
                score = priority_service.calculate_order_priority(order_id, queue_id)
                results[order_id] = score.normalized_score
            except Exception as e:
                logger.error(f"Failed to calculate priority for order {order_id}: {str(e)}")
                results[order_id] = 0
        
        db.commit()
    finally:
        db.close()
    
    return results


async def auto_rebalance_queues():
    """Automatically rebalance queues based on configuration"""
    db = SessionLocal()
    try:
        # Get all queues with auto-rebalance enabled
        configs = db.query(QueuePriorityConfig).filter(
            QueuePriorityConfig.rebalance_enabled == True
        ).all()
        
        priority_service = PriorityService(db)
        current_time = datetime.utcnow()
        
        for config in configs:
            try:
                # Check if it's time to rebalance
                last_rebalance = getattr(config, 'last_rebalance_time', None)
                if last_rebalance:
                    time_since_last = (current_time - last_rebalance).total_seconds()
                    if time_since_last < config.rebalance_interval:
                        continue
                
                # Perform rebalance
                result = priority_service.rebalance_queue(config.queue_id)
                
                if result.get("rebalanced"):
                    logger.info(
                        f"Auto-rebalanced queue {config.queue_id}: "
                        f"{result.get('items_reordered', 0)} items reordered"
                    )
                
                # Update last rebalance time (would need to add this field)
                # config.last_rebalance_time = current_time
                
            except Exception as e:
                logger.error(f"Failed to auto-rebalance queue {config.queue_id}: {str(e)}")
        
        db.commit()
    finally:
        db.close()