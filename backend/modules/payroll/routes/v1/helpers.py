# backend/modules/payroll/routes/v1/helpers.py

"""
Helper functions for v1 payroll routes.

Centralizes common calculations and utilities to reduce duplication.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ...models.payroll_configuration import PayrollJobTracking
from ...enums.payroll_enums import PayrollJobStatus


def calculate_job_progress(job: PayrollJobTracking) -> Dict[str, Any]:
    """
    Calculate job progress metrics from tracking data.

    Args:
        job: PayrollJobTracking instance

    Returns:
        Dictionary with progress metrics
    """
    total = job.metadata.get("employee_count", 0)
    if isinstance(total, str) and total == "all":
        # For "all employees" jobs, estimate based on processed count
        processed = job.metadata.get("total_processed", 0)
        if job.status == PayrollJobStatus.COMPLETED:
            total = processed
        else:
            # Estimate total based on progress
            total = max(100, processed * 2)  # Minimum 100 for progress calculation

    processed = job.metadata.get("total_processed", 0)
    progress = (processed / total * 100) if total > 0 else 0

    # Calculate estimated completion time
    estimated_completion = None
    if job.status == PayrollJobStatus.PROCESSING and progress > 0:
        elapsed = (datetime.utcnow() - job.started_at).total_seconds()
        if progress > 0:
            total_estimated = elapsed / (progress / 100)
            remaining = total_estimated - elapsed
            estimated_completion = datetime.utcnow() + timedelta(seconds=remaining)

    return {
        "progress": min(progress, 100),  # Cap at 100%
        "total_items": total,
        "processed_items": processed,
        "successful_items": job.metadata.get("successful", 0),
        "failed_items": job.metadata.get("failed", 0),
        "estimated_completion": estimated_completion,
    }


def format_job_summary(job: PayrollJobTracking) -> Dict[str, Any]:
    """
    Format job data into a consistent summary structure.

    Args:
        job: PayrollJobTracking instance

    Returns:
        Dictionary with formatted job summary
    """
    progress_data = calculate_job_progress(job)

    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status.value,
        "progress": progress_data["progress"],
        "started_at": job.started_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "total_items": progress_data["total_items"],
        "processed_items": progress_data["processed_items"],
        "successful_items": progress_data["successful_items"],
        "failed_items": progress_data["failed_items"],
        "estimated_completion": (
            progress_data["estimated_completion"].isoformat()
            if progress_data["estimated_completion"]
            else None
        ),
        "error_message": job.error_message,
    }


def validate_date_range(
    start_date: Any, end_date: Any, max_days: Optional[int] = None
) -> Dict[str, Any]:
    """
    Validate date range for queries and exports.

    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed days in range

    Returns:
        Dictionary with validation results
    """
    result = {"valid": True, "error": None, "days_in_range": 0}

    if end_date <= start_date:
        result["valid"] = False
        result["error"] = "End date must be after start date"
        return result

    # Calculate days in range
    if hasattr(start_date, "date"):
        # datetime object
        delta = end_date.date() - start_date.date()
    else:
        # date object
        delta = end_date - start_date

    result["days_in_range"] = delta.days

    if max_days and delta.days > max_days:
        result["valid"] = False
        result["error"] = f"Date range cannot exceed {max_days} days"

    return result


def get_tenant_filter(user: Any) -> Optional[int]:
    """
    Get tenant ID for filtering queries.

    Args:
        user: Current user object

    Returns:
        Tenant ID or None
    """
    return user.tenant_id if hasattr(user, "tenant_id") else None


def format_error_details(
    error: Exception, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format exception details for consistent error responses.

    Args:
        error: Exception instance
        context: Additional context information

    Returns:
        Dictionary with error details
    """
    error_details = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if context:
        error_details["context"] = context

    # Add specific details for known error types
    if hasattr(error, "orig"):
        # SQLAlchemy database errors
        error_details["database_error"] = str(error.orig)

    return error_details
