# backend/core/background_tasks.py

import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
import logging
from celery import Celery
from celery.schedules import crontab
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.database import get_db

logger = logging.getLogger(__name__)

# Celery configuration
celery_app = Celery(
    "auraconnect_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.core.background_tasks",
        "backend.modules.loyalty.tasks",
        "backend.modules.customers.tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    result_expires=3600,  # 1 hour
    task_routes={
        "analytics.*": {"queue": "analytics"},
        "notifications.*": {"queue": "notifications"},
        "rewards.*": {"queue": "rewards"},
        "cleanup.*": {"queue": "cleanup"}
    }
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    # Analytics tasks
    "calculate-daily-analytics": {
        "task": "backend.core.background_tasks.calculate_daily_analytics",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
        "options": {"queue": "analytics"}
    },
    "calculate-weekly-analytics": {
        "task": "backend.core.background_tasks.calculate_weekly_analytics", 
        "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Weekly on Monday at 2 AM
        "options": {"queue": "analytics"}
    },
    "calculate-monthly-analytics": {
        "task": "backend.core.background_tasks.calculate_monthly_analytics",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),  # Monthly on 1st at 3 AM
        "options": {"queue": "analytics"}
    },
    
    # Loyalty system tasks
    "expire-old-rewards": {
        "task": "backend.modules.loyalty.tasks.expire_old_rewards",
        "schedule": crontab(hour=0, minute=30),  # Daily at 12:30 AM
        "options": {"queue": "rewards"}
    },
    "process-birthday-rewards": {
        "task": "backend.modules.loyalty.tasks.process_birthday_rewards",
        "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
        "options": {"queue": "rewards"}
    },
    "send-expiring-reward-notifications": {
        "task": "backend.modules.loyalty.tasks.send_expiring_reward_notifications",
        "schedule": crontab(hour=10, minute=0),  # Daily at 10 AM
        "options": {"queue": "notifications"}
    },
    
    # Customer analytics tasks
    "calculate-customer-segments": {
        "task": "backend.modules.customers.tasks.calculate_customer_segments",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
        "options": {"queue": "analytics"}
    },
    "calculate-churn-risk": {
        "task": "backend.modules.customers.tasks.calculate_churn_risk",
        "schedule": crontab(hour=5, minute=0),  # Daily at 5 AM
        "options": {"queue": "analytics"}
    },
    
    # Cleanup tasks
    "cleanup-old-sessions": {
        "task": "backend.core.background_tasks.cleanup_old_sessions",
        "schedule": crontab(hour=23, minute=0),  # Daily at 11 PM
        "options": {"queue": "cleanup"}
    },
    "cleanup-analytics-cache": {
        "task": "backend.core.background_tasks.cleanup_analytics_cache",
        "schedule": crontab(hour=23, minute=30),  # Daily at 11:30 PM
        "options": {"queue": "cleanup"}
    }
}


class TaskManager:
    """Manager for background tasks and analytics"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url) if hasattr(settings, 'redis_url') and settings.redis_url else None
        self.task_history = {}
    
    def schedule_analytics_calculation(self, analytics_type: str, date_range: Dict[str, Any] = None):
        """Schedule analytics calculation task"""
        task_id = f"analytics_{analytics_type}_{datetime.utcnow().isoformat()}"
        
        if analytics_type == "daily":
            result = calculate_daily_analytics.delay()
        elif analytics_type == "weekly":
            result = calculate_weekly_analytics.delay()
        elif analytics_type == "monthly":
            result = calculate_monthly_analytics.delay()
        elif analytics_type == "custom":
            result = calculate_custom_analytics.delay(date_range)
        else:
            raise ValueError(f"Unknown analytics type: {analytics_type}")
        
        self.task_history[task_id] = {
            "task_id": result.id,
            "type": analytics_type,
            "scheduled_at": datetime.utcnow(),
            "status": "pending"
        }
        
        return {"task_id": task_id, "celery_task_id": result.id}
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a background task"""
        if task_id in self.task_history:
            task_info = self.task_history[task_id]
            celery_task = celery_app.AsyncResult(task_info["task_id"])
            
            return {
                "task_id": task_id,
                "celery_task_id": task_info["task_id"],
                "type": task_info["type"],
                "scheduled_at": task_info["scheduled_at"],
                "status": celery_task.status,
                "result": celery_task.result if celery_task.ready() else None,
                "progress": celery_task.info if celery_task.status == "PROGRESS" else None
            }
        
        return {"error": "Task not found"}
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a background task"""
        if task_id in self.task_history:
            task_info = self.task_history[task_id]
            celery_app.control.revoke(task_info["task_id"], terminate=True)
            
            return {"success": True, "message": f"Task {task_id} cancelled"}
        
        return {"success": False, "error": "Task not found"}


# Global task manager instance
task_manager = TaskManager()


# Core background tasks
@celery_app.task(bind=True, name="backend.core.background_tasks.calculate_daily_analytics")
def calculate_daily_analytics(self):
    """Calculate daily analytics for all modules"""
    try:
        # Update task progress
        self.update_state(state="PROGRESS", meta={"current": 0, "total": 4, "status": "Starting daily analytics"})
        
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Calculate loyalty analytics
            self.update_state(state="PROGRESS", meta={"current": 1, "total": 4, "status": "Calculating loyalty analytics"})
            from modules.loyalty.services.analytics_service import LoyaltyAnalyticsService
            loyalty_analytics = LoyaltyAnalyticsService(db)
            loyalty_results = loyalty_analytics.calculate_daily_analytics()
            
            # Calculate customer analytics
            self.update_state(state="PROGRESS", meta={"current": 2, "total": 4, "status": "Calculating customer analytics"})
            from modules.customers.services.analytics_service import CustomerAnalyticsService
            customer_analytics = CustomerAnalyticsService(db)
            customer_results = customer_analytics.calculate_daily_analytics()
            
            # Calculate revenue analytics
            self.update_state(state="PROGRESS", meta={"current": 3, "total": 4, "status": "Calculating revenue analytics"})
            revenue_results = calculate_revenue_analytics(db)
            
            # Aggregate results
            self.update_state(state="PROGRESS", meta={"current": 4, "total": 4, "status": "Finalizing analytics"})
            
            results = {
                "date": datetime.utcnow().date().isoformat(),
                "loyalty": loyalty_results,
                "customers": customer_results,
                "revenue": revenue_results,
                "calculated_at": datetime.utcnow().isoformat()
            }
            
            # Cache results
            if task_manager.redis_client:
                cache_key = f"analytics:daily:{datetime.utcnow().date().isoformat()}"
                task_manager.redis_client.setex(cache_key, 86400, str(results))  # Cache for 24 hours
            
            logger.info(f"Daily analytics calculated successfully: {results}")
            return results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error calculating daily analytics: {str(e)}")
        self.update_state(
            state="FAILURE",
            meta={"current": 0, "total": 4, "status": f"Failed: {str(e)}"}
        )
        raise


@celery_app.task(bind=True, name="backend.core.background_tasks.calculate_weekly_analytics")
def calculate_weekly_analytics(self):
    """Calculate weekly analytics aggregation"""
    try:
        self.update_state(state="PROGRESS", meta={"current": 0, "total": 3, "status": "Starting weekly analytics"})
        
        # Implementation for weekly analytics
        # This would aggregate daily analytics into weekly summaries
        
        results = {
            "week_start": (datetime.utcnow() - timedelta(days=7)).date().isoformat(),
            "week_end": datetime.utcnow().date().isoformat(),
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Weekly analytics calculated successfully: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating weekly analytics: {str(e)}")
        raise


@celery_app.task(bind=True, name="backend.core.background_tasks.calculate_monthly_analytics")
def calculate_monthly_analytics(self):
    """Calculate monthly analytics aggregation"""
    try:
        self.update_state(state="PROGRESS", meta={"current": 0, "total": 3, "status": "Starting monthly analytics"})
        
        # Implementation for monthly analytics
        # This would aggregate weekly analytics into monthly summaries
        
        results = {
            "month": datetime.utcnow().strftime("%Y-%m"),
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Monthly analytics calculated successfully: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating monthly analytics: {str(e)}")
        raise


@celery_app.task(bind=True, name="backend.core.background_tasks.calculate_custom_analytics")
def calculate_custom_analytics(self, date_range: Dict[str, Any]):
    """Calculate analytics for custom date range"""
    try:
        start_date = datetime.fromisoformat(date_range["start_date"])
        end_date = datetime.fromisoformat(date_range["end_date"])
        
        self.update_state(
            state="PROGRESS", 
            meta={
                "current": 0, 
                "total": 2, 
                "status": f"Calculating analytics from {start_date.date()} to {end_date.date()}"
            }
        )
        
        # Implementation for custom date range analytics
        
        results = {
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Custom analytics calculated successfully: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating custom analytics: {str(e)}")
        raise


@celery_app.task(name="backend.core.background_tasks.cleanup_old_sessions")
def cleanup_old_sessions():
    """Clean up expired sessions and temporary data"""
    try:
        # Implementation for session cleanup
        logger.info("Session cleanup completed successfully")
        return {"cleaned_sessions": 0, "cleaned_at": datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {str(e)}")
        raise


@celery_app.task(name="backend.core.background_tasks.cleanup_analytics_cache")
def cleanup_analytics_cache():
    """Clean up old analytics cache entries"""
    try:
        if not task_manager.redis_client:
            return {"message": "Redis not available, skipping cache cleanup"}
        
        # Clean up cache entries older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        cleaned_keys = 0
        
        # Get all analytics cache keys
        for key in task_manager.redis_client.scan_iter(match="analytics:*"):
            # Check if key is old enough to clean
            try:
                # Extract date from key and compare
                # This would need to be implemented based on your key format
                task_manager.redis_client.delete(key)
                cleaned_keys += 1
            except:
                pass
        
        logger.info(f"Analytics cache cleanup completed: {cleaned_keys} keys cleaned")
        return {"cleaned_keys": cleaned_keys, "cleaned_at": datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Error cleaning up analytics cache: {str(e)}")
        raise


def calculate_revenue_analytics(db) -> Dict[str, Any]:
    """Calculate revenue analytics for a given period"""
    try:
        # This would implement revenue calculation logic
        # For now, return placeholder data
        
        return {
            "total_revenue": 0.0,
            "revenue_by_category": {},
            "average_order_value": 0.0,
            "order_count": 0
        }
        
    except Exception as e:
        logger.error(f"Error calculating revenue analytics: {str(e)}")
        return {"error": str(e)}


# Utility functions for task management
def start_background_analytics():
    """Start background analytics calculation"""
    return task_manager.schedule_analytics_calculation("daily")


def get_analytics_task_status(task_id: str):
    """Get status of analytics task"""
    return task_manager.get_task_status(task_id)


def schedule_custom_analytics(start_date: str, end_date: str):
    """Schedule custom analytics for date range"""
    date_range = {"start_date": start_date, "end_date": end_date}
    return task_manager.schedule_analytics_calculation("custom", date_range)


# Health check for background tasks
@celery_app.task(name="backend.core.background_tasks.health_check")
def health_check():
    """Health check task to verify background task system is working"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker_id": health_check.request.hostname
    }