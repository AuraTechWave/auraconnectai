"""
Background tasks for payroll processing with persistent job tracking.

Addresses code review concerns about in-memory job tracking by using
PayrollConfigurationService for persistent storage.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from ..services.enhanced_payroll_service import EnhancedPayrollService
from ...payroll.services.payroll_configuration_service import (
    PayrollConfigurationService,
)
from ...payroll.models.payroll_configuration import PayrollJobTracking


async def process_payroll_batch_persistent(
    job_id: str,
    payroll_service: EnhancedPayrollService,
    config_service: PayrollConfigurationService,
    staff_ids: List[int],
    pay_period_start: date,
    pay_period_end: date,
    tenant_id: Optional[int],
    force_recalculate: bool,
):
    """
    Background task to process payroll using persistent job tracking.

    Addresses code review: "API Reliability: In-memory job status tracking
    will be lost on server restart. Consider persistent storage."
    """
    try:
        # Update job status to running
        config_service.update_job_progress(job_id=job_id, status="running")

        completed_count = 0
        failed_count = 0
        processing_errors = []

        # Process each staff member
        for staff_id in staff_ids:
            try:
                if force_recalculate:
                    await payroll_service.recalculate_payroll(
                        staff_id=staff_id,
                        pay_period_start=pay_period_start,
                        pay_period_end=pay_period_end,
                        tenant_id=tenant_id,
                    )
                else:
                    await payroll_service.process_payroll_for_staff(
                        staff_id=staff_id,
                        pay_period_start=pay_period_start,
                        pay_period_end=pay_period_end,
                        tenant_id=tenant_id,
                    )

                completed_count += 1

                # Update progress after each successful staff processing
                progress = int((completed_count / len(staff_ids)) * 100)
                config_service.update_job_progress(
                    job_id=job_id,
                    completed_items=completed_count,
                    progress_percentage=progress,
                )

            except Exception as e:
                failed_count += 1
                processing_errors.append({"staff_id": staff_id, "error": str(e)})

                # Update failed count
                config_service.update_job_progress(
                    job_id=job_id,
                    failed_items=failed_count,
                    error_details={"processing_errors": processing_errors},
                )

        # Mark job as completed
        final_status = "completed" if failed_count == 0 else "completed_with_errors"
        config_service.update_job_progress(
            job_id=job_id,
            status=final_status,
            progress_percentage=100,
            result_data={
                "total_processed": len(staff_ids),
                "successful": completed_count,
                "failed": failed_count,
                "processing_errors": processing_errors,
            },
        )

    except Exception as e:
        # Mark job as failed due to batch processing error
        config_service.update_job_progress(
            job_id=job_id,
            status="failed",
            error_details={
                "batch_error": str(e),
                "message": "Batch processing failed completely",
            },
        )


async def process_payroll_export_persistent(
    export_id: str,
    config_service: PayrollConfigurationService,
    export_format: str,
    staff_ids: List[int],
    pay_period_start: date,
    pay_period_end: date,
    tenant_id: Optional[int],
):
    """
    Background task to export payroll data with persistent tracking.
    """
    try:
        # Update job status to running
        config_service.update_job_progress(job_id=export_id, status="running")

        # Simulate export processing
        # In real implementation, this would generate CSV, PDF, or other formats
        export_data = {
            "format": export_format,
            "staff_count": len(staff_ids),
            "pay_period": f"{pay_period_start} to {pay_period_end}",
            "generated_at": str(date.today()),
        }

        # Update progress incrementally
        for i, staff_id in enumerate(staff_ids):
            # Simulate processing each staff member's data
            progress = int(((i + 1) / len(staff_ids)) * 100)
            config_service.update_job_progress(
                job_id=export_id, progress_percentage=progress, completed_items=i + 1
            )

        # Mark export as completed
        config_service.update_job_progress(
            job_id=export_id,
            status="completed",
            progress_percentage=100,
            result_data=export_data,
        )

    except Exception as e:
        # Mark export as failed
        config_service.update_job_progress(
            job_id=export_id,
            status="failed",
            error_details={
                "export_error": str(e),
                "message": "Export processing failed",
            },
        )
