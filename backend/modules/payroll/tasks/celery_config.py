# backend/modules/payroll/tasks/celery_config.py

"""
Celery configuration for payroll background tasks.

This provides an example of how to configure Celery for
distributed, durable task processing instead of FastAPI's
in-process BackgroundTasks.
"""

from celery import Celery
from typing import Optional
import os

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "payroll_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.modules.payroll.tasks.payroll_tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task execution settings
    task_acks_late=True,  # Tasks acknowledged after execution
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,  # 60 seconds
    task_max_retries=3,
    
    # Rate limiting
    task_default_rate_limit="100/m",  # 100 tasks per minute
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "payroll.cleanup_old_jobs",
            "schedule": 3600.0,  # Every hour
            "args": ()
        },
        "retry-failed-webhooks": {
            "task": "payroll.retry_failed_webhooks",
            "schedule": 300.0,  # Every 5 minutes
            "args": ()
        },
        "generate-daily-audit-summary": {
            "task": "payroll.generate_audit_summary",
            "schedule": {
                "hour": 2,  # 2 AM daily
                "minute": 0
            },
            "args": ()
        }
    }
)

# Task routing for different queues
celery_app.conf.task_routes = {
    "payroll.process_batch_payroll": {"queue": "payroll_heavy"},
    "payroll.export_audit_logs": {"queue": "exports"},
    "payroll.send_webhook": {"queue": "webhooks"},
    "payroll.*": {"queue": "payroll_default"}
}

# Queue configuration with priorities
celery_app.conf.task_queue_max_priority = 10
celery_app.conf.task_default_priority = 5

# Task priorities
TASK_PRIORITIES = {
    "urgent": 9,
    "high": 7,
    "normal": 5,
    "low": 3
}


def get_celery_app() -> Celery:
    """Get configured Celery app instance."""
    return celery_app


def configure_celery_for_flask(app):
    """Configure Celery with Flask app context."""
    class ContextTask(celery_app.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery_app.Task = ContextTask
    return celery_app


# Example usage in Docker Compose:
"""
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  celery_worker:
    build: .
    command: celery -A backend.modules.payroll.tasks.celery_config:celery_app worker --loglevel=info -Q payroll_default,payroll_heavy,exports,webhooks
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
      - db
  
  celery_beat:
    build: .
    command: celery -A backend.modules.payroll.tasks.celery_config:celery_app beat --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
  
  flower:
    build: .
    command: celery -A backend.modules.payroll.tasks.celery_config:celery_app flower
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
"""