# backend/modules/payroll/tests/test_batch_processing.py

"""
Functional tests for batch payroll processing.

Tests the complete batch processing lifecycle including:
- Job creation and tracking
- Status updates
- Cancellation
- Error handling
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import uuid

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from ..routes.v1.batch_processing_routes import (
    run_batch_payroll,
    get_batch_job_status,
    process_payroll_batch
)
from ..models.payroll_configuration import PayrollJobTracking
from ..schemas.batch_processing_schemas import (
    BatchPayrollRequest,
    CalculationOptions
)
from ..enums.payroll_enums import PayrollJobStatus
from ..exceptions import JobNotFoundException, BatchProcessingError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock()
    user.id = 1
    user.email = "test@example.com"
    user.tenant_id = 1
    return user


@pytest.fixture
def batch_request():
    """Sample batch payroll request."""
    return BatchPayrollRequest(
        employee_ids=[1, 2, 3],
        pay_period_start=date(2025, 1, 1),
        pay_period_end=date(2025, 1, 15),
        calculation_options=CalculationOptions(
            include_overtime=True,
            include_bonuses=True
        )
    )


class TestBatchProcessingLifecycle:
    """Test complete batch processing lifecycle."""
    
    @pytest.mark.asyncio
    async def test_successful_batch_creation(self, mock_db, mock_user, batch_request):
        """Test successful batch job creation."""
        # Setup
        background_tasks = BackgroundTasks()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Execute
        response = await run_batch_payroll(
            batch_request=batch_request,
            background_tasks=background_tasks,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.status == "pending"
        assert response.employee_count == 3
        assert response.job_id is not None
        assert mock_db.add.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_batch_status_tracking(self, mock_db, mock_user):
        """Test job status tracking."""
        # Setup
        job_id = str(uuid.uuid4())
        mock_job = Mock(spec=PayrollJobTracking)
        mock_job.job_id = job_id
        mock_job.job_type = "batch_payroll"
        mock_job.status = PayrollJobStatus.PROCESSING
        mock_job.started_at = datetime.utcnow()
        mock_job.completed_at = None
        mock_job.metadata = {
            "employee_count": 10,
            "total_processed": 5,
            "successful": 4,
            "failed": 1
        }
        mock_job.error_message = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        
        # Execute
        response = await get_batch_job_status(
            job_id=job_id,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.job_id == job_id
        assert response.status == PayrollJobStatus.PROCESSING
        assert response.progress == 50.0  # 5 of 10 processed
        assert response.successful_count == 4
        assert response.failed_count == 1
    
    @pytest.mark.asyncio
    async def test_job_not_found(self, mock_db, mock_user):
        """Test handling of non-existent job."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await get_batch_job_status(
                job_id="non-existent-job",
                db=mock_db,
                current_user=mock_user
            )
        
        # Should raise HTTPException with 404
        assert "404" in str(exc_info.value)


class TestBatchProcessingBackgroundTask:
    """Test background processing logic."""
    
    @pytest.mark.asyncio
    async def test_successful_batch_processing(self, mock_db, batch_request):
        """Test successful batch processing in background."""
        # Setup
        job_id = str(uuid.uuid4())
        mock_job = Mock(spec=PayrollJobTracking)
        mock_job.status = PayrollJobStatus.PENDING
        mock_job.metadata = {}
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_db.commit = Mock()
        
        # Mock batch service
        with patch('backend.modules.payroll.routes.v1.batch_processing_routes.BatchPayrollService') as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.process_batch = AsyncMock(return_value=[
                Mock(success=True, gross_amount=1000, net_amount=800),
                Mock(success=True, gross_amount=1200, net_amount=960),
                Mock(success=False, gross_amount=0, net_amount=0)
            ])
            
            # Execute
            await process_payroll_batch(
                db=mock_db,
                job_id=job_id,
                batch_request=batch_request,
                user_id=1
            )
            
            # Verify job status updates
            assert mock_job.status == PayrollJobStatus.COMPLETED
            assert mock_job.completed_at is not None
            assert mock_job.metadata["total_processed"] == 3
            assert mock_job.metadata["successful"] == 2
            assert mock_job.metadata["failed"] == 1
            assert mock_db.commit.call_count >= 2  # Status updates
    
    @pytest.mark.asyncio
    async def test_batch_processing_failure(self, mock_db, batch_request):
        """Test handling of processing failures."""
        # Setup
        job_id = str(uuid.uuid4())
        mock_job = Mock(spec=PayrollJobTracking)
        mock_job.status = PayrollJobStatus.PENDING
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_db.commit = Mock()
        
        # Mock batch service to raise error
        with patch('backend.modules.payroll.routes.v1.batch_processing_routes.BatchPayrollService') as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.process_batch = AsyncMock(
                side_effect=Exception("Database connection lost")
            )
            
            # Execute and verify
            with pytest.raises(Exception) as exc_info:
                await process_payroll_batch(
                    db=mock_db,
                    job_id=job_id,
                    batch_request=batch_request,
                    user_id=1
                )
            
            # Verify job marked as failed
            assert mock_job.status == PayrollJobStatus.FAILED
            assert mock_job.error_message == "Database connection lost"
            assert mock_job.completed_at is not None


class TestBatchValidation:
    """Test input validation for batch processing."""
    
    @pytest.mark.asyncio
    async def test_invalid_date_range(self, mock_db, mock_user):
        """Test validation of date ranges."""
        # Create request with invalid dates
        invalid_request = BatchPayrollRequest(
            employee_ids=[1, 2, 3],
            pay_period_start=date(2025, 1, 15),
            pay_period_end=date(2025, 1, 1),  # End before start
            calculation_options=None
        )
        
        background_tasks = BackgroundTasks()
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await run_batch_payroll(
                batch_request=invalid_request,
                background_tasks=background_tasks,
                db=mock_db,
                current_user=mock_user
            )
        
        # Should raise validation error
        assert "ValidationError" in str(exc_info.value)
        assert "after start" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_empty_employee_list(self, mock_db, mock_user):
        """Test handling of empty employee list."""
        # This should be valid - processes all employees
        request = BatchPayrollRequest(
            employee_ids=None,  # Process all
            pay_period_start=date(2025, 1, 1),
            pay_period_end=date(2025, 1, 15),
            calculation_options=None
        )
        
        background_tasks = BackgroundTasks()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Execute
        response = await run_batch_payroll(
            batch_request=request,
            background_tasks=background_tasks,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.status == "pending"
        assert response.employee_count is None  # Unknown until processing


class TestJobCancellation:
    """Test batch job cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, mock_db, mock_user):
        """Test cancelling a pending job."""
        # Import the cancel function
        from ..routes.v1.batch_processing_routes import cancel_batch_job
        
        # Setup
        job_id = str(uuid.uuid4())
        mock_job = Mock(spec=PayrollJobTracking)
        mock_job.job_id = job_id
        mock_job.status = PayrollJobStatus.PENDING
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_db.commit = Mock()
        
        # Execute
        response = await cancel_batch_job(
            job_id=job_id,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert mock_job.status == PayrollJobStatus.CANCELLED
        assert "cancelled" in response["status"]
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_job(self, mock_db, mock_user):
        """Test that completed jobs cannot be cancelled."""
        from ..routes.v1.batch_processing_routes import cancel_batch_job
        
        # Setup
        job_id = str(uuid.uuid4())
        mock_job = Mock(spec=PayrollJobTracking)
        mock_job.job_id = job_id
        mock_job.status = PayrollJobStatus.COMPLETED
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await cancel_batch_job(
                job_id=job_id,
                db=mock_db,
                current_user=mock_user
            )
        
        # Should raise error about invalid operation
        assert "Cannot cancel" in str(exc_info.value)