"""
Background tasks for priority system maintenance and optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from core.database import SessionLocal
from ..models.priority_models import (
    QueuePriorityConfig, OrderPriorityScore, PriorityMetrics
)
from ..models.queue_models import (
    OrderQueue, QueueItem, QueueStatus, QueueItemStatus
)
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
                # Check if it's time to rebalance
                should_rebalance = True
                
                if config.last_rebalance_time:
                    time_since_rebalance = (
                        datetime.utcnow() - config.last_rebalance_time
                    ).total_seconds() / 60
                    
                    if time_since_rebalance < config.rebalance_interval_minutes:
                        should_rebalance = False
                
                if should_rebalance:
                    # Check fairness threshold
                    fairness = service._calculate_fairness_index(config.queue_id)
                    
                    if fairness < config.rebalance_threshold:
                        logger.info(
                            f"Auto-rebalancing queue {config.queue_id} "
                            f"(fairness: {fairness:.2f})"
                        )
                        
                        result = service.rebalance_queue(config.queue_id, force=False)
                        
                        logger.info(
                            f"Rebalanced queue {config.queue_id}: "
                            f"{result.items_rebalanced} items, "
                            f"fairness {result.fairness_before:.2f} -> "
                            f"{result.fairness_after:.2f}"
                        )
                    else:
                        # Update last rebalance time even if not needed
                        # to prevent checking too frequently
                        config.last_rebalance_time = datetime.utcnow()
                        db.commit()
                        
            except Exception as e:
                logger.error(f"Error rebalancing queue {config.queue_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in auto_rebalance_queues task: {e}")
    finally:
        db.close()


def expire_priority_boosts():
    """
    Expire temporary priority boosts that have passed their expiration time.
    This task should be scheduled to run periodically (e.g., every 30 seconds).
    """
    db = SessionLocal()
    try:
        # Find expired boosts
        expired_scores = db.query(OrderPriorityScore).filter(
            OrderPriorityScore.is_boosted == True,
            OrderPriorityScore.boost_expires_at <= datetime.utcnow()
        ).all()
        
        if expired_scores:
            logger.info(f"Expiring {len(expired_scores)} priority boosts")
            
            for score in expired_scores:
                # Remove boost
                score.total_score = score.base_score
                score.boost_score = 0
                score.is_boosted = False
                score.boost_expires_at = None
                score.boost_reason = None
            
            db.commit()
            
            # Get affected queues for resequencing
            affected_queues = set()
            for score in expired_scores:
                queue_item = db.query(QueueItem).filter(
                    QueueItem.id == score.queue_item_id
                ).first()
                if queue_item:
                    affected_queues.add(queue_item.queue_id)
            
            # Resequence affected queues
            service = PriorityService(db)
            for queue_id in affected_queues:
                service._resequence_queue_after_adjustment(queue_id)
                
    except Exception as e:
        logger.error(f"Error in expire_priority_boosts task: {e}")
    finally:
        db.close()


def recalculate_stale_priorities():
    """
    Recalculate priority scores that haven't been updated recently.
    This task should be scheduled to run periodically (e.g., every 5 minutes).
    """
    db = SessionLocal()
    try:
        # Define stale threshold (e.g., 10 minutes)
        stale_threshold = datetime.utcnow() - timedelta(minutes=10)
        
        # Find stale scores for active queue items
        stale_items = db.query(
            QueueItem, OrderPriorityScore
        ).join(
            OrderPriorityScore,
            OrderPriorityScore.queue_item_id == QueueItem.id
        ).filter(
            QueueItem.status.in_([
                QueueItemStatus.QUEUED,
                QueueItemStatus.IN_PREPARATION
            ]),
            OrderPriorityScore.calculated_at < stale_threshold
        ).limit(100).all()  # Process in batches
        
        if stale_items:
            logger.info(f"Recalculating {len(stale_items)} stale priority scores")
            
            service = PriorityService(db)
            affected_queues = set()
            
            for queue_item, old_score in stale_items:
                try:
                    # Recalculate priority
                    new_score = service.calculate_order_priority(
                        queue_item.order_id,
                        queue_item.queue_id
                    )
                    
                    # Track affected queues if score changed significantly
                    if abs(new_score.total_score - old_score.total_score) > 5:
                        affected_queues.add(queue_item.queue_id)
                        
                except Exception as e:
                    logger.error(
                        f"Error recalculating priority for order {queue_item.order_id}: {e}"
                    )
                    continue
            
            # Resequence affected queues
            for queue_id in affected_queues:
                try:
                    service._resequence_queue_after_adjustment(queue_id)
                except Exception as e:
                    logger.error(f"Error resequencing queue {queue_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in recalculate_stale_priorities task: {e}")
    finally:
        db.close()


def collect_priority_metrics():
    """
    Collect and store priority system metrics for monitoring and analysis.
    This task should be scheduled to run hourly.
    """
    db = SessionLocal()
    try:
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Get all active queues
        active_queues = db.query(OrderQueue).filter(
            OrderQueue.status == QueueStatus.ACTIVE
        ).all()
        
        service = PriorityService(db)
        
        for queue in active_queues:
            try:
                metrics = _collect_metrics(db, service, queue.id, current_hour)
                
                # Store or update metrics
                existing = db.query(PriorityMetrics).filter(
                    PriorityMetrics.queue_id == queue.id,
                    PriorityMetrics.metric_date == current_hour,
                    PriorityMetrics.hour_of_day == current_hour.hour
                ).first()
                
                if existing:
                    # Update existing metrics
                    for key, value in metrics.items():
                        setattr(existing, key, value)
                else:
                    # Create new metrics record
                    new_metrics = PriorityMetrics(
                        queue_id=queue.id,
                        metric_date=current_hour,
                        hour_of_day=current_hour.hour,
                        **metrics
                    )
                    db.add(new_metrics)
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Error collecting metrics for queue {queue.id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in collect_priority_metrics task: {e}")
    finally:
        db.close()


def _collect_metrics(
    db: Session,
    service: PriorityService,
    queue_id: int,
    metric_hour: datetime
) -> Dict[str, Any]:
    """Collect metrics for a specific queue and hour"""
    # Calculate fairness
    fairness_index = service._calculate_fairness_index(queue_id)
    gini_coefficient = 1 - fairness_index
    
    # Get wait time variance
    wait_times = []
    queue_items = db.query(QueueItem).filter(
        QueueItem.queue_id == queue_id,
        QueueItem.status == QueueItemStatus.QUEUED
    ).all()
    
    for item in queue_items:
        wait_time = (datetime.utcnow() - item.queued_at).total_seconds() / 60
        wait_times.append(wait_time)
    
    if wait_times:
        mean_wait = sum(wait_times) / len(wait_times)
        variance = sum((t - mean_wait) ** 2 for t in wait_times) / len(wait_times)
        max_wait_variance = variance
    else:
        max_wait_variance = 0
    
    # Get position changes from adjustment logs
    hour_start = metric_hour
    hour_end = hour_start + timedelta(hours=1)
    
    adjustments = db.query(PriorityAdjustmentLog).join(
        QueueItem
    ).filter(
        QueueItem.queue_id == queue_id,
        PriorityAdjustmentLog.adjusted_at >= hour_start,
        PriorityAdjustmentLog.adjusted_at < hour_end
    ).all()
    
    if adjustments:
        position_changes = [
            abs(adj.new_position - adj.old_position) 
            for adj in adjustments 
            if adj.old_position and adj.new_position
        ]
        position_change_avg = sum(position_changes) / len(position_changes) if position_changes else 0
    else:
        position_change_avg = 0
    
    # Get calculation performance metrics
    calculations = db.query(OrderPriorityScore).join(
        QueueItem
    ).filter(
        QueueItem.queue_id == queue_id,
        OrderPriorityScore.calculated_at >= hour_start,
        OrderPriorityScore.calculated_at < hour_end
    ).all()
    
    if calculations:
        calc_times = [c.calculation_time_ms for c in calculations if c.calculation_time_ms]
        avg_calculation_time_ms = sum(calc_times) / len(calc_times) if calc_times else 0
        total_calculations = len(calculations)
    else:
        avg_calculation_time_ms = 0
        total_calculations = 0
    
    # For now, cache hit rate is not implemented
    cache_hit_rate = 0.0
    
    # Count manual adjustments
    manual_adjustments = len([a for a in adjustments if a.adjustment_type == 'manual'])
    
    return {
        'gini_coefficient': gini_coefficient,
        'max_wait_variance': max_wait_variance,
        'position_change_avg': position_change_avg,
        'avg_calculation_time_ms': avg_calculation_time_ms,
        'total_calculations': total_calculations,
        'cache_hit_rate': cache_hit_rate,
        'manual_adjustments': manual_adjustments
    }


def cleanup_old_priority_data():
    """
    Clean up old priority scores and logs.
    This task should be scheduled to run daily.
    """
    db = SessionLocal()
    try:
        # Define retention periods
        score_retention_days = 7
        log_retention_days = 30
        metrics_retention_days = 90
        
        # Clean up old priority scores for completed items
        cutoff_date = datetime.utcnow() - timedelta(days=score_retention_days)
        
        old_scores = db.query(OrderPriorityScore).join(
            QueueItem
        ).filter(
            QueueItem.status.in_([
                QueueItemStatus.COMPLETED,
                QueueItemStatus.CANCELLED
            ]),
            QueueItem.completed_at < cutoff_date
        ).all()
        
        if old_scores:
            logger.info(f"Cleaning up {len(old_scores)} old priority scores")
            for score in old_scores:
                db.delete(score)
            db.commit()
        
        # Clean up old adjustment logs
        log_cutoff = datetime.utcnow() - timedelta(days=log_retention_days)
        
        old_logs = db.query(PriorityAdjustmentLog).filter(
            PriorityAdjustmentLog.adjusted_at < log_cutoff
        ).all()
        
        if old_logs:
            logger.info(f"Cleaning up {len(old_logs)} old adjustment logs")
            for log in old_logs:
                db.delete(log)
            db.commit()
        
        # Clean up old metrics
        metrics_cutoff = datetime.utcnow() - timedelta(days=metrics_retention_days)
        
        old_metrics = db.query(PriorityMetrics).filter(
            PriorityMetrics.metric_date < metrics_cutoff
        ).all()
        
        if old_metrics:
            logger.info(f"Cleaning up {len(old_metrics)} old metric records")
            for metric in old_metrics:
                db.delete(metric)
            db.commit()
            
    except Exception as e:
        logger.error(f"Error in cleanup_old_priority_data task: {e}")
    finally:
        db.close()


# Celery task registration (if using Celery)
# from celery import shared_task
# 
# @shared_task
# def auto_rebalance_queues_task():
#     return auto_rebalance_queues()
# 
# @shared_task
# def expire_priority_boosts_task():
#     return expire_priority_boosts()
# 
# etc...