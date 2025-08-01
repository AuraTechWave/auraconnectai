# backend/modules/promotions/routers/analytics_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import io

from core.database import get_db
from modules.auth.dependencies import get_current_user, require_admin

from ..services.analytics_service import PromotionAnalyticsService
from ..services.reporting_service import PromotionReportingService

router = APIRouter(prefix="/analytics", tags=["Promotion Analytics"])


@router.get("/performance-report")
def get_promotion_performance_report(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    promotion_ids: Optional[List[int]] = Query(None),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get comprehensive promotion performance report"""
    try:
        service = PromotionAnalyticsService(db)
        report = service.generate_promotion_performance_report(
            start_date=start_date,
            end_date=end_date,
            promotion_ids=promotion_ids,
            include_inactive=include_inactive
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate performance report: {str(e)}")


@router.get("/executive-summary")
def get_executive_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get executive summary report with key insights and recommendations"""
    try:
        service = PromotionReportingService(db)
        summary = service.generate_executive_summary(
            start_date=start_date,
            end_date=end_date
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate executive summary: {str(e)}")


@router.get("/coupon-analytics")
def get_coupon_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    promotion_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get coupon usage analytics report"""
    try:
        service = PromotionAnalyticsService(db)
        report = service.generate_coupon_analytics_report(
            start_date=start_date,
            end_date=end_date,
            promotion_id=promotion_id
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate coupon analytics: {str(e)}")


@router.get("/referral-analytics")
def get_referral_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    program_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get referral program analytics report"""
    try:
        service = PromotionAnalyticsService(db)
        report = service.generate_referral_analytics_report(
            start_date=start_date,
            end_date=end_date,
            program_id=program_id
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate referral analytics: {str(e)}")


@router.get("/daily-aggregates")
def get_daily_analytics_aggregates(
    target_date: datetime,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get daily analytics aggregates for a specific date"""
    try:
        service = PromotionAnalyticsService(db)
        aggregates = service.generate_daily_analytics_aggregates(target_date)
        return aggregates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate daily aggregates: {str(e)}")


@router.get("/comparison-report")
def get_comparison_report(
    period1_start: datetime,
    period1_end: datetime,
    period2_start: datetime,
    period2_end: datetime,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get comparison report between two time periods"""
    try:
        service = PromotionReportingService(db)
        report = service.generate_comparison_report(
            period1_start=period1_start,
            period1_end=period1_end,
            period2_start=period2_start,
            period2_end=period2_end
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate comparison report: {str(e)}")


@router.get("/scheduled-report")
def get_scheduled_report(
    report_type: str = Query(..., pattern="^(executive|performance|coupons|referrals)$"),
    frequency: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
    recipients: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Generate a scheduled report"""
    try:
        service = PromotionReportingService(db)
        report = service.generate_scheduled_report(
            report_type=report_type,
            frequency=frequency,
            recipients=recipients
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate scheduled report: {str(e)}")


@router.get("/export/csv")
def export_report_csv(
    report_type: str = Query(..., pattern="^(performance|coupons|referrals)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    promotion_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Export report data as CSV"""
    try:
        analytics_service = PromotionAnalyticsService(db)
        reporting_service = PromotionReportingService(db)
        
        # Generate the appropriate report
        if report_type == "performance":
            report_data = analytics_service.generate_promotion_performance_report(
                start_date=start_date,
                end_date=end_date,
                promotion_ids=promotion_ids
            )
        elif report_type == "coupons":
            report_data = analytics_service.generate_coupon_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
        elif report_type == "referrals":
            report_data = analytics_service.generate_referral_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        # Export to CSV
        csv_content = reporting_service.export_report_csv(report_data, report_type)
        
        # Create response
        csv_io = io.StringIO(csv_content)
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}_report.csv"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export CSV: {str(e)}")


@router.get("/export/json")
def export_report_json(
    report_type: str = Query(..., pattern="^(executive|performance|coupons|referrals)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    promotion_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Export report data as JSON"""
    try:
        analytics_service = PromotionAnalyticsService(db)
        reporting_service = PromotionReportingService(db)
        
        # Generate the appropriate report
        if report_type == "executive":
            report_data = reporting_service.generate_executive_summary(
                start_date=start_date,
                end_date=end_date
            )
        elif report_type == "performance":
            report_data = analytics_service.generate_promotion_performance_report(
                start_date=start_date,
                end_date=end_date,
                promotion_ids=promotion_ids
            )
        elif report_type == "coupons":
            report_data = analytics_service.generate_coupon_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
        elif report_type == "referrals":
            report_data = analytics_service.generate_referral_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        # Export to JSON
        json_content = reporting_service.export_report_json(report_data)
        
        return StreamingResponse(
            io.BytesIO(json_content.encode('utf-8')),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={report_type}_report.json"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export JSON: {str(e)}")


@router.get("/metrics/summary")
def get_metrics_summary(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get quick metrics summary for dashboard"""
    try:
        from datetime import timedelta
        from ..models.promotion_models import PromotionUsage, CouponUsage, CustomerReferral
        
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Quick metrics
        week_promotions = db.query(PromotionUsage).filter(
            PromotionUsage.created_at >= week_ago
        ).count()
        
        week_coupons = db.query(CouponUsage).filter(
            CouponUsage.created_at >= week_ago
        ).count()
        
        week_referrals = db.query(CustomerReferral).filter(
            CustomerReferral.created_at >= week_ago
        ).count()
        
        month_revenue = db.query(func.sum(PromotionUsage.final_order_amount)).filter(
            PromotionUsage.created_at >= month_ago
        ).scalar() or 0
        
        month_discounts = db.query(func.sum(PromotionUsage.discount_amount)).filter(
            PromotionUsage.created_at >= month_ago
        ).scalar() or 0
        
        return {
            "last_7_days": {
                "promotions_used": week_promotions,
                "coupons_used": week_coupons,
                "referrals_created": week_referrals
            },
            "last_30_days": {
                "revenue_generated": float(month_revenue),
                "total_discounts": float(month_discounts),
                "roi_percentage": round(
                    ((month_revenue - month_discounts) / month_discounts * 100) if month_discounts > 0 else 0, 2
                )
            },
            "generated_at": now.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics summary: {str(e)}")


@router.get("/performance/trends")
def get_performance_trends(
    days: int = Query(30, ge=7, le=365),
    promotion_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get performance trends over time"""
    try:
        from sqlalchemy import func, Date
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Daily promotion usage trends
        query = db.query(
            func.date(PromotionUsage.created_at).label('date'),
            func.count(PromotionUsage.id).label('usage_count'),
            func.sum(PromotionUsage.discount_amount).label('total_discount'),
            func.sum(PromotionUsage.final_order_amount).label('total_revenue'),
            func.count(func.distinct(PromotionUsage.customer_id)).label('unique_customers')
        ).filter(
            PromotionUsage.created_at >= start_date,
            PromotionUsage.created_at <= end_date
        )
        
        if promotion_id:
            query = query.filter(PromotionUsage.promotion_id == promotion_id)
        
        daily_data = query.group_by(func.date(PromotionUsage.created_at)).all()
        
        # Format trends data
        trends = []
        for data in daily_data:
            roi = 0
            if data.total_discount and data.total_discount > 0:
                roi = ((data.total_revenue - data.total_discount) / data.total_discount) * 100
            
            trends.append({
                "date": data.date.isoformat(),
                "usage_count": data.usage_count,
                "total_discount": float(data.total_discount or 0),
                "total_revenue": float(data.total_revenue or 0),
                "unique_customers": data.unique_customers,
                "roi_percentage": round(roi, 2)
            })
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "promotion_id": promotion_id,
            "trends": trends,
            "summary": {
                "total_days": len(trends),
                "total_usage": sum(t["usage_count"] for t in trends),
                "total_discount": sum(t["total_discount"] for t in trends),
                "total_revenue": sum(t["total_revenue"] for t in trends),
                "average_daily_usage": round(sum(t["usage_count"] for t in trends) / len(trends), 2) if trends else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance trends: {str(e)}")


@router.get("/customer-segments")
def get_customer_segment_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get analytics broken down by customer segments"""
    try:
        from sqlalchemy import func
        
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Customer usage analysis
        customer_analysis = db.query(
            PromotionUsage.customer_id,
            func.count(PromotionUsage.id).label('usage_count'),
            func.sum(PromotionUsage.discount_amount).label('total_savings'),
            func.sum(PromotionUsage.final_order_amount).label('total_spent'),
            func.count(func.distinct(PromotionUsage.promotion_id)).label('unique_promotions')
        ).filter(
            PromotionUsage.created_at >= start_date,
            PromotionUsage.created_at <= end_date,
            PromotionUsage.customer_id.isnot(None)
        ).group_by(PromotionUsage.customer_id).all()
        
        # Segment customers
        segments = {
            "new_users": {"count": 0, "total_savings": 0, "total_spent": 0, "avg_promotions": 0},
            "light_users": {"count": 0, "total_savings": 0, "total_spent": 0, "avg_promotions": 0},
            "regular_users": {"count": 0, "total_savings": 0, "total_spent": 0, "avg_promotions": 0},
            "power_users": {"count": 0, "total_savings": 0, "total_spent": 0, "avg_promotions": 0}
        }
        
        for customer in customer_analysis:
            usage_count = customer.usage_count
            
            if usage_count == 1:
                segment = "new_users"
            elif usage_count <= 3:
                segment = "light_users"
            elif usage_count <= 8:
                segment = "regular_users"
            else:
                segment = "power_users"
            
            segments[segment]["count"] += 1
            segments[segment]["total_savings"] += float(customer.total_savings or 0)
            segments[segment]["total_spent"] += float(customer.total_spent or 0)
            segments[segment]["avg_promotions"] += customer.unique_promotions
        
        # Calculate averages
        for segment_name, segment_data in segments.items():
            if segment_data["count"] > 0:
                segment_data["avg_savings"] = round(segment_data["total_savings"] / segment_data["count"], 2)
                segment_data["avg_spent"] = round(segment_data["total_spent"] / segment_data["count"], 2)
                segment_data["avg_promotions"] = round(segment_data["avg_promotions"] / segment_data["count"], 2)
            else:
                segment_data["avg_savings"] = 0
                segment_data["avg_spent"] = 0
                segment_data["avg_promotions"] = 0
        
        total_customers = sum(s["count"] for s in segments.values())
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_customers_analyzed": total_customers,
            "segments": segments,
            "segment_distribution": {
                f"{segment}_percentage": round((data["count"] / total_customers * 100), 1) if total_customers > 0 else 0
                for segment, data in segments.items()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get customer segment analytics: {str(e)}")