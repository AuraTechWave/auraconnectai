# backend/modules/payments/api/reconciliation_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date, datetime, timedelta
import logging

from core.database import get_db
from core.auth import get_current_user, require_permission
from core.auth import User, Permission
from ..services.reconciliation_service import payment_reconciliation_service
from ..models.payment_models import PaymentGateway
from ..schemas.payment_schemas import (
    ReconciliationReportResponse,
    SettlementReportResponse,
    FinancialSummaryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reconciliation", tags=["payment-reconciliation"])


@router.get("/daily-report", response_model=ReconciliationReportResponse)
async def get_daily_reconciliation_report(
    report_date: date = Query(..., description="Date for the report"),
    restaurant_id: Optional[int] = Query(None, description="Filter by restaurant"),
    location_id: Optional[int] = Query(None, description="Filter by location"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate daily payment reconciliation report
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    try:
        report = await payment_reconciliation_service.generate_daily_reconciliation_report(
            db=db,
            report_date=report_date,
            restaurant_id=restaurant_id,
            location_id=location_id,
        )
        
        return ReconciliationReportResponse(**report)
        
    except Exception as e:
        logger.error(f"Failed to generate daily reconciliation report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/gateway-settlement", response_model=SettlementReportResponse)
async def get_gateway_settlement_report(
    gateway: PaymentGateway = Query(..., description="Payment gateway"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate settlement report for a specific payment gateway
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    if (end_date - start_date).days > 90:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
    
    try:
        report = await payment_reconciliation_service.generate_gateway_settlement_report(
            db=db,
            gateway=gateway,
            start_date=start_date,
            end_date=end_date,
        )
        
        return SettlementReportResponse(**report)
        
    except Exception as e:
        logger.error(f"Failed to generate gateway settlement report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/financial-summary", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    restaurant_id: Optional[int] = Query(None, description="Filter by restaurant"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate comprehensive financial summary report
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")
    
    try:
        summary = await payment_reconciliation_service.generate_financial_summary(
            db=db,
            start_date=start_date,
            end_date=end_date,
            restaurant_id=restaurant_id,
        )
        
        return FinancialSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to generate financial summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary")


@router.get("/today")
async def get_today_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get today's payment summary
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    today = date.today()
    
    try:
        report = await payment_reconciliation_service.generate_daily_reconciliation_report(
            db=db,
            report_date=today,
        )
        
        # Simplify for dashboard display
        return {
            "date": today.isoformat(),
            "total_transactions": report["summary"]["total_transactions"],
            "gross_amount": report["summary"]["total_gross_amount"],
            "net_amount": report["summary"]["total_net_amount"],
            "refunds": report["summary"]["total_refunds"],
            "final_amount": report["summary"]["net_after_refunds"],
            "by_gateway": {
                gateway: {
                    "count": data["count"],
                    "amount": data["net_amount"],
                }
                for gateway, data in report["by_gateway"].items()
                if data["count"] > 0
            },
        }
        
    except Exception as e:
        logger.error(f"Failed to get today's summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get summary")


@router.get("/week-summary")
async def get_week_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current week's payment summary
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    try:
        summary = await payment_reconciliation_service.generate_financial_summary(
            db=db,
            start_date=start_of_week,
            end_date=today,
        )
        
        return {
            "period": {
                "start": start_of_week.isoformat(),
                "end": today.isoformat(),
            },
            "summary": summary["summary"],
            "by_gateway": summary["by_gateway"],
            "trends": summary["trends"],
        }
        
    except Exception as e:
        logger.error(f"Failed to get week summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get summary")


@router.get("/month-summary")
async def get_month_summary(
    year: int = Query(..., description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get monthly payment summary
    
    Required permissions: payment.reconciliation.view
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_VIEW)
    
    # Calculate month date range
    start_date = date(year, month, 1)
    
    # Get last day of month
    if month == 12:
        end_date = date(year, month, 31)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    try:
        summary = await payment_reconciliation_service.generate_financial_summary(
            db=db,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "period": {
                "year": year,
                "month": month,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": summary["summary"],
            "by_gateway": summary["by_gateway"],
            "trends": summary["trends"],
        }
        
    except Exception as e:
        logger.error(f"Failed to get month summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get summary")


@router.post("/export")
async def export_reconciliation_report(
    report_type: str = Query(..., description="Report type: daily, settlement, financial"),
    format: str = Query("csv", description="Export format: csv, excel, pdf"),
    start_date: date = Query(..., description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    gateway: Optional[PaymentGateway] = Query(None, description="Payment gateway"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export reconciliation report in various formats
    
    Required permissions: payment.reconciliation.export
    """
    await require_permission(current_user, Permission.PAYMENT_RECONCILIATION_EXPORT)
    
    # Generate report based on type
    report_data = None
    
    try:
        if report_type == "daily":
            report_data = await payment_reconciliation_service.generate_daily_reconciliation_report(
                db=db,
                report_date=start_date,
            )
        elif report_type == "settlement" and gateway:
            report_data = await payment_reconciliation_service.generate_gateway_settlement_report(
                db=db,
                gateway=gateway,
                start_date=start_date,
                end_date=end_date or start_date,
            )
        elif report_type == "financial":
            report_data = await payment_reconciliation_service.generate_financial_summary(
                db=db,
                start_date=start_date,
                end_date=end_date or start_date,
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid report type or missing parameters")
        
        # TODO: Implement actual export functionality
        # For now, return the export metadata
        return {
            "status": "export_initiated",
            "report_type": report_type,
            "format": format,
            "data_points": len(report_data.get("payment_ids", [])) if "payment_ids" in report_data else 0,
            "export_url": f"/api/v1/payments/exports/{current_user.id}_{datetime.utcnow().timestamp()}.{format}",
        }
        
    except Exception as e:
        logger.error(f"Failed to export reconciliation report: {e}")
        raise HTTPException(status_code=500, detail="Failed to export report")