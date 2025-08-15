# backend/modules/payroll/tasks/payroll_tasks.py

"""
Celery tasks for payroll background processing.

These tasks replace FastAPI BackgroundTasks for production use.
"""

from celery import Task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json

from .celery_config import celery_app, TASK_PRIORITIES
from core.database import SessionLocal
from ..models.payroll_configuration import PayrollJobTracking
from ..enums.payroll_enums import PayrollJobStatus
from ..services.batch_payroll_service import BatchPayrollService
from ..schemas.batch_processing_schemas import BatchPayrollRequest, CalculationOptions

logger = get_task_logger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True, base=DatabaseTask, name="payroll.process_batch_payroll", max_retries=3
)
def process_batch_payroll(
    self,
    job_id: str,
    employee_ids: Optional[List[int]],
    pay_period_start: str,
    pay_period_end: str,
    calculation_options: Optional[Dict[str, Any]],
    user_id: int,
    tenant_id: Optional[int] = None,
    priority: str = "normal",
):
    """
    Process payroll for multiple employees in batch.

    This is the Celery version of the background task.
    """
    logger.info(f"Starting batch payroll job {job_id}")

    try:
        # Get job tracking record
        job = (
            self.db.query(PayrollJobTracking)
            .filter(PayrollJobTracking.job_id == job_id)
            .first()
        )

        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Update status to processing
        job.status = PayrollJobStatus.PROCESSING
        job.metadata["celery_task_id"] = self.request.id
        self.db.commit()

        # Convert string dates back to date objects
        from datetime import date

        pay_start = date.fromisoformat(pay_period_start)
        pay_end = date.fromisoformat(pay_period_end)

        # Create calculation options if provided
        calc_options = None
        if calculation_options:
            calc_options = CalculationOptions(**calculation_options)

        # Process batch
        batch_service = BatchPayrollService(self.db)
        results = batch_service.process_batch_sync(  # Sync version for Celery
            employee_ids=employee_ids,
            pay_period_start=pay_start,
            pay_period_end=pay_end,
            calculation_options=calc_options,
        )

        # Update job with results
        job.status = PayrollJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.metadata.update(
            {
                "total_processed": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "total_gross": str(sum(r.gross_amount for r in results if r.success)),
                "total_net": str(sum(r.net_amount for r in results if r.success)),
            }
        )
        self.db.commit()

        logger.info(f"Completed batch payroll job {job_id}: {len(results)} processed")

        # Send completion webhook if configured
        send_webhook.apply_async(
            args=[
                "payroll.batch_completed",
                {
                    "job_id": job_id,
                    "total_processed": len(results),
                    "successful": job.metadata["successful"],
                    "failed": job.metadata["failed"],
                },
            ],
            priority=TASK_PRIORITIES["low"],
        )

    except Exception as e:
        logger.error(f"Error processing batch payroll {job_id}: {str(e)}")

        # Update job status
        if job:
            job.status = PayrollJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self.db.commit()

        # Retry with exponential backoff
        raise self.retry(
            exc=e, countdown=60 * (2**self.request.retries)  # 1min, 2min, 4min
        )


@celery_app.task(
    bind=True, base=DatabaseTask, name="payroll.export_audit_logs", max_retries=2
)
def export_audit_logs(
    self,
    export_id: str,
    filters: Dict[str, Any],
    format: str,
    user_id: int,
    tenant_id: Optional[int] = None,
):
    """
    Export audit logs to specified format.
    """
    logger.info(f"Starting audit export {export_id} in {format} format")

    try:
        from ..models.payroll_audit import PayrollAuditLog
        from datetime import date

        # Build query based on filters
        query = self.db.query(PayrollAuditLog)

        if "start_date" in filters:
            query = query.filter(
                PayrollAuditLog.timestamp >= date.fromisoformat(filters["start_date"])
            )

        if "end_date" in filters:
            end_date = date.fromisoformat(filters["end_date"]) + timedelta(days=1)
            query = query.filter(PayrollAuditLog.timestamp < end_date)

        if tenant_id:
            query = query.filter(PayrollAuditLog.tenant_id == tenant_id)

        # Fetch data in batches to avoid memory issues
        batch_size = 1000
        offset = 0
        all_records = []

        while True:
            batch = query.limit(batch_size).offset(offset).all()
            if not batch:
                break
            all_records.extend(batch)
            offset += batch_size

            # Update progress
            progress = min(offset / query.count() * 100, 90)
            logger.info(f"Export {export_id} progress: {progress:.1f}%")

        # Generate export file based on format
        if format == "csv":
            file_path = generate_csv_export(export_id, all_records)
        elif format == "json":
            file_path = generate_json_export(export_id, all_records)
        else:
            file_path = generate_pdf_export(export_id, all_records)

        # Upload to storage (S3, GCS, etc.)
        download_url = upload_export_file(file_path, export_id)

        # Send notification
        send_export_notification.apply_async(
            args=[user_id, export_id, download_url], countdown=5
        )

        logger.info(f"Completed audit export {export_id}")

    except Exception as e:
        logger.error(f"Error exporting audit logs {export_id}: {str(e)}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@celery_app.task(name="payroll.send_webhook", max_retries=5)
def send_webhook(event_type: str, payload: Dict[str, Any]):
    """
    Send webhook notifications to subscribed URLs.
    """
    from ..routes.v1.webhook_routes import send_webhook_notification
    import asyncio

    db = SessionLocal()
    try:
        from ..models.payroll_configuration import PayrollWebhookSubscription

        # Get active subscriptions for this event
        subscriptions = (
            db.query(PayrollWebhookSubscription)
            .filter(
                PayrollWebhookSubscription.is_active == True,
                PayrollWebhookSubscription.event_types.contains([event_type]),
            )
            .all()
        )

        logger.info(f"Sending {event_type} webhook to {len(subscriptions)} subscribers")

        # Send to each subscription
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for sub in subscriptions:
            try:
                status_code, response = loop.run_until_complete(
                    send_webhook_notification(
                        webhook_url=sub.webhook_url,
                        event_type=event_type,
                        payload=payload,
                        secret_key=sub.secret_key,
                    )
                )

                if status_code and 200 <= status_code < 300:
                    logger.info(f"Successfully sent webhook to {sub.webhook_url}")
                    sub.last_triggered_at = datetime.utcnow()
                    sub.total_events_sent += 1
                else:
                    logger.warning(
                        f"Failed to send webhook to {sub.webhook_url}: {status_code}"
                    )
                    sub.failure_count += 1

                db.commit()

            except Exception as e:
                logger.error(f"Error sending webhook to {sub.webhook_url}: {str(e)}")
                sub.failure_count += 1
                db.commit()

    finally:
        db.close()


@celery_app.task(name="payroll.cleanup_old_jobs")
def cleanup_old_jobs():
    """
    Clean up old completed/failed jobs.
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Delete old completed jobs
        deleted = (
            db.query(PayrollJobTracking)
            .filter(
                PayrollJobTracking.completed_at < cutoff_date,
                PayrollJobTracking.status.in_(
                    [
                        PayrollJobStatus.COMPLETED,
                        PayrollJobStatus.FAILED,
                        PayrollJobStatus.CANCELLED,
                    ]
                ),
            )
            .delete()
        )

        db.commit()
        logger.info(f"Cleaned up {deleted} old jobs")

    finally:
        db.close()


@celery_app.task(name="payroll.retry_failed_webhooks")
def retry_failed_webhooks():
    """
    Retry failed webhook deliveries.
    """
    # Implementation would retry webhooks with failure_count > 0
    # and implement exponential backoff
    pass


@celery_app.task(name="payroll.generate_audit_summary")
def generate_daily_audit_summary():
    """
    Generate daily audit summary report.
    """
    # Implementation would generate and email daily audit summaries
    pass


# Helper functions
def generate_csv_export(export_id: str, records: List[Any]) -> str:
    """Generate CSV export file."""
    # Implementation
    pass


def generate_json_export(export_id: str, records: List[Any]) -> str:
    """Generate JSON export file."""
    # Implementation
    pass


def generate_pdf_export(export_id: str, records: List[Any]) -> str:
    """Generate PDF export file."""
    # Implementation
    pass


def upload_export_file(file_path: str, export_id: str) -> str:
    """Upload export file to cloud storage."""
    # Implementation would upload to S3/GCS and return URL
    pass


@celery_app.task
def send_export_notification(user_id: int, export_id: str, download_url: str):
    """Send export completion notification."""
    # Implementation would send email/notification
    pass
