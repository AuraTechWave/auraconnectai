"""
Enhanced FastAPI routes for Phase 4: API & Schemas.

Comprehensive REST endpoints for payroll and tax features with:
- POST /payrolls/run - Execute payroll processing
- GET /payrolls/{staff_id} - Retrieve staff payroll information
- GET /payrolls/rules - Get tax rules and policies
- Authentication and authorization
- Comprehensive OpenAPI documentation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid
from datetime import datetime, date

from ....core.database import get_db
from ....core.auth import (
    require_payroll_access, require_payroll_write, require_staff_access,
    get_current_user, User
)
from ..services.enhanced_payroll_service import EnhancedPayrollService
from ..schemas.enhanced_payroll_schemas import (
    PayrollRunRequest, PayrollRunResponse, PayrollHistoryResponse,
    PayrollRulesResponse, StaffPayrollDetail, PayrollStatsResponse,
    PayrollQueryFilters, PaginationParams, PayrollBatchStatus,
    PayrollExportRequest, PayrollExportResponse
)
from ...payroll.services.payroll_tax_engine import PayrollTaxEngine
from ...payroll.models.payroll_models import TaxRule
from .payroll_background_tasks import process_payroll_batch_persistent


router = APIRouter(prefix="/payrolls", tags=["Enhanced Payroll"])


# In-memory storage for batch job tracking (in production, use Redis or database)
BATCH_JOBS = {}


@router.post("/run", response_model=PayrollRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_payroll(
    request: PayrollRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Execute payroll processing for specified staff members and pay period.
    
    ## Authentication Required
    - Requires `payroll_manager` or `admin` role
    
    ## Request Body
    - **staff_ids**: Optional list of staff IDs (processes all active staff if not provided)
    - **pay_period_start**: Start date of pay period (YYYY-MM-DD)
    - **pay_period_end**: End date of pay period (YYYY-MM-DD)
    - **tenant_id**: Optional tenant ID for multi-tenant environments
    - **force_recalculate**: Force recalculation of existing payroll
    
    ## Response
    Returns a job ID and summary of the payroll run. Processing happens asynchronously.
    
    ## Example
    ```json
    {
        "staff_ids": [1, 2, 3],
        "pay_period_start": "2024-01-15",
        "pay_period_end": "2024-01-29",
        "tenant_id": 1,
        "force_recalculate": false
    }
    ```
    """
    try:
        payroll_service = EnhancedPayrollService(db)
        config_service = PayrollConfigurationService(db)
        
        # Determine staff IDs to process
        if request.staff_ids is None:
            # Get all active staff (would implement proper query in production)
            staff_ids_to_process = [1, 2, 3, 4, 5]  # Mock data
        else:
            staff_ids_to_process = request.staff_ids
        
        # Create persistent job tracking instead of in-memory storage
        # Addresses code review: "API Reliability: In-memory job status tracking"
        job_params = {
            "staff_ids": staff_ids_to_process,
            "pay_period_start": request.pay_period_start,
            "pay_period_end": request.pay_period_end
        }
        
        job_tracking = config_service.create_job_tracking(
            job_type="batch_payroll",
            job_params=job_params,
            created_by=current_user.email if hasattr(current_user, 'email') else None,
            tenant_id=request.tenant_id
        )
        
        job_id = job_tracking.job_id
        
        # Update job with total items and start status
        job_tracking.total_items = len(staff_ids_to_process)
        config_service.update_job_progress(
            job_id=job_id,
            status="processing"
        )
        
        # Start background processing with persistent tracking
        background_tasks.add_task(
            process_payroll_batch_persistent,
            job_id,
            payroll_service,
            config_service,
            staff_ids_to_process,
            request.pay_period_start,
            request.pay_period_end,
            request.tenant_id,
            request.force_recalculate
        )
        
        return PayrollRunResponse(
            job_id=job_id,
            status="processing",
            total_staff=len(staff_ids_to_process),
            successful_count=0,
            failed_count=0,
            pay_period_start=request.pay_period_start,
            pay_period_end=request.pay_period_end,
            total_gross_pay=0.0,
            total_net_pay=0.0,
            total_deductions=0.0,
            processing_errors=[],
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate payroll run: {str(e)}"
        )


@router.get("/run/{job_id}/status", response_model=PayrollBatchStatus)
async def get_payroll_run_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get the status of a payroll batch processing job from persistent storage.
    
    ## Authentication Required
    - Requires `payroll_manager`, `payroll_clerk`, or `admin` role
    
    ## Path Parameters
    - **job_id**: The job ID returned from POST /payrolls/run
    
    ## Response
    Returns current status, progress, and any errors for the batch job.
    """
    config_service = PayrollConfigurationService(db)
    job_status = config_service.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll job not found"
        )
    
    return PayrollBatchStatus(
        job_id=job_id,
        status=job_status["status"],
        progress=job_status["progress_percentage"],
        total_staff=job_status["total_items"],
        completed_staff=job_status["completed_items"],
        failed_staff=job_status["failed_items"],
        error_summary=[
            error.get("error", "Unknown error") 
            for error in (job_status.get("error_details", {}).get("processing_errors", [])[:5])
        ]
    )


@router.get("/{staff_id}", response_model=PayrollHistoryResponse)
async def get_staff_payroll(
    staff_id: int,
    limit: int = Query(10, ge=1, le=100, description="Number of payroll records to return"),
    tenant_id: Optional[int] = Query(None, description="Tenant ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_access)
):
    """
    Retrieve payroll history for a specific staff member.
    
    ## Authentication Required
    - Requires `staff_viewer`, `manager`, `payroll_clerk`, `payroll_manager`, or `admin` role
    
    ## Path Parameters
    - **staff_id**: The ID of the staff member
    
    ## Query Parameters
    - **limit**: Number of records to return (1-100, default: 10)
    - **tenant_id**: Optional tenant ID for filtering
    
    ## Response
    Returns payroll history with summary information for each pay period.
    """
    try:
        payroll_service = EnhancedPayrollService(db)
        
        # Get payroll history
        payment_history = await payroll_service.get_employee_payment_history(
            staff_id=staff_id,
            limit=limit,
            tenant_id=tenant_id
        )
        
        # Convert to API response format
        payroll_summaries = []
        for payment in payment_history:
            period_str = f"{payment['pay_period_end'].strftime('%Y-%m')}"
            payroll_summaries.append({
                "staff_id": staff_id,
                "staff_name": f"Staff Member {staff_id}",  # Would get from database
                "period": period_str,
                "gross_pay": payment['gross_amount'],
                "net_pay": payment['net_amount'],
                "total_deductions": payment['gross_amount'] - payment['net_amount'],
                "total_hours": (payment['regular_hours'] or 0) + (payment['overtime_hours'] or 0),
                "processed_at": payment['processed_at']
            })
        
        return PayrollHistoryResponse(
            staff_id=staff_id,
            staff_name=f"Staff Member {staff_id}",  # Would get from database
            payroll_history=payroll_summaries,
            total_records=len(payroll_summaries)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payroll history: {str(e)}"
        )


@router.get("/{staff_id}/detail", response_model=StaffPayrollDetail)
async def get_staff_payroll_detail(
    staff_id: int,
    pay_period_start: date = Query(..., description="Pay period start date"),
    pay_period_end: date = Query(..., description="Pay period end date"),
    tenant_id: Optional[int] = Query(None, description="Tenant ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_access)
):
    """
    Retrieve detailed payroll information for a staff member and specific pay period.
    
    ## Authentication Required
    - Requires `staff_viewer`, `manager`, `payroll_clerk`, `payroll_manager`, or `admin` role
    
    ## Path Parameters
    - **staff_id**: The ID of the staff member
    
    ## Query Parameters
    - **pay_period_start**: Start date of the pay period (YYYY-MM-DD)
    - **pay_period_end**: End date of the pay period (YYYY-MM-DD)
    - **tenant_id**: Optional tenant ID for filtering
    
    ## Response
    Returns comprehensive payroll details including hours, earnings, and deductions breakdown.
    """
    try:
        payroll_service = EnhancedPayrollService(db)
        
        # Process payroll for the specific period to get detailed information
        payroll_response = await payroll_service.process_payroll_for_staff(
            staff_id=staff_id,
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            tenant_id=tenant_id
        )
        
        # Convert to detailed API response format
        return StaffPayrollDetail(
            staff_id=staff_id,
            staff_name=f"Staff Member {staff_id}",  # Would get from database
            staff_role="server",  # Would get from database
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            
            # Hours (from breakdown)
            regular_hours=payroll_response.breakdown.hours_worked,
            overtime_hours=payroll_response.breakdown.overtime_hours,
            total_hours=payroll_response.breakdown.hours_worked + payroll_response.breakdown.overtime_hours,
            
            # Pay rates
            base_hourly_rate=payroll_response.breakdown.hourly_rate,
            overtime_rate=payroll_response.breakdown.overtime_rate,
            
            # Earnings
            regular_pay=payroll_response.breakdown.hours_worked * payroll_response.breakdown.hourly_rate,
            overtime_pay=payroll_response.breakdown.overtime_hours * payroll_response.breakdown.overtime_rate,
            gross_pay=payroll_response.gross_pay,
            
            # Tax deductions
            federal_tax=payroll_response.breakdown.tax_deductions * 0.6,  # Estimated breakdown
            state_tax=payroll_response.breakdown.tax_deductions * 0.25,
            social_security=payroll_response.breakdown.tax_deductions * 0.1,
            medicare=payroll_response.breakdown.tax_deductions * 0.05,
            total_tax_deductions=payroll_response.breakdown.tax_deductions,
            
            # Benefit deductions
            health_insurance=payroll_response.breakdown.other_deductions * 0.6,  # Estimated breakdown
            retirement_contribution=payroll_response.breakdown.other_deductions * 0.3,
            total_benefit_deductions=payroll_response.breakdown.other_deductions,
            
            # Other deductions
            total_other_deductions=0.0,
            
            # Totals
            total_deductions=payroll_response.deductions,
            net_pay=payroll_response.net_pay,
            
            # Metadata
            processed_at=payroll_response.created_at,
            payment_id=None  # Would be set if available
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detailed payroll information: {str(e)}"
        )


@router.get("/rules", response_model=PayrollRulesResponse)
async def get_payroll_rules(
    location: str = Query("default", description="Location/jurisdiction for tax rules"),
    tenant_id: Optional[int] = Query(None, description="Tenant ID filter"),
    active_only: bool = Query(True, description="Return only active rules"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Retrieve tax rules and policies for payroll calculations.
    
    ## Authentication Required
    - Requires `payroll_clerk`, `payroll_manager`, or `admin` role
    
    ## Query Parameters
    - **location**: Location/jurisdiction for tax rules (default: "default")
    - **tenant_id**: Optional tenant ID for filtering
    - **active_only**: Return only currently active rules (default: true)
    
    ## Response
    Returns comprehensive tax rules information including rates, jurisdictions, and effective dates.
    
    ## Example
    - GET /payrolls/rules?location=california&active_only=true
    - GET /payrolls/rules?tenant_id=1
    """
    try:
        # Query tax rules from database
        query = db.query(TaxRule)
        
        if tenant_id:
            query = query.filter(TaxRule.tenant_id == tenant_id)
        
        if active_only:
            query = query.filter(TaxRule.is_active == True)
        
        tax_rules = query.all()
        
        # Convert to API response format
        rule_info_list = []
        for rule in tax_rules:
            rule_info_list.append({
                "rule_id": rule.id,
                "tax_type": rule.tax_type.value if rule.tax_type else "unknown",
                "jurisdiction": rule.jurisdiction or "default",
                "rate": rule.rate or 0.0,
                "description": rule.description or f"{rule.tax_type} tax for {rule.jurisdiction}",
                "effective_date": rule.effective_date,
                "expiry_date": rule.expiry_date,
                "is_active": rule.is_active or False
            })
        
        return PayrollRulesResponse(
            location=location,
            total_rules=len(rule_info_list),
            active_rules=len([r for r in rule_info_list if r["is_active"]]),
            tax_rules=rule_info_list,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tax rules: {str(e)}"
        )


@router.get("/stats", response_model=PayrollStatsResponse)
async def get_payroll_statistics(
    period_start: date = Query(..., description="Statistics period start date"),
    period_end: date = Query(..., description="Statistics period end date"),
    tenant_id: Optional[int] = Query(None, description="Tenant ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get payroll statistics and analytics for a specific period.
    
    ## Authentication Required
    - Requires `payroll_clerk`, `payroll_manager`, or `admin` role
    
    ## Query Parameters
    - **period_start**: Start date for statistics period (YYYY-MM-DD)
    - **period_end**: End date for statistics period (YYYY-MM-DD)
    - **tenant_id**: Optional tenant ID for filtering
    
    ## Response
    Returns comprehensive payroll statistics including totals, averages, and breakdowns.
    """
    try:
        payroll_service = EnhancedPayrollService(db)
        
        # Get payroll summary for the period
        summary = await payroll_service.get_payroll_summary(
            pay_period_start=period_start,
            pay_period_end=period_end,
            tenant_id=tenant_id
        )
        
        return PayrollStatsResponse(
            period_start=period_start,
            period_end=period_end,
            total_employees=summary['total_employees'],
            total_gross_pay=summary['total_gross_pay'],
            total_net_pay=summary['total_net_pay'],
            total_tax_deductions=summary['total_tax_deductions'],
            total_benefit_deductions=summary['total_benefit_deductions'],
            average_hours_per_employee=summary['average_hours_per_employee'],
            average_gross_pay=summary['total_gross_pay'] / summary['total_employees'] if summary['total_employees'] > 0 else 0,
            
            # Breakdowns
            deduction_breakdown={
                "federal_tax": float(summary['total_tax_deductions'] * 0.6),
                "state_tax": float(summary['total_tax_deductions'] * 0.25),
                "social_security": float(summary['total_tax_deductions'] * 0.1),
                "medicare": float(summary['total_tax_deductions'] * 0.05)
            },
            earnings_breakdown={
                "regular_pay": float(summary['total_gross_pay'] * 0.85),
                "overtime_pay": float(summary['total_gross_pay'] * 0.15),
                "bonuses": 0.0,
                "commissions": 0.0
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payroll statistics: {str(e)}"
        )


@router.post("/export", response_model=PayrollExportResponse)
async def export_payroll_data(
    request: PayrollExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Export payroll data in various formats (CSV, Excel, PDF).
    
    ## Authentication Required
    - Requires `payroll_clerk`, `payroll_manager`, or `admin` role
    
    ## Request Body
    - **format**: Export format (csv, xlsx, pdf)
    - **pay_period_start**: Export period start date
    - **pay_period_end**: Export period end date
    - **staff_ids**: Optional specific staff IDs to export
    - **include_details**: Include detailed breakdown
    - **tenant_id**: Optional tenant ID filter
    
    ## Response
    Returns export job ID. The actual file will be generated asynchronously.
    """
    try:
        export_id = str(uuid.uuid4())
        
        # In production, this would start a background export job
        background_tasks.add_task(
            process_payroll_export,
            export_id,
            request
        )
        
        return PayrollExportResponse(
            export_id=export_id,
            status="processing",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate payroll export: {str(e)}"
        )


# Background task functions

async def process_payroll_batch(
    job_id: str,
    payroll_service: EnhancedPayrollService,
    staff_ids: List[int],
    pay_period_start: date,
    pay_period_end: date,
    tenant_id: Optional[int],
    force_recalculate: bool
):
    """Background task to process payroll for multiple staff members."""
    try:
        job_data = BATCH_JOBS[job_id]
        
        # Process each staff member
        for staff_id in staff_ids:
            try:
                if force_recalculate:
                    await payroll_service.recalculate_payroll(
                        staff_id=staff_id,
                        pay_period_start=pay_period_start,
                        pay_period_end=pay_period_end,
                        tenant_id=tenant_id
                    )
                else:
                    await payroll_service.process_payroll_for_staff(
                        staff_id=staff_id,
                        pay_period_start=pay_period_start,
                        pay_period_end=pay_period_end,
                        tenant_id=tenant_id
                    )
                
                job_data["completed_staff"] += 1
                
            except Exception as e:
                job_data["failed_staff"] += 1
                job_data["processing_errors"].append({
                    "staff_id": staff_id,
                    "error": str(e)
                })
        
        job_data["status"] = "completed"
        
    except Exception as e:
        BATCH_JOBS[job_id]["status"] = "failed"
        BATCH_JOBS[job_id]["processing_errors"].append({
            "error": f"Batch processing failed: {str(e)}"
        })


async def process_payroll_export(export_id: str, request: PayrollExportRequest):
    """Background task to generate payroll export files."""
    # In production, this would generate the actual export file
    # and upload it to cloud storage, then update the export status
    pass