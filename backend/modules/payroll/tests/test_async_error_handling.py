# backend/modules/payroll/tests/test_async_error_handling.py

"""
Tests for async job error handling and recovery.

Tests Celery task failures, retries, and recovery workflows
for background payroll processing.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import asyncio

from celery import states
from celery.exceptions import Retry, MaxRetriesExceededError

from ..tasks.payroll_tasks import (
    process_batch_payroll_task,
    export_audit_logs_task,
    send_webhook_notification_task,
    retry_failed_payments_task
)
from ..models.payroll_configuration import PayrollJobTracking
from ..enums.payroll_enums import PayrollJobStatus
from ..exceptions import BatchProcessingError, WebhookDeliveryError


class TestAsyncErrorHandling:
    """Test error handling in async/background jobs."""
    
    @pytest.fixture
    def mock_celery_task(self):
        """Create mock Celery task context."""
        task = Mock()
        task.request = Mock()
        task.request.id = "test-task-id-123"
        task.request.retries = 0
        task.max_retries = 3
        task.retry = Mock(side_effect=Retry("Retry requested"))
        return task
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_database_failure(self, mock_db, mock_celery_task):
        """Test batch processing recovery from database failures."""
        
        job_id = "batch_20240115_001"
        
        # Simulate database connection failure
        mock_db.query.side_effect = Exception("Database connection lost")
        
        with patch('backend.modules.payroll.tasks.payroll_tasks.get_db', return_value=mock_db):
            with patch.object(mock_celery_task, 'retry') as mock_retry:
                # Task should retry on database failure
                with pytest.raises(Retry):
                    await process_batch_payroll_task.apply_async(
                        args=[job_id],
                        task_id=mock_celery_task.request.id
                    )
                
                # Verify retry was called with exponential backoff
                mock_retry.assert_called_once()
                retry_kwargs = mock_retry.call_args[1]
                assert retry_kwargs['countdown'] >= 60  # At least 1 minute
                assert retry_kwargs['max_retries'] == 3
    
    @pytest.mark.asyncio
    async def test_batch_processing_partial_failure_recovery(self, mock_db):
        """Test recovery from partial batch processing failures."""
        
        job_id = "batch_20240115_002"
        
        # Create job tracking record
        job_tracking = Mock(spec=PayrollJobTracking)
        job_tracking.job_id = job_id
        job_tracking.status = PayrollJobStatus.PROCESSING
        job_tracking.total_employees = 10
        job_tracking.processed_count = 3
        job_tracking.success_count = 2
        job_tracking.failure_count = 1
        job_tracking.error_details = [
            {"employee_id": 3, "error": "Tax calculation failed"}
        ]
        
        # Mock query to return job tracking
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = job_tracking
        
        # Test resume from failure
        with patch('backend.modules.payroll.tasks.payroll_tasks.BatchPayrollService') as mock_service:
            mock_batch_service = Mock()
            mock_service.return_value = mock_batch_service
            
            # Mock resuming from employee 4
            mock_batch_service.process_batch.return_value = [
                Mock(employee_id=i, success=True) for i in range(4, 11)
            ]
            
            # Resume processing
            result = await retry_failed_payments_task.apply_async(
                args=[job_id, {"resume_from_employee": 4}]
            )
            
            # Verify resumed correctly
            assert mock_batch_service.process_batch.called
            call_args = mock_batch_service.process_batch.call_args
            assert call_args[1]['start_from_employee_id'] == 4
    
    @pytest.mark.asyncio
    async def test_webhook_delivery_with_retries(self, mock_celery_task):
        """Test webhook delivery with automatic retries."""
        
        webhook_url = "https://example.com/webhook"
        payload = {"event": "payment.completed", "payment_id": 123}
        
        # Simulate temporary network failure
        with patch('requests.post') as mock_post:
            mock_post.side_effect = [
                Exception("Connection timeout"),  # First attempt fails
                Exception("Connection timeout"),  # Second attempt fails
                Mock(status_code=200, json=lambda: {"success": True})  # Third succeeds
            ]
            
            with patch.object(mock_celery_task, 'request') as mock_request:
                mock_request.retries = 2  # Already retried twice
                
                # Should succeed on third attempt
                result = await send_webhook_notification_task(
                    webhook_url=webhook_url,
                    payload=payload,
                    _task=mock_celery_task
                )
                
                assert result["status"] == "delivered"
                assert result["attempts"] == 3
    
    @pytest.mark.asyncio
    async def test_webhook_max_retries_exceeded(self, mock_celery_task):
        """Test webhook delivery when max retries exceeded."""
        
        webhook_url = "https://example.com/webhook"
        payload = {"event": "payment.completed", "payment_id": 123}
        
        # All attempts fail
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Permanent failure")
            
            with patch.object(mock_celery_task, 'request') as mock_request:
                mock_request.retries = 3  # Already at max retries
                
                # Should raise max retries exceeded
                with pytest.raises(MaxRetriesExceededError):
                    await send_webhook_notification_task(
                        webhook_url=webhook_url,
                        payload=payload,
                        _task=mock_celery_task
                    )
        
        # Verify failure is logged
        with patch('backend.modules.payroll.tasks.payroll_tasks.log_webhook_failure') as mock_log:
            mock_log.assert_called_with(
                webhook_url=webhook_url,
                error="Permanent failure",
                attempts=4
            )
    
    @pytest.mark.asyncio
    async def test_export_task_with_memory_limit(self):
        """Test export task handling memory limitations."""
        
        # Large export request
        export_params = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "format": "excel",
            "employee_count": 10000  # Large dataset
        }
        
        with patch('backend.modules.payroll.tasks.payroll_tasks.PaymentExportService') as mock_service:
            mock_export_service = Mock()
            mock_service.return_value = mock_export_service
            
            # Simulate memory error on large dataset
            mock_export_service.export_payments.side_effect = MemoryError(
                "Dataset too large for memory"
            )
            
            # Task should handle by chunking
            with patch.object(mock_export_service, 'export_payments_chunked') as mock_chunked:
                mock_chunked.return_value = {
                    "file_path": "/exports/large_export.xlsx",
                    "chunks_processed": 10,
                    "total_records": 10000
                }
                
                result = await export_audit_logs_task.apply_async(
                    args=[export_params]
                )
                
                # Verify switched to chunked processing
                assert mock_chunked.called
                assert result["chunks_processed"] == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_job_locking(self, mock_db):
        """Test handling of concurrent job execution."""
        
        job_id = "batch_20240115_003"
        
        # Simulate job already running
        existing_job = Mock(spec=PayrollJobTracking)
        existing_job.status = PayrollJobStatus.PROCESSING
        existing_job.locked_by = "other-worker-123"
        existing_job.locked_at = datetime.utcnow()
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.first.return_value = existing_job
        
        # Attempt to process same job
        with pytest.raises(BatchProcessingError) as exc_info:
            await process_batch_payroll_task.apply_async(
                args=[job_id]
            )
        
        assert "already being processed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_task_timeout_handling(self, mock_celery_task):
        """Test handling of task timeouts."""
        
        job_id = "batch_20240115_004"
        
        # Set task timeout
        mock_celery_task.time_limit = 300  # 5 minutes
        mock_celery_task.soft_time_limit = 270  # 4.5 minutes
        
        with patch('backend.modules.payroll.tasks.payroll_tasks.BatchPayrollService') as mock_service:
            mock_batch_service = Mock()
            mock_service.return_value = mock_batch_service
            
            # Simulate long-running task
            async def slow_process(*args, **kwargs):
                await asyncio.sleep(400)  # Exceeds timeout
                return []
            
            mock_batch_service.process_batch = slow_process
            
            # Task should be terminated
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    process_batch_payroll_task(job_id),
                    timeout=mock_celery_task.soft_time_limit
                )
        
        # Verify cleanup occurred
        with patch('backend.modules.payroll.tasks.payroll_tasks.cleanup_failed_job') as mock_cleanup:
            mock_cleanup.assert_called_with(job_id, "Task timeout exceeded")
    
    @pytest.mark.asyncio
    async def test_dead_letter_queue_handling(self):
        """Test failed tasks moved to dead letter queue."""
        
        failed_task = {
            "task_id": "failed-task-123",
            "task_name": "process_batch_payroll_task",
            "args": ["batch_20240115_005"],
            "kwargs": {},
            "exception": "Unrecoverable error",
            "traceback": "...",
            "retries": 3,
            "timestamp": datetime.utcnow()
        }
        
        with patch('backend.modules.payroll.tasks.payroll_tasks.move_to_dlq') as mock_dlq:
            mock_dlq.return_value = {
                "dlq_id": "dlq-entry-456",
                "can_retry_manually": True
            }
            
            # Move failed task to DLQ
            dlq_result = await move_to_dead_letter_queue(failed_task)
            
            assert dlq_result["dlq_id"] is not None
            assert dlq_result["can_retry_manually"] is True
        
        # Verify admin notification sent
        with patch('backend.modules.payroll.tasks.payroll_tasks.send_admin_alert') as mock_alert:
            mock_alert.assert_called_with(
                subject="Payroll task moved to DLQ",
                task_info=failed_task
            )
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker for repeated failures."""
        
        webhook_url = "https://unreliable-service.com/webhook"
        
        # Track failure count
        failure_count = 0
        
        with patch('backend.modules.payroll.tasks.payroll_tasks.CircuitBreaker') as mock_cb:
            circuit_breaker = Mock()
            mock_cb.return_value = circuit_breaker
            
            # Simulate circuit breaker states
            circuit_breaker.call.side_effect = [
                Exception("Service unavailable"),  # 1st failure
                Exception("Service unavailable"),  # 2nd failure
                Exception("Service unavailable"),  # 3rd failure - trips breaker
                Exception("Circuit breaker open"),  # 4th call blocked
            ]
            
            # Multiple webhook attempts
            for i in range(4):
                try:
                    await send_webhook_notification_task(
                        webhook_url=webhook_url,
                        payload={"attempt": i}
                    )
                except Exception as e:
                    failure_count += 1
                    if i == 3:
                        assert "Circuit breaker open" in str(e)
            
            assert failure_count == 4
            assert circuit_breaker.state == "open"
    
    @pytest.mark.asyncio
    async def test_idempotent_task_execution(self, mock_db):
        """Test idempotent task execution to prevent duplicate processing."""
        
        job_id = "batch_20240115_006"
        idempotency_key = f"payroll_batch_{job_id}"
        
        # Mock idempotency check
        with patch('backend.modules.payroll.tasks.payroll_tasks.check_idempotency') as mock_check:
            mock_check.side_effect = [
                False,  # First execution - not processed
                True    # Second execution - already processed
            ]
            
            # First execution should proceed
            result1 = await process_batch_payroll_task(
                job_id=job_id,
                idempotency_key=idempotency_key
            )
            assert result1["status"] == "completed"
            
            # Second execution should skip
            result2 = await process_batch_payroll_task(
                job_id=job_id,
                idempotency_key=idempotency_key
            )
            assert result2["status"] == "skipped"
            assert result2["reason"] == "Already processed"